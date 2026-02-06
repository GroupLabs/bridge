// Hybrid Search Benchmark - Real FAISS FastScan + SeekStorm
// Measures end-to-end hybrid search QPS with production components
//
// Run with: cargo run --release --bin hybrid_bench
//
// Performance findings (1M docs, k=10):
// - SeekStorm bottleneck: BM25 scoring (Count is 2x faster than Topk)
// - QueryType::Intersection is ~40% faster than Union (fewer docs to score)
// - Async/shard overhead is minimal (2 vs 8 shards ~same performance)
// - segment_number_bits=0 crashes SeekStorm (bug in their single-shard path)

#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(dead_code)]

// Link against FAISS libraries
#[link(name = "faiss_c")]
#[link(name = "faiss")]
#[link(name = "omp")]
extern "C" {}

mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

use bindings::*;
use core::text_index::FastInvertedIndex;
use libc::c_longlong;
use rand::Rng;
use rayon::prelude::*;
use seekstorm::index::{
    create_index, IndexDocuments, IndexMetaObject,
    SimilarityType, StemmerType, StopwordType, FrequentwordType, TokenizerType, AccessType,
    Document, NgramSet,
};
use seekstorm::search::{QueryType, ResultType, Search};
use serde_json::json;
use std::collections::{HashMap, HashSet};
use std::ffi::CString;
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;
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
    /// Create a FastScan IVF-PQ4 index with configurable nprobe
    /// Note: Uses sequential IDs (0..n) for simplicity
    fn create_fastscan(dimension: i32, vectors: &[Vec<f32>], _ids: &[i64], nprobe: usize) -> Result<Self, String> {
        let n = vectors.len();
        let nlist = (n as f64).sqrt().ceil() as i32;
        // For FastScan, M must divide dimension evenly and work well with SIMD
        // Use M=32 for 128D (each subquantizer handles 4 dimensions)
        let m = 32.min(dimension / 4);
        let desc = CString::new(format!("IVF{},PQ{}x4fs", nlist, m)).unwrap();
        Self::create_with_desc(&desc, dimension, vectors, nprobe)
    }

    /// Create FastScan IVF-PQ4 with RefineFlat for high recall + high QPS
    /// Uses index_factory then manually sets nprobe via ParameterSpace
    fn create_fastscan_refine(dimension: i32, vectors: &[Vec<f32>], nprobe: usize, k_factor: f32) -> Result<Self, String> {
        let n = vectors.len();
        let nlist = (n as f64).sqrt().ceil() as i32;
        let m = 32.min(dimension / 4);

        // Create IVF-PQ with RFlat wrapper via index_factory
        let desc = CString::new(format!("IVF{},PQ{}x4fs,RFlat", nlist, m)).unwrap();

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

            // Train
            let train_status = faiss_Index_train(index, n_vectors, flat.as_ptr());
            if train_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to train index".to_string());
            }

            // Add vectors
            let add_status = faiss_Index_add(index, n_vectors, flat.as_ptr());
            if add_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to add vectors".to_string());
            }

            // Set k_factor on RefineFlat wrapper
            let refine = faiss_IndexRefineFlat_cast(index);
            if !refine.is_null() {
                faiss_IndexRefineFlat_set_k_factor(refine, k_factor);
            }

            // Set nprobe via ParameterSpace (works through wrappers)
            let mut ps: *mut bindings::FaissParameterSpace = ptr::null_mut();
            if faiss_ParameterSpace_new(&mut ps) == 0 && !ps.is_null() {
                let nprobe_str = CString::new(format!("nprobe={}", nprobe)).unwrap();
                faiss_ParameterSpace_set_index_parameters(ps, index, nprobe_str.as_ptr());
                faiss_ParameterSpace_free(ps);
            }

            Ok(Self { ptr: index, dimension })
        }
    }

    fn create_with_desc(desc: &CString, dimension: i32, vectors: &[Vec<f32>], nprobe: usize) -> Result<Self, String> {
        let n = vectors.len();

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

            // Flatten vectors
            let flat: Vec<f32> = vectors.iter().flatten().copied().collect();
            let n_vectors = n as c_longlong;

            // Train
            let train_status = faiss_Index_train(index, n_vectors, flat.as_ptr());
            if train_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to train index".to_string());
            }

            // Add vectors (sequential IDs 0..n)
            let add_status = faiss_Index_add(index, n_vectors, flat.as_ptr());
            if add_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to add vectors".to_string());
            }

            // Set nprobe for IVF index (searches more clusters for better recall)
            let ivf = faiss_IndexIVF_cast(index);
            if !ivf.is_null() {
                faiss_IndexIVF_set_nprobe(ivf, nprobe);
            }
        }

        Ok(Self { ptr: index, dimension })
    }

    /// Search for k nearest neighbors
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
// DATA LOADING (SIFT1M format)
// ============================================================================

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

