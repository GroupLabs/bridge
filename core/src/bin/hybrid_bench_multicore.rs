// Multi-core Hybrid Search Benchmark
// Comprehensive benchmark testing different scales, backends, and thread configurations
//
// Run with: cargo run --release --bin hybrid_bench_multicore
//
// Test matrix:
// - Scales: 100k, 500k, 1M docs
// - Vector backends: FAISS FastScan, Descartes (with SIMD)
// - Text engines: SeekStorm (Union), Fast Inverted Index
// - Core counts: 1, 4, 8

#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(dead_code)]

#[link(name = "faiss_c")]
#[link(name = "faiss")]
#[link(name = "omp")]
extern "C" {}

mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

use bindings::*;
use core::descartes::{DescartesConfig, DescartesIndex};
use core::text_index::FastInvertedIndex;
use libc::c_longlong;
use rand::Rng;
use rayon::prelude::*;
use seekstorm::index::{
    create_index, Document, IndexDocuments, IndexMetaObject,
    AccessType, FrequentwordType, NgramSet, SimilarityType, StemmerType, StopwordType, TokenizerType,
};
use seekstorm::search::{QueryType, ResultType, Search};
use serde_json::json;
use std::collections::HashMap;
use std::ffi::CString;
use std::ptr;
use std::sync::Arc;
use std::time::Instant;

// ============================================================================
// FAISS WRAPPER
// ============================================================================

struct FaissIndex {
    ptr: *mut bindings::FaissIndex,
    dimension: i32,
}

unsafe impl Send for FaissIndex {}
unsafe impl Sync for FaissIndex {}

impl Drop for FaissIndex {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { faiss_Index_free(self.ptr); }
        }
    }
}

impl FaissIndex {
    fn create_fastscan(dimension: i32, vectors: &[Vec<f32>], ids: &[i64]) -> Result<Self, String> {
        let n = vectors.len();
        let nlist = (n as f64).sqrt().ceil() as i32;
        let m = 32.min(dimension / 4);
        let desc = CString::new(format!("IDMap2,IVF{},PQ{}x4fs", nlist, m)).unwrap();

        let mut index: *mut bindings::FaissIndex = ptr::null_mut();
        unsafe {
            let status = faiss_index_factory(
                &mut index,
                dimension,
                desc.as_ptr(),
                FaissMetricType_METRIC_L2,
            );

            if status != 0 {
                let error = faiss_get_last_error();
                let msg = std::ffi::CStr::from_ptr(error).to_string_lossy().to_string();
                return Err(format!("Failed to create index: {}", msg));
            }

            let flat: Vec<f32> = vectors.iter().flatten().copied().collect();
            let n_vectors = n as c_longlong;

            let train_status = faiss_Index_train(index, n_vectors, flat.as_ptr());
            if train_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to train index".to_string());
            }

            let add_status = faiss_Index_add_with_ids(index, n_vectors, flat.as_ptr(), ids.as_ptr());
            if add_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to add vectors".to_string());
            }
        }

        Ok(Self { ptr: index, dimension })
    }

    fn search(&self, query: &[f32], k: usize) -> Vec<(i64, f32)> {
        let mut distances = vec![0.0f32; k];
        let mut labels = vec![-1i64; k];

        unsafe {
            let status = faiss_Index_search(
                self.ptr,
                1,
                query.as_ptr(),
                k as c_longlong,
                distances.as_mut_ptr(),
                labels.as_mut_ptr(),
            );

            if status != 0 {
                return Vec::new();
            }
        }

        labels.into_iter()
            .zip(distances.into_iter())
            .filter(|(id, _)| *id != -1)
            .collect()
    }
}

// ============================================================================
// DATA GENERATION
// ============================================================================

fn generate_random_vectors(n: usize, dim: usize) -> Vec<Vec<f32>> {
    let mut rng = rand::thread_rng();
    (0..n)
        .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
        .collect()
}

