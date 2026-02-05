// Scalar Quantization (Int8) for memory-efficient vector storage
// Inspired by Descartes SQ8 approach - 4x memory reduction vs float32

use serde::{Deserialize, Serialize};

// FFI declarations for SIMD-optimized distance functions
extern "C" {
    fn bridge_l2_distance_i8(a: *const i8, b: *const i8, dim: usize) -> i32;
    fn bridge_simd_type() -> i32;
}

/// Returns the SIMD implementation type being used.
/// 0 = scalar, 1 = NEON, 2 = AVX2
pub fn simd_type() -> i32 {
    unsafe { bridge_simd_type() }
}

/// Returns a human-readable string for the SIMD type
pub fn simd_type_name() -> &'static str {
    match simd_type() {
        0 => "scalar",
        1 => "NEON",
        2 => "AVX2",
        _ => "unknown",
    }
}

/// Scalar Quantizer: maps float32 values to int8 [-128, 127]
/// Uses per-dimension min/max for optimal range utilization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScalarQuantizer {
    /// Dimension of vectors
    pub dimension: usize,
    /// Minimum value per dimension (learned from training data)
    pub mins: Vec<f32>,
    /// Maximum value per dimension (learned from training data)
    pub maxs: Vec<f32>,
    /// Scale factor per dimension: 255 / (max - min)
    pub scales: Vec<f32>,
    /// Whether the quantizer has been trained
    pub trained: bool,
}

impl ScalarQuantizer {
    /// Create a new untrained quantizer
    pub fn new(dimension: usize) -> Self {
        Self {
            dimension,
            mins: vec![0.0; dimension],
            maxs: vec![1.0; dimension],
            scales: vec![255.0; dimension],
            trained: false,
        }
    }

    /// Train the quantizer by learning min/max per dimension
    pub fn train(&mut self, vectors: &[Vec<f32>]) {
        if vectors.is_empty() {
            return;
        }

        // Initialize with first vector
        self.mins = vectors[0].clone();
        self.maxs = vectors[0].clone();

        // Find min/max per dimension
        for vec in vectors.iter() {
            for (d, &val) in vec.iter().enumerate() {
                if val < self.mins[d] {
                    self.mins[d] = val;
                }
                if val > self.maxs[d] {
                    self.maxs[d] = val;
                }
            }
        }

        // Compute scale factors with small epsilon to avoid division by zero
        const EPSILON: f32 = 1e-10;
        for d in 0..self.dimension {
            let range = self.maxs[d] - self.mins[d];
            self.scales[d] = if range > EPSILON {
                255.0 / range
            } else {
                1.0 // Constant dimension, scale doesn't matter
            };
        }

        self.trained = true;
    }

    /// Encode a float32 vector to int8
    /// Maps [min, max] -> [-128, 127]
    #[inline]
    pub fn encode(&self, vector: &[f32]) -> Vec<i8> {
        debug_assert_eq!(vector.len(), self.dimension);

        vector
            .iter()
            .zip(self.mins.iter())
            .zip(self.scales.iter())
            .map(|((&val, &min), &scale)| {
                // Map to [0, 255] then shift to [-128, 127]
                let normalized = ((val - min) * scale).round() as i32;
                let clamped = normalized.clamp(0, 255);
                (clamped - 128) as i8
            })
            .collect()
    }

    /// Decode an int8 vector back to float32 (for verification)
    #[inline]
    pub fn decode(&self, quantized: &[i8]) -> Vec<f32> {
        debug_assert_eq!(quantized.len(), self.dimension);

        quantized
            .iter()
            .zip(self.mins.iter())
            .zip(self.scales.iter())
            .map(|((&q, &min), &scale)| {
                // Shift from [-128, 127] to [0, 255] then map back
                let normalized = (q as i32 + 128) as f32;
                min + normalized / scale
            })
            .collect()
    }

    /// Compute L2 squared distance between two int8 vectors
    /// This is ~4x faster than float32 due to SIMD and cache efficiency
    #[inline]
    pub fn l2_distance_squared(a: &[i8], b: &[i8]) -> i32 {
        // Compiler will auto-vectorize this with -C target-cpu=native
        a.iter()
            .zip(b.iter())
            .map(|(&x, &y)| {
                let diff = x as i32 - y as i32;
                diff * diff
            })
            .sum()
    }

    /// Compute L2 squared distance and convert to f32 scale
    #[inline]
    pub fn l2_distance_f32(&self, a: &[i8], b: &[i8]) -> f32 {
        // For simplicity, just return the int32 distance as f32
        // The relative ordering is preserved
        Self::l2_distance_squared(a, b) as f32
    }
}

