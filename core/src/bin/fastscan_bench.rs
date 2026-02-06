// FAISS SIFT1M Benchmark - Comparing Index Types
// Run with: cargo run --release --bin fastscan_bench

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
use libc::c_longlong;
use std::ffi::CString;
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;
use std::ptr;
use std::time::Instant;

struct FaissIndex {
    ptr: *mut bindings::FaissIndex,
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
    fn create(desc: &str, dimension: i32, vectors: &[f32], n: usize, nprobe: usize) -> Result<Self, String> {
        let desc_cstr = CString::new(desc).unwrap();

        let mut index: *mut bindings::FaissIndex = ptr::null_mut();
        unsafe {
            let status = faiss_index_factory(
                &mut index,
                dimension,
                desc_cstr.as_ptr(),
                FaissMetricType_METRIC_L2,
            );

            if status != 0 {
                let error = faiss_get_last_error();
                let msg = std::ffi::CStr::from_ptr(error).to_string_lossy().to_string();
                return Err(format!("Failed to create index: {}", msg));
            }

            let n_vectors = n as c_longlong;

            let train_status = faiss_Index_train(index, n_vectors, vectors.as_ptr());
            if train_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to train index".to_string());
            }

            let add_status = faiss_Index_add(index, n_vectors, vectors.as_ptr());
            if add_status != 0 {
                faiss_Index_free(index);
                return Err("Failed to add vectors".to_string());
            }

            // Set nprobe on IVF indices
            let ivf = faiss_IndexIVF_cast(index);
            if !ivf.is_null() {
                faiss_IndexIVF_set_nprobe(ivf, nprobe);
            }
        }

        Ok(Self { ptr: index })
    }

    fn search(&self, query: &[f32], k: usize) -> Vec<(i64, f32)> {
        let mut distances = vec![0.0f32; k];
        let mut labels = vec![-1i64; k];

        unsafe {
            faiss_Index_search(
                self.ptr,
                1,
                query.as_ptr(),
                k as c_longlong,
                distances.as_mut_ptr(),
                labels.as_mut_ptr(),
            );
        }

        labels.into_iter()
            .zip(distances.into_iter())
            .filter(|(id, _)| *id != -1)
            .collect()
    }
}

fn read_fvecs(path: &Path) -> std::io::Result<(Vec<f32>, usize, usize)> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);

    let mut dim_buf = [0u8; 4];
    reader.read_exact(&mut dim_buf)?;
    let dim = i32::from_le_bytes(dim_buf) as usize;

    let file_size = std::fs::metadata(path)?.len() as usize;
    let vector_size = 4 + dim * 4;
    let n = file_size / vector_size;

    let mut data = vec![0f32; n * dim];
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);

    for i in 0..n {
        let mut dim_buf = [0u8; 4];
        reader.read_exact(&mut dim_buf)?;

        let start = i * dim;
        let slice = &mut data[start..start + dim];
        let byte_slice = unsafe {
            std::slice::from_raw_parts_mut(slice.as_mut_ptr() as *mut u8, dim * 4)
        };
        reader.read_exact(byte_slice)?;
    }

    Ok((data, n, dim))
}

fn read_ivecs(path: &Path) -> std::io::Result<(Vec<i32>, usize, usize)> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);

    let mut k_buf = [0u8; 4];
    reader.read_exact(&mut k_buf)?;
    let k = i32::from_le_bytes(k_buf) as usize;

    let file_size = std::fs::metadata(path)?.len() as usize;
    let vector_size = 4 + k * 4;
    let n = file_size / vector_size;

    let mut data = vec![0i32; n * k];
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);

    for i in 0..n {
        let mut k_buf = [0u8; 4];
        reader.read_exact(&mut k_buf)?;

        let start = i * k;
        let slice = &mut data[start..start + k];
        let byte_slice = unsafe {
            std::slice::from_raw_parts_mut(slice.as_mut_ptr() as *mut u8, k * 4)
        };
        reader.read_exact(byte_slice)?;
    }

    Ok((data, n, k))
}

fn compute_recall(ground_truth: &[i32], results: &[(i64, f32)], k: usize) -> f64 {
    let gt_set: std::collections::HashSet<i64> = ground_truth.iter().take(k).map(|&x| x as i64).collect();
    let result_set: std::collections::HashSet<i64> = results.iter().take(k).map(|(id, _)| *id).collect();
    gt_set.intersection(&result_set).count() as f64 / k as f64
}

struct BenchResult {
    name: String,
    build_time: f64,
    qps: f64,
    recall: f64,
    p50_us: f64,
    p99_us: f64,
}