fn generate_documents(n: usize, vocab_size: usize) -> Vec<String> {
    let mut rng = rand::thread_rng();
    let vocab: Vec<String> = (0..vocab_size).map(|i| format!("word{}", i)).collect();

    (0..n)
        .map(|_| {
            let num_words = rng.gen_range(20..100);
            (0..num_words)
                .map(|_| vocab[rng.gen_range(0..vocab.len())].clone())
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect()
}

// ============================================================================
// RRF FUSION
// ============================================================================

const RRF_K: f32 = 60.0;

fn weighted_rrf(
    vector_results: &[(i64, f32)],
    text_results: &[(i64, f32)],
    vector_weight: f32,
    text_weight: f32,
) -> Vec<(i64, f32)> {
    let mut scores: HashMap<i64, f32> = HashMap::new();

    for (rank, (id, _)) in vector_results.iter().enumerate() {
        let rrf = vector_weight / (RRF_K + rank as f32);
        *scores.entry(*id).or_insert(0.0) += rrf;
    }

    for (rank, (id, _)) in text_results.iter().enumerate() {
        let rrf = text_weight / (RRF_K + rank as f32);
        *scores.entry(*id).or_insert(0.0) += rrf;
    }

    let mut results: Vec<_> = scores.into_iter().collect();
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    results
}

// ============================================================================
// BENCHMARK CONFIGURATION
// ============================================================================

#[derive(Clone, Copy, Debug)]
enum VectorBackend {
    FaissFastScan,
    Descartes,
}

#[derive(Clone, Copy, Debug)]
enum TextBackend {
    SeekStorm,
    FastInverted,
}

#[derive(Clone)]
struct BenchConfig {
    n_documents: usize,
    dimension: usize,
    k: usize,
    num_queries: usize,
    num_threads: usize,
    vector_backend: VectorBackend,
    text_backend: TextBackend,
}

impl BenchConfig {
    fn label(&self) -> String {
        format!(
            "{}docs_{:?}_{:?}_{}t",
            format_num(self.n_documents),
            self.vector_backend,
            self.text_backend,
            self.num_threads
        )
    }
}

#[derive(Clone)]
struct BenchResult {
    config: BenchConfig,
    vector_qps: f64,
    text_qps: f64,
    hybrid_qps: f64,
    multicore_qps: f64,
    build_time_secs: f64,
    p50_us: f64,
    p99_us: f64,
}

fn format_num(n: usize) -> String {
    if n >= 1_000_000 {
        format!("{}M", n / 1_000_000)
    } else if n >= 1_000 {
        format!("{}k", n / 1_000)
    } else {
        format!("{}", n)
    }
}

// ============================================================================
// BENCHMARK RUNNER
// ============================================================================

async fn run_benchmark(config: BenchConfig) -> Result<BenchResult, String> {
    let n = config.n_documents;
    let dim = config.dimension;
    let k = config.k;

    println!("\n--- {} ---", config.label());
    println!("Generating {} vectors ({}D) and documents...", format_num(n), dim);

    let vectors = generate_random_vectors(n, dim);
    let ids: Vec<i64> = (0..n as i64).collect();
    let documents = generate_documents(n, 10_000);

    // Build vector index
    let build_start = Instant::now();

    let faiss_index: Option<Arc<FaissIndex>> = match config.vector_backend {
        VectorBackend::FaissFastScan => {
            println!("Building FAISS FastScan index...");
            Some(Arc::new(FaissIndex::create_fastscan(dim as i32, &vectors, &ids)?))
        }
        VectorBackend::Descartes => None,
    };

    let descartes_index: Option<Arc<DescartesIndex>> = match config.vector_backend {
        VectorBackend::Descartes => {
            println!("Building Descartes index...");
            let descartes_config = DescartesConfig::new(dim)
                .with_m(32)
                .with_ef_construction(200)
                .with_ef_search(64);
            let mut index = DescartesIndex::new(descartes_config);
            index.build_with_ids(&vectors, &ids);
            Some(Arc::new(index))
        }
        VectorBackend::FaissFastScan => None,
    };

    // Build text index
    let seekstorm_index = match config.text_backend {
        TextBackend::SeekStorm => {
            println!("Building SeekStorm BM25 index...");
            let temp_dir = tempfile::tempdir().map_err(|e| e.to_string())?;
            let index_path = temp_dir.path().to_path_buf();

            let schema_json = r#"[{"field":"body","field_type":"Text","stored":true,"indexed":true}]"#;
            let schema = serde_json::from_str(schema_json).unwrap();

            let meta = IndexMetaObject {
                id: 0,
                name: "bench".into(),
                similarity: SimilarityType::Bm25f,
                tokenizer: TokenizerType::UnicodeAlphanumeric,
                stemmer: StemmerType::None,
                stop_words: StopwordType::None,
                frequent_words: FrequentwordType::None,
                // Mixed bigrams + frequent trigrams for 2x faster phrase queries
                ngram_indexing: NgramSet::NgramFF as u8
                    | NgramSet::NgramFR as u8
                    | NgramSet::NgramRF as u8
                    | NgramSet::NgramFFF as u8,
                access_type: AccessType::Ram,
            };

            // Use 1 shard per CPU core for optimal SeekStorm performance
            let num_cores = std::thread::available_parallelism().map(|p| p.get()).unwrap_or(8);
            let segment_number_bits = (num_cores as f64).log2().ceil() as usize;
            let index = create_index(&index_path, meta, &schema, &Vec::new(), segment_number_bits, false, None)
                .await
                .map_err(|e| format!("Failed to create text index: {}", e))?;

            // Index documents in batches
            let batch_size = 10_000;
            for batch_start in (0..n).step_by(batch_size) {
                let batch_end = (batch_start + batch_size).min(n);
                let docs: Vec<Document> = (batch_start..batch_end)
                    .map(|i| {
                        let mut doc: Document = HashMap::new();
                        doc.insert("body".to_string(), json!(documents[i]));
                        doc
                    })
                    .collect();
                index.index_documents(docs).await;
            }
            // Store temp_dir to keep it alive
            Some((index, temp_dir))
        }
        TextBackend::FastInverted => None,
    };

    let fast_index: Option<Arc<FastInvertedIndex>> = match config.text_backend {
        TextBackend::FastInverted => {
            println!("Building Fast Inverted index...");
            Some(Arc::new(FastInvertedIndex::build_with_ids(&documents, &ids)))
        }
        TextBackend::SeekStorm => None,
    };

    let build_time = build_start.elapsed();
    println!("Build time: {:.2}s", build_time.as_secs_f64());

    // Configure rayon thread pool
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(config.num_threads)
        .build()
        .map_err(|e| e.to_string())?;

    // Generate queries
    let query_vectors: Vec<Vec<f32>> = (0..config.num_queries)
        .map(|i| vectors[i % n].clone())
        .collect();

    let query_texts: Vec<String> = (0..config.num_queries)
        .map(|i| {
            let doc = &documents[i % n];
            doc.split_whitespace().take(3).collect::<Vec<_>>().join(" ")
        })
        .collect();

    // Warmup
    println!("Warming up...");
    for i in 0..100.min(config.num_queries) {
        if let Some(ref faiss) = faiss_index {
            let _ = faiss.search(&query_vectors[i], k);
        }
        if let Some(ref descartes) = descartes_index {
            let _ = descartes.search(&query_vectors[i], k);
        }
        if let Some((ref ss_index, _)) = seekstorm_index {
            let _ = ss_index.search(
                query_texts[i].clone(),
                QueryType::Union,
                0, k,
                ResultType::Topk,
                false,
                Vec::new(), Vec::new(), Vec::new(), Vec::new(),
            ).await;
        }
        if let Some(ref fast_idx) = fast_index {
            let _ = fast_idx.search(&query_texts[i], k);
        }
    }

    // Measure vector-only QPS
    println!("Measuring vector-only QPS...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        if let Some(ref faiss) = faiss_index {
            let _ = faiss.search(&query_vectors[i], k);
        } else if let Some(ref descartes) = descartes_index {
            let _ = descartes.search(&query_vectors[i], k);
        }
    }
    let vector_time = start.elapsed();
    let vector_qps = config.num_queries as f64 / vector_time.as_secs_f64();

    // Measure text-only QPS
    println!("Measuring text-only QPS...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        if let Some((ref ss_index, _)) = seekstorm_index {
            let _ = ss_index.search(
                query_texts[i].clone(),
                QueryType::Union,
                0, k,
                ResultType::Topk,
                false,
                Vec::new(), Vec::new(), Vec::new(), Vec::new(),
            ).await;
        } else if let Some(ref fast_idx) = fast_index {
            let _ = fast_idx.search(&query_texts[i], k);
        }
    }
    let text_time = start.elapsed();
    let text_qps = config.num_queries as f64 / text_time.as_secs_f64();

    // Measure hybrid QPS (sequential, single thread)
    println!("Measuring hybrid QPS (sequential)...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        let vector_results = if let Some(ref faiss) = faiss_index {
            faiss.search(&query_vectors[i], k)
        } else if let Some(ref descartes) = descartes_index {
            descartes.search(&query_vectors[i], k)
                .iter()
                .map(|r| (r.id, r.distance))
                .collect()
        } else {
            vec![]
        };

        let text_results = if let Some((ref ss_index, _)) = seekstorm_index {
            let result = ss_index.search(
                query_texts[i].clone(),
                QueryType::Union,
                0, k,
                ResultType::Topk,
                false,
                Vec::new(), Vec::new(), Vec::new(), Vec::new(),
            ).await;
            result.results.iter().map(|r| (r.doc_id as i64, r.score)).collect()
        } else if let Some(ref fast_idx) = fast_index {
            fast_idx.search(&query_texts[i], k)
        } else {
            vec![]
        };

        let _ = weighted_rrf(&vector_results, &text_results, 0.5, 0.5);
    }
    let hybrid_time = start.elapsed();
    let hybrid_qps = config.num_queries as f64 / hybrid_time.as_secs_f64();

    // Measure multi-core QPS using rayon
    println!("Measuring multi-core QPS ({} threads)...", config.num_threads);
    let mut latencies: Vec<f64> = Vec::with_capacity(config.num_queries);

    // Clone Arc references for parallel iteration
    let faiss_ref = faiss_index.clone();
    let descartes_ref = descartes_index.clone();
    let fast_ref = fast_index.clone();

    let start = Instant::now();

    // For FastInverted, we can use true parallelism with rayon
    if fast_ref.is_some() {
        let results: Vec<f64> = pool.install(|| {
            (0..config.num_queries)
                .into_par_iter()
                .map(|i| {
                    let query_start = Instant::now();

                    let vector_results = if let Some(ref faiss) = faiss_ref {
                        faiss.search(&query_vectors[i], k)
                    } else if let Some(ref descartes) = descartes_ref {
                        descartes.search(&query_vectors[i], k)
                            .iter()
                            .map(|r| (r.id, r.distance))
                            .collect()
                    } else {
                        vec![]
                    };

                    let text_results = if let Some(ref fast_idx) = fast_ref {
                        fast_idx.search(&query_texts[i], k)
                    } else {
                        vec![]
                    };

                    let _ = weighted_rrf(&vector_results, &text_results, 0.5, 0.5);
                    query_start.elapsed().as_micros() as f64
                })
                .collect()
        });
        latencies = results;
    } else {
        // For SeekStorm, we run sequentially since it's async
        for i in 0..config.num_queries {
            let query_start = Instant::now();

            let vector_results = if let Some(ref faiss) = faiss_ref {
                faiss.search(&query_vectors[i], k)
            } else if let Some(ref descartes) = descartes_ref {
                descartes.search(&query_vectors[i], k)
                    .iter()
                    .map(|r| (r.id, r.distance))
                    .collect()
            } else {
                vec![]
            };

            let text_results = if let Some((ref ss_index, _)) = seekstorm_index {
                let result = ss_index.search(
                    query_texts[i].clone(),
                    QueryType::Union,
                    0, k,
                    ResultType::Topk,
                    false,
                    Vec::new(), Vec::new(), Vec::new(), Vec::new(),
                ).await;
                result.results.iter().map(|r| (r.doc_id as i64, r.score)).collect()
            } else {
                vec![]
            };

            let _ = weighted_rrf(&vector_results, &text_results, 0.5, 0.5);
            latencies.push(query_start.elapsed().as_micros() as f64);
        }
    }

    let multicore_time = start.elapsed();
    let multicore_qps = config.num_queries as f64 / multicore_time.as_secs_f64();

    // Calculate latency percentiles
    latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50 = latencies.get((latencies.len() as f64 * 0.50) as usize).copied().unwrap_or(0.0);
    let p99 = latencies.get((latencies.len() as f64 * 0.99) as usize).copied().unwrap_or(0.0);

    Ok(BenchResult {
        config,
        vector_qps,
        text_qps,
        hybrid_qps,
        multicore_qps,
        build_time_secs: build_time.as_secs_f64(),
        p50_us: p50,
        p99_us: p99,
    })
}

