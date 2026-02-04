// Search algorithms for Descartes index
// Beam search with coordinate-based pruning

use crate::descartes::{
    bitset::BitSet,
    graph::FullyNavigatableGraph,
    quantization::QuantizedVectorStorage,
};
use std::cmp::Reverse;
use std::collections::BinaryHeap;

/// Search result with ID and distance
#[derive(Debug, Clone)]
pub struct SearchResult {
    pub id: i64,
    pub distance: f32,
}

impl SearchResult {
    pub fn new(id: i64, distance: f32) -> Self {
        Self { id, distance }
    }
}

/// Beam search on the FNG graph
/// Returns top-k nearest neighbors
pub fn beam_search(
    graph: &FullyNavigatableGraph,
    storage: &QuantizedVectorStorage,
    query: &[i8],
    k: usize,
    ef_search: usize,
) -> Vec<SearchResult> {
    if graph.is_empty() {
        return Vec::new();
    }

    let entry_point = match graph.entry_point {
        Some(ep) => ep,
        None => return Vec::new(),
    };

    // Start from entry point and navigate down
    let mut current = entry_point;

    // Greedy search from top level down to level 1
    for level in (1..=graph.max_level).rev() {
        current = greedy_search_layer(graph, storage, query, current, level);
    }

    // At level 0, do full beam search
    let candidates = search_layer_0(graph, storage, query, current, ef_search);

    // Return top k
    candidates
        .into_iter()
        .take(k)
        .map(|(dist, id)| SearchResult::new(id as i64, dist as f32))
        .collect()
}

/// Greedy search in a single layer
fn greedy_search_layer(
    graph: &FullyNavigatableGraph,
    storage: &QuantizedVectorStorage,
    query: &[i8],
    start: usize,
    level: usize,
) -> usize {
    let mut current = start;
    let mut current_dist = storage.distance_to(query, current);

    loop {
        let mut improved = false;

        for &neighbor in graph.neighbors(current, level) {
            let dist = storage.distance_to(query, neighbor);
            if dist < current_dist {
                current = neighbor;
                current_dist = dist;
                improved = true;
            }
        }

        if !improved {
            break;
        }
    }

    current
}

/// Full beam search at level 0
/// Uses BitSet for O(1) visited tracking and optimized heap operations.
fn search_layer_0(
    graph: &FullyNavigatableGraph,
    storage: &QuantizedVectorStorage,
    query: &[i8],
    entry_point: usize,
    ef: usize,
) -> Vec<(i32, usize)> {
    let mut visited = BitSet::new(graph.len());

    // Min-heap for candidates (closest first)
    let mut candidates: BinaryHeap<Reverse<(i32, usize)>> = BinaryHeap::with_capacity(ef * 2);

    // Max-heap for results (farthest first, for easy pruning)
    let mut results: BinaryHeap<(i32, usize)> = BinaryHeap::with_capacity(ef + 1);

    // Initialize
    let entry_dist = storage.distance_to(query, entry_point);
    candidates.push(Reverse((entry_dist, entry_point)));
    results.push((entry_dist, entry_point));
    visited.insert(entry_point);

    // Track worst distance for fast pruning (avoids peek() calls)
    let mut worst_dist = entry_dist;

    while let Some(Reverse((c_dist, c_id))) = candidates.pop() {
        // Early termination: if candidate is worse than worst result
        if c_dist > worst_dist && results.len() >= ef {
            break;
        }

        // Get neighbors once
        let neighbors = graph.neighbors(c_id, 0);

        // Process neighbors in batches for better cache utilization
        for &neighbor in neighbors {
            // BitSet.insert returns true if this is a new insertion
            if !visited.insert(neighbor) {
                continue;
            }

            let dist = storage.distance_to(query, neighbor);

            // Only add if better than worst or we need more results
            if results.len() < ef || dist < worst_dist {
                candidates.push(Reverse((dist, neighbor)));
                results.push((dist, neighbor));

                // Keep only top ef results
                if results.len() > ef {
                    results.pop(); // Remove farthest
                    // Update worst distance from new max
                    if let Some(&(d, _)) = results.peek() {
                        worst_dist = d;
                    }
                }
            }
        }
    }

    // Sort by distance and return
    let mut result_vec: Vec<(i32, usize)> = results.into_iter().collect();
    result_vec.sort_by_key(|(d, _)| *d);
    result_vec
}

