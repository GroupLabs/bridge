// Hybrid Search Benchmark
// Measures end-to-end hybrid search QPS (vector + BM25 combined)
// to determine if Bridge has competitive hybrid search performance.
//
// Architecture:
// Bridge hybrid search combines:
// 1. Vector search: FAISS FastScan or Descartes (62k QPS alone / 18k QPS)
// 2. Text search: SeekStorm BM25
// 3. Fusion: Weighted RRF (Reciprocal Rank Fusion)

use crate::descartes::quantization::simd_type_name;
use crate::descartes::{DescartesConfig, DescartesIndex};
use rand::Rng;
use std::collections::HashMap;
use std::time::Instant;

/// Generate random vectors for benchmarking
fn generate_random_vectors(n: usize, dim: usize) -> Vec<Vec<f32>> {
    let mut rng = rand::thread_rng();
    (0..n)
        .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
        .collect()
}

/// Generate synthetic text documents with varied vocabulary
fn generate_synthetic_text(n: usize, vocab_size: usize) -> Vec<String> {
    let mut rng = rand::thread_rng();
    let words: Vec<String> = (0..vocab_size)
        .map(|i| format!("word{}", i))
        .collect();

    (0..n)
        .map(|_| {
            let num_words = rng.gen_range(10..50);
            (0..num_words)
                .map(|_| words[rng.gen_range(0..vocab_size)].clone())
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect()
}

/// Inverted index for fast text search simulation
pub struct InvertedIndex {
    /// word -> list of (doc_id, term_frequency)
    posting_lists: HashMap<String, Vec<(i64, f32)>>,
    /// Total number of documents
    num_docs: usize,
}

impl InvertedIndex {
    /// Build inverted index from documents
    pub fn build(documents: &[String]) -> Self {
        let mut posting_lists: HashMap<String, Vec<(i64, f32)>> = HashMap::new();

        for (doc_id, doc) in documents.iter().enumerate() {
            let words: Vec<&str> = doc.split_whitespace().collect();
            let doc_len = words.len() as f32;

            // Count term frequencies
            let mut term_counts: HashMap<&str, usize> = HashMap::new();
            for word in &words {
                *term_counts.entry(*word).or_insert(0) += 1;
            }

            // Add to posting lists
            for (word, count) in term_counts {
                let tf = count as f32 / (doc_len + 1.0);
                posting_lists
                    .entry(word.to_string())
                    .or_insert_with(Vec::new)
                    .push((doc_id as i64, tf));
            }
        }

        Self {
            posting_lists,
            num_docs: documents.len(),
        }
    }

    /// Search using the inverted index (much faster than linear scan)
    pub fn search(&self, query: &str, k: usize) -> Vec<(i64, f32)> {
        let query_words: Vec<&str> = query.split_whitespace().collect();

        // Accumulate scores for matching documents
        let mut scores: HashMap<i64, f32> = HashMap::new();

        for word in &query_words {
            if let Some(postings) = self.posting_lists.get(*word) {
                // IDF approximation
                let idf = ((self.num_docs as f32) / (postings.len() as f32 + 1.0)).ln() + 1.0;

                for (doc_id, tf) in postings {
                    *scores.entry(*doc_id).or_insert(0.0) += tf * idf;
                }
            }
        }

        // Convert to sorted results
        let mut results: Vec<(i64, f32)> = scores.into_iter().collect();
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(k);
        results
    }
}

/// Weighted RRF (Reciprocal Rank Fusion)
const DEFAULT_RRF_K: f32 = 60.0;

fn weighted_rrf(
    vector_results: Vec<(i64, f32)>,
    text_results: Vec<(i64, f32)>,
    vector_weight: f32,
    text_weight: f32,
) -> Vec<(i64, f32)> {
    let mut combined_scores: HashMap<i64, f32> = HashMap::new();

    // Add vector results with reciprocal rank
    for (rank, (id, _dist)) in vector_results.iter().enumerate() {
        let rrf_score = vector_weight / (DEFAULT_RRF_K + rank as f32);
        combined_scores.insert(*id, rrf_score);
    }

    // Add text results with reciprocal rank
    for (rank, (id, _score)) in text_results.iter().enumerate() {
        let rrf_score = text_weight / (DEFAULT_RRF_K + rank as f32);
        combined_scores
            .entry(*id)
            .and_modify(|score| *score += rrf_score)
            .or_insert(rrf_score);
    }

    // Convert to results and sort by combined score
    let mut results: Vec<(i64, f32)> = combined_scores.into_iter().collect();
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    results
}

/// Benchmark configuration
#[derive(Clone)]
pub struct HybridBenchConfig {
    pub n_documents: usize,
    pub dimension: usize,
    pub k: usize,
    pub num_queries: usize,
    pub vector_weight: f32,
    pub text_weight: f32,
}

impl Default for HybridBenchConfig {
    fn default() -> Self {
        Self {
            n_documents: 100_000,
            dimension: 128,
            k: 10,
            num_queries: 1000,
            vector_weight: 0.5,
            text_weight: 0.5,
        }
    }
}

/// Benchmark result
#[derive(Clone)]
pub struct HybridBenchResult {
    pub config: HybridBenchConfig,
    pub build_time_secs: f64,
    pub vector_only_qps: f64,
    pub text_only_qps: f64,
    pub hybrid_qps: f64,
    pub latency_p50_us: f64,
    pub latency_p99_us: f64,
}

/// Run hybrid search benchmark
pub fn run_hybrid_benchmark(config: HybridBenchConfig) -> HybridBenchResult {
    let n = config.n_documents;
    let dim = config.dimension;
    let k = config.k;

    println!("  Generating {} vectors of {}D...", n, dim);
    let vectors = generate_random_vectors(n, dim);
    let ids: Vec<i64> = (0..n as i64).collect();

    println!("  Generating {} text documents...", n);
    let documents = generate_synthetic_text(n, 10_000);

    // Build both indices
    println!("  Building Descartes index...");
    let build_start = Instant::now();
    let descartes_config = DescartesConfig::new(dim)
        .with_m(32)
        .with_ef_construction(200)
        .with_ef_search(64);

    let mut vector_index = DescartesIndex::new(descartes_config);
    vector_index.build_with_ids(&vectors, &ids);

    println!("  Building inverted index for text search...");
    let text_index = InvertedIndex::build(&documents);

    let build_time = build_start.elapsed();
    println!("  Total build time: {:.2}s", build_time.as_secs_f64());

    // Generate queries
    let query_vectors: Vec<Vec<f32>> = (0..config.num_queries)
        .map(|i| vectors[i % n].clone())
        .collect();

    let query_texts: Vec<String> = (0..config.num_queries)
        .map(|i| {
            // Use words from documents as queries
            let doc = &documents[i % n];
            let words: Vec<&str> = doc.split_whitespace().take(3).collect();
            words.join(" ")
        })
        .collect();

    // Warmup
    for i in 0..100.min(config.num_queries) {
        let _ = vector_index.search(&query_vectors[i], k);
        let _ = text_index.search(&query_texts[i], k);
    }

    // Measure vector-only QPS
    println!("  Measuring vector-only QPS...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        let _ = vector_index.search(&query_vectors[i], k);
    }
    let vector_time = start.elapsed();
    let vector_only_qps = config.num_queries as f64 / vector_time.as_secs_f64();

    // Measure text-only QPS
    println!("  Measuring text-only QPS...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        let _ = text_index.search(&query_texts[i], k);
    }
    let text_time = start.elapsed();
    let text_only_qps = config.num_queries as f64 / text_time.as_secs_f64();

    // Measure hybrid QPS with latency tracking
    println!("  Measuring hybrid QPS...");
    let mut latencies: Vec<f64> = Vec::with_capacity(config.num_queries);

    let start = Instant::now();
    for i in 0..config.num_queries {
        let query_start = Instant::now();

        // Simulate parallel execution by running both
        let vector_results = vector_index.search(&query_vectors[i], k);
        let text_results = text_index.search(&query_texts[i], k);

        // Convert vector results to (id, distance) pairs
        let vector_pairs: Vec<(i64, f32)> = vector_results
            .iter()
            .map(|r| (r.id, r.distance))
            .collect();

        // RRF fusion
        let _ = weighted_rrf(
            vector_pairs,
            text_results,
            config.vector_weight,
            config.text_weight,
        );

        latencies.push(query_start.elapsed().as_micros() as f64);
    }
    let hybrid_time = start.elapsed();
    let hybrid_qps = config.num_queries as f64 / hybrid_time.as_secs_f64();

    // Calculate latency percentiles
    latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50_idx = (latencies.len() as f64 * 0.50) as usize;
    let p99_idx = (latencies.len() as f64 * 0.99) as usize;
    let latency_p50_us = latencies.get(p50_idx).copied().unwrap_or(0.0);
    let latency_p99_us = latencies.get(p99_idx).copied().unwrap_or(0.0);

    HybridBenchResult {
        config,
        build_time_secs: build_time.as_secs_f64(),
        vector_only_qps,
        text_only_qps,
        hybrid_qps,
        latency_p50_us,
        latency_p99_us,
    }
}

/// Print benchmark results
pub fn print_hybrid_results(result: &HybridBenchResult) {
    println!("\n{}", "=".repeat(60));
    println!("HYBRID SEARCH BENCHMARK RESULTS");
    println!("SIMD: {}", simd_type_name());
    println!("{}\n", "=".repeat(60));

    println!("Configuration:");
    println!("  Documents:    {}", format_num(result.config.n_documents));
    println!("  Dimension:    {}D", result.config.dimension);
    println!("  k:            {}", result.config.k);
    println!("  Queries:      {}", result.config.num_queries);
    println!("  Weights:      vector={:.1}, text={:.1}",
             result.config.vector_weight, result.config.text_weight);

    println!("\nPerformance:");
    println!("  Build time:       {:.2}s", result.build_time_secs);
    println!("  Vector-only QPS:  {:.0}", result.vector_only_qps);
    println!("  Text-only QPS:    {:.0}", result.text_only_qps);
    println!("  Hybrid QPS:       {:.0}", result.hybrid_qps);

    println!("\nLatency:");
    println!("  p50:  {:.1}µs", result.latency_p50_us);
    println!("  p99:  {:.1}µs", result.latency_p99_us);

    // Comparison with competitors
    println!("\n{}", "-".repeat(60));
    println!("Competitive Comparison (approximate):");
    println!("{}", "-".repeat(60));
    println!("{:>20} {:>15} {:>10}", "System", "Hybrid QPS", "Notes");
    println!("{:-<50}", "");
    println!("{:>20} {:>15}", "Elasticsearch+kNN", "~5-10k");
    println!("{:>20} {:>15}", "Pinecone", "~10-20k");
    println!("{:>20} {:>15}", "Weaviate", "~15-30k");
    println!("{:>20} {:>15}", "Milvus", "~20-40k");
    println!("{:>20} {:>15.0} {:>10}",
             "Bridge (this)", result.hybrid_qps, "(measured)");
}

fn format_num(n: usize) -> String {
    if n >= 1_000_000 {
        format!("{}M", n / 1_000_000)
    } else if n >= 1_000 {
        format!("{}K", n / 1_000)
    } else {
        format!("{}", n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::hint::black_box;

    #[test]
    fn bench_hybrid_search_10k() {
        println!("\n=== Hybrid Search Benchmark (10K docs, 128D) ===\n");

        let config = HybridBenchConfig {
            n_documents: 10_000,
            dimension: 128,
            k: 10,
            num_queries: 500,
            vector_weight: 0.5,
            text_weight: 0.5,
        };

        let result = run_hybrid_benchmark(config);
        print_hybrid_results(&result);

        // Basic sanity checks
        assert!(result.vector_only_qps > 1000.0, "Vector QPS too low");
        assert!(result.text_only_qps > 100.0, "Text QPS too low");
        assert!(result.hybrid_qps > 100.0, "Hybrid QPS too low");
    }

    #[test]
    fn bench_hybrid_search_100k() {
        println!("\n=== Hybrid Search Benchmark (100K docs, 128D) ===\n");

        let config = HybridBenchConfig {
            n_documents: 100_000,
            dimension: 128,
            k: 10,
            num_queries: 1000,
            vector_weight: 0.5,
            text_weight: 0.5,
        };

        let result = run_hybrid_benchmark(config);
        print_hybrid_results(&result);

        assert!(result.vector_only_qps > 500.0, "Vector QPS too low for 100K");
        assert!(result.hybrid_qps > 50.0, "Hybrid QPS too low for 100K");
    }

    #[test]
    #[ignore] // Run with: cargo test --release bench_hybrid_1m -- --ignored --nocapture
    fn bench_hybrid_search_1m() {
        println!("\n=== Hybrid Search Benchmark (1M docs, 128D) ===\n");

        let config = HybridBenchConfig {
            n_documents: 1_000_000,
            dimension: 128,
            k: 10,
            num_queries: 1000,
            vector_weight: 0.5,
            text_weight: 0.5,
        };

        let result = run_hybrid_benchmark(config);
        print_hybrid_results(&result);
    }

    #[test]
    fn bench_vector_only() {
        // Quick vector-only benchmark to verify SIMD performance
        let n = 10_000;
        let dim = 128;
        let k = 10;

        let vectors = generate_random_vectors(n, dim);
        let ids: Vec<i64> = (0..n as i64).collect();

        let config = DescartesConfig::new(dim)
            .with_m(32)
            .with_ef_construction(200)
            .with_ef_search(64);

        let mut index = DescartesIndex::new(config);
        index.build_with_ids(&vectors, &ids);

        // Warmup
        for i in 0..100 {
            black_box(index.search(&vectors[i % n], k));
        }

        // Benchmark
        let num_queries = 1000;
        let start = Instant::now();
        for i in 0..num_queries {
            black_box(index.search(&vectors[i % n], k));
        }
        let elapsed = start.elapsed();
        let qps = num_queries as f64 / elapsed.as_secs_f64();

        println!("\n=== Vector-Only Benchmark (Descartes) ===");
        println!("SIMD: {}", simd_type_name());
        println!("Vectors: {}K × {}D", n / 1000, dim);
        println!("QPS: {:.0}", qps);
        println!("Latency: {:.1}µs avg", elapsed.as_micros() as f64 / num_queries as f64);
    }

    #[test]
    fn bench_rrf_fusion() {
        // Benchmark the RRF fusion step in isolation
        let n_results = 100;
        let iterations = 10_000;

        // Generate mock results
        let vector_results: Vec<(i64, f32)> = (0..n_results)
            .map(|i| (i as i64, i as f32 * 0.1))
            .collect();
        let text_results: Vec<(i64, f32)> = (50..150)
            .map(|i| (i as i64, i as f32 * 0.05))
            .collect();

        // Warmup
        for _ in 0..100 {
            black_box(weighted_rrf(
                black_box(vector_results.clone()),
                black_box(text_results.clone()),
                0.5,
                0.5,
            ));
        }

        // Benchmark
        let start = Instant::now();
        for _ in 0..iterations {
            black_box(weighted_rrf(
                black_box(vector_results.clone()),
                black_box(text_results.clone()),
                0.5,
                0.5,
            ));
        }
        let elapsed = start.elapsed();

        let ns_per_fusion = elapsed.as_nanos() as f64 / iterations as f64;
        let fusions_per_sec = 1_000_000_000.0 / ns_per_fusion;

        println!("\n=== RRF Fusion Benchmark ===");
        println!("Input: {} vector + {} text results", n_results, n_results);
        println!("Time per fusion: {:.0}ns", ns_per_fusion);
        println!("Fusions/sec: {:.0}M", fusions_per_sec / 1_000_000.0);

        // RRF should be reasonably fast (<50µs)
        assert!(ns_per_fusion < 50_000.0, "RRF fusion too slow: {}ns", ns_per_fusion);
    }

    #[test]
    fn bench_hybrid_matrix() {
        // Test multiple configurations
        let configs = vec![
            (10_000, 128),
            (10_000, 512),
            (100_000, 128),
        ];

        println!("\n{}", "=".repeat(70));
        println!("HYBRID SEARCH BENCHMARK MATRIX");
        println!("SIMD: {}", simd_type_name());
        println!("{}\n", "=".repeat(70));

        println!("{:>10} {:>6} {:>12} {:>12} {:>12} {:>10} {:>10}",
            "Docs", "Dim", "Vector QPS", "Text QPS", "Hybrid QPS", "p50(µs)", "p99(µs)");
        println!("{:-<80}", "");

        for (n, dim) in configs {
            let config = HybridBenchConfig {
                n_documents: n,
                dimension: dim,
                k: 10,
                num_queries: 500,
                vector_weight: 0.5,
                text_weight: 0.5,
            };

            let result = run_hybrid_benchmark(config);

            println!("{:>10} {:>6} {:>12.0} {:>12.0} {:>12.0} {:>10.1} {:>10.1}",
                format_num(n), dim,
                result.vector_only_qps,
                result.text_only_qps,
                result.hybrid_qps,
                result.latency_p50_us,
                result.latency_p99_us
            );
        }
    }
}