fn read_ivecs(path: &Path) -> std::io::Result<Vec<Vec<i32>>> {
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
    Ok(ground_truth)
}

fn compute_recall(gt: &[i32], results: &[(i64, f32)], k: usize) -> f64 {
    let gt_set: HashSet<i64> = gt.iter().take(k).map(|&x| x as i64).collect();
    let result_set: HashSet<i64> = results.iter().take(k).map(|(id, _)| *id).collect();
    gt_set.intersection(&result_set).count() as f64 / k as f64
}

// ============================================================================
// DATA GENERATION (synthetic)
// ============================================================================

fn generate_random_vectors(n: usize, dim: usize) -> Vec<Vec<f32>> {
    let mut rng = rand::thread_rng();
    (0..n)
        .map(|_| (0..dim).map(|_| rng.gen::<f32>()).collect())
        .collect()
}

fn generate_documents(n: usize) -> Vec<String> {
    let mut rng = rand::thread_rng();
    let vocab: Vec<String> = (0..10_000).map(|i| format!("word{}", i)).collect();

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
// BENCHMARK
// ============================================================================

#[derive(Clone)]
struct BenchConfig {
    n_documents: usize,
    dimension: usize,
    k: usize,
    num_queries: usize,
}

struct BenchResult {
    vector_qps: f64,
    text_qps: f64,
    hybrid_qps: f64,
    hybrid_parallel_qps: f64,
    p50_us: f64,
    p99_us: f64,
    build_time_secs: f64,
    vector_recall: Option<f64>,
    hybrid_recall: Option<f64>,
}

async fn run_benchmark(config: BenchConfig) -> Result<BenchResult, String> {
    let n = config.n_documents;
    let dim = config.dimension;
    let k = config.k;

    println!("Generating {} vectors ({}D)...", n, dim);
    let vectors = generate_random_vectors(n, dim);
    let ids: Vec<i64> = (0..n as i64).collect();

    println!("Generating {} documents...", n);
    let documents = generate_documents(n);

    // Build FAISS FastScan index
    println!("Building FAISS FastScan index (IVF-PQ4)...");
    let build_start = Instant::now();
    let faiss_index = Arc::new(FaissIndex::create_fastscan(dim as i32, &vectors, &ids, 64)?);

    // Build SeekStorm text index
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

    // Shard configuration for SeekStorm
    // Testing results (1M docs, 10k queries):
    //   segment_number_bits=0 (1 shard): CRASHES - SeekStorm bug
    //   segment_number_bits=1 (2 shards): 9,816 text QPS, 8,465 hybrid QPS
    //   segment_number_bits=3 (8 shards): 9,890 text QPS, 8,222 hybrid QPS
    // Conclusion: async/tokio overhead is NOT the bottleneck (2 vs 8 shards ~same perf)
    let num_cores = std::thread::available_parallelism().map(|p| p.get()).unwrap_or(8);
    let segment_number_bits = (num_cores as f64).log2().ceil() as usize;
    let text_index = create_index(&index_path, meta, &schema, &Vec::new(), segment_number_bits, false, None)
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
        text_index.index_documents(docs).await;
    }

    let build_time = build_start.elapsed();
    println!("Build time: {:.2}s", build_time.as_secs_f64());

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

    // Warmup - important for SeekStorm to populate caches
    println!("Warming up...");
    for i in 0..500.min(config.num_queries) {
        let _ = faiss_index.search(&query_vectors[i], k);
        let _ = text_index.search(
            query_texts[i].clone(),
            QueryType::Intersection,
            0, k as usize,
            ResultType::Topk,
            false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
    }

    // Measure vector-only QPS
    println!("Measuring vector-only QPS (FAISS FastScan)...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        let _ = faiss_index.search(&query_vectors[i], k);
    }
    let vector_time = start.elapsed();
    let vector_qps = config.num_queries as f64 / vector_time.as_secs_f64();

    // Measure text-only QPS
    println!("Measuring text-only QPS (SeekStorm BM25)...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        let _ = text_index.search(
            query_texts[i].clone(),
            QueryType::Intersection,  // Intersection is faster (fewer docs to score)
            0, k as usize,
            ResultType::Topk,
            false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
    }
    let text_time = start.elapsed();
    let text_qps = config.num_queries as f64 / text_time.as_secs_f64();

    // Measure hybrid QPS (sequential - baseline)
    println!("Measuring hybrid QPS (sequential)...");
    let start = Instant::now();
    for i in 0..config.num_queries {
        let vector_results = faiss_index.search(&query_vectors[i], k);
        let text_result = text_index.search(
            query_texts[i].clone(),
            QueryType::Intersection,
            0, k as usize,
            ResultType::Topk,
            false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
        let text_results: Vec<(i64, f32)> = text_result.results
            .iter()
            .map(|r| (r.doc_id as i64, r.score))
            .collect();
        let _ = weighted_rrf(&vector_results, &text_results, 0.5, 0.5);
    }
    let hybrid_time = start.elapsed();
    let hybrid_qps = config.num_queries as f64 / hybrid_time.as_secs_f64();

    // Measure hybrid QPS (optimized parallel)
    // True parallelism: spawn FAISS on blocking thread pool, run SeekStorm async
    // spawn_blocking allows FAISS to run on a separate thread while SeekStorm runs async
    println!("Measuring hybrid QPS (optimized parallel)...");
    let mut latencies: Vec<f64> = Vec::with_capacity(config.num_queries);

    let start = Instant::now();
    for i in 0..config.num_queries {
        let query_start = Instant::now();

        // Clone data for spawn_blocking (moves into closure)
        let faiss_clone = Arc::clone(&faiss_index);
        let query_vec = query_vectors[i].clone();
        let k_copy = k;

        // Spawn blocking FAISS search on separate thread
        let vector_handle = tokio::task::spawn_blocking(move || {
            faiss_clone.search(&query_vec, k_copy)
        });

        // Run SeekStorm concurrently (async)
        let text_future = text_index.search(
            query_texts[i].clone(),
            QueryType::Intersection,
            0, k as usize,
            ResultType::Topk,
            false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        );

        // Wait for both to complete in parallel
        let (vector_results, text_result) = tokio::join!(
            async { vector_handle.await.unwrap() },
            text_future
        );

        // RRF rerank
        let text_results: Vec<(i64, f32)> = text_result.results
            .iter()
            .map(|r| (r.doc_id as i64, r.score))
            .collect();

        let _ = weighted_rrf(&vector_results, &text_results, 0.5, 0.5);
        latencies.push(query_start.elapsed().as_micros() as f64);
    }
    let hybrid_parallel_time = start.elapsed();
    let hybrid_parallel_qps = config.num_queries as f64 / hybrid_parallel_time.as_secs_f64();

    // Calculate latency percentiles
    latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50 = latencies.get((latencies.len() as f64 * 0.50) as usize).copied().unwrap_or(0.0);
    let p99 = latencies.get((latencies.len() as f64 * 0.99) as usize).copied().unwrap_or(0.0);

    Ok(BenchResult {
        vector_qps,
        text_qps,
        hybrid_qps,
        hybrid_parallel_qps,
        p50_us: p50,
        p99_us: p99,
        build_time_secs: build_time.as_secs_f64(),
        vector_recall: None,
        hybrid_recall: None,
    })
}

async fn run_sift1m_benchmark(k: usize, num_queries: usize, num_threads: usize) -> Result<BenchResult, String> {
    let data_dir = Path::new("data");

    println!("Loading SIFT1M data...");
    let (base_vectors, dim) = read_fvecs(&data_dir.join("sift_base.fvecs"))
        .map_err(|e| format!("Failed to read sift_base.fvecs: {}", e))?;
    let (query_vectors, _) = read_fvecs(&data_dir.join("sift_query.fvecs"))
        .map_err(|e| format!("Failed to read sift_query.fvecs: {}", e))?;
    let ground_truth = read_ivecs(&data_dir.join("sift_groundtruth.ivecs"))
        .map_err(|e| format!("Failed to read sift_groundtruth.ivecs: {}", e))?;

    let n = base_vectors.len();
    println!("  Base: {} vectors × {}D", n, dim);
    println!("  Queries: {}", query_vectors.len());
    println!("  Threads: {}", num_threads);

    // Generate synthetic text documents (SIFT1M has no text)
    println!("Generating {} synthetic documents...", n);
    let documents = generate_documents(n);

    let ids: Vec<i64> = (0..n as i64).collect();

    // Build FAISS FastScan index
    println!("Building FAISS FastScan index (IVF-PQ4+RFlat)...");
    let build_start = Instant::now();
    // FastScan + RefineFlat: high QPS from PQ, high recall from reranking
    // Balanced tuning: nprobe=64, k_factor=30 for ~8k QPS with >95% recall
    let faiss_index = Arc::new(FaissIndex::create_fastscan_refine(dim as i32, &base_vectors, 64, 30.0)?);

    // Build FastInvertedIndex for sync text search (enables rayon parallelism)
    println!("Building FastInvertedIndex for text search...");
    let fast_text_index = Arc::new(FastInvertedIndex::build_with_ids(&documents, &ids));

    let build_time = build_start.elapsed();
    println!("Build time: {:.2}s", build_time.as_secs_f64());

    // Configure rayon thread pool
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(num_threads)
        .build()
        .map_err(|e| e.to_string())?;

    // Use actual SIFT1M queries
    let num_queries = num_queries.min(query_vectors.len());

    // Generate query texts from synthetic documents
    let query_texts: Vec<String> = (0..num_queries)
        .map(|i| {
            let doc = &documents[i % n];
            doc.split_whitespace().take(3).collect::<Vec<_>>().join(" ")
        })
        .collect();

    // Warmup
    println!("Warming up...");
    for i in 0..500.min(num_queries) {
        let _ = faiss_index.search(&query_vectors[i], k);
        let _ = fast_text_index.search(&query_texts[i], k);
    }

    // Measure vector-only QPS + recall (single-threaded baseline)
    println!("Measuring vector-only QPS (FAISS FastScan, 1 thread)...");
    let mut vector_recalls: Vec<f64> = Vec::with_capacity(num_queries);
    let start = Instant::now();
    for i in 0..num_queries {
        let results = faiss_index.search(&query_vectors[i], k);
        vector_recalls.push(compute_recall(&ground_truth[i], &results, k));
    }
    let vector_time = start.elapsed();
    let vector_qps = num_queries as f64 / vector_time.as_secs_f64();
    let vector_recall = vector_recalls.iter().sum::<f64>() / num_queries as f64;

    // Measure text-only QPS (single-threaded)
    println!("Measuring text-only QPS (FastInvertedIndex, 1 thread)...");
    let start = Instant::now();
    for i in 0..num_queries {
        let _ = fast_text_index.search(&query_texts[i], k);
    }
    let text_time = start.elapsed();
    let text_qps = num_queries as f64 / text_time.as_secs_f64();

    // Measure hybrid QPS (sequential, 1 thread - baseline)
    println!("Measuring hybrid QPS (sequential, 1 thread)...");
    let start = Instant::now();
    for i in 0..num_queries {
        let vector_results = faiss_index.search(&query_vectors[i], k);
        let text_results = fast_text_index.search(&query_texts[i], k);
        let _ = weighted_rrf(&vector_results, &text_results, 0.5, 0.5);
    }
    let hybrid_time = start.elapsed();
    let hybrid_qps = num_queries as f64 / hybrid_time.as_secs_f64();

    // Measure hybrid QPS (multi-core with rayon) + recall
    println!("Measuring hybrid QPS (rayon, {} threads)...", num_threads);

    let start = Instant::now();
    let results: Vec<(f64, f64)> = pool.install(|| {
        (0..num_queries)
            .into_par_iter()
            .map(|i| {
                let query_start = Instant::now();

                // Vector search
                let vector_results = faiss_index.search(&query_vectors[i], k);

                // Text search (sync - no async overhead)
                let text_results = fast_text_index.search(&query_texts[i], k);

                // RRF fusion
                let hybrid_results = weighted_rrf(&vector_results, &text_results, 0.5, 0.5);

                // Compute recall
                let hybrid_result_tuples: Vec<(i64, f32)> = hybrid_results.into_iter().take(k).collect();
                let recall = compute_recall(&ground_truth[i], &hybrid_result_tuples, k);

                let latency = query_start.elapsed().as_micros() as f64;
                (latency, recall)
            })
            .collect()
    });

    let hybrid_parallel_time = start.elapsed();
    let hybrid_parallel_qps = num_queries as f64 / hybrid_parallel_time.as_secs_f64();

    // Extract latencies and recalls from rayon results
    let mut latencies: Vec<f64> = results.iter().map(|(l, _)| *l).collect();
    let hybrid_recalls: Vec<f64> = results.iter().map(|(_, r)| *r).collect();
    let hybrid_recall = hybrid_recalls.iter().sum::<f64>() / num_queries as f64;

    latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50 = latencies.get((latencies.len() as f64 * 0.50) as usize).copied().unwrap_or(0.0);
    let p99 = latencies.get((latencies.len() as f64 * 0.99) as usize).copied().unwrap_or(0.0);

    Ok(BenchResult {
        vector_qps,
        text_qps,
        hybrid_qps,
        hybrid_parallel_qps,
        p50_us: p50,
        p99_us: p99,
        build_time_secs: build_time.as_secs_f64(),
        vector_recall: Some(vector_recall),
        hybrid_recall: Some(hybrid_recall),
    })
}

fn print_results(config: &BenchConfig, result: &BenchResult) {
    println!("\n{}", "=".repeat(70));
    println!("HYBRID SEARCH BENCHMARK - FAISS FastScan + SeekStorm BM25");
    println!("{}", "=".repeat(70));

    println!("\nConfiguration:");
    println!("  Documents:     {:>10}", format_num(config.n_documents));
    println!("  Dimension:     {:>10}D", config.dimension);
    println!("  k:             {:>10}", config.k);
    println!("  Queries:       {:>10}", config.num_queries);

    println!("\nBuild:");
    println!("  Time:          {:>10.2}s", result.build_time_secs);

    println!("\nThroughput (QPS):");
    println!("  Vector-only (FastScan):    {:>10.0}", result.vector_qps);
    println!("  Text-only (SeekStorm):     {:>10.0}", result.text_qps);
    println!("  Hybrid (sequential):       {:>10.0}", result.hybrid_qps);
    println!("  Hybrid (parallel):         {:>10.0}", result.hybrid_parallel_qps);

    if let Some(vr) = result.vector_recall {
        println!("\nRecall@{}:", config.k);
        println!("  Vector-only:   {:>10.1}%", vr * 100.0);
        if let Some(hr) = result.hybrid_recall {
            println!("  Hybrid (RRF):  {:>10.1}%", hr * 100.0);
        }
    }

    println!("\nLatency (parallel hybrid):");
    println!("  p50:           {:>10.1}µs", result.p50_us);
    println!("  p99:           {:>10.1}µs", result.p99_us);

    println!("\n{}", "-".repeat(70));
    println!("Competitive Comparison:");
    println!("{}", "-".repeat(70));
    println!("{:>25} {:>15}", "System", "Hybrid QPS");
    println!("{:-<45}", "");
    println!("{:>25} {:>15}", "Elasticsearch+kNN", "~5-10k");
    println!("{:>25} {:>15}", "Pinecone", "~10-20k");
    println!("{:>25} {:>15}", "Weaviate", "~15-30k");
    println!("{:>25} {:>15}", "Milvus", "~20-40k");
    println!("{:>25} {:>15.0}", "Bridge (measured)", result.hybrid_parallel_qps);
    println!("{}", "=".repeat(70));
}

fn format_num(n: usize) -> String {
    if n >= 1_000_000 { format!("{}M", n / 1_000_000) }
    else if n >= 1_000 { format!("{}K", n / 1_000) }
    else { format!("{}", n) }
}

fn print_sift1m_results(result: &BenchResult, k: usize, num_queries: usize, num_threads: usize) {
    println!("\n{}", "=".repeat(70));
    println!("SIFT1M HYBRID SEARCH BENCHMARK - FAISS FastScan + FastInvertedIndex");
    println!("{}", "=".repeat(70));

    println!("\nConfiguration:");
    println!("  Documents:     {:>10}", "1M (SIFT1M)");
    println!("  Dimension:     {:>10}D", 128);
    println!("  k:             {:>10}", k);
    println!("  Queries:       {:>10}", num_queries);
    println!("  Threads:       {:>10}", num_threads);

    println!("\nBuild:");
    println!("  Time:          {:>10.2}s", result.build_time_secs);

    println!("\nThroughput (QPS):");
    println!("  Vector-only (FastScan, 1T):     {:>10.0}", result.vector_qps);
    println!("  Text-only (FastInverted, 1T):   {:>10.0}", result.text_qps);
    println!("  Hybrid (sequential, 1T):        {:>10.0}", result.hybrid_qps);
    println!("  Hybrid (rayon, {}T):           {:>10.0}", num_threads, result.hybrid_parallel_qps);

    let speedup = result.hybrid_parallel_qps / result.hybrid_qps;
    println!("  Speedup ({}T vs 1T):           {:>10.1}x", num_threads, speedup);

    if let Some(vr) = result.vector_recall {
        println!("\nRecall@{}:", k);
        println!("  Vector-only:   {:>10.1}%", vr * 100.0);
        if let Some(hr) = result.hybrid_recall {
            println!("  Hybrid (RRF):  {:>10.1}%", hr * 100.0);
        }
    }

    println!("\nLatency (per query):");
    println!("  p50:           {:>10.1}µs", result.p50_us);
    println!("  p99:           {:>10.1}µs", result.p99_us);

    println!("{}", "=".repeat(70));
}

#[tokio::main]
async fn main() {
    // Disable OpenMP threading for FAISS (rayon handles parallelism)
    std::env::set_var("OMP_NUM_THREADS", "1");

    let args: Vec<String> = std::env::args().collect();
    let use_sift1m = args.iter().any(|a| a == "--sift1m" || a == "-s");

    // Parse thread count from NUM_THREADS env var or default to available cores
    let num_threads: usize = std::env::var("NUM_THREADS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| std::thread::available_parallelism().map(|p| p.get()).unwrap_or(8));

    println!("Bridge Hybrid Search Benchmark");
    println!("==============================\n");

    if use_sift1m {
        // SIFT1M benchmark with recall
        let k = 10;
        let num_queries = 10_000;

        println!(">>> Running SIFT1M benchmark (threads={}) <<<\n", num_threads);

        match run_sift1m_benchmark(k, num_queries, num_threads).await {
            Ok(result) => print_sift1m_results(&result, k, num_queries, num_threads),
            Err(e) => eprintln!("Benchmark failed: {}", e),
        }
    } else {
        // Synthetic data benchmark
        let configs = vec![
            BenchConfig { n_documents: 1_000_000, dimension: 128, k: 10, num_queries: 10_000 },
        ];

        for config in configs {
            println!("\n>>> Testing {} documents × {}D <<<\n",
                     format_num(config.n_documents), config.dimension);

            match run_benchmark(config.clone()).await {
                Ok(result) => print_results(&config, &result),
                Err(e) => eprintln!("Benchmark failed: {}", e),
            }
        }
    }
}
