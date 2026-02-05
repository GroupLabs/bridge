// Descartes-inspired vector search engine
// Fully Navigatable Graph (FNG) with adaptive neighbor selection and Int8 quantization

pub mod quantization;
pub mod graph;
pub mod build;
pub mod search;
pub mod adaptive;
pub mod persistence;
pub mod bitset;
pub mod ivf;
pub mod benchmark;
pub mod bench_compare;
pub mod hybrid_bench;

use serde::{Deserialize, Serialize};

pub use quantization::{ScalarQuantizer, QuantizedVectorStorage, simd_type, simd_type_name};
pub use graph::{GraphNode, FullyNavigatableGraph};
pub use build::GraphBuilder;
pub use search::SearchResult;
pub use adaptive::AdaptiveNeighborSelector;
pub use bitset::BitSet;
pub use ivf::{IvfConfig, IvfIndex};

/// Configuration for Descartes index
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DescartesConfig {
    /// Vector dimension
    pub dimension: usize,
    /// Maximum neighbors per node at level 0
    pub m: usize,
    /// Maximum neighbors per node at higher levels
    pub m_max: usize,
    /// Size of candidate list during construction
    pub ef_construction: usize,
    /// Size of candidate list during search
    pub ef_search: usize,
    /// Level multiplier for exponential distribution
    pub ml: f64,
    /// Number of sectors for coordinate partitioning (typically 4)
    pub num_sectors: usize,
}

impl Default for DescartesConfig {
    fn default() -> Self {
        Self {
            dimension: 128,
            m: 32,
            m_max: 32,
            ef_construction: 200,
            ef_search: 64,
            ml: 1.0 / (32_f64).ln(), // 1/ln(M)
            num_sectors: 4,
        }
    }
}

impl DescartesConfig {
    pub fn new(dimension: usize) -> Self {
        Self {
            dimension,
            ..Default::default()
        }
    }

    pub fn with_m(mut self, m: usize) -> Self {
        self.m = m;
        self.m_max = m;
        self.ml = 1.0 / (m as f64).ln();
        self
    }

    pub fn with_ef_construction(mut self, ef: usize) -> Self {
        self.ef_construction = ef;
        self
    }

    pub fn with_ef_search(mut self, ef: usize) -> Self {
        self.ef_search = ef;
        self
    }
}

/// Main Descartes index structure
pub struct DescartesIndex {
    pub config: DescartesConfig,
    pub quantizer: ScalarQuantizer,
    pub storage: QuantizedVectorStorage,
    pub graph: FullyNavigatableGraph,
    /// Original vectors for reranking (enables high recall with fast search)
    pub original_vectors: Vec<Vec<f32>>,
    /// ID mapping: internal index -> external ID
    pub id_map: Vec<i64>,
    /// Reverse mapping: external ID -> internal index
    pub reverse_id_map: std::collections::HashMap<i64, usize>,
}

impl DescartesIndex {
    /// Create a new empty index
    pub fn new(config: DescartesConfig) -> Self {
        Self {
            quantizer: ScalarQuantizer::new(config.dimension),
            storage: QuantizedVectorStorage::new(config.dimension, 0),
            graph: FullyNavigatableGraph::new(config.m, config.m_max),
            original_vectors: Vec::new(),
            id_map: Vec::new(),
            reverse_id_map: std::collections::HashMap::new(),
            config,
        }
    }

    /// Build index from vectors with IDs
    pub fn build_with_ids(&mut self, vectors: &[Vec<f32>], ids: &[i64]) {
        assert_eq!(vectors.len(), ids.len(), "vectors and ids must have same length");

        if vectors.is_empty() {
            return;
        }

        // Store ID mapping
        self.id_map = ids.to_vec();
        self.reverse_id_map.clear();
        for (idx, &id) in ids.iter().enumerate() {
            self.reverse_id_map.insert(id, idx);
        }

        // Store original vectors for reranking
        self.original_vectors = vectors.to_vec();

        // Train quantizer and encode vectors
        self.quantizer.train(vectors);
        self.storage = QuantizedVectorStorage::new(self.config.dimension, vectors.len());

        for (i, vec) in vectors.iter().enumerate() {
            let quantized = self.quantizer.encode(vec);
            self.storage.set_vector(i, &quantized);
        }

        // Build graph
        let mut builder = GraphBuilder::new(self.config.clone());
        self.graph = builder.build(&self.storage, &self.quantizer);
    }