fn print_results_table(results: &[BenchResult]) {
    println!("\n{}", "=".repeat(120));
    println!("MULTI-CORE HYBRID SEARCH BENCHMARK RESULTS");
    println!("{}", "=".repeat(120));
    println!(
        "{:<25} {:>12} {:>12} {:>12} {:>12} {:>10} {:>10} {:>10}",
        "Config", "Vector QPS", "Text QPS", "Hybrid QPS", "Multi-core", "Build(s)", "p50(µs)", "p99(µs)"
    );
    println!("{}", "-".repeat(120));

    for result in results {
        println!(
            "{:<25} {:>12.0} {:>12.0} {:>12.0} {:>12.0} {:>10.1} {:>10.0} {:>10.0}",
            result.config.label(),
            result.vector_qps,
            result.text_qps,
            result.hybrid_qps,
            result.multicore_qps,
            result.build_time_secs,
            result.p50_us,
            result.p99_us,
        );
    }
    println!("{}", "=".repeat(120));
}

fn print_summary(results: &[BenchResult]) {
    println!("\n{}", "=".repeat(80));
    println!("SUMMARY");
    println!("{}", "=".repeat(80));

    // Find best configs
    let best_hybrid = results.iter()
        .max_by(|a, b| a.hybrid_qps.partial_cmp(&b.hybrid_qps).unwrap())
        .unwrap();

    let best_multicore = results.iter()
        .max_by(|a, b| a.multicore_qps.partial_cmp(&b.multicore_qps).unwrap())
        .unwrap();

    println!("\nBest single-threaded hybrid: {} @ {:.0} QPS",
             best_hybrid.config.label(), best_hybrid.hybrid_qps);
    println!("Best multi-core hybrid: {} @ {:.0} QPS",
             best_multicore.config.label(), best_multicore.multicore_qps);

    // Calculate speedups
    let baseline_100k = results.iter()
        .find(|r| r.config.n_documents == 100_000
                && matches!(r.config.text_backend, TextBackend::SeekStorm)
                && r.config.num_threads == 1);

    if let Some(baseline) = baseline_100k {
        println!("\nSpeedup vs 100k/SeekStorm/1-thread baseline ({:.0} QPS):", baseline.hybrid_qps);
        for result in results {
            let speedup = result.multicore_qps / baseline.hybrid_qps;
            println!("  {} -> {:.1}x", result.config.label(), speedup);
        }
    }
}

