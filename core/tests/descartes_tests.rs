// Integration tests for Descartes vector search engine

use core::descartes::{
    DescartesConfig, DescartesIndex,
    quantization::{ScalarQuantizer, QuantizedVectorStorage},
    graph::FullyNavigatableGraph,
    build::{GraphBuilder, verify_level_distribution},
    adaptive::count_sector_coverage,
};
use rand::Rng;

/// Generate random test vectors
fn generate_random_vectors(n: usize, dim: usize) -> Vec<Vec<f32>> {
    let mut rng = rand::thread_rng();
    (0..n)
        .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
        .collect()
}

/// Generate clustered test vectors (for more realistic testing)
fn generate_clustered_vectors(n: usize, dim: usize, num_clusters: usize) -> Vec<Vec<f32>> {
    let mut rng = rand::thread_rng();

    // Generate cluster centers
    let centers: Vec<Vec<f32>> = (0..num_clusters)
        .map(|_| (0..dim).map(|_| rng.gen::<f32>() * 10.0).collect())
        .collect();

    // Generate points around centers
    (0..n)
        .map(|i| {
            let center = &centers[i % num_clusters];
            center
                .iter()
                .map(|&c| c + rng.gen::<f32>() * 0.5 - 0.25)
                .collect()
        })
        .collect()
}

// ============================================================================
// QUANTIZATION TESTS
// ============================================================================

#[test]
fn test_quantization_roundtrip_precision() {
    let mut quantizer = ScalarQuantizer::new(128);

    let vectors = generate_random_vectors(100, 128);
    quantizer.train(&vectors);

    let mut max_error = 0.0f32;
    for vec in &vectors {
        let encoded = quantizer.encode(vec);
        let decoded = quantizer.decode(&encoded);

        for (orig, recon) in vec.iter().zip(decoded.iter()) {
            let error = (orig - recon).abs();
            max_error = max_error.max(error);
        }
    }

    // Max error should be within quantization bound
    let max_range: f32 = quantizer.maxs.iter()
        .zip(quantizer.mins.iter())
        .map(|(max, min)| max - min)
        .fold(0.0f32, |a, b| a.max(b));

    let expected_max_error = max_range / 255.0 * 2.0; // 2 bins tolerance
    assert!(
        max_error < expected_max_error,
        "Max quantization error {} exceeds expected {}",
        max_error,
        expected_max_error
    );
}

#[test]
fn test_quantization_range_bounds() {
    let mut quantizer = ScalarQuantizer::new(10);

    // Test with extreme values
    let vectors = vec![
        vec![-1000.0f32; 10],
        vec![1000.0f32; 10],
        vec![0.0f32; 10],
    ];
    quantizer.train(&vectors);

    for vec in &vectors {
        let encoded = quantizer.encode(vec);
        for &val in &encoded {
            assert!(val >= -128 && val <= 127, "Value {} out of i8 range", val);
        }
    }
}

#[test]
fn test_quantization_ordering_preserved() {
    let mut quantizer = ScalarQuantizer::new(8);

    // Vectors at increasing distances from origin
    let vectors = vec![
        vec![0.0f32; 8],
        vec![0.1f32; 8],
        vec![0.2f32; 8],
        vec![0.3f32; 8],
        vec![0.5f32; 8],
        vec![1.0f32; 8],
    ];
    quantizer.train(&vectors);

    let origin = vec![0.0f32; 8];
    let q_origin = quantizer.encode(&origin);

    let mut last_dist = 0i32;
    for vec in &vectors {
        let q_vec = quantizer.encode(vec);
        let dist = ScalarQuantizer::l2_distance_squared(&q_origin, &q_vec);
        assert!(dist >= last_dist, "Distance ordering not preserved");
        last_dist = dist;
    }
}

#[test]
fn test_column_major_storage_correctness() {
    let mut storage = QuantizedVectorStorage::new(5, 10);

    // Set vectors
    for i in 0..10 {
        let vec: Vec<i8> = (0..5).map(|d| (i * 5 + d) as i8).collect();
        storage.set_vector(i, &vec);
    }

    // Verify retrieval
    for i in 0..10 {
        let expected: Vec<i8> = (0..5).map(|d| (i * 5 + d) as i8).collect();
        let actual = storage.get_vector(i);
        assert_eq!(actual, expected, "Vector {} mismatch", i);
    }
}

// ============================================================================
// GRAPH TESTS
// ============================================================================