/// Row-major storage for quantized vectors
/// This layout is optimal for cache-friendly distance computations
/// Each vector is stored contiguously: data[i * dimension..(i+1) * dimension] = vector[i]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantizedVectorStorage {
    /// Dimension of vectors
    dimension: usize,
    /// Number of vectors stored
    num_vectors: usize,
    /// Capacity (max vectors before reallocation)
    capacity: usize,
    /// Row-major data: data[i * dimension + d] = vector[i][d]
    /// Contiguous storage enables CPU prefetching and SIMD vectorization
    data: Vec<i8>,
}

impl QuantizedVectorStorage {
    /// Create storage for n vectors of given dimension
    pub fn new(dimension: usize, capacity: usize) -> Self {
        Self {
            dimension,
            num_vectors: 0,
            capacity,
            data: vec![0i8; dimension * capacity],
        }
    }

    /// Get dimension
    #[inline]
    pub fn dimension(&self) -> usize {
        self.dimension
    }

    /// Get number of vectors
    #[inline]
    pub fn num_vectors(&self) -> usize {
        self.num_vectors
    }

    /// Get raw data slice
    #[inline]
    pub fn data(&self) -> &[i8] {
        &self.data
    }

    /// Set vector at index (row-major layout)
    pub fn set_vector(&mut self, index: usize, vector: &[i8]) {
        debug_assert_eq!(vector.len(), self.dimension);

        // Ensure capacity
        if index >= self.capacity {
            self.ensure_capacity(index + 1);
        }

        let start = index * self.dimension;
        self.data[start..start + self.dimension].copy_from_slice(vector);

        if index >= self.num_vectors {
            self.num_vectors = index + 1;
        }
    }

    /// Get vector slice at index (zero-copy for row-major)
    #[inline]
    pub fn get_vector_slice(&self, index: usize) -> &[i8] {
        debug_assert!(index < self.num_vectors);
        let start = index * self.dimension;
        &self.data[start..start + self.dimension]
    }

    /// Get vector at index (returns owned Vec for compatibility)
    pub fn get_vector(&self, index: usize) -> Vec<i8> {
        self.get_vector_slice(index).to_vec()
    }

    /// Compute L2 squared distance between query and vector at index
    /// Row-major layout enables sequential memory access and auto-vectorization
    #[inline]
    pub fn distance_to(&self, query: &[i8], index: usize) -> i32 {
        debug_assert_eq!(query.len(), self.dimension);
        debug_assert!(index < self.num_vectors);

        let vec = self.get_vector_slice(index);
        l2_distance_i8(query, vec)
    }

    /// Batch distance computation for multiple indices
    pub fn distances_to(&self, query: &[i8], indices: &[usize]) -> Vec<i32> {
        indices
            .iter()
            .map(|&idx| self.distance_to(query, idx))
            .collect()
    }

    /// Ensure capacity for at least n vectors
    pub fn ensure_capacity(&mut self, n: usize) {
        if n > self.capacity {
            let new_capacity = (n * 3 / 2).max(n); // 1.5x growth
            let mut new_data = vec![0i8; self.dimension * new_capacity];

            // Copy existing data (row-major is simple copy)
            let copy_len = self.num_vectors * self.dimension;
            new_data[..copy_len].copy_from_slice(&self.data[..copy_len]);

            self.data = new_data;
            self.capacity = new_capacity;
        }
    }
}

/// Compute L2 squared distance between two i8 vectors
/// Uses SIMD-optimized C++ implementation (AVX2 on x86_64, NEON on ARM64)
#[inline]
pub fn l2_distance_i8(a: &[i8], b: &[i8]) -> i32 {
    debug_assert_eq!(a.len(), b.len());
    unsafe { bridge_l2_distance_i8(a.as_ptr(), b.as_ptr(), a.len()) }
}

