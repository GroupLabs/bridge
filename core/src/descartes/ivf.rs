// IVF (Inverted File Index) for Descartes
// Clusters vectors and searches only the closest clusters for speed

use crate::descartes::quantization::{ScalarQuantizer, QuantizedVectorStorage};
use crate::descartes::search::SearchResult;
use rand::seq::SliceRandom;
use rand::Rng;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};

/// IVF Index configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IvfConfig {
    /// Vector dimension
    pub dimension: usize,
    /// Number of clusters (centroids)
    pub nlist: usize,
    /// Number of clusters to probe during search
    pub nprobe: usize,
    /// Number of k-means iterations
    pub kmeans_iters: usize,
}

impl IvfConfig {
    pub fn new(dimension: usize) -> Self {
        Self {
            dimension,
            nlist: 100,    // sqrt(n) is typical, will be adjusted
            nprobe: 8,     // Search 8 clusters by default
            kmeans_iters: 10, // Fewer iterations for speed
        }
    }

    pub fn with_nlist(mut self, nlist: usize) -> Self {
        self.nlist = nlist;
        self
    }

    pub fn with_nprobe(mut self, nprobe: usize) -> Self {
        self.nprobe = nprobe;
        self
    }

    /// Auto-configure nlist based on dataset size
    /// Rule of thumb: nlist = sqrt(n) for balanced speed/recall
    pub fn auto_nlist(mut self, n_vectors: usize) -> Self {
        self.nlist = ((n_vectors as f64).sqrt() as usize).max(16).min(4096);
        self
    }
}

/// Inverted list storing vector indices for one cluster
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct InvertedList {
    /// Vector indices belonging to this cluster
    pub indices: Vec<usize>,
}

/// IVF Index using SQ8 quantization
#[derive(Serialize, Deserialize)]
pub struct IvfIndex {
    pub config: IvfConfig,
    /// Scalar quantizer for vectors
    pub quantizer: ScalarQuantizer,
    /// Quantized vector storage (SQ8)
    pub storage: QuantizedVectorStorage,
    /// Cluster centroids (float32 for accurate coarse search)
    pub centroids_f32: Vec<Vec<f32>>,
    /// Cluster centroids (quantized for fast search)
    pub centroids: Vec<Vec<i8>>,
    /// Inverted lists: one per centroid
    pub inverted_lists: Vec<InvertedList>,
    /// Original vectors for reranking
    pub original_vectors: Vec<Vec<f32>>,
    /// ID mapping
    pub id_map: Vec<i64>,
    /// Whether the index is trained
    pub trained: bool,
}

impl IvfIndex {
    /// Create a new empty IVF index
    pub fn new(config: IvfConfig) -> Self {
        Self {
            quantizer: ScalarQuantizer::new(config.dimension),
            storage: QuantizedVectorStorage::new(config.dimension, 0),
            centroids_f32: Vec::new(),
            centroids: Vec::new(),
            inverted_lists: Vec::new(),
            original_vectors: Vec::new(),
            id_map: Vec::new(),
            trained: false,
            config,
        }
    }

    /// Build the index from vectors
    pub fn build(&mut self, vectors: &[Vec<f32>], ids: &[i64]) {
        assert_eq!(vectors.len(), ids.len());
        if vectors.is_empty() {
            return;
        }

        let n = vectors.len();

        // Store ID mapping and original vectors
        self.id_map = ids.to_vec();
        self.original_vectors = vectors.to_vec();

        // Train scalar quantizer
        self.quantizer.train(vectors);

        // Quantize all vectors
        self.storage = QuantizedVectorStorage::new(self.config.dimension, n);
        for (i, vec) in vectors.iter().enumerate() {
            let quantized = self.quantizer.encode(vec);
            self.storage.set_vector(i, &quantized);
        }

        // Run k-means clustering
        self.train_kmeans(vectors);

        // Assign vectors to clusters
        self.assign_to_clusters();

        self.trained = true;
    }