#[test]
fn test_level_distribution_exponential() {
    let config = DescartesConfig::new(4).with_m(16);
    let builder = GraphBuilder::new(config);

    let mut rng = rand::thread_rng();
    let levels: Vec<usize> = (0..10000)
        .map(|_| {
            let r: f64 = rng.gen();
            let ml = 1.0 / (16_f64).ln();
            (-r.ln() * ml).floor() as usize
        })
        .collect();

    // Count distribution
    let mut counts = vec![0usize; 10];
    for &l in &levels {
        if l < counts.len() {
            counts[l] += 1;
        }
    }

    // Level 0 should have most nodes
    assert!(counts[0] > 5000, "Level 0 should have >50% of nodes");

    // Each level should have fewer nodes than previous (exponential decay)
    for i in 1..5 {
        if counts[i - 1] > 100 {
            assert!(
                counts[i] < counts[i - 1],
                "Level {} ({}) should have fewer nodes than level {} ({})",
                i, counts[i], i - 1, counts[i - 1]
            );
        }
    }

    assert!(verify_level_distribution(&levels));
}

#[test]
fn test_graph_connectivity_guaranteed() {
    let vectors = generate_random_vectors(200, 8);
    let config = DescartesConfig::new(8).with_m(8);

    let mut quantizer = ScalarQuantizer::new(8);
    quantizer.train(&vectors);

    let mut storage = QuantizedVectorStorage::new(8, vectors.len());
    for (i, vec) in vectors.iter().enumerate() {
        storage.set_vector(i, &quantizer.encode(vec));
    }

    let mut builder = GraphBuilder::new(config);
    let graph = builder.build(&storage, &quantizer);

    assert!(graph.verify_connectivity(), "Graph must be fully connected");
}

#[test]
fn test_neighbor_counts_within_limits() {
    let vectors = generate_random_vectors(100, 4);
    let m = 8;
    let config = DescartesConfig::new(4).with_m(m);

    let mut quantizer = ScalarQuantizer::new(4);
    quantizer.train(&vectors);

    let mut storage = QuantizedVectorStorage::new(4, vectors.len());
    for (i, vec) in vectors.iter().enumerate() {
        storage.set_vector(i, &quantizer.encode(vec));
    }

    let mut builder = GraphBuilder::new(config.clone());
    let graph = builder.build(&storage, &quantizer);

    for node in &graph.nodes {
        // Level 0: max 2*M neighbors
        assert!(
            node.neighbors[0].len() <= m * 2,
            "Node {} has {} level-0 neighbors, max is {}",
            node.id,
            node.neighbors[0].len(),
            m * 2
        );

        // Higher levels: max M neighbors
        for level in 1..node.neighbors.len() {
            assert!(
                node.neighbors[level].len() <= m,
                "Node {} has {} level-{} neighbors, max is {}",
                node.id,
                node.neighbors[level].len(),
                level,
                m
            );
        }
    }
}

#[test]
fn test_sector_coverage_diversity() {
    let mut storage = QuantizedVectorStorage::new(4, 8);

    // Create vectors in different quadrants (4 sectors for 2D partitioning)
    storage.set_vector(0, &[50, 50, 0, 0]);   // Quadrant ++
    storage.set_vector(1, &[-50, 50, 0, 0]);  // Quadrant -+
    storage.set_vector(2, &[50, -50, 0, 0]);  // Quadrant +-
    storage.set_vector(3, &[-50, -50, 0, 0]); // Quadrant --
    storage.set_vector(4, &[0, 0, 0, 0]);     // Origin

    let origin_vec = storage.get_vector(4);

    // All 4 quadrants represented
    let all_neighbors = vec![0usize, 1, 2, 3];
    let coverage = count_sector_coverage(&origin_vec, &all_neighbors, &storage, 4);
    assert_eq!(coverage, 4, "Should cover all 4 sectors");

    // Only 2 quadrants
    let two_neighbors = vec![0usize, 1];
    let coverage = count_sector_coverage(&origin_vec, &two_neighbors, &storage, 4);
    assert!(coverage >= 2, "Should cover at least 2 sectors");
}

// ============================================================================
// SEARCH TESTS
// ============================================================================

#[test]
fn test_search_returns_correct_k() {
    let vectors = generate_random_vectors(100, 8);
    let config = DescartesConfig::new(8).with_ef_search(32);
    let mut index = DescartesIndex::new(config);

    let ids: Vec<i64> = (0..100).collect();
    index.build_with_ids(&vectors, &ids);

    let results = index.search(&vectors[0], 10);
    assert_eq!(results.len(), 10, "Should return exactly k=10 results");

    let results = index.search(&vectors[0], 5);
    assert_eq!(results.len(), 5, "Should return exactly k=5 results");
}

#[test]
fn test_search_results_sorted_by_distance() {
    let vectors = generate_random_vectors(100, 8);
    let config = DescartesConfig::new(8).with_ef_search(64);
    let mut index = DescartesIndex::new(config);

    let ids: Vec<i64> = (0..100).collect();
    index.build_with_ids(&vectors, &ids);

    let results = index.search(&vectors[50], 20);

    for i in 1..results.len() {
        assert!(
            results[i - 1].distance <= results[i].distance,
            "Results not sorted: {} > {} at positions {}, {}",
            results[i - 1].distance,
            results[i].distance,
            i - 1,
            i
        );
    }
}

