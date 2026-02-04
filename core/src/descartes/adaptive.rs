// Adaptive neighbor selection with coordinate-based partitioning
// Descartes-inspired approach: distribute neighbors across directional sectors

use crate::descartes::quantization::QuantizedVectorStorage;

/// Represents a directional sector (quadrant in 2D, octant in 3D, etc.)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Sector(pub u8);

impl Sector {
    /// Compute sector for a direction vector
    /// Uses sign of first few dimensions to partition space
    pub fn from_direction(direction: &[i8], num_sectors_log2: usize) -> Self {
        let mut sector: u8 = 0;

        // Use first log2(num_sectors) dimensions for sector assignment
        for i in 0..num_sectors_log2.min(direction.len()) {
            if direction[i] >= 0 {
                sector |= 1 << i;
            }
        }

        Sector(sector)
    }

    /// Get sector from comparing two vectors
    pub fn from_vectors(from: &[i8], to: &[i8], num_sectors_log2: usize) -> Self {
        let direction: Vec<i8> = to
            .iter()
            .zip(from.iter())
            .map(|(&a, &b)| {
                let diff = a as i16 - b as i16;
                if diff > 0 { 1 } else if diff < 0 { -1 } else { 0 }
            })
            .collect();

        Self::from_direction(&direction, num_sectors_log2)
    }
}

/// Candidate neighbor with its metadata
#[derive(Debug, Clone)]
pub struct Candidate {
    pub id: usize,
    pub distance: i32,
    pub sector: Sector,
}

impl Candidate {
    pub fn new(id: usize, distance: i32, sector: Sector) -> Self {
        Self { id, distance, sector }
    }
}

/// Adaptive neighbor selector using coordinate-based partitioning
pub struct AdaptiveNeighborSelector {
    /// Number of sectors (power of 2: 4, 8, 16, etc.)
    pub num_sectors: usize,
    /// Log2 of num_sectors for efficient computation
    num_sectors_log2: usize,
    /// Maximum neighbors to select
    pub max_neighbors: usize,
    /// Whether to use diversity heuristic
    pub use_diversity: bool,
}

impl AdaptiveNeighborSelector {
    pub fn new(num_sectors: usize, max_neighbors: usize) -> Self {
        let num_sectors_log2 = (num_sectors as f64).log2() as usize;
        Self {
            num_sectors,
            num_sectors_log2,
            max_neighbors,
            use_diversity: true,
        }
    }

    /// Select neighbors with sector-based diversity
    /// Ensures neighbors are distributed across directional sectors
    pub fn select_neighbors(
        &self,
        node_vector: &[i8],
        candidates: &mut Vec<Candidate>,
        storage: &QuantizedVectorStorage,
    ) -> Vec<usize> {
        if candidates.is_empty() {
            return Vec::new();
        }

        // Sort by distance
        candidates.sort_by_key(|c| c.distance);

        if !self.use_diversity || candidates.len() <= self.max_neighbors {
            // Simple case: just take top-k
            return candidates
                .iter()
                .take(self.max_neighbors)
                .map(|c| c.id)
                .collect();
        }

        // Compute sectors for all candidates
        for candidate in candidates.iter_mut() {
            let neighbor_vec = storage.get_vector(candidate.id);
            candidate.sector = Sector::from_vectors(node_vector, &neighbor_vec, self.num_sectors_log2);
        }

        // Greedy selection with sector diversity
        let mut selected: Vec<usize> = Vec::with_capacity(self.max_neighbors);
        let mut sector_counts = vec![0usize; self.num_sectors];

        for candidate in candidates.iter() {
            if selected.len() >= self.max_neighbors {
                break;
            }

            let sector_idx = candidate.sector.0 as usize;

            // Check if this sector is under-represented
            let min_sector_count = sector_counts.iter().copied().min().unwrap_or(0);
            let this_sector_count = sector_counts[sector_idx];

            // Accept if: first neighbor, sector is under-represented, or we need more neighbors
            let should_accept = selected.is_empty()
                || this_sector_count <= min_sector_count
                || selected.len() < self.max_neighbors / 2;

            if should_accept || !self.use_heuristic_pruning(&selected, candidate, storage, node_vector) {
                selected.push(candidate.id);
                sector_counts[sector_idx] += 1;
            }
        }

        // If we don't have enough, fill with remaining best candidates
        if selected.len() < self.max_neighbors {
            for candidate in candidates.iter() {
                if selected.len() >= self.max_neighbors {
                    break;
                }
                if !selected.contains(&candidate.id) {
                    selected.push(candidate.id);
                }
            }
        }

        selected
    }

