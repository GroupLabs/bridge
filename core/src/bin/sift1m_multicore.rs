// SIFT1M Multi-core Benchmark
// Measures QPS and recall with parallel search across N cores
//
// Run with: cargo run --release --bin sift1m_multicore

use core::descartes::{DescartesConfig, DescartesIndex};
use rayon::prelude::*;
use std::collections::HashSet;
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

fn read_fvecs(path: &Path) -> std::io::Result<(Vec<Vec<f32>>, usize)> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let mut dim_buf = [0u8; 4];
    reader.read_exact(&mut dim_buf)?;
    let dim = i32::from_le_bytes(dim_buf) as usize;
    let file_size = std::fs::metadata(path)?.len() as usize;
    let n = file_size / (4 + dim * 4);

    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let mut vectors = Vec::with_capacity(n);
    for _ in 0..n {
        reader.read_exact(&mut dim_buf)?;
        let mut vec = vec![0f32; dim];
        let byte_slice =
            unsafe { std::slice::from_raw_parts_mut(vec.as_mut_ptr() as *mut u8, dim * 4) };
        reader.read_exact(byte_slice)?;
        vectors.push(vec);
    }
    Ok((vectors, dim))
}

fn read_ivecs(path: &Path) -> std::io::Result<(Vec<Vec<i32>>, usize)> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let mut k_buf = [0u8; 4];
    reader.read_exact(&mut k_buf)?;
    let k = i32::from_le_bytes(k_buf) as usize;
    let file_size = std::fs::metadata(path)?.len() as usize;
    let n = file_size / (4 + k * 4);

    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let mut ground_truth = Vec::with_capacity(n);
    for _ in 0..n {
        reader.read_exact(&mut k_buf)?;
        let mut vec = vec![0i32; k];
        let byte_slice =
            unsafe { std::slice::from_raw_parts_mut(vec.as_mut_ptr() as *mut u8, k * 4) };
        reader.read_exact(byte_slice)?;
        ground_truth.push(vec);
    }
    Ok((ground_truth, k))
}

fn compute_recall(gt: &[i32], results: &[i64], k: usize) -> f64 {
    let gt_set: HashSet<i64> = gt.iter().take(k).map(|&x| x as i64).collect();
    let result_set: HashSet<i64> = results.iter().take(k).cloned().collect();
    gt_set.intersection(&result_set).count() as f64 / k as f64
}

fn main() {
    let num_threads = std::env::var("NUM_THREADS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8);

    rayon::ThreadPoolBuilder::new()
        .num_threads(num_threads)
        .build_global()
        .unwrap();

    println!("SIFT1M Multi-core Benchmark");
    println!("===========================");
    println!("Threads: {}\n", num_threads);

    let data_dir = Path::new("data");

    println!("Loading SIFT1M data...");
    let (base_vectors, dim) =
        read_fvecs(&data_dir.join("sift_base.fvecs")).expect("Failed to read base vectors");
    let (query_vectors, _) =
        read_fvecs(&data_dir.join("sift_query.fvecs")).expect("Failed to read query vectors");
    let (ground_truth, _) =
        read_ivecs(&data_dir.join("sift_groundtruth.ivecs")).expect("Failed to read ground truth");

    println!(
        "  Base: {} vectors × {}D",
        base_vectors.len(),
        dim
    );
    println!("  Queries: {}\n", query_vectors.len());

    let k = 10;
    let num_queries = query_vectors.len().min(10_000);

    // Test configurations: (name, rerank_factor, ef_search)
    let configs = vec![
        ("ef=64,  rerank=10x", 10, 64),
        ("ef=128, rerank=10x", 10, 128),
        ("ef=256, rerank=10x", 10, 256),
        ("ef=256, rerank=30x", 30, 256),
        ("ef=512, rerank=30x", 30, 512),
    ];

    println!("Building Descartes index (M=32, efConstruction=200)...");
    let build_start = Instant::now();

    let base_config = DescartesConfig::new(dim)
        .with_m(32)
        .with_ef_construction(200)
        .with_ef_search(64)
        .with_rerank_factor(10);

    let mut index = DescartesIndex::new(base_config);
    let ids: Vec<i64> = (0..base_vectors.len() as i64).collect();
    index.build_with_ids(&base_vectors, &ids);
    let build_time = build_start.elapsed();

    println!("  Build time: {:.2}s", build_time.as_secs_f64());
    println!("  Memory: {:.1} MB\n", index.memory_usage() as f64 / 1e6);

    // Wrap in Arc for thread-safe sharing
    let index = Arc::new(index);

    println!(
        "{:25} {:>12} {:>12} {:>12} {:>12}",
        "Config", "QPS", "QPS/core", "Recall@10", "p50 (µs)"
    );
    println!("{}", "-".repeat(75));

    for (name, rerank_factor, ef_search) in configs {
        // Update config (need to clone Arc and modify)
        let mut index_clone = (*index).clone();
        index_clone.config.rerank_factor = rerank_factor;
        index_clone.config.ef_search = ef_search;
        let index_ref = Arc::new(index_clone);

        // Warmup (single-threaded)
        for i in 0..100 {
            let _ = index_ref.search(&query_vectors[i], k);
        }

        // Parallel search benchmark
        let start = Instant::now();
        let results: Vec<Vec<i64>> = (0..num_queries)
            .into_par_iter()
            .map(|i| {
                let res = index_ref.search(&query_vectors[i], k);
                res.iter().map(|r| r.id).collect()
            })
            .collect();
        let elapsed = start.elapsed();

        let qps = num_queries as f64 / elapsed.as_secs_f64();
        let qps_per_core = qps / num_threads as f64;

        // Compute recall
        let total_recall: f64 = results
            .iter()
            .enumerate()
            .take(num_queries)
            .map(|(i, res)| compute_recall(&ground_truth[i], res, k))
            .sum();
        let recall = total_recall / num_queries as f64;

        // Measure latencies (parallel)
        let latencies: Vec<f64> = (0..num_queries)
            .into_par_iter()
            .map(|i| {
                let t = Instant::now();
                let _ = index_ref.search(&query_vectors[i], k);
                t.elapsed().as_nanos() as f64 / 1000.0
            })
            .collect();

        let mut sorted_latencies = latencies;
        sorted_latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let p50 = sorted_latencies[(num_queries as f64 * 0.50) as usize];

        println!(
            "{:25} {:>12.0} {:>12.0} {:>11.1}% {:>12.1}",
            name,
            qps,
            qps_per_core,
            recall * 100.0,
            p50
        );
    }

    println!("\n{}", "=".repeat(75));
    println!("Summary:");
    println!("  - {} threads on SIFT1M (1M vectors × 128D)", num_threads);
    println!("  - QPS scales ~linearly with cores for read-heavy workloads");
    println!("  - Target: >95% recall with ef=256+ and rerank=30x");
    println!("{}", "=".repeat(75));
}