/// Batch search - search for multiple queries efficiently
pub fn batch_search(
    graph: &FullyNavigatableGraph,
    storage: &QuantizedVectorStorage,
    queries: &[Vec<i8>],
    k: usize,
    ef_search: usize,
) -> Vec<Vec<SearchResult>> {
    use rayon::prelude::*;

    queries
        .par_iter()
        .map(|query| beam_search(graph, storage, query, k, ef_search))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::descartes::{
        build::GraphBuilder,
        quantization::{ScalarQuantizer, QuantizedVectorStorage},
        DescartesConfig,
    };
    use rand::Rng;

    fn create_test_index(n: usize, dim: usize) -> (FullyNavigatableGraph, QuantizedVectorStorage, Vec<Vec<f32>>, ScalarQuantizer) {
        let mut rng = rand::thread_rng();
        let vectors: Vec<Vec<f32>> = (0..n)
            .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
            .collect();

        let config = DescartesConfig::new(dim).with_m(8);

        let mut quantizer = ScalarQuantizer::new(dim);
        quantizer.train(&vectors);

        let mut storage = QuantizedVectorStorage::new(dim, n);
        for (i, vec) in vectors.iter().enumerate() {
            let quantized = quantizer.encode(vec);
            storage.set_vector(i, &quantized);
        }

        let mut builder = GraphBuilder::new(config);
        let graph = builder.build(&storage, &quantizer);

        (graph, storage, vectors, quantizer)
    }

    #[test]
    fn test_search_returns_k() {
        let (graph, storage, _, quantizer) = create_test_index(100, 4);

        let query = vec![0.5f32; 4];
        let q_query = quantizer.encode(&query);

        let results = beam_search(&graph, &storage, &q_query, 10, 32);

        assert_eq!(results.len(), 10, "Should return exactly k results");
    }

    #[test]
    fn test_search_results_sorted() {
        let (graph, storage, _, quantizer) = create_test_index(100, 4);

        let query = vec![0.5f32; 4];
        let q_query = quantizer.encode(&query);

        let results = beam_search(&graph, &storage, &q_query, 20, 64);

        // Verify results are sorted by distance
        for i in 1..results.len() {
            assert!(
                results[i - 1].distance <= results[i].distance,
                "Results not sorted: {} > {}",
                results[i - 1].distance,
                results[i].distance
            );
        }
    }

    #[test]
    fn test_search_recall_small() {
        let (graph, storage, vectors, quantizer) = create_test_index(100, 4);

        // Test with a known vector (first one)
        let query = &vectors[0];
        let q_query = quantizer.encode(query);

        let results = beam_search(&graph, &storage, &q_query, 5, 32);

        // The exact match should be in top results
        let found = results.iter().any(|r| r.id == 0);
        assert!(found, "Should find exact match in results");
    }

    #[test]
    fn test_batch_search() {
        let (graph, storage, vectors, quantizer) = create_test_index(100, 4);

        let queries: Vec<Vec<i8>> = vectors[0..5]
            .iter()
            .map(|v| quantizer.encode(v))
            .collect();

        let results = batch_search(&graph, &storage, &queries, 5, 32);

        assert_eq!(results.len(), 5, "Should return results for each query");

        for (i, query_results) in results.iter().enumerate() {
            assert!(!query_results.is_empty(), "Query {} should have results", i);
        }
    }

    #[test]
    fn test_empty_graph_search() {
        let graph = FullyNavigatableGraph::new(8, 8);
        let storage = QuantizedVectorStorage::new(4, 0);

        let query = vec![0i8; 4];
        let results = beam_search(&graph, &storage, &query, 10, 32);

        assert!(results.is_empty(), "Empty graph should return no results");
    }
}