    /// Train k-means clustering to find centroids
    /// Uses sampling for large datasets to speed up training
    fn train_kmeans(&mut self, vectors: &[Vec<f32>]) {
        let n = vectors.len();
        let dim = self.config.dimension;
        let k = self.config.nlist.min(n);

        // For large datasets, train on a sample for speed
        // Sample size: max(10 * k, min(n, 50000))
        let sample_size = (k * 10).max(1000).min(n).min(50_000);
        let use_sampling = n > sample_size;

        let training_vectors: Vec<&Vec<f32>> = if use_sampling {
            // Random sampling
            let mut rng = rand::thread_rng();
            let mut indices: Vec<usize> = (0..n).collect();
            indices.shuffle(&mut rng);
            indices.truncate(sample_size);
            indices.iter().map(|&i| &vectors[i]).collect()
        } else {
            vectors.iter().collect()
        };

        // Initialize centroids using k-means++ on sample
        let mut centroids_f32 = self.kmeans_plusplus_init_refs(&training_vectors, k);

        // K-means iterations on sample
        for _iter in 0..self.config.kmeans_iters {
            // Assign training vectors to nearest centroid
            let assignments: Vec<usize> = training_vectors
                .par_iter()
                .map(|v| self.find_nearest_centroid_f32(v, &centroids_f32))
                .collect();

            // Recompute centroids
            let mut new_centroids = vec![vec![0.0f64; dim]; k];
            let mut counts = vec![0usize; k];

            for (i, &cluster) in assignments.iter().enumerate() {
                counts[cluster] += 1;
                for (d, &val) in training_vectors[i].iter().enumerate() {
                    new_centroids[cluster][d] += val as f64;
                }
            }

            // Average and handle empty clusters
            for c in 0..k {
                if counts[c] > 0 {
                    for d in 0..dim {
                        centroids_f32[c][d] = (new_centroids[c][d] / counts[c] as f64) as f32;
                    }
                }
            }
        }

        // Store float32 centroids (for accurate coarse search)
        self.centroids_f32 = centroids_f32.clone();

        // Quantize centroids (for fast fine search)
        self.centroids = centroids_f32
            .iter()
            .map(|c| self.quantizer.encode(c))
            .collect();

        // Initialize inverted lists
        self.inverted_lists = vec![InvertedList::default(); k];
    }

    /// K-means++ initialization for sampled vectors (references)
    fn kmeans_plusplus_init_refs(&self, vectors: &[&Vec<f32>], k: usize) -> Vec<Vec<f32>> {
        let mut rng = rand::thread_rng();
        let n = vectors.len();
        let mut centroids = Vec::with_capacity(k);

        // Choose first centroid randomly
        let first_idx = rng.gen_range(0..n);
        centroids.push(vectors[first_idx].clone());

        // Choose remaining centroids
        for _ in 1..k {
            let distances: Vec<f32> = vectors
                .iter()
                .map(|v| {
                    centroids
                        .iter()
                        .map(|c| l2_distance_f32(v, c))
                        .fold(f32::INFINITY, f32::min)
                })
                .collect();

            let total: f32 = distances.iter().sum();
            if total <= 0.0 {
                let idx = rng.gen_range(0..n);
                centroids.push(vectors[idx].clone());
                continue;
            }

            let mut r = rng.gen::<f32>() * total;
            let mut chosen = 0;
            for (i, &d) in distances.iter().enumerate() {
                r -= d;
                if r <= 0.0 {
                    chosen = i;
                    break;
                }
            }
            centroids.push(vectors[chosen].clone());
        }

        centroids
    }

    /// Find nearest centroid for a float32 vector
    fn find_nearest_centroid_f32(&self, vector: &[f32], centroids: &[Vec<f32>]) -> usize {
        let mut best_idx = 0;
        let mut best_dist = f32::INFINITY;

        for (i, centroid) in centroids.iter().enumerate() {
            let dist = l2_distance_f32(vector, centroid);
            if dist < best_dist {
                best_dist = dist;
                best_idx = i;
            }
        }

        best_idx
    }