    /// Heuristic pruning: reject candidate if a selected neighbor is closer to it
    /// than the node itself (HNSW-style pruning)
    fn use_heuristic_pruning(
        &self,
        selected: &[usize],
        candidate: &Candidate,
        storage: &QuantizedVectorStorage,
        _node_vector: &[i8],
    ) -> bool {
        let candidate_vec = storage.get_vector(candidate.id);

        for &selected_id in selected {
            // Distance from candidate to selected neighbor
            let dist_to_selected = storage.distance_to(&candidate_vec, selected_id);

            // If selected neighbor is closer to candidate than node is, prune
            if dist_to_selected < candidate.distance {
                return true;
            }
        }

        false
    }

    /// Simpler selection without sector diversity (for comparison)
    pub fn select_simple(&self, candidates: &mut Vec<Candidate>) -> Vec<usize> {
        candidates.sort_by_key(|c| c.distance);
        candidates
            .iter()
            .take(self.max_neighbors)
            .map(|c| c.id)
            .collect()
    }
}

/// Count how many sectors are covered by the given neighbors
pub fn count_sector_coverage(
    node_vector: &[i8],
    neighbors: &[usize],
    storage: &QuantizedVectorStorage,
    num_sectors: usize,
) -> usize {
    use std::collections::HashSet;

    let num_sectors_log2 = (num_sectors as f64).log2() as usize;
    let sectors: HashSet<u8> = neighbors
        .iter()
        .map(|&id| {
            let vec = storage.get_vector(id);
            Sector::from_vectors(node_vector, &vec, num_sectors_log2).0
        })
        .collect();

    sectors.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_storage() -> QuantizedVectorStorage {
        let mut storage = QuantizedVectorStorage::new(4, 10);

        // Create vectors in different quadrants
        storage.set_vector(0, &[10, 10, 0, 0]);   // Sector 0b11 (+, +)
        storage.set_vector(1, &[-10, 10, 0, 0]);  // Sector 0b10 (-, +)
        storage.set_vector(2, &[10, -10, 0, 0]);  // Sector 0b01 (+, -)
        storage.set_vector(3, &[-10, -10, 0, 0]); // Sector 0b00 (-, -)
        storage.set_vector(4, &[5, 5, 0, 0]);    // Sector 0b11 (+, +) - closer
        storage.set_vector(5, &[0, 0, 0, 0]);    // Origin

        storage
    }

    #[test]
    fn test_sector_computation() {
        let dir_pp = vec![1i8, 1, 0, 0];
        let dir_pm = vec![1i8, -1, 0, 0];
        let dir_mp = vec![-1i8, 1, 0, 0];
        let dir_mm = vec![-1i8, -1, 0, 0];

        assert_eq!(Sector::from_direction(&dir_pp, 2).0, 0b11);
        assert_eq!(Sector::from_direction(&dir_pm, 2).0, 0b01);
        assert_eq!(Sector::from_direction(&dir_mp, 2).0, 0b10);
        assert_eq!(Sector::from_direction(&dir_mm, 2).0, 0b00);
    }

    #[test]
    fn test_adaptive_selection_diversity() {
        let storage = create_test_storage();
        let selector = AdaptiveNeighborSelector::new(4, 4);

        let node_vec = storage.get_vector(5); // Origin

        let mut candidates: Vec<Candidate> = (0..5)
            .map(|id| {
                let dist = storage.distance_to(&node_vec, id);
                Candidate::new(id, dist, Sector(0))
            })
            .collect();

        let selected = selector.select_neighbors(&node_vec, &mut candidates, &storage);

        // Should select neighbors from different sectors
        let coverage = count_sector_coverage(&node_vec, &selected, &storage, 4);
        assert!(coverage >= 2, "Should have sector diversity, got {}", coverage);
    }

    #[test]
    fn test_sector_coverage_count() {
        let storage = create_test_storage();
        let node_vec = storage.get_vector(5);

        // All from same sector
        let same_sector = vec![0usize, 4]; // Both in (+, +)
        let coverage = count_sector_coverage(&node_vec, &same_sector, &storage, 4);
        assert_eq!(coverage, 1);

        // From different sectors
        let diff_sectors = vec![0usize, 1, 2, 3]; // One from each quadrant
        let coverage = count_sector_coverage(&node_vec, &diff_sectors, &storage, 4);
        assert_eq!(coverage, 4);
    }

    #[test]
    fn test_simple_selection() {
        let selector = AdaptiveNeighborSelector::new(4, 3);

        let mut candidates = vec![
            Candidate::new(0, 100, Sector(0)),
            Candidate::new(1, 50, Sector(0)),
            Candidate::new(2, 75, Sector(0)),
            Candidate::new(3, 25, Sector(0)),
        ];

        let selected = selector.select_simple(&mut candidates);

        assert_eq!(selected.len(), 3);
        assert_eq!(selected[0], 3); // Closest
        assert_eq!(selected[1], 1); // Second closest
        assert_eq!(selected[2], 2); // Third closest
    }
}