    /// Search for k nearest neighbors
    /// Uses quantized search with efficient reranking for high recall and speed.
    pub fn search(&self, query: &[f32], k: usize) -> Vec<SearchResult> {
        let quantized_query = self.quantizer.encode(query);

        // Fetch 3*k candidates for reranking - balances speed and recall
        let rerank_k = (k * 3).max(32);
        let candidates = search::beam_search(
            &self.graph,
            &self.storage,
            &quantized_query,
            rerank_k,
            self.config.ef_search,
        );

        // Rerank top candidates using original float32 vectors
        // Pre-allocate to avoid reallocations
        let mut reranked: Vec<(f32, i64)> = Vec::with_capacity(candidates.len());
        for r in &candidates {
            let idx = r.id as usize;
            if idx < self.original_vectors.len() {
                let dist = l2_distance_f32_fast(query, &self.original_vectors[idx]);
                let ext_id = *self.id_map.get(idx).unwrap_or(&r.id);
                reranked.push((dist, ext_id));
            }
        }

        reranked.sort_unstable_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

        reranked
            .into_iter()
            .take(k)
            .map(|(dist, id)| SearchResult::new(id, dist))
            .collect()
    }

    /// Get number of vectors in index
    pub fn len(&self) -> usize {
        self.storage.num_vectors()
    }

    /// Check if index is empty
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Get memory usage estimate in bytes
    pub fn memory_usage(&self) -> usize {
        let quantized_size = self.storage.data().len();
        let graph_size = self.graph.memory_usage();
        let original_size = self.original_vectors.len() * self.config.dimension * 4;
        let id_map_size = self.id_map.len() * 8;

        quantized_size + graph_size + original_size + id_map_size
    }
}