/// Pure Rust fallback (for comparison benchmarking)
#[inline]
pub fn l2_distance_i8_rust(a: &[i8], b: &[i8]) -> i32 {
    debug_assert_eq!(a.len(), b.len());

    let mut sum0: i32 = 0;
    let mut sum1: i32 = 0;
    let mut sum2: i32 = 0;
    let mut sum3: i32 = 0;

    let len = a.len();
    let chunks = len / 4;

    for i in 0..chunks {
        let base = i * 4;
        unsafe {
            let d0 = *a.get_unchecked(base) as i32 - *b.get_unchecked(base) as i32;
            let d1 = *a.get_unchecked(base + 1) as i32 - *b.get_unchecked(base + 1) as i32;
            let d2 = *a.get_unchecked(base + 2) as i32 - *b.get_unchecked(base + 2) as i32;
            let d3 = *a.get_unchecked(base + 3) as i32 - *b.get_unchecked(base + 3) as i32;
            sum0 += d0 * d0;
            sum1 += d1 * d1;
            sum2 += d2 * d2;
            sum3 += d3 * d3;
        }
    }

    for i in (chunks * 4)..len {
        let d = unsafe { *a.get_unchecked(i) as i32 - *b.get_unchecked(i) as i32 };
        sum0 += d * d;
    }

    sum0 + sum1 + sum2 + sum3
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_quantization_roundtrip() {
        let mut quantizer = ScalarQuantizer::new(4);

        // Train with some sample vectors
        let vectors = vec![
            vec![0.0, 0.5, 1.0, -1.0],
            vec![0.5, 0.0, 0.5, 0.0],
            vec![1.0, 1.0, 0.0, 1.0],
        ];
        quantizer.train(&vectors);

        // Encode and decode
        for vec in &vectors {
            let encoded = quantizer.encode(vec);
            let decoded = quantizer.decode(&encoded);

            // Check within tolerance (quantization error)
            for (original, reconstructed) in vec.iter().zip(decoded.iter()) {
                let error = (original - reconstructed).abs();
                // Tolerance depends on range: 2/255 * range
                let range = quantizer.maxs.iter()
                    .zip(quantizer.mins.iter())
                    .map(|(max, min)| max - min)
                    .fold(0.0f32, |a, b| a.max(b));
                assert!(error < range * 0.02, "Roundtrip error too large: {} vs {}", original, reconstructed);
            }
        }
    }

    #[test]
    fn test_quantization_range() {
        let mut quantizer = ScalarQuantizer::new(3);

        let vectors = vec![
            vec![-100.0, 0.0, 100.0],
            vec![50.0, -50.0, 0.0],
        ];
        quantizer.train(&vectors);

        for vec in &vectors {
            let encoded = quantizer.encode(vec);

            // Check all values are in valid i8 range
            for &val in &encoded {
                assert!((-128..=127).contains(&(val as i32)), "Value {} out of i8 range", val);
            }
        }
    }

    #[test]
    fn test_quantization_preserves_ordering() {
        let mut quantizer = ScalarQuantizer::new(4);

        let vectors = vec![
            vec![0.0, 0.0, 0.0, 0.0],
            vec![1.0, 0.0, 0.0, 0.0],
            vec![2.0, 0.0, 0.0, 0.0],
            vec![3.0, 0.0, 0.0, 0.0],
        ];
        quantizer.train(&vectors);

        let query = vec![0.0, 0.0, 0.0, 0.0];
        let q_query = quantizer.encode(&query);

        let mut distances: Vec<(usize, i32)> = vectors
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let q_v = quantizer.encode(v);
                (i, ScalarQuantizer::l2_distance_squared(&q_query, &q_v))
            })
            .collect();

        distances.sort_by_key(|(_, d)| *d);

        // Should be ordered: 0, 1, 2, 3
        assert_eq!(distances[0].0, 0);
        assert_eq!(distances[1].0, 1);
        assert_eq!(distances[2].0, 2);
        assert_eq!(distances[3].0, 3);
    }

    #[test]
    fn test_row_major_layout() {
        let mut storage = QuantizedVectorStorage::new(3, 4);

        // Add vectors
        storage.set_vector(0, &[1, 2, 3]);
        storage.set_vector(1, &[4, 5, 6]);
        storage.set_vector(2, &[7, 8, 9]);

        // Verify retrieval
        assert_eq!(storage.get_vector(0), vec![1, 2, 3]);
        assert_eq!(storage.get_vector(1), vec![4, 5, 6]);
        assert_eq!(storage.get_vector(2), vec![7, 8, 9]);

        // Verify row-major storage: vector[i] at offset i * dimension
        let data = storage.data();
        // Vector 0: [1, 2, 3]
        assert_eq!(data[0], 1);
        assert_eq!(data[1], 2);
        assert_eq!(data[2], 3);
        // Vector 1: [4, 5, 6]
        assert_eq!(data[3], 4);
        assert_eq!(data[4], 5);
        assert_eq!(data[5], 6);
        // Vector 2: [7, 8, 9]
        assert_eq!(data[6], 7);
        assert_eq!(data[7], 8);
        assert_eq!(data[8], 9);
    }

    #[test]
    fn test_storage_distance() {
        let mut storage = QuantizedVectorStorage::new(3, 4);

        storage.set_vector(0, &[0, 0, 0]);
        storage.set_vector(1, &[1, 0, 0]);
        storage.set_vector(2, &[0, 1, 0]);

        let query = vec![0i8, 0, 0];

        assert_eq!(storage.distance_to(&query, 0), 0); // exact match
        assert_eq!(storage.distance_to(&query, 1), 1); // diff of 1 in one dim
        assert_eq!(storage.distance_to(&query, 2), 1); // diff of 1 in one dim
    }

    #[test]
    fn test_storage_capacity_growth() {
        let mut storage = QuantizedVectorStorage::new(2, 2);

        storage.set_vector(0, &[1, 2]);
        storage.set_vector(1, &[3, 4]);

        // Grow capacity
        storage.ensure_capacity(10);

        // Verify data preserved
        assert_eq!(storage.get_vector(0), vec![1, 2]);
        assert_eq!(storage.get_vector(1), vec![3, 4]);

        // Add more vectors
        storage.set_vector(5, &[5, 6]);
        assert_eq!(storage.get_vector(5), vec![5, 6]);
    }

    #[test]
    fn test_simd_type() {
        let simd = super::simd_type();
        let name = super::simd_type_name();
        println!("SIMD implementation: {} (type={})", name, simd);
        // On ARM64: expect NEON (1), on x86_64: expect AVX2 (2)
        #[cfg(target_arch = "aarch64")]
        assert_eq!(simd, 1, "Expected NEON on ARM64");
        #[cfg(target_arch = "x86_64")]
        assert_eq!(simd, 2, "Expected AVX2 on x86_64");
    }

    #[test]
    fn test_simd_distance_correctness() {
        // Test that SIMD distance matches scalar reference
        let a: Vec<i8> = (0..128).map(|i| (i % 256) as i8).collect();
        let b: Vec<i8> = (0..128).map(|i| ((i * 2) % 256) as i8).collect();

        let simd_dist = l2_distance_i8(&a, &b);

        // Compute reference scalar
        let ref_dist: i32 = a.iter()
            .zip(b.iter())
            .map(|(&x, &y)| {
                let d = x as i32 - y as i32;
                d * d
            })
            .sum();

        assert_eq!(simd_dist, ref_dist, "SIMD distance should match scalar reference");
    }

    #[test]
    fn test_simd_distance_benchmark() {
        use std::time::Instant;
        use std::hint::black_box;

        let dim = 128;
        let n_vectors = 10_000;
        let n_iterations = 100;

        // Generate random vectors
        let mut rng = rand::thread_rng();
        use rand::Rng;
        let vectors: Vec<Vec<i8>> = (0..n_vectors)
            .map(|_| (0..dim).map(|_| rng.gen::<i8>()).collect())
            .collect();
        let query: Vec<i8> = (0..dim).map(|_| rng.gen::<i8>()).collect();

        // Warmup
        for v in vectors.iter().take(100) {
            black_box(l2_distance_i8(black_box(&query), black_box(v)));
            black_box(l2_distance_i8_rust(black_box(&query), black_box(v)));
        }

        // Benchmark SIMD (C++)
        let start = Instant::now();
        for _ in 0..n_iterations {
            for v in &vectors {
                black_box(l2_distance_i8(black_box(&query), black_box(v)));
            }
        }
        let elapsed_simd = start.elapsed();

        // Benchmark Rust fallback
        let start = Instant::now();
        for _ in 0..n_iterations {
            for v in &vectors {
                black_box(l2_distance_i8_rust(black_box(&query), black_box(v)));
            }
        }
        let elapsed_rust = start.elapsed();

        let total_distances = n_vectors * n_iterations;
        let ns_per_simd = elapsed_simd.as_nanos() as f64 / total_distances as f64;
        let ns_per_rust = elapsed_rust.as_nanos() as f64 / total_distances as f64;

        println!("\n=== Distance Benchmark Comparison ===");
        println!("SIMD type: {}", super::simd_type_name());
        println!("Dimension: {}, Vectors: {}", dim, n_vectors);
        println!("C++ SIMD: {:.1}ns/dist ({:.1}M/sec)", ns_per_simd, 1000.0 / ns_per_simd);
        println!("Rust:     {:.1}ns/dist ({:.1}M/sec)", ns_per_rust, 1000.0 / ns_per_rust);
        println!("Speedup:  {:.2}x", ns_per_rust / ns_per_simd);
    }
}
