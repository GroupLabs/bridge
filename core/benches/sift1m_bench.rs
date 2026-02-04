// Standalone benchmark for Descartes index
// Target: recall@10 >99%, QPS >60k on SIFT1M-like data

use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId, Throughput};
use core::descartes::{DescartesConfig, DescartesIndex};
use rand::Rng;
use std::time::Instant;

/// Generate SIFT-like random vectors (128D, normalized)
fn generate_sift_like_vectors(n: usize) -> Vec<Vec<f32>> {
    let mut rng = rand::thread_rng();
    (0..n)
        .map(|_| {
            let vec: Vec<f32> = (0..128).map(|_| rng.gen::<f32>()).collect();
            // Normalize to unit length (common for SIFT)
            let norm: f32 = vec.iter().map(|x| x * x).sum::<f32>().sqrt();
            vec.iter().map(|x| x / norm).collect()
        })
        .collect()
}

/// Generate clustered vectors for more realistic workload
fn generate_clustered_vectors(n: usize, dim: usize, num_clusters: usize) -> Vec<Vec<f32>> {
    let mut rng = rand::thread_rng();

    let centers: Vec<Vec<f32>> = (0..num_clusters)
        .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
        .collect();

    (0..n)
        .map(|i| {
            let center = &centers[i % num_clusters];
            center
                .iter()
                .map(|&c| c + (rng.gen::<f32>() - 0.5) * 0.2)
                .collect()
        })
        .collect()
}

/// Compute ground truth using brute force
fn compute_ground_truth(vectors: &[Vec<f32>], query: &[f32], k: usize) -> Vec<usize> {
    let mut distances: Vec<(f32, usize)> = vectors
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

    distances.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    distances.iter().take(k).map(|(_, i)| *i).collect()
}

/// Compute recall@k
fn compute_recall(ground_truth: &[usize], results: &[i64], k: usize) -> f64 {
    let gt_set: std::collections::HashSet<usize> = ground_truth.iter().take(k).cloned().collect();
    let result_set: std::collections::HashSet<usize> = results.iter().take(k).map(|&x| x as usize).collect();

    gt_set.intersection(&result_set).count() as f64 / k as f64
}

fn benchmark_build_time(c: &mut Criterion) {
    let mut group = c.benchmark_group("build_time");

    for size in [10_000, 50_000, 100_000].iter() {
        let vectors = generate_sift_like_vectors(*size);

        group.throughput(Throughput::Elements(*size as u64));
        group.bench_with_input(
            BenchmarkId::new("descartes", size),
            size,
            |b, _| {
                b.iter(|| {
                    let config = DescartesConfig::new(128)
                        .with_m(32)
                        .with_ef_construction(200);
                    let mut index = DescartesIndex::new(config);
                    let ids: Vec<i64> = (0..*size as i64).collect();
                    index.build_with_ids(&vectors, &ids);
                    index
                });
            },
        );
    }

    group.finish();
}

fn benchmark_search_throughput(c: &mut Criterion) {
    let mut group = c.benchmark_group("search_throughput");

    // Build index once
    let n = 100_000;
    let vectors = generate_sift_like_vectors(n);

    let config = DescartesConfig::new(128)
        .with_m(32)
        .with_ef_construction(200)
        .with_ef_search(64);

    let mut index = DescartesIndex::new(config);
    let ids: Vec<i64> = (0..n as i64).collect();
    index.build_with_ids(&vectors, &ids);

    // Generate queries
    let queries = generate_sift_like_vectors(1000);

    group.throughput(Throughput::Elements(1000));
    group.bench_function("search_1000_queries", |b| {
        b.iter(|| {
            for query in &queries {
                let _ = index.search(query, 10);
            }
        });
    });

    group.finish();
}

fn benchmark_recall(c: &mut Criterion) {
    let mut group = c.benchmark_group("recall");

    let n = 50_000;
    let vectors = generate_clustered_vectors(n, 128, 100);

    let config = DescartesConfig::new(128)
        .with_m(32)
        .with_ef_construction(200)
        .with_ef_search(128); // Higher ef for better recall

    let mut index = DescartesIndex::new(config);
    let ids: Vec<i64> = (0..n as i64).collect();
    index.build_with_ids(&vectors, &ids);

    // Test queries
    let num_queries = 100;
    let queries: Vec<&Vec<f32>> = vectors.iter().take(num_queries).collect();

    group.bench_function("recall_at_10", |b| {
        b.iter(|| {
            let mut total_recall = 0.0;

            for query in &queries {
                let ground_truth = compute_ground_truth(&vectors, query, 10);
                let results = index.search(query, 10);
                let result_ids: Vec<i64> = results.iter().map(|r| r.id).collect();

                total_recall += compute_recall(&ground_truth, &result_ids, 10);
            }

            total_recall / num_queries as f64
        });
    });

    group.finish();
}

fn measure_metrics() {
    println!("\n=== Descartes Benchmark Metrics ===\n");

    // Dataset sizes to test
    let sizes = [10_000, 50_000, 100_000];

    for &n in &sizes {
        println!("--- {} vectors ---", n);

        let vectors = generate_sift_like_vectors(n);

        // Build
        let build_start = Instant::now();
        let config = DescartesConfig::new(128)
            .with_m(32)
            .with_ef_construction(200)
            .with_ef_search(64);

        let mut index = DescartesIndex::new(config);
        let ids: Vec<i64> = (0..n as i64).collect();
        index.build_with_ids(&vectors, &ids);
        let build_time = build_start.elapsed();

        println!("Build time: {:.2}s", build_time.as_secs_f64());
        println!("Memory usage: {:.2} MB", index.memory_usage() as f64 / 1_000_000.0);

        // Search throughput
        let queries = generate_sift_like_vectors(1000);
        let search_start = Instant::now();
        for query in &queries {
            let _ = index.search(query, 10);
        }
        let search_time = search_start.elapsed();
        let qps = 1000.0 / search_time.as_secs_f64();

        println!("QPS (k=10): {:.0}", qps);

        // Recall
        let mut total_recall = 0.0;
        let num_queries = 100.min(n);

        for i in 0..num_queries {
            let query = &vectors[i];
            let ground_truth = compute_ground_truth(&vectors, query, 10);
            let results = index.search(query, 10);
            let result_ids: Vec<i64> = results.iter().map(|r| r.id).collect();

            total_recall += compute_recall(&ground_truth, &result_ids, 10);
        }

        let avg_recall = total_recall / num_queries as f64;
        println!("Recall@10: {:.2}%", avg_recall * 100.0);

        // Memory comparison
        let float32_size = n * 128 * 4;
        let actual_size = index.memory_usage();
        let compression = float32_size as f64 / actual_size as f64;
        println!("Memory reduction vs float32: {:.2}x", compression);

        println!();
    }

    println!("=== Benchmark Complete ===");
}

criterion_group!(
    benches,
    benchmark_build_time,
    benchmark_search_throughput,
    benchmark_recall,
);

criterion_main!(benches);

// Run metrics measurement when benchmark is invoked
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[ignore] // Run with: cargo test --release -- --ignored
    fn run_metrics() {
        measure_metrics();
    }
}
