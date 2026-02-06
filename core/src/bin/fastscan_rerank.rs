// FastScan with Reranking Benchmark
// Two-stage: PQ4 overcollect -> exact distance rerank

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
use std::collections::HashSet;
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
            let status = faiss_index_factory(&mut index, dimension, desc_cstr.as_ptr(), FaissMetricType_METRIC_L2);
            if status != 0 {
                let error = faiss_get_last_error();
                let msg = std::ffi::CStr::from_ptr(error).to_string_lossy().to_string();
                return Err(format!("Failed to create index: {}", msg));
            }

            let n_vectors = n as c_longlong;
            faiss_Index_train(index, n_vectors, vectors.as_ptr());
            faiss_Index_add(index, n_vectors, vectors.as_ptr());

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
            faiss_Index_search(self.ptr, 1, query.as_ptr(), k as c_longlong, distances.as_mut_ptr(), labels.as_mut_ptr());
        }
        labels.into_iter().zip(distances).filter(|(id, _)| *id != -1).collect()
    }
}

/// Compute exact L2 distance
fn l2_distance(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b.iter()).map(|(x, y)| (x - y).powi(2)).sum()
}

/// Rerank candidates using exact distances
fn rerank(query: &[f32], candidates: &[(i64, f32)], base_vectors: &[f32], dim: usize, k: usize) -> Vec<(i64, f32)> {
    let mut reranked: Vec<(i64, f32)> = candidates.iter()
        .map(|(id, _)| {
            let vec_start = (*id as usize) * dim;
            let vec = &base_vectors[vec_start..vec_start + dim];
            let exact_dist = l2_distance(query, vec);
            (*id, exact_dist)
        })
        .collect();

    reranked.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
    reranked.truncate(k);
    reranked
}

fn read_fvecs(path: &Path) -> std::io::Result<(Vec<f32>, usize, usize)> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let mut dim_buf = [0u8; 4];
    reader.read_exact(&mut dim_buf)?;
    let dim = i32::from_le_bytes(dim_buf) as usize;
    let file_size = std::fs::metadata(path)?.len() as usize;
    let n = file_size / (4 + dim * 4);

    let mut data = vec![0f32; n * dim];
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    for i in 0..n {
        reader.read_exact(&mut dim_buf)?;
        let slice = &mut data[i * dim..(i + 1) * dim];
        let byte_slice = unsafe { std::slice::from_raw_parts_mut(slice.as_mut_ptr() as *mut u8, dim * 4) };
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
    let n = file_size / (4 + k * 4);

    let mut data = vec![0i32; n * k];
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    for i in 0..n {
        reader.read_exact(&mut k_buf)?;
        let slice = &mut data[i * k..(i + 1) * k];
        let byte_slice = unsafe { std::slice::from_raw_parts_mut(slice.as_mut_ptr() as *mut u8, k * 4) };
        reader.read_exact(byte_slice)?;
    }
    Ok((data, n, k))
}

fn compute_recall(gt: &[i32], results: &[(i64, f32)], k: usize) -> f64 {
    let gt_set: HashSet<i64> = gt.iter().take(k).map(|&x| x as i64).collect();
    let result_set: HashSet<i64> = results.iter().take(k).map(|(id, _)| *id).collect();
    gt_set.intersection(&result_set).count() as f64 / k as f64
}

fn main() {
    std::env::set_var("OMP_NUM_THREADS", "1");

    println!("FastScan + Reranking SIFT1M Benchmark");
    println!("=====================================\n");

    let data_dir = Path::new("data");

    println!("Loading SIFT1M data...");
    let (base_vectors, n_base, dim) = read_fvecs(&data_dir.join("sift_base.fvecs")).expect("Failed to read base");
    let (query_vectors, n_queries, _) = read_fvecs(&data_dir.join("sift_query.fvecs")).expect("Failed to read queries");
    let (ground_truth, _, gt_k) = read_ivecs(&data_dir.join("sift_groundtruth.ivecs")).expect("Failed to read GT");
    println!("  Base: {} × {}D, Queries: {}\n", n_base, dim, n_queries);

    let k = 10;
    let num_queries = n_queries.min(10_000);
    let nlist = (n_base as f64).sqrt().ceil() as i32;

    // Build FastScan index
    println!("Building IVF-PQ4fs index...");
    let build_start = Instant::now();
    let index = FaissIndex::create(&format!("IVF{},PQ32x4fs", nlist), dim as i32, &base_vectors, n_base, 32)
        .expect("Failed to create index");
    println!("  Build time: {:.2}s\n", build_start.elapsed().as_secs_f64());

    // Test configurations: (name, nprobe, k_oversample)
    let configs = vec![
        ("PQ4fs+rerank (k=100)", 32, 100),
        ("PQ4fs+rerank (k=200)", 32, 200),
        ("PQ4fs+rerank (k=300)", 32, 300),
        ("PQ4fs+rerank (k=500)", 32, 500),
        ("PQ4fs+rerank (k=500, np=64)", 64, 500),
        ("PQ4fs+rerank (k=1000, np=64)", 64, 1000),
    ];

    println!("Running benchmarks...\n");
    println!("{:35} {:>10} {:>12} {:>12}", "Config", "QPS", "Recall@10", "p50 (µs)");
    println!("{}", "-".repeat(75));

    for (name, nprobe, k_oversample) in configs {
        // Update nprobe
        unsafe {
            let ivf = faiss_IndexIVF_cast(index.ptr);
            if !ivf.is_null() {
                faiss_IndexIVF_set_nprobe(ivf, nprobe);
            }
        }

        // Warmup
        for i in 0..100 {
            let query = &query_vectors[i * dim..(i + 1) * dim];
            let candidates = index.search(query, k_oversample);
            if k_oversample > k {
                let _ = rerank(query, &candidates, &base_vectors, dim, k);
            }
        }

        // Measure QPS
        let start = Instant::now();
        let mut all_results: Vec<Vec<(i64, f32)>> = Vec::with_capacity(num_queries);
        for i in 0..num_queries {
            let query = &query_vectors[i * dim..(i + 1) * dim];
            let candidates = index.search(query, k_oversample);
            let results = if k_oversample > k {
                rerank(query, &candidates, &base_vectors, dim, k)
            } else {
                candidates
            };
            all_results.push(results);
        }
        let elapsed = start.elapsed();
        let qps = num_queries as f64 / elapsed.as_secs_f64();

        // Compute recall
        let mut total_recall = 0.0;
        for i in 0..num_queries {
            let gt = &ground_truth[i * gt_k..(i + 1) * gt_k];
            total_recall += compute_recall(gt, &all_results[i], k);
        }
        let recall = total_recall / num_queries as f64;

        // Latency
        let mut latencies: Vec<f64> = Vec::with_capacity(num_queries);
        for i in 0..num_queries {
            let query = &query_vectors[i * dim..(i + 1) * dim];
            let t = Instant::now();
            let candidates = index.search(query, k_oversample);
            if k_oversample > k {
                let _ = rerank(query, &candidates, &base_vectors, dim, k);
            }
            latencies.push(t.elapsed().as_nanos() as f64 / 1000.0);
        }
        latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let p50 = latencies[(num_queries as f64 * 0.50) as usize];

        println!("{:35} {:>10.0} {:>11.1}% {:>12.1}", name, qps, recall * 100.0, p50);
    }

    println!("\n{}", "=".repeat(75));
}