#[tokio::main]
async fn main() {
    println!("Multi-core Hybrid Search Benchmark");
    println!("===================================\n");
    println!("Testing matrix of configurations...\n");

    let mut results = Vec::new();

    // Test matrix - reduced for faster runs, expand as needed
    let scales = [100_000]; // Add 500_000, 1_000_000 for full test
    let thread_counts = [1, 4, 8];

    // Test 1: FastInverted with different thread counts (fastest)
    for &n in &scales {
        for &threads in &thread_counts {
            let config = BenchConfig {
                n_documents: n,
                dimension: 128,
                k: 10,
                num_queries: 1000,
                num_threads: threads,
                vector_backend: VectorBackend::FaissFastScan,
                text_backend: TextBackend::FastInverted,
            };

            match run_benchmark(config.clone()).await {
                Ok(result) => results.push(result),
                Err(e) => eprintln!("Benchmark failed: {}", e),
            }
        }
    }

    // Test 2: SeekStorm baseline with different thread counts
    for &n in &scales {
        for &threads in &[1usize] {  // SeekStorm is async, so threads don't help much
            let config = BenchConfig {
                n_documents: n,
                dimension: 128,
                k: 10,
                num_queries: 1000,
                num_threads: threads,
                vector_backend: VectorBackend::FaissFastScan,
                text_backend: TextBackend::SeekStorm,
            };

            match run_benchmark(config.clone()).await {
                Ok(result) => results.push(result),
                Err(e) => eprintln!("Benchmark failed: {}", e),
            }
        }
    }

    // Test 3: Descartes backend comparison
    for &n in &scales {
        let config = BenchConfig {
            n_documents: n,
            dimension: 128,
            k: 10,
            num_queries: 1000,
            num_threads: 8,
            vector_backend: VectorBackend::Descartes,
            text_backend: TextBackend::FastInverted,
        };

        match run_benchmark(config.clone()).await {
            Ok(result) => results.push(result),
            Err(e) => eprintln!("Benchmark failed: {}", e),
        }
    }

    // Print results
    print_results_table(&results);
    print_summary(&results);

    println!("\nDone!");
}
