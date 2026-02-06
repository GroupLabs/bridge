// Descartes SIFT1M Benchmark with different rerank factors
// Run with: cargo run --release --bin descartes_sift1m

use core::descartes::{DescartesConfig, DescartesIndex};
use std::collections::HashSet;
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;
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
        let byte_slice = unsafe { std::slice::from_raw_parts_mut(vec.as_mut_ptr() as *mut u8, dim * 4) };
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
        let byte_slice = unsafe { std::slice::from_raw_parts_mut(vec.as_mut_ptr() as *mut u8, k * 4) };
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
    println!("Descartes SIFT1M Benchmark");
    println!("==========================\n");

    let data_dir = Path::new("data");

    println!("Loading SIFT1M data...");
    let (base_vectors, dim) = read_fvecs(&data_dir.join("sift_base.fvecs")).expect("Failed to read base");
    let (query_vectors, _) = read_fvecs(&data_dir.join("sift_query.fvecs")).expect("Failed to read queries");
    let (ground_truth, _) = read_ivecs(&data_dir.join("sift_groundtruth.ivecs")).expect("Failed to read GT");
    println!("  Base: {} × {}D, Queries: {}\n", base_vectors.len(), dim, query_vectors.len());

    let k = 10;
    let num_queries = query_vectors.len().min(10_000);

    // Test configurations: (name, rerank_factor, ef_search)
    // Focus on high ef_search to hit >95% recall
    let configs = vec![
        ("rerank=10x, ef=64", 10, 64),
        ("rerank=10x, ef=128", 10, 128),
        ("rerank=10x, ef=256", 10, 256),
        ("rerank=10x, ef=512", 10, 512),
        ("rerank=30x, ef=256", 30, 256),
        ("rerank=30x, ef=512", 30, 512),
    ];

    println!("Building Descartes index (M=32, efConstruction=200)...");
    let build_start = Instant::now();

    // Build once with base config
    let base_config = DescartesConfig::new(dim)
        .with_m(32)
        .with_ef_construction(200)
        .with_ef_search(64)
        .with_rerank_factor(3);

    let mut index = DescartesIndex::new(base_config);
    let ids: Vec<i64> = (0..base_vectors.len() as i64).collect();
    index.build_with_ids(&base_vectors, &ids);
    println!("  Build time: {:.2}s\n", build_start.elapsed().as_secs_f64());

    println!("{:30} {:>10} {:>12} {:>12}", "Config", "QPS", "Recall@10", "p50 (µs)");
    println!("{}", "-".repeat(70));

    for (name, rerank_factor, ef_search) in configs {
        // Update config for this run
        index.config.rerank_factor = rerank_factor;
        index.config.ef_search = ef_search;

        // Warmup
        for i in 0..100 {
            let _ = index.search(&query_vectors[i], k);
        }

        // Measure QPS
        let start = Instant::now();
        let mut results: Vec<Vec<i64>> = Vec::with_capacity(num_queries);
        for i in 0..num_queries {
            let res = index.search(&query_vectors[i], k);
            results.push(res.iter().map(|r| r.id).collect());
        }
        let elapsed = start.elapsed();
        let qps = num_queries as f64 / elapsed.as_secs_f64();

        // Compute recall
        let mut total_recall = 0.0;
        for i in 0..num_queries {
            total_recall += compute_recall(&ground_truth[i], &results[i], k);
        }
        let recall = total_recall / num_queries as f64;

        // Latency
        let mut latencies: Vec<f64> = Vec::with_capacity(num_queries);
        for i in 0..num_queries {
            let t = Instant::now();
            let _ = index.search(&query_vectors[i], k);
            latencies.push(t.elapsed().as_nanos() as f64 / 1000.0);
        }
        latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let p50 = latencies[(num_queries as f64 * 0.50) as usize];

        println!("{:30} {:>10.0} {:>11.1}% {:>12.1}", name, qps, recall * 100.0, p50);
    }

    println!("\n{}", "=".repeat(70));
}