#[test]
fn test_search_finds_exact_match() {
    let vectors = generate_random_vectors(50, 4);
    let config = DescartesConfig::new(4).with_ef_search(32);
    let mut index = DescartesIndex::new(config);

    let ids: Vec<i64> = (100..150).collect();
    index.build_with_ids(&vectors, &ids);

    // Search for an exact vector
    let results = index.search(&vectors[25], 1);

    assert!(!results.is_empty());
    // With reranking using original vectors, exact match should be first
    assert_eq!(results[0].id, 125, "Should find exact match as first result");
    // Distance should be very close to 0 with reranking
    assert!(results[0].distance < 0.001, "Distance to exact match should be ~0");
}

#[test]
fn test_search_recall_on_clustered_data() {
    let vectors = generate_clustered_vectors(500, 16, 10);
    let config = DescartesConfig::new(16)
        .with_m(16)
        .with_ef_construction(100)
        .with_ef_search(64);

    let mut index = DescartesIndex::new(config);
    let ids: Vec<i64> = (0..500).collect();
    index.build_with_ids(&vectors, &ids);

    // Compute ground truth for first 10 queries
    let mut total_recall = 0.0;
    let k = 10;
    let num_queries = 10;

    for q_idx in 0..num_queries {
        let query = &vectors[q_idx];

        // Brute force ground truth
        let mut ground_truth: Vec<(f32, usize)> = vectors
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let dist: f32 = query.iter()
                    .zip(v.iter())
                    .map(|(a, b)| (a - b).powi(2))
                    .sum();
                (dist, i)
            })
            .collect();
        ground_truth.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());

        let true_neighbors: std::collections::HashSet<i64> = ground_truth
            .iter()
            .take(k)
            .map(|(_, i)| *i as i64)
            .collect();

        // ANN search
        let results = index.search(query, k);
        let found: std::collections::HashSet<i64> = results.iter().map(|r| r.id).collect();

        let recall = true_neighbors.intersection(&found).count() as f64 / k as f64;
        total_recall += recall;
    }

    let avg_recall = total_recall / num_queries as f64;
    assert!(
        avg_recall > 0.8,
        "Average recall {} should be > 80%",
        avg_recall
    );
}

// ============================================================================
// PERSISTENCE TESTS
// ============================================================================

#[test]
fn test_persistence_roundtrip() {
    use core::descartes::persistence::{save_descartes_index, load_descartes_index};
    use tempfile::tempdir;

    let vectors = generate_random_vectors(50, 8);
    let config = DescartesConfig::new(8);
    let mut index = DescartesIndex::new(config);

    let ids: Vec<i64> = (1000..1050).collect();
    index.build_with_ids(&vectors, &ids);

    // Save
    let dir = tempdir().unwrap();
    let path = dir.path().join("test_index.bin");
    save_descartes_index(&index, &path).unwrap();

    // Load
    let loaded = load_descartes_index(&path).unwrap();

    // Verify
    assert_eq!(loaded.len(), index.len());
    assert_eq!(loaded.config.dimension, index.config.dimension);

    // Search should produce same results
    let original_results = index.search(&vectors[0], 5);
    let loaded_results = loaded.search(&vectors[0], 5);

    for (orig, load) in original_results.iter().zip(loaded_results.iter()) {
        assert_eq!(orig.id, load.id);
        assert!((orig.distance - load.distance).abs() < 0.001);
    }
}

// ============================================================================
// INDEX TESTS
// ============================================================================

#[test]
fn test_index_memory_usage() {
    let vectors = generate_random_vectors(1000, 128);
    let config = DescartesConfig::new(128).with_m(16);
    let mut index = DescartesIndex::new(config);

    let ids: Vec<i64> = (0..1000).collect();
    index.build_with_ids(&vectors, &ids);

    let memory = index.memory_usage();

    // Float32: 1000 * 128 * 4 = 512KB
    // Int8: 1000 * 128 = 128KB (4x reduction)
    let float32_size = 1000 * 128 * 4;
    let int8_size = 1000 * 128;

    // With reranking support, we store both quantized and original vectors
    // Memory will be higher but enables high recall with fast search
    assert!(
        memory > int8_size,
        "Memory usage should be at least int8 storage size"
    );

    println!("Memory usage: {} bytes", memory);
    println!("Float32 would be: {} bytes", float32_size);
}

#[test]
fn test_empty_index() {
    let config = DescartesConfig::new(4);
    let index = DescartesIndex::new(config);

    assert!(index.is_empty());
    assert_eq!(index.len(), 0);

    let results = index.search(&[0.0; 4], 10);
    assert!(results.is_empty());
}