fn benchmark_index(
    name: &str,
    desc: &str,
    dimension: i32,
    base_vectors: &[f32],
    n_base: usize,
    query_vectors: &[f32],
    ground_truth: &[i32],
    gt_k: usize,
    k: usize,
    nprobe: usize,
    num_queries: usize,
) -> Result<BenchResult, String> {
    println!("  Building {}...", name);
    let build_start = Instant::now();
    let index = FaissIndex::create(desc, dimension, base_vectors, n_base, nprobe)?;
    let build_time = build_start.elapsed().as_secs_f64();

    // Warmup
    for i in 0..100.min(num_queries) {
        let query = &query_vectors[i * dimension as usize..(i + 1) * dimension as usize];
        let _ = index.search(query, k);
    }

    // QPS
    let search_start = Instant::now();
    let mut results: Vec<Vec<(i64, f32)>> = Vec::with_capacity(num_queries);
    for i in 0..num_queries {
        let query = &query_vectors[i * dimension as usize..(i + 1) * dimension as usize];
        results.push(index.search(query, k));
    }
    let search_time = search_start.elapsed();
    let qps = num_queries as f64 / search_time.as_secs_f64();

    // Recall
    let mut total_recall = 0.0;
    for i in 0..num_queries {
        let gt = &ground_truth[i * gt_k..(i + 1) * gt_k];
        total_recall += compute_recall(gt, &results[i], k);
    }
    let recall = total_recall / num_queries as f64;

    // Latency
    let mut latencies: Vec<f64> = Vec::with_capacity(num_queries);
    for i in 0..num_queries {
        let query = &query_vectors[i * dimension as usize..(i + 1) * dimension as usize];
        let start = Instant::now();
        let _ = index.search(query, k);
        latencies.push(start.elapsed().as_nanos() as f64 / 1000.0);
    }
    latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50 = latencies[(num_queries as f64 * 0.50) as usize];
    let p99 = latencies[(num_queries as f64 * 0.99) as usize];

    Ok(BenchResult {
        name: name.to_string(),
        build_time,
        qps,
        recall,
        p50_us: p50,
        p99_us: p99,
    })
}

fn main() {
    std::env::set_var("OMP_NUM_THREADS", "1");

    println!("FAISS SIFT1M Benchmark Comparison");
    println!("==================================\n");

    let data_dir = Path::new("data");

    // Load data
    println!("Loading SIFT1M data...");
    let (base_vectors, n_base, dim) = read_fvecs(&data_dir.join("sift_base.fvecs"))
        .expect("Failed to read sift_base.fvecs");
    let (query_vectors, n_queries, _) = read_fvecs(&data_dir.join("sift_query.fvecs"))
        .expect("Failed to read sift_query.fvecs");
    let (ground_truth, _, gt_k) = read_ivecs(&data_dir.join("sift_groundtruth.ivecs"))
        .expect("Failed to read sift_groundtruth.ivecs");
    println!("  Base: {} × {}D, Queries: {}\n", n_base, dim, n_queries);

    let k = 10;
    let num_queries = 10_000;
    let nlist = (n_base as f64).sqrt().ceil() as i32;

    // Index configurations - FastScan with reranking
    let configs = vec![
        ("IVF-PQ4fs (nprobe=32)", format!("IVF{},PQ32x4fs", nlist), 32),
        // Refine = rerank with original vectors stored in IndexFlat
        ("IVF-PQ4fs+Refine (nprobe=32)", format!("IVF{},PQ32x4fs,RFlat", nlist), 32),
        ("IVF-PQ4fs+Refine (nprobe=64)", format!("IVF{},PQ32x4fs,RFlat", nlist), 64),
        ("IVF-Flat (nprobe=32)", format!("IVF{},Flat", nlist), 32),
    ];

    println!("Running benchmarks...\n");
    let mut results: Vec<BenchResult> = Vec::new();

    for (name, desc, nprobe) in configs {
        match benchmark_index(
            name,
            &desc,
            dim as i32,
            &base_vectors,
            n_base,
            &query_vectors,
            &ground_truth,
            gt_k,
            k,
            nprobe,
            num_queries,
        ) {
            Ok(result) => {
                println!("    QPS: {:.0}, Recall@{}: {:.1}%\n", result.qps, k, result.recall * 100.0);
                results.push(result);
            }
            Err(e) => println!("    Error: {}\n", e),
        }
    }

    // Print summary table
    println!("\n{}", "=".repeat(80));
    println!("SUMMARY: FAISS SIFT1M (1M vectors × 128D, k=10)");
    println!("{}", "=".repeat(80));
    println!("{:30} {:>10} {:>12} {:>12} {:>12}", "Index", "QPS", "Recall@10", "p50 (µs)", "p99 (µs)");
    println!("{}", "-".repeat(80));
    for r in &results {
        println!("{:30} {:>10.0} {:>11.1}% {:>12.1} {:>12.1}",
            r.name, r.qps, r.recall * 100.0, r.p50_us, r.p99_us);
    }
    println!("{}", "=".repeat(80));
}
