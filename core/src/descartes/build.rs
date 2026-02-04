// Graph construction for Descartes index
// Implements batch insertion with level assignment and neighbor selection

use crate::descartes::{
    adaptive::{AdaptiveNeighborSelector, Candidate},
    bitset::BitSet,
    graph::FullyNavigatableGraph,
    quantization::{QuantizedVectorStorage, ScalarQuantizer},
    DescartesConfig,
};
use rand::Rng;
use std::collections::BinaryHeap;
use std::cmp::Reverse;

/// Builder for constructing Descartes graph
pub struct GraphBuilder {
    config: DescartesConfig,
    rng_seed: u64,
}

impl GraphBuilder {
    pub fn new(config: DescartesConfig) -> Self {
        Self {
            config,
            rng_seed: 42,
        }
    }

    pub fn with_seed(mut self, seed: u64) -> Self {
        self.rng_seed = seed;
        self
    }

    /// Assign level using exponential distribution (HNSW-style)
    /// Higher levels are exponentially less likely
    fn assign_level(&self, rng: &mut impl Rng) -> usize {
        let r: f64 = rng.gen();
        let level = (-r.ln() * self.config.ml).floor() as usize;
        level.min(16) // Cap at reasonable level to prevent outliers
    }

    /// Build the graph from quantized vectors
    pub fn build(
        &mut self,
        storage: &QuantizedVectorStorage,
        _quantizer: &ScalarQuantizer,
    ) -> FullyNavigatableGraph {
        let n = storage.num_vectors();
        if n == 0 {
            return FullyNavigatableGraph::new(self.config.m, self.config.m_max);
        }

        // Assign levels to all nodes first
        let mut rng = rand::thread_rng();
        let levels: Vec<usize> = (0..n).map(|_| self.assign_level(&mut rng)).collect();

        let max_level = *levels.iter().max().unwrap_or(&0);

        // Create graph with nodes
        let mut graph = FullyNavigatableGraph::new(self.config.m, self.config.m_max);
        for &level in &levels {
            graph.add_node(level);
        }

        // Find entry point (node with highest level)
        let entry_point = levels
            .iter()
            .enumerate()
            .max_by_key(|(_, &l)| l)
            .map(|(i, _)| i)
            .unwrap_or(0);

        graph.entry_point = Some(entry_point);
        graph.max_level = max_level;

        // Insert nodes one by one (sequential for correctness, could be parallelized with locking)
        for (node_id, &node_level) in levels.iter().enumerate() {
            self.insert_node(&mut graph, storage, node_id, node_level);
        }

        // Ensure connectivity at level 0
        self.ensure_connectivity(&mut graph, storage);

        graph
    }

    /// Insert a single node into the graph
    fn insert_node(
        &self,
        graph: &mut FullyNavigatableGraph,
        storage: &QuantizedVectorStorage,
        node_id: usize,
        node_level: usize,
    ) {
        if graph.len() <= 1 {
            return; // First node, nothing to connect
        }

        let entry_point = match graph.entry_point {
            Some(ep) => ep,
            None => return,
        };

        let query = storage.get_vector(node_id);
        let mut current = entry_point;

        // Search from top level down to node's level + 1
        for level in (node_level + 1..=graph.max_level).rev() {
            current = self.greedy_search_layer(graph, storage, &query, current, level);
        }

        // At node's levels and below, find neighbors and connect
        for level in (0..=node_level).rev() {
            let neighbors = self.search_layer(
                graph,
                storage,
                &query,
                vec![current],
                self.config.ef_construction,
                level,
            );

            // Select neighbors using adaptive selection
            let selector = AdaptiveNeighborSelector::new(
                self.config.num_sectors,
                if level == 0 { self.config.m * 2 } else { self.config.m_max },
            );

            let mut candidates: Vec<Candidate> = neighbors
                .iter()
                .filter(|&&id| id != node_id)
                .map(|&id| {
                    let dist = storage.distance_to(&query, id);
                    Candidate::new(id, dist, crate::descartes::adaptive::Sector(0))
                })
                .collect();

            let selected = selector.select_neighbors(&query, &mut candidates, storage);

            // Connect node to selected neighbors
            for &neighbor_id in &selected {
                graph.connect(node_id, neighbor_id, level);
            }

            // Prune neighbors if they exceed limit
            for &neighbor_id in &selected {
                self.prune_connections(graph, storage, neighbor_id, level);
            }

            // Update current for next level
            if let Some(&closest) = selected.first() {
                current = closest;
            }
        }
    }