    /// Assign all vectors to their nearest cluster (parallelized)
    fn assign_to_clusters(&mut self) {
        // Parallel assignment
        let assignments: Vec<usize> = self.original_vectors
            .par_iter()
            .map(|v| {
                let mut best_idx = 0;
                let mut best_dist = f32::INFINITY;
                for (i, c) in self.centroids_f32.iter().enumerate() {
                    let dist = l2_distance_f32(v, c);
                    if dist < best_dist {
                        best_dist = dist;
                        best_idx = i;
                    }
                }
                best_idx
            })
            .collect();

        // Clear and populate inverted lists
        for list in &mut self.inverted_lists {
            list.indices.clear();
        }
        for (i, &cluster) in assignments.iter().enumerate() {
            self.inverted_lists[cluster].indices.push(i);
        }
    }

    /// Find k nearest centroids using float32 (for accurate coarse search)
    #[inline]
    fn find_nearest_k_centroids_f32(&self, vector: &[f32], k: usize) -> Vec<usize> {
        let mut distances: Vec<(f32, usize)> = self.centroids_f32
            .iter()
            .enumerate()
            .map(|(i, c)| (l2_distance_f32(vector, c), i))
            .collect();

        let k = k.min(distances.len());
        distances.select_nth_unstable_by(k.saturating_sub(1), |a, b| {
            a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal)
        });
        distances.truncate(k);
        distances.sort_unstable_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

        distances.into_iter().map(|(_, i)| i).collect()
    }

    /// Search for k nearest neighbors
    pub fn search(&self, query: &[f32], k: usize) -> Vec<SearchResult> {
        if !self.trained || self.centroids.is_empty() {
            return Vec::new();
        }

        let quantized_query = self.quantizer.encode(query);

        // Find nearest clusters to probe (using float32 for accuracy)
        let probe_clusters = self.find_nearest_k_centroids_f32(query, self.config.nprobe);

        // Collect candidates from probed clusters
        let mut candidates: Vec<(i32, usize)> = Vec::new();

        for &cluster_idx in &probe_clusters {
            let list = &self.inverted_lists[cluster_idx];
            for &vec_idx in &list.indices {
                let dist = self.storage.distance_to(&quantized_query, vec_idx);
                candidates.push((dist, vec_idx));
            }
        }

        // Sort and take top candidates for reranking
        let rerank_k = (k * 3).max(32).min(candidates.len());
        candidates.select_nth_unstable_by_key(rerank_k.saturating_sub(1), |(d, _)| *d);
        candidates.truncate(rerank_k);

        // Rerank with original float32 vectors
        let mut reranked: Vec<(f32, i64)> = candidates
            .iter()
            .map(|(_, idx)| {
                let dist = l2_distance_f32(query, &self.original_vectors[*idx]);
                let id = self.id_map[*idx];
                (dist, id)
            })
            .collect();

        reranked.sort_unstable_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

        reranked
            .into_iter()
            .take(k)
            .map(|(dist, id)| SearchResult::new(id, dist))
            .collect()
    }

    /// Batch search with parallelism
    pub fn batch_search(&self, queries: &[Vec<f32>], k: usize) -> Vec<Vec<SearchResult>> {
        queries
            .par_iter()
            .map(|q| self.search(q, k))
            .collect()
    }

    /// Get number of vectors
    pub fn len(&self) -> usize {
        self.storage.num_vectors()
    }

    /// Check if empty
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Get memory usage estimate
    pub fn memory_usage(&self) -> usize {
        let quantized = self.storage.data().len();
        let centroids = self.centroids.len() * self.config.dimension;
        let inverted_lists: usize = self.inverted_lists.iter().map(|l| l.indices.len() * 8).sum();
        let original = self.original_vectors.len() * self.config.dimension * 4;
        let ids = self.id_map.len() * 8;

        quantized + centroids + inverted_lists + original + ids
    }
}

