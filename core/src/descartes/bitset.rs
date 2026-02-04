// Fast bit vector for visited node tracking
// Replaces HashSet for O(1) insert/lookup with minimal memory

/// A fixed-size bit set for fast visited tracking
/// Uses 1 bit per element vs ~40+ bytes per entry in HashSet
#[derive(Debug, Clone)]
pub struct BitSet {
    bits: Vec<u64>,
    size: usize,
}

impl BitSet {
    /// Create a new BitSet with capacity for `size` elements
    #[inline]
    pub fn new(size: usize) -> Self {
        let num_words = (size + 63) / 64;
        Self {
            bits: vec![0u64; num_words],
            size,
        }
    }

    /// Insert an element, returns true if it was not already present
    #[inline]
    pub fn insert(&mut self, idx: usize) -> bool {
        debug_assert!(idx < self.size, "BitSet index out of bounds: {} >= {}", idx, self.size);
        let word = idx / 64;
        let bit = 1u64 << (idx % 64);
        let was_set = self.bits[word] & bit != 0;
        self.bits[word] |= bit;
        !was_set
    }

    /// Check if an element is present
    #[inline]
    pub fn contains(&self, idx: usize) -> bool {
        if idx >= self.size {
            return false;
        }
        let word = idx / 64;
        let bit = 1u64 << (idx % 64);
        self.bits[word] & bit != 0
    }

    /// Clear all bits (reuse allocation)
    #[inline]
    pub fn clear(&mut self) {
        for word in &mut self.bits {
            *word = 0;
        }
    }

    /// Get the capacity (number of bits)
    #[inline]
    pub fn capacity(&self) -> usize {
        self.size
    }

    /// Count the number of set bits
    pub fn count(&self) -> usize {
        self.bits.iter().map(|w| w.count_ones() as usize).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bitset_basic() {
        let mut bs = BitSet::new(100);

        assert!(!bs.contains(0));
        assert!(!bs.contains(50));
        assert!(!bs.contains(99));

        assert!(bs.insert(0));   // New insert returns true
        assert!(!bs.insert(0));  // Duplicate returns false

        assert!(bs.contains(0));
        assert!(!bs.contains(1));
    }

    #[test]
    fn test_bitset_boundaries() {
        let mut bs = BitSet::new(128);

        // Test at word boundaries
        assert!(bs.insert(63));
        assert!(bs.insert(64));
        assert!(bs.insert(127));

        assert!(bs.contains(63));
        assert!(bs.contains(64));
        assert!(bs.contains(127));
        assert!(!bs.contains(62));
        assert!(!bs.contains(65));
    }

    #[test]
    fn test_bitset_clear() {
        let mut bs = BitSet::new(100);

        bs.insert(10);
        bs.insert(50);
        bs.insert(90);

        assert_eq!(bs.count(), 3);

        bs.clear();

        assert_eq!(bs.count(), 0);
        assert!(!bs.contains(10));
        assert!(!bs.contains(50));
        assert!(!bs.contains(90));
    }

    #[test]
    fn test_bitset_large() {
        let mut bs = BitSet::new(10_000);

        for i in (0..10_000).step_by(100) {
            bs.insert(i);
        }

        assert_eq!(bs.count(), 100);

        for i in (0..10_000).step_by(100) {
            assert!(bs.contains(i));
        }

        for i in (1..10_000).step_by(100) {
            assert!(!bs.contains(i));
        }
    }
}