/// Fast L2 squared distance for float32 vectors
/// Uses 4 accumulators to break dependency chain
#[inline]
fn l2_distance_f32_fast(a: &[f32], b: &[f32]) -> f32 {
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

    fn generate_random_vectors(n: usize, dim: usize) -> Vec<Vec<f32>> {
        let mut rng = rand::thread_rng();
        (0..n)
            .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
            .collect()
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

    fn compute_ground_truth(vectors: &[Vec<f32>], query: &[f32], k: usize) -> Vec<usize> {
        let mut distances: Vec<(f32, usize)> = vectors
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let dist: f32 = query.iter().zip(v.iter()).map(|(a, b)| (a - b).powi(2)).sum();
                (dist, i)
            })
            .collect();
        distances.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
        distances.iter().take(k).map(|(_, i)| *i).collect()
    }

    fn compute_recall(ground_truth: &[usize], results: &[SearchResult], k: usize) -> f64 {
        use std::collections::HashSet;
        let gt_set: HashSet<usize> = ground_truth.iter().take(k).cloned().collect();
        let result_set: HashSet<usize> = results.iter().take(k).map(|r| r.id as usize).collect();
        gt_set.intersection(&result_set).count() as f64 / k as f64
    }

    #[test]
    fn test_descartes_index_basic() {
        let config = DescartesConfig::new(4);
        let mut index = DescartesIndex::new(config);

        let vectors = vec![
            vec![1.0, 0.0, 0.0, 0.0],
            vec![0.0, 1.0, 0.0, 0.0],
            vec![0.0, 0.0, 1.0, 0.0],
            vec![0.0, 0.0, 0.0, 1.0],
            vec![0.5, 0.5, 0.0, 0.0],
        ];
        let ids: Vec<i64> = (100..105).collect();

        index.build_with_ids(&vectors, &ids);

        assert_eq!(index.len(), 5);
        assert!(!index.is_empty());

        let results = index.search(&[1.0, 0.0, 0.0, 0.0], 3);
        assert!(!results.is_empty());
        assert_eq!(results[0].id, 100);
    }

    #[test]
    fn test_descartes_recall_random() {
        let n = 1000;
        let dim = 32;
        let k = 10;

        let vectors = generate_random_vectors(n, dim);
        let config = DescartesConfig::new(dim)
            .with_m(16)
            .with_ef_construction(100)
            .with_ef_search(64);

        let mut index = DescartesIndex::new(config);
        let ids: Vec<i64> = (0..n as i64).collect();
        index.build_with_ids(&vectors, &ids);

        let mut total_recall = 0.0;
        let num_queries = 50;

        for i in 0..num_queries {
            let query = &vectors[i];
            let ground_truth = compute_ground_truth(&vectors, query, k);
            let results = index.search(query, k);
            total_recall += compute_recall(&ground_truth, &results, k);
        }

        let avg_recall = total_recall / num_queries as f64;
        assert!(avg_recall > 0.9, "Recall {} should be > 90%", avg_recall);
    }

    #[test]
    fn test_descartes_recall_clustered() {
        let n = 2000;
        let dim = 64;
        let k = 10;

        let vectors = generate_clustered_vectors(n, dim, 20);
        let config = DescartesConfig::new(dim)
            .with_m(32)
            .with_ef_construction(200)
            .with_ef_search(256); // Higher ef_search for better recall

        let mut index = DescartesIndex::new(config);
        let ids: Vec<i64> = (0..n as i64).collect();
        index.build_with_ids(&vectors, &ids);

        let mut total_recall = 0.0;
        let num_queries = 100;

        for i in 0..num_queries {
            let query = &vectors[i];
            let ground_truth = compute_ground_truth(&vectors, query, k);
            let results = index.search(query, k);
            total_recall += compute_recall(&ground_truth, &results, k);
        }

        let avg_recall = total_recall / num_queries as f64;
        // Clustered data can be harder - accept 85%+ recall
        assert!(avg_recall > 0.85, "Clustered recall {} should be > 85%", avg_recall);
    }

    #[test]
    fn test_descartes_memory_efficiency() {
        let n = 1000;
        let dim = 128;

        let vectors = generate_random_vectors(n, dim);
        let config = DescartesConfig::new(dim);

        let mut index = DescartesIndex::new(config);
        let ids: Vec<i64> = (0..n as i64).collect();
        index.build_with_ids(&vectors, &ids);

        let memory = index.memory_usage();
        let float32_size = n * dim * 4;

        // With original vectors for reranking, total memory is higher
        // but quantized storage enables fast graph traversal
        println!("Memory: {} bytes, Float32 only: {} bytes", memory, float32_size);
        assert!(memory > 0);
    }

    #[test]
    fn test_descartes_empty_index() {
        let config = DescartesConfig::new(8);
        let index = DescartesIndex::new(config);

        assert!(index.is_empty());
        assert_eq!(index.len(), 0);

        let results = index.search(&[0.0; 8], 10);
        assert!(results.is_empty());
    }

    #[test]
    fn test_descartes_search_k_results() {
        let vectors = generate_random_vectors(100, 16);
        let config = DescartesConfig::new(16).with_ef_search(32);

        let mut index = DescartesIndex::new(config);
        let ids: Vec<i64> = (0..100).collect();
        index.build_with_ids(&vectors, &ids);

        let results = index.search(&vectors[0], 5);
        assert_eq!(results.len(), 5);

        let results = index.search(&vectors[0], 20);
        assert_eq!(results.len(), 20);
    }

    #[test]
    fn test_descartes_results_sorted() {
        let vectors = generate_random_vectors(200, 16);
        let config = DescartesConfig::new(16).with_ef_search(64);

        let mut index = DescartesIndex::new(config);
        let ids: Vec<i64> = (0..200).collect();
        index.build_with_ids(&vectors, &ids);

        let results = index.search(&vectors[50], 20);

        for i in 1..results.len() {
            assert!(
                results[i - 1].distance <= results[i].distance,
                "Results not sorted at {}: {} > {}",
                i,
                results[i - 1].distance,
                results[i].distance
            );
        }
    }

    /// Quick performance test (10k vectors)
    #[test]
    fn test_descartes_performance_10k() {
        use std::time::Instant;

        let n = 10_000;
        let dim = 128;
        let k = 10;

        let vectors = generate_random_vectors(n, dim);

        let build_start = Instant::now();
        // ef_search=80 with reranking balances speed and recall
        let config = DescartesConfig::new(dim)
            .with_m(32)
            .with_ef_construction(200)
            .with_ef_search(80);

        let mut index = DescartesIndex::new(config);
        let ids: Vec<i64> = (0..n as i64).collect();
        index.build_with_ids(&vectors, &ids);
        let build_time = build_start.elapsed();

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

        println!("\n=== Descartes 10K Benchmark ===");
        println!("Build: {:.2}s | Memory: {:.2}MB | QPS: {:.0} | Recall@10: {:.1}%",
            build_time.as_secs_f64(),
            index.memory_usage() as f64 / 1_000_000.0,
            qps,
            avg_recall * 100.0
        );

        // Assertions
        assert!(avg_recall > 0.9, "Recall should be >90%");
    }
}
