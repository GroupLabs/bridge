// Fully Navigatable Graph (FNG) structure
// Multi-level hierarchy with coordinate-based neighbor partitioning

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// A node in the FNG graph
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphNode {
    /// Node ID (index in vector storage)
    pub id: usize,
    /// Level in the hierarchy (0 = bottom, higher = sparser)
    pub level: usize,
    /// Neighbors at each level: neighbors[level] = vec of neighbor IDs
    pub neighbors: Vec<Vec<usize>>,
}

impl GraphNode {
    pub fn new(id: usize, max_level: usize) -> Self {
        Self {
            id,
            level: max_level,
            neighbors: (0..=max_level).map(|_| Vec::new()).collect(),
        }
    }

    /// Get neighbors at a specific level
    #[inline]
    pub fn neighbors_at(&self, level: usize) -> &[usize] {
        self.neighbors.get(level).map(|v| v.as_slice()).unwrap_or(&[])
    }

    /// Add a neighbor at a specific level
    pub fn add_neighbor(&mut self, level: usize, neighbor_id: usize) {
        if level < self.neighbors.len() && !self.neighbors[level].contains(&neighbor_id) {
            self.neighbors[level].push(neighbor_id);
        }
    }

    /// Remove a neighbor at a specific level
    pub fn remove_neighbor(&mut self, level: usize, neighbor_id: usize) {
        if level < self.neighbors.len() {
            self.neighbors[level].retain(|&id| id != neighbor_id);
        }
    }

    /// Set neighbors at a specific level (replacing existing)
    pub fn set_neighbors(&mut self, level: usize, neighbors: Vec<usize>) {
        if level < self.neighbors.len() {
            self.neighbors[level] = neighbors;
        }
    }
}

/// Fully Navigatable Graph for HNSW-style approximate nearest neighbor search
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FullyNavigatableGraph {
    /// All nodes in the graph
    pub nodes: Vec<GraphNode>,
    /// Entry point for search (highest level node)
    pub entry_point: Option<usize>,
    /// Maximum level in the graph
    pub max_level: usize,
    /// Maximum neighbors per node at level 0
    pub m: usize,
    /// Maximum neighbors per node at higher levels (typically 2*M)
    pub m_max: usize,
}

impl FullyNavigatableGraph {
    /// Create an empty graph
    pub fn new(m: usize, m_max: usize) -> Self {
        Self {
            nodes: Vec::new(),
            entry_point: None,
            max_level: 0,
            m,
            m_max,
        }
    }

    /// Add a node to the graph
    pub fn add_node(&mut self, level: usize) -> usize {
        let id = self.nodes.len();
        self.nodes.push(GraphNode::new(id, level));

        // Update entry point if this is the first node or has higher level
        if self.entry_point.is_none() || level > self.max_level {
            self.entry_point = Some(id);
            self.max_level = level;
        }

        id
    }

    /// Get a node by ID
    #[inline]
    pub fn get_node(&self, id: usize) -> Option<&GraphNode> {
        self.nodes.get(id)
    }

    /// Get a mutable node by ID
    #[inline]
    pub fn get_node_mut(&mut self, id: usize) -> Option<&mut GraphNode> {
        self.nodes.get_mut(id)
    }

    /// Get number of nodes
    #[inline]
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// Check if graph is empty
    #[inline]
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    /// Get all neighbors at a level for a node
    #[inline]
    pub fn neighbors(&self, node_id: usize, level: usize) -> &[usize] {
        self.nodes
            .get(node_id)
            .map(|n| n.neighbors_at(level))
            .unwrap_or(&[])
    }

    /// Connect two nodes at a given level (bidirectional)
    pub fn connect(&mut self, node_a: usize, node_b: usize, level: usize) {
        if node_a == node_b {
            return;
        }

        if let Some(node) = self.nodes.get_mut(node_a) {
            node.add_neighbor(level, node_b);
        }
        if let Some(node) = self.nodes.get_mut(node_b) {
            node.add_neighbor(level, node_a);
        }
    }

    /// Set neighbors for a node at a level (replaces existing)
    pub fn set_neighbors(&mut self, node_id: usize, level: usize, neighbors: Vec<usize>) {
        if let Some(node) = self.nodes.get_mut(node_id) {
            node.set_neighbors(level, neighbors);
        }
    }

    /// Get nodes at a specific level (nodes with level >= given level)
    pub fn nodes_at_level(&self, level: usize) -> Vec<usize> {
        self.nodes
            .iter()
            .filter(|n| n.level >= level)
            .map(|n| n.id)
            .collect()
    }

    /// Verify graph connectivity from entry point
    pub fn verify_connectivity(&self) -> bool {
        if self.is_empty() {
            return true;
        }

        let entry = match self.entry_point {
            Some(e) => e,
            None => return false,
        };

        // BFS from entry point at level 0
        let mut visited = HashSet::new();
        let mut queue = vec![entry];
        visited.insert(entry);

        while let Some(current) = queue.pop() {
            for &neighbor in self.neighbors(current, 0) {
                if !visited.contains(&neighbor) {
                    visited.insert(neighbor);
                    queue.push(neighbor);
                }
            }
        }

        visited.len() == self.len()
    }