    /// Greedy search in a single layer, returns closest node
    fn greedy_search_layer(
        &self,
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

    /// Search layer returning multiple candidates
    /// Uses BitSet for O(1) visited tracking
    fn search_layer(
        &self,
        graph: &FullyNavigatableGraph,
        storage: &QuantizedVectorStorage,
        query: &[i8],
        entry_points: Vec<usize>,
        ef: usize,
        level: usize,
    ) -> Vec<usize> {
        let mut visited = BitSet::new(graph.len().max(1));
        let mut candidates: BinaryHeap<Reverse<(i32, usize)>> = BinaryHeap::with_capacity(ef * 2);
        let mut results: BinaryHeap<(i32, usize)> = BinaryHeap::with_capacity(ef + 1);

        // Initialize with entry points
        for &ep in &entry_points {
            let dist = storage.distance_to(query, ep);
            candidates.push(Reverse((dist, ep)));
            results.push((dist, ep));
            visited.insert(ep);
        }

        while let Some(Reverse((c_dist, c_id))) = candidates.pop() {
            // If candidate is worse than worst result, stop
            if let Some(&(worst_dist, _)) = results.peek() {
                if c_dist > worst_dist && results.len() >= ef {
                    break;
                }
            }

            // Explore neighbors
            for &neighbor in graph.neighbors(c_id, level) {
                // BitSet.insert returns true if this is a new insertion
                if !visited.insert(neighbor) {
                    continue;
                }

                let dist = storage.distance_to(query, neighbor);

                // Add to candidates if closer than worst result
                let should_add = results.len() < ef || {
                    if let Some(&(worst_dist, _)) = results.peek() {
                        dist < worst_dist
                    } else {
                        true
                    }
                };

                if should_add {
                    candidates.push(Reverse((dist, neighbor)));
                    results.push((dist, neighbor));

                    // Keep only top ef
                    if results.len() > ef {
                        results.pop();
                    }
                }
            }
        }

        // Return results sorted by distance
        let mut result_vec: Vec<(i32, usize)> = results.into_iter().collect();
        result_vec.sort_by_key(|(d, _)| *d);
        result_vec.into_iter().map(|(_, id)| id).collect()
    }

    /// Prune connections if they exceed the limit
    fn prune_connections(
        &self,
        graph: &mut FullyNavigatableGraph,
        storage: &QuantizedVectorStorage,
        node_id: usize,
        level: usize,
    ) {
        let max_neighbors = if level == 0 {
            self.config.m * 2
        } else {
            self.config.m_max
        };

        let neighbors = graph.neighbors(node_id, level).to_vec();
        if neighbors.len() <= max_neighbors {
            return;
        }

        // Get node vector
        let node_vec = storage.get_vector(node_id);

        // Select best neighbors using adaptive selection
        let selector = AdaptiveNeighborSelector::new(self.config.num_sectors, max_neighbors);

        let mut candidates: Vec<Candidate> = neighbors
            .iter()
            .map(|&id| {
                let dist = storage.distance_to(&node_vec, id);
                Candidate::new(id, dist, crate::descartes::adaptive::Sector(0))
            })
            .collect();

        let selected = selector.select_neighbors(&node_vec, &mut candidates, storage);

        // Update neighbors
        graph.set_neighbors(node_id, level, selected);
    }

    /// Ensure all nodes are reachable from entry point at level 0
    /// Uses BitSet for O(1) visited tracking
    fn ensure_connectivity(&self, graph: &mut FullyNavigatableGraph, storage: &QuantizedVectorStorage) {
        let n = graph.len();
        if n <= 1 {
            return;
        }

        // Find disconnected components using BFS
        let mut visited = BitSet::new(n);
        let mut queue = Vec::with_capacity(n);

        if let Some(entry) = graph.entry_point {
            queue.push(entry);
            visited.insert(entry);
        }

        while let Some(current) = queue.pop() {
            for &neighbor in graph.neighbors(current, 0) {
                if visited.insert(neighbor) {
                    queue.push(neighbor);
                }
            }
        }

        // Connect any unvisited nodes to their nearest visited node
        // Collect visited nodes for iteration (can't iterate BitSet directly)
        let visited_nodes: Vec<usize> = (0..n).filter(|&i| visited.contains(i)).collect();

        // Collect nodes to connect (to avoid borrow issues)
        let mut connections: Vec<(usize, usize)> = Vec::new();

        for node_id in 0..n {
            if visited.contains(node_id) {
                continue;
            }

            let node_vec = storage.get_vector(node_id);

            // Find nearest visited node
            let nearest = visited_nodes
                .iter()
                .map(|&v| (storage.distance_to(&node_vec, v), v))
                .min_by_key(|(d, _)| *d)
                .map(|(_, id)| id);

            if let Some(nearest_id) = nearest {
                connections.push((node_id, nearest_id));
                visited.insert(node_id);
            }
        }

        // Apply connections and prune
        for (node_id, nearest_id) in connections {
            graph.connect(node_id, nearest_id, 0);
            // Prune both nodes to maintain neighbor limits
            self.prune_connections(graph, storage, node_id, 0);
            self.prune_connections(graph, storage, nearest_id, 0);
        }
    }
}

/// Verify exponential distribution of levels
pub fn verify_level_distribution(levels: &[usize]) -> bool {
    if levels.is_empty() {
        return true;
    }

    let mut counts = vec![0usize; *levels.iter().max().unwrap_or(&0) + 1];

    for &level in levels {
        counts[level] += 1;
    }

    // Check exponential decay: each level should have roughly 1/M times the previous
    // Allow some variance due to randomness
    for i in 1..counts.len() {
        if counts[i - 1] == 0 {
            continue;
        }

        let ratio = counts[i] as f64 / counts[i - 1] as f64;

        // Ratio should be less than 1 (exponential decay)
        // With ml = 1/ln(M), expected ratio is ~1/M
        if ratio > 1.0 {
            return false;
        }
    }

    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::descartes::quantization::ScalarQuantizer;

    fn create_test_vectors(n: usize, dim: usize) -> Vec<Vec<f32>> {
        let mut rng = rand::thread_rng();
        (0..n)
            .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
            .collect()
    }

    #[test]
    fn test_level_assignment() {
        let config = DescartesConfig::new(4).with_m(16);
        let builder = GraphBuilder::new(config);
        let mut rng = rand::thread_rng();

        let levels: Vec<usize> = (0..1000).map(|_| builder.assign_level(&mut rng)).collect();

        // Most should be level 0
        let level_0_count = levels.iter().filter(|&&l| l == 0).count();
        assert!(
            level_0_count > 500,
            "Expected most nodes at level 0, got {}",
            level_0_count
        );

        // Should follow exponential distribution
        assert!(verify_level_distribution(&levels));
    }

    #[test]
    fn test_graph_build() {
        let vectors = create_test_vectors(100, 4);
        let config = DescartesConfig::new(4).with_m(8);

        let mut quantizer = ScalarQuantizer::new(4);
        quantizer.train(&vectors);

        let mut storage = QuantizedVectorStorage::new(4, vectors.len());
        for (i, vec) in vectors.iter().enumerate() {
            let quantized = quantizer.encode(vec);
            storage.set_vector(i, &quantized);
        }

        let mut builder = GraphBuilder::new(config);
        let graph = builder.build(&storage, &quantizer);

        assert_eq!(graph.len(), 100);
        assert!(graph.entry_point.is_some());
        assert!(graph.verify_connectivity(), "Graph should be connected");
    }

    #[test]
    fn test_neighbor_limits() {
        let vectors = create_test_vectors(50, 4);
        let config = DescartesConfig::new(4).with_m(4);

        let mut quantizer = ScalarQuantizer::new(4);
        quantizer.train(&vectors);

        let mut storage = QuantizedVectorStorage::new(4, vectors.len());
        for (i, vec) in vectors.iter().enumerate() {
            let quantized = quantizer.encode(vec);
            storage.set_vector(i, &quantized);
        }

        let mut builder = GraphBuilder::new(config.clone());
        let graph = builder.build(&storage, &quantizer);

        // Check neighbor counts don't exceed limits
        for node in &graph.nodes {
            // Level 0: max 2*M
            assert!(
                node.neighbors[0].len() <= config.m * 2,
                "Level 0 neighbors {} exceed limit {}",
                node.neighbors[0].len(),
                config.m * 2
            );

            // Higher levels: max M_max
            for level in 1..node.neighbors.len() {
                assert!(
                    node.neighbors[level].len() <= config.m_max,
                    "Level {} neighbors {} exceed limit {}",
                    level,
                    node.neighbors[level].len(),
                    config.m_max
                );
            }
        }
    }

    #[test]
    fn test_verify_level_distribution_valid() {
        // Typical HNSW-like distribution
        let levels = vec![0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2];
        assert!(verify_level_distribution(&levels));
    }

    #[test]
    fn test_verify_level_distribution_invalid() {
        // Inverted distribution (more high levels than low)
        let levels = vec![2, 2, 2, 2, 1, 1, 0];
        assert!(!verify_level_distribution(&levels));
    }
}