/// L2 squared distance for float32 vectors
#[inline]
fn l2_distance_f32(a: &[f32], b: &[f32]) -> f32 {
    debug_assert_eq!(a.len(), b.len());

    let mut sum0: f32 = 0.0;
    let mut sum1: f32 = 0.0;
    let mut sum2: f32 = 0.0;
    let mut sum3: f32 = 0.0;

    let len = a.len();
    let chunks = len / 4;

    for i in 0..chunks {
        let base = i * 4;
        unsafe {
            let d0 = *a.get_unchecked(base) - *b.get_unchecked(base);
            let d1 = *a.get_unchecked(base + 1) - *b.get_unchecked(base + 1);
            let d2 = *a.get_unchecked(base + 2) - *b.get_unchecked(base + 2);
            let d3 = *a.get_unchecked(base + 3) - *b.get_unchecked(base + 3);
            sum0 += d0 * d0;
            sum1 += d1 * d1;
            sum2 += d2 * d2;
            sum3 += d3 * d3;
        }
    }

    for i in (chunks * 4)..len {
        let d = unsafe { *a.get_unchecked(i) - *b.get_unchecked(i) };
        sum0 += d * d;
    }

    sum0 + sum1 + sum2 + sum3
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::Rng;
    use std::collections::HashSet;

    fn generate_random_vectors(n: usize, dim: usize) -> Vec<Vec<f32>> {
        let mut rng = rand::thread_rng();
        (0..n)
            .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
            .collect()
    }

    fn compute_ground_truth(vectors: &[Vec<f32>], query: &[f32], k: usize) -> Vec<usize> {
        let mut distances: Vec<(f32, usize)> = vectors
            .iter()
            .enumerate()
            .map(|(i, v)| (l2_distance_f32(query, v), i))
            .collect();
        distances.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
        distances.iter().take(k).map(|(_, i)| *i).collect()
    }

    fn compute_recall(ground_truth: &[usize], results: &[SearchResult], k: usize) -> f64 {
        let gt_set: HashSet<usize> = ground_truth.iter().take(k).cloned().collect();
        let result_set: HashSet<usize> = results.iter().take(k).map(|r| r.id as usize).collect();
        gt_set.intersection(&result_set).count() as f64 / k as f64
    }

    #[test]
    fn test_ivf_basic() {
        let config = IvfConfig::new(4).with_nlist(2).with_nprobe(2);
        let mut index = IvfIndex::new(config);

        let vectors = vec![
            vec![1.0, 0.0, 0.0, 0.0],
            vec![0.9, 0.1, 0.0, 0.0],
            vec![0.0, 1.0, 0.0, 0.0],
            vec![0.0, 0.9, 0.1, 0.0],
        ];
        let ids: Vec<i64> = (0..4).collect();

        index.build(&vectors, &ids);

        assert_eq!(index.len(), 4);
        assert!(!index.is_empty());

        let results = index.search(&[1.0, 0.0, 0.0, 0.0], 2);
        assert_eq!(results.len(), 2);
        // First result should be the exact match
        assert_eq!(results[0].id, 0);
    }

    #[test]
    fn test_ivf_recall_1k() {
        let n = 1000;
        let dim = 32;
        let k = 10;

        let vectors = generate_random_vectors(n, dim);
        let ids: Vec<i64> = (0..n as i64).collect();

        let config = IvfConfig::new(dim)
            .auto_nlist(n)
            .with_nprobe(16);

        let mut index = IvfIndex::new(config);
        index.build(&vectors, &ids);

        let mut total_recall = 0.0;
        let num_queries = 50;

        for i in 0..num_queries {
            let query = &vectors[i];
            let ground_truth = compute_ground_truth(&vectors, query, k);
            let results = index.search(query, k);
            total_recall += compute_recall(&ground_truth, &results, k);
        }

        let avg_recall = total_recall / num_queries as f64;
        println!("IVF 1K Recall@{}: {:.1}%", k, avg_recall * 100.0);
        assert!(avg_recall > 0.85, "Recall {} should be > 85%", avg_recall);
    }

    #[test]
    fn test_ivf_performance_10k() {
        use std::time::Instant;

        let n = 10_000;
        let dim = 128;
        let k = 10;

        // Use clustered data which is more representative of real-world use cases
        let vectors = generate_clustered_vectors(n, dim, 50);
        let ids: Vec<i64> = (0..n as i64).collect();

        // Configure IVF for clustered data
        // nlist=64, nprobe=16 should work well for 50 natural clusters
        let config = IvfConfig::new(dim)
            .with_nlist(64)
            .with_nprobe(16);

        let build_start = Instant::now();
        let mut index = IvfIndex::new(config.clone());
        index.build(&vectors, &ids);
        let build_time = build_start.elapsed();

        // Warmup
        for i in 0..100 {
            let _ = index.search(&vectors[i], k);
        }

        // Search throughput
        let num_queries = 1000;
        let search_start = Instant::now();
        for i in 0..num_queries {
            let _ = index.search(&vectors[i % n], k);
        }
        let search_time = search_start.elapsed();
        let qps = num_queries as f64 / search_time.as_secs_f64();

        // Recall
        let mut total_recall = 0.0;
        let recall_queries = 100;
        for i in 0..recall_queries {
            let ground_truth = compute_ground_truth(&vectors, &vectors[i], k);
            let results = index.search(&vectors[i], k);
            total_recall += compute_recall(&ground_truth, &results, k);
        }
        let avg_recall = total_recall / recall_queries as f64;

        println!("\n=== IVF 10K Benchmark (Clustered Data) ===");
        println!("nlist: {}, nprobe: {}", config.nlist, config.nprobe);
        println!("Build: {:.2}s | Memory: {:.2}MB | QPS: {:.0} | Recall@{}: {:.1}%",
            build_time.as_secs_f64(),
            index.memory_usage() as f64 / 1_000_000.0,
            qps,
            k,
            avg_recall * 100.0
        );

        // Clustered data should achieve >85% recall
        assert!(avg_recall > 0.85, "Recall {} should be > 85%", avg_recall);
    }

    fn generate_clustered_vectors(n: usize, dim: usize, num_clusters: usize) -> Vec<Vec<f32>> {
        let mut rng = rand::thread_rng();
        let centers: Vec<Vec<f32>> = (0..num_clusters)
            .map(|_| (0..dim).map(|_| rng.gen::<f32>() * 10.0).collect())
            .collect();

        (0..n)
            .map(|i| {
                let center = &centers[i % num_clusters];
                center.iter().map(|&c| c + rng.gen::<f32>() * 0.5 - 0.25).collect()
            })
            .collect()
    }

    #[test]
    fn test_ivf_nprobe_tradeoff() {
        use std::time::Instant;

        let n = 10_000;
        let dim = 128;
        let k = 10;

        let vectors = generate_random_vectors(n, dim);
        let ids: Vec<i64> = (0..n as i64).collect();

        println!("\n=== IVF nprobe vs QPS/Recall Tradeoff ===");
        println!("{:>8} {:>10} {:>10}", "nprobe", "QPS", "Recall@10");
        println!("{:-<30}", "");

        for nprobe in [1, 2, 4, 8, 16, 32] {
            let config = IvfConfig::new(dim)
                .auto_nlist(n)
                .with_nprobe(nprobe);

            let mut index = IvfIndex::new(config);
            index.build(&vectors, &ids);

            // QPS
            let num_queries = 500;
            let start = Instant::now();
            for i in 0..num_queries {
                let _ = index.search(&vectors[i % n], k);
            }
            let qps = num_queries as f64 / start.elapsed().as_secs_f64();

            // Recall
            let mut total_recall = 0.0;
            for i in 0..50 {
                let ground_truth = compute_ground_truth(&vectors, &vectors[i], k);
                let results = index.search(&vectors[i], k);
                total_recall += compute_recall(&ground_truth, &results, k);
            }
            let recall = total_recall / 50.0;

            println!("{:>8} {:>10.0} {:>9.1}%", nprobe, qps, recall * 100.0);
        }
    }

    #[test]
    fn test_ivf_vs_hnsw_comparison() {
        use std::time::Instant;
        use crate::descartes::{DescartesConfig, DescartesIndex};

        let n = 10_000;
        let dim = 128;
        let k = 10;

        // Use clustered data (realistic)
        let vectors = generate_clustered_vectors(n, dim, 50);
        let ids: Vec<i64> = (0..n as i64).collect();

        println!("\n=== HNSW vs IVF Comparison (10K vectors, 128D, clustered) ===\n");

        // Build HNSW
        let hnsw_config = DescartesConfig::new(dim)
            .with_m(32)
            .with_ef_construction(200)
            .with_ef_search(80);

        let start = Instant::now();
        let mut hnsw_index = DescartesIndex::new(hnsw_config);
        hnsw_index.build_with_ids(&vectors, &ids);
        let hnsw_build_time = start.elapsed();

        // Build IVF - use fewer probes since data is well-clustered
        let ivf_config = IvfConfig::new(dim)
            .with_nlist(64)
            .with_nprobe(8);

        let start = Instant::now();
        let mut ivf_index = IvfIndex::new(ivf_config);
        ivf_index.build(&vectors, &ids);
        let ivf_build_time = start.elapsed();

        // Warmup
        for i in 0..100 {
            let _ = hnsw_index.search(&vectors[i], k);
            let _ = ivf_index.search(&vectors[i], k);
        }

        // Benchmark HNSW
        let num_queries = 1000;
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = hnsw_index.search(&vectors[i % n], k);
        }
        let hnsw_qps = num_queries as f64 / start.elapsed().as_secs_f64();

        // Benchmark IVF
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = ivf_index.search(&vectors[i % n], k);
        }
        let ivf_qps = num_queries as f64 / start.elapsed().as_secs_f64();

        // Recall
        let mut hnsw_recall = 0.0;
        let mut ivf_recall = 0.0;
        let recall_queries = 100;

        for i in 0..recall_queries {
            let ground_truth = compute_ground_truth(&vectors, &vectors[i], k);
            let hnsw_results = hnsw_index.search(&vectors[i], k);
            let ivf_results = ivf_index.search(&vectors[i], k);
            hnsw_recall += compute_recall(&ground_truth, &hnsw_results, k);
            ivf_recall += compute_recall(&ground_truth, &ivf_results, k);
        }
        hnsw_recall /= recall_queries as f64;
        ivf_recall /= recall_queries as f64;

        println!("{:>10} {:>10} {:>10} {:>10} {:>10}", "Index", "Build(s)", "Memory(MB)", "QPS", "Recall@10");
        println!("{:-<52}", "");
        println!("{:>10} {:>10.2} {:>10.2} {:>10.0} {:>9.1}%",
            "HNSW", hnsw_build_time.as_secs_f64(), hnsw_index.memory_usage() as f64 / 1e6, hnsw_qps, hnsw_recall * 100.0);
        println!("{:>10} {:>10.2} {:>10.2} {:>10.0} {:>9.1}%",
            "IVF", ivf_build_time.as_secs_f64(), ivf_index.memory_usage() as f64 / 1e6, ivf_qps, ivf_recall * 100.0);
        println!();
        println!("IVF speedup: {:.2}x", ivf_qps / hnsw_qps);
    }
}