    /// Get statistics about the graph
    pub fn stats(&self) -> GraphStats {
        let mut total_edges = 0;
        let mut max_neighbors = 0;
        let mut level_counts = vec![0usize; self.max_level + 1];

        for node in &self.nodes {
            for level_neighbors in &node.neighbors {
                total_edges += level_neighbors.len();
                max_neighbors = max_neighbors.max(level_neighbors.len());
            }

            // Count nodes at each level (nodes exist at all levels <= their level)
            for l in 0..=node.level {
                if l < level_counts.len() {
                    level_counts[l] += 1;
                }
            }
        }

        GraphStats {
            num_nodes: self.nodes.len(),
            num_edges: total_edges / 2, // Each edge counted twice
            max_level: self.max_level,
            level_counts,
            max_neighbors,
            avg_neighbors_l0: if self.nodes.is_empty() {
                0.0
            } else {
                self.nodes.iter().map(|n| n.neighbors[0].len()).sum::<usize>() as f64
                    / self.nodes.len() as f64
            },
        }
    }

    /// Estimate memory usage in bytes
    pub fn memory_usage(&self) -> usize {
        let node_base_size = std::mem::size_of::<GraphNode>();
        let mut total = self.nodes.len() * node_base_size;

        for node in &self.nodes {
            for neighbors in &node.neighbors {
                total += neighbors.capacity() * std::mem::size_of::<usize>();
            }
        }

        total
    }
}

/// Statistics about the graph structure
#[derive(Debug, Clone)]
pub struct GraphStats {
    pub num_nodes: usize,
    pub num_edges: usize,
    pub max_level: usize,
    pub level_counts: Vec<usize>,
    pub max_neighbors: usize,
    pub avg_neighbors_l0: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_graph_node_creation() {
        let node = GraphNode::new(0, 3);
        assert_eq!(node.id, 0);
        assert_eq!(node.level, 3);
        assert_eq!(node.neighbors.len(), 4); // levels 0, 1, 2, 3
    }

    #[test]
    fn test_graph_add_nodes() {
        let mut graph = FullyNavigatableGraph::new(32, 32);

        let id0 = graph.add_node(0);
        let id1 = graph.add_node(1);
        let id2 = graph.add_node(2);

        assert_eq!(id0, 0);
        assert_eq!(id1, 1);
        assert_eq!(id2, 2);

        assert_eq!(graph.len(), 3);
        assert_eq!(graph.entry_point, Some(2)); // Highest level
        assert_eq!(graph.max_level, 2);
    }

    #[test]
    fn test_graph_connectivity() {
        let mut graph = FullyNavigatableGraph::new(32, 32);

        let n0 = graph.add_node(0);
        let n1 = graph.add_node(0);
        let n2 = graph.add_node(0);
        let n3 = graph.add_node(0);

        // Create a connected graph
        graph.connect(n0, n1, 0);
        graph.connect(n1, n2, 0);
        graph.connect(n2, n3, 0);

        assert!(graph.verify_connectivity());

        // Add an isolated node
        let _n4 = graph.add_node(0);
        assert!(!graph.verify_connectivity());
    }

    #[test]
    fn test_neighbor_operations() {
        let mut graph = FullyNavigatableGraph::new(32, 32);

        let n0 = graph.add_node(1);
        let n1 = graph.add_node(1);
        let n2 = graph.add_node(1);

        graph.connect(n0, n1, 0);
        graph.connect(n0, n2, 0);
        graph.connect(n0, n1, 1);

        assert_eq!(graph.neighbors(n0, 0).len(), 2);
        assert_eq!(graph.neighbors(n0, 1).len(), 1);
        assert!(graph.neighbors(n0, 0).contains(&n1));
        assert!(graph.neighbors(n0, 0).contains(&n2));
    }

    #[test]
    fn test_graph_stats() {
        let mut graph = FullyNavigatableGraph::new(32, 32);

        let n0 = graph.add_node(0);
        let n1 = graph.add_node(1);
        let n2 = graph.add_node(2);

        graph.connect(n0, n1, 0);
        graph.connect(n1, n2, 0);
        graph.connect(n1, n2, 1);

        let stats = graph.stats();
        assert_eq!(stats.num_nodes, 3);
        assert_eq!(stats.max_level, 2);
        assert!(stats.avg_neighbors_l0 > 0.0);
    }

    #[test]
    fn test_nodes_at_level() {
        let mut graph = FullyNavigatableGraph::new(32, 32);

        graph.add_node(0); // Only at level 0
        graph.add_node(1); // At levels 0, 1
        graph.add_node(2); // At levels 0, 1, 2

        assert_eq!(graph.nodes_at_level(0).len(), 3);
        assert_eq!(graph.nodes_at_level(1).len(), 2);
        assert_eq!(graph.nodes_at_level(2).len(), 1);
    }
}
