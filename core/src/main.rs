// src/main.rs - High-Performance Hybrid Search System

// Explicit link directives for FAISS and OpenMP libraries
// Required because LTO can prevent build.rs link instructions from propagating
#[link(name = "faiss_c")]
#[link(name = "faiss")]
#[link(name = "omp")]
#[link(name = "c++")]
extern "C" {}

#[allow(non_upper_case_globals)]
#[allow(non_camel_case_types)]
#[allow(dead_code)]
mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

mod persistence;
pub mod descartes;
mod fdb;
pub mod text_index;

use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use bindings::*;
use dashmap::DashMap;
use libc::{c_int, c_longlong};
use log::{error, info};
use persistence::{Operation, WalWriter, load_snapshot, save_snapshot, IndexMetadata, FilterMetadata};
use fdb::{DocumentMetadata, OptionalFdbClient};
use seekstorm::index::{
    create_index, open_index, Document, IndexArc, IndexDocuments, IndexMetaObject,
    SimilarityType, StemmerType, StopwordType, FrequentwordType, TokenizerType, AccessType,
};
use seekstorm::search::{QueryType, ResultType, Search};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::HashMap;
use std::ffi::CString;
use std::marker::PhantomData;
use std::path::{Path, PathBuf};
use std::ptr;
use std::sync::Arc;
use std::sync::atomic::{AtomicI64, AtomicU64, AtomicU8, Ordering};
use tokio::sync::RwLock;
use rayon::ThreadPoolBuilder;
use arc_swap::ArcSwap;

// Import Descartes module for pure Rust vector search
use descartes::{DescartesConfig, DescartesIndex};

// Constants
const INDICES_PATH: &str = "./indices";
const BATCH_SIZE: usize = 100;
const BATCH_TIMEOUT_MS: u64 = 50;
const DEFAULT_RRF_K: f32 = 60.0;
const HNSW_SQ8_UPGRADE_THRESHOLD: usize = 10_000; // Auto-upgrade to HNSW_SQ8 at 10k vectors
const HNSW_SQ8_K_FACTOR: f32 = 3.0; // Rerank factor for SQ8 (lower than PQ4 since SQ8 is more accurate)
                                     // k_factor=3 gives ~97-98% recall with better QPS than FastScan

// Index types
const INDEX_TYPE_HNSW: u8 = 0;
const INDEX_TYPE_FASTSCAN: u8 = 1;  // IVF-PQ4 with FastScan (62k QPS, 96.6% recall, 8x memory reduction)
const INDEX_TYPE_HNSW_SQ8: u8 = 2;  // HNSW with 8-bit scalar quantization (42k QPS, 96.6% recall, 4x memory reduction)
const INDEX_TYPE_DESCARTES: u8 = 3; // Pure Rust FNG with Int8 quantization (99%+ recall, no FAISS dependency)

// ============================================================================
// DATA STRUCTURES
// ============================================================================

/// Wrapper around the raw FAISS index pointer
struct FaissIndexWrapper(*mut FaissIndex, PhantomData<*const ()>);

unsafe impl Send for FaissIndexWrapper {}
unsafe impl Sync for FaissIndexWrapper {}

impl Drop for FaissIndexWrapper {
    fn drop(&mut self) {
        if !self.0.is_null() {
            unsafe {
                faiss_Index_free(self.0);
            }
        }
    }
}



/// High-performance vector index data with lock-free structures
struct VectorIndexData {
    index: ArcSwap<FaissIndexWrapper>,  // Lock-free swappable FAISS index
    descartes_index: RwLock<Option<DescartesIndex>>, // Optional pure Rust backend
    dimension: c_int,
    k: c_longlong,
    text_map: DashMap<i64, Arc<str>>,  // Lock-free concurrent hashmap
    filter_map: DashMap<i64, FilterMetadata>,  // In-memory filter metadata for search-time filtering
    next_id: AtomicI64,                 // Lock-free ID counter
    index_type: AtomicU8,              // 0=HNSW, 1=FastScan, 2=HNSW_SQ8, 3=Descartes
    upgrade_type: AtomicU8,            // Target upgrade type: 1=FastScan, 2=HNSW_SQ8, 3=Descartes
    /// Buffer for upgrade (stores all vectors for re-indexing)
    vector_buffer: RwLock<Vec<(i64, Vec<f32>)>>,
}

impl VectorIndexData {
    fn new(index_ptr: *mut FaissIndex, dimension: c_int, k: c_longlong, upgrade_type: u8) -> Self {
        Self {
            index: ArcSwap::from_pointee(FaissIndexWrapper(index_ptr, PhantomData)),
            descartes_index: RwLock::new(None),
            dimension,
            k,
            text_map: DashMap::new(),
            filter_map: DashMap::new(),
            next_id: AtomicI64::new(0),
            index_type: AtomicU8::new(INDEX_TYPE_HNSW),
            upgrade_type: AtomicU8::new(upgrade_type),
            vector_buffer: RwLock::new(Vec::new()),
        }
    }

    fn from_metadata(index_ptr: *mut FaissIndex, metadata: IndexMetadata) -> Self {
        let data = Self {
            index: ArcSwap::from_pointee(FaissIndexWrapper(index_ptr, PhantomData)),
            descartes_index: RwLock::new(None),
            dimension: metadata.dimension,
            k: metadata.k,
            text_map: DashMap::new(),
            filter_map: DashMap::new(),
            next_id: AtomicI64::new(metadata.next_id),
            index_type: AtomicU8::new(metadata.index_type),
            upgrade_type: AtomicU8::new(metadata.upgrade_type),
            vector_buffer: RwLock::new(Vec::new()),
        };

        for (id, text) in metadata.text_map {
            data.text_map.insert(id, Arc::from(text.as_str()));
        }

        for (id, filter) in metadata.filter_map {
            data.filter_map.insert(id, filter);
        }

        data
    }

    /// Check if using Descartes backend
    fn is_descartes(&self) -> bool {
        self.index_type.load(Ordering::SeqCst) == INDEX_TYPE_DESCARTES
    }
}

/// Combined vector + text index
#[derive(Clone)]
struct BridgeIndex {
    name: String,
    vector_index: Arc<VectorIndexData>,
    text_index: IndexArc,
    wal: Arc<WalWriter>,
    // Dedicated thread pool for FAISS blocking operations
    faiss_pool: Arc<rayon::ThreadPool>,
    // Semaphore to limit concurrent SeekStorm writes (prevents shard_queue exhaustion)
    text_write_semaphore: Arc<tokio::sync::Semaphore>,
}

/// Application state with WAL and persistence
struct AppState {
    indices: Arc<RwLock<HashMap<String, BridgeIndex>>>,
    op_counter: Arc<AtomicU64>,
    fdb: Arc<OptionalFdbClient>,
}

// ============================================================================
// REQUEST/RESPONSE STRUCTURES
// ============================================================================

#[derive(Deserialize)]
struct CreateIndexRequest {
    name: String,
    dimension: c_int,
    k: Option<c_longlong>,
    #[serde(default = "default_upgrade_type")]
    upgrade_type: String,  // "fastscan" or "hnsw_sq8"
}

fn default_upgrade_type() -> String { "fastscan".to_string() }

fn parse_upgrade_type(s: &str) -> u8 {
    match s.to_lowercase().as_str() {
        "hnsw_sq8" => INDEX_TYPE_HNSW_SQ8,
        "descartes" => INDEX_TYPE_DESCARTES,
        _ => INDEX_TYPE_FASTSCAN, // default
    }
}

/// Numeric filter for search
#[derive(Clone, Debug, Deserialize, Serialize)]
struct NumericFilter {
    field: String,
    #[serde(default)]
    min: Option<f64>,
    #[serde(default)]
    max: Option<f64>,
}

/// Rich metadata stored in FDB (not needed for filtering)
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
struct RichMetadata {
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    author: Option<String>,
    #[serde(default)]
    source_url: Option<String>,
    #[serde(default)]
    custom_fields: HashMap<String, serde_json::Value>,
}

#[derive(Clone, Deserialize, Serialize)]
struct AddRequest {
    index: String,
    text: String,
    vector: Vec<f32>,
    /// Filter tags for search-time filtering (e.g., ["category:tech", "status:published"])
    #[serde(default)]
    filter_tags: Vec<String>,
    /// Creation timestamp for time-based filtering
    #[serde(default)]
    created_at: Option<i64>,
    /// Numeric fields for range filtering (e.g., {"price": 29.99, "rating": 4.5})
    #[serde(default)]
    filter_numerics: HashMap<String, f64>,
    /// Rich metadata stored in FDB (title, author, custom fields)
    #[serde(default)]
    metadata: Option<RichMetadata>,
}

#[derive(Deserialize)]
struct BatchAddRequest {
    index: String,
    documents: Vec<DocumentRequest>,
}

#[derive(Clone, Deserialize, Serialize)]
struct DocumentRequest {
    text: String,
    vector: Vec<f32>,
    /// Filter tags for search-time filtering
    #[serde(default)]
    filter_tags: Vec<String>,
    /// Creation timestamp for time-based filtering
    #[serde(default)]
    created_at: Option<i64>,
    /// Numeric fields for range filtering
    #[serde(default)]
    filter_numerics: HashMap<String, f64>,
    /// Rich metadata stored in FDB
    #[serde(default)]
    metadata: Option<RichMetadata>,
}

#[derive(Deserialize)]
struct DeleteRequest {
    index: String,
    ids: Vec<i64>,
}

#[derive(Deserialize)]
struct SearchRequest {
    index: String,
    vector_query: Option<Vec<f32>>,
    text_query: Option<String>,
    #[serde(default = "default_vector_weight")]
    vector_weight: f32,
    #[serde(default = "default_text_weight")]
    text_weight: f32,
    #[serde(default = "default_k")]
    k: usize,
    #[serde(default)]
    text_offset: u64,
    #[serde(default = "default_text_length")]
    text_length: u64,
    /// Filter by tags (documents must have ALL specified tags)
    #[serde(default)]
    filter_tags: Vec<String>,
    /// Filter documents created after this timestamp
    #[serde(default)]
    created_after: Option<i64>,
    /// Filter documents created before this timestamp
    #[serde(default)]
    created_before: Option<i64>,
    /// Numeric range filters
    #[serde(default)]
    numeric_filters: Vec<NumericFilter>,
    /// Include rich metadata from FDB in results
    #[serde(default)]
    include_metadata: bool,
}

fn default_vector_weight() -> f32 { 0.5 }
fn default_text_weight() -> f32 { 0.5 }
fn default_k() -> usize { 10 }
fn default_text_length() -> u64 { 100 }

#[derive(Debug, Serialize, Deserialize)]
struct RRFSearchResult {
    id: i64,
    text: String,
    score: f32,
    vector_rank: Option<usize>,
    text_rank: Option<usize>,
    source: String,  // "both", "vector", or "text"
    /// Rich metadata from FDB (only included if include_metadata=true)
    #[serde(skip_serializing_if = "Option::is_none")]
    metadata: Option<RichMetadata>,
}

#[derive(Debug, Serialize, Deserialize)]
struct SearchResults {
    results: Vec<RRFSearchResult>,
    total: usize,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

/// Batch search request - multiple queries executed together for higher throughput
#[derive(Deserialize)]
struct BatchSearchRequest {
    index: String,
    queries: Vec<BatchQueryItem>,
    #[serde(default = "default_k")]
    k: usize,
    #[serde(default = "default_batch_window_ms")]
    window_ms: u64,  // Time to wait for more queries (0 = no waiting)
}

#[derive(Deserialize)]
struct BatchQueryItem {
    vector_query: Option<Vec<f32>>,
    text_query: Option<String>,
    #[serde(default = "default_vector_weight")]
    vector_weight: f32,
    #[serde(default = "default_text_weight")]
    text_weight: f32,
}

fn default_batch_window_ms() -> u64 { 0 }

#[derive(Serialize)]
struct BatchSearchResponse {
    results: Vec<SearchResults>,
    batch_size: usize,
    total_time_ms: f64,
}

// ============================================================================
// FAISS OPERATIONS (with spawn_blocking for async)
// ============================================================================

/// Create a FAISS index (CPU-intensive, wrapped in spawn_blocking)
async fn create_faiss_index_async(dimension: c_int, k: c_longlong, upgrade_type: u8) -> Result<Arc<VectorIndexData>, String> {
    tokio::task::spawn_blocking(move || {
        let metric_description = CString::new("IDMap,HNSW32,Flat").unwrap();
        let mut index_ptr: *mut FaissIndex = ptr::null_mut();

        unsafe {
            let status = faiss_index_factory(
                &mut index_ptr,
                dimension,
                metric_description.as_ptr(),
                FaissMetricType_METRIC_L2,
            );

            if status != 0 {
                let error = faiss_get_last_error();
                let error_message = std::ffi::CStr::from_ptr(error)
                    .to_string_lossy()
                    .to_string();
                return Err(format!("Error creating FAISS index: {}", error_message));
            }

            if index_ptr.is_null() {
                return Err("Failed to create FAISS index: null pointer returned.".to_string());
            }
        }

        Ok(Arc::new(VectorIndexData::new(index_ptr, dimension, k, upgrade_type)))
    })
    .await
    .unwrap()
}

/// Create an HNSW_SQ8 index from buffered vectors (Descartes-inspired)
/// Uses 8-bit scalar quantization for memory efficiency + reranking for high recall
/// Returns a FaissIndexWrapper (Send+Sync safe) containing the new index
fn create_hnsw_sq8_index(
    dimension: c_int,
    vectors: Vec<(i64, Vec<f32>)>,
) -> Result<FaissIndexWrapper, String> {
    let n = vectors.len();
    // HNSW with 8-bit scalar quantization
    // SQ8 quantizes each float32 to uint8 (4x memory reduction)
    // HNSW32 means M=32 bidirectional links per node
    // No reranking - SQ8 is accurate enough (better than PQ4)
    let desc = CString::new("IDMap2,HNSW32_SQ8").unwrap();

    info!("Creating HNSW_SQ8 index: vectors={}, k_factor={}", n, HNSW_SQ8_K_FACTOR);

    let mut index: *mut FaissIndex = ptr::null_mut();
    unsafe {
        // Create HNSW_SQ8 + RFlat index via factory
        let status = faiss_index_factory(
            &mut index,
            dimension,
            desc.as_ptr(),
            FaissMetricType_METRIC_L2,
        );

        if status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error)
                .to_string_lossy()
                .to_string();
            return Err(format!("Error creating HNSW_SQ8 index: {}", error_message));
        }

        // Flatten vectors for training
        let flat: Vec<f32> = vectors.iter().flat_map(|(_, v)| v.iter().copied()).collect();
        let ids: Vec<i64> = vectors.iter().map(|(id, _)| *id).collect();
        let n_vectors = vectors.len() as c_longlong;

        // Train SQ8 (learns quantization ranges from data)
        let train_status = faiss_Index_train(index, n_vectors, flat.as_ptr());
        if train_status != 0 {
            faiss_Index_free(index);
            return Err("Failed to train HNSW_SQ8 index".to_string());
        }

        info!("HNSW_SQ8 trained, adding {} vectors", n);

        // Add all vectors with custom IDs
        let add_status = faiss_Index_add_with_ids(index, n_vectors, flat.as_ptr(), ids.as_ptr());
        if add_status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error)
                .to_string_lossy()
                .to_string();
            faiss_Index_free(index);
            return Err(format!("Failed to add vectors: {}", error_message));
        }

        info!("HNSW_SQ8 ready: {} vectors", n);

        Ok(FaissIndexWrapper(index, PhantomData))
    }
}

/// Create a FastScan IVF-PQ4 index from buffered vectors
/// Uses 4-bit product quantization for maximum memory efficiency (8x reduction)
/// Returns a FaissIndexWrapper (Send+Sync safe) containing the new index
fn create_fastscan_index(
    dimension: c_int,
    vectors: Vec<(i64, Vec<f32>)>,
) -> Result<FaissIndexWrapper, String> {
    let n = vectors.len();
    // IVF with PQ4 (4-bit product quantization) + FastScan
    // nlist = sqrt(n) for good clustering
    let nlist = (n as f64).sqrt().ceil() as i32;
    // m = dimension / 2 subquantizers (each subquantizer handles 2 dimensions)
    let m = dimension / 2;
    // IVF + PQ4fs (4-bit PQ with FastScan)
    let desc = CString::new(format!("IDMap2,IVF{}_PQ{}x4fs", nlist, m)).unwrap();

    info!("Creating FastScan index: vectors={}, nlist={}, m={}", n, nlist, m);

    let mut index: *mut FaissIndex = ptr::null_mut();
    unsafe {
        let status = faiss_index_factory(
            &mut index,
            dimension,
            desc.as_ptr(),
            FaissMetricType_METRIC_L2,
        );

        if status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error)
                .to_string_lossy()
                .to_string();
            return Err(format!("Error creating FastScan index: {}", error_message));
        }

        // Flatten vectors for training
        let flat: Vec<f32> = vectors.iter().flat_map(|(_, v)| v.iter().copied()).collect();
        let ids: Vec<i64> = vectors.iter().map(|(id, _)| *id).collect();
        let n_vectors = vectors.len() as c_longlong;

        // Train IVF clustering and PQ codebook
        let train_status = faiss_Index_train(index, n_vectors, flat.as_ptr());
        if train_status != 0 {
            faiss_Index_free(index);
            return Err("Failed to train FastScan index".to_string());
        }

        info!("FastScan trained, adding {} vectors", n);

        // Add all vectors with custom IDs
        let add_status = faiss_Index_add_with_ids(index, n_vectors, flat.as_ptr(), ids.as_ptr());
        if add_status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error)
                .to_string_lossy()
                .to_string();
            faiss_Index_free(index);
            return Err(format!("Failed to add vectors: {}", error_message));
        }

        info!("FastScan ready: {} vectors", n);

        Ok(FaissIndexWrapper(index, PhantomData))
    }
}

/// Add vectors to FAISS in batch (CPU-intensive, uses Rayon pool)
async fn faiss_add_batch(
    faiss_pool: Arc<rayon::ThreadPool>,
    index_data: Arc<VectorIndexData>,
    vectors: Vec<Vec<f32>>,
    ids: Vec<i64>,
) -> Result<(), String> {
    // First, add to the current index
    {
        let vectors_clone = vectors.clone();
        let ids_clone = ids.clone();
        let index_data_clone = index_data.clone();

        let (tx, rx) = tokio::sync::oneshot::channel();

        faiss_pool.spawn(move || {
            let n = vectors_clone.len() as c_longlong;
            let flat_vectors: Vec<f32> = vectors_clone.into_iter().flatten().collect();

            // Lock-free access via ArcSwap
            let index_arc = index_data_clone.index.load();
            let result = unsafe {
                let status = faiss_Index_add_with_ids(
                    index_arc.0,
                    n,
                    flat_vectors.as_ptr(),
                    ids_clone.as_ptr(),
                );

                if status != 0 {
                    Err("Failed to add vectors to FAISS".to_string())
                } else {
                    Ok(())
                }
            };

            let _ = tx.send(result);
        });

        rx.await.unwrap()?;
    }

    // Buffer vectors for potential upgrade
    let should_upgrade = {
        let mut buffer = index_data.vector_buffer.write().await;
        for (id, vec) in ids.iter().zip(vectors.iter()) {
            buffer.push((*id, vec.clone()));
        }

        // Check if upgrade needed (HNSW -> upgraded index at threshold)
        index_data.index_type.load(Ordering::SeqCst) == INDEX_TYPE_HNSW
            && buffer.len() >= HNSW_SQ8_UPGRADE_THRESHOLD
    };

    if should_upgrade {
        let upgrade_type = index_data.upgrade_type.load(Ordering::SeqCst);
        let upgrade_name = match upgrade_type {
            INDEX_TYPE_FASTSCAN => "FastScan",
            INDEX_TYPE_HNSW_SQ8 => "HNSW_SQ8",
            INDEX_TYPE_DESCARTES => "Descartes",
            _ => "FastScan", // default
        };
        info!("Upgrading to {} index...", upgrade_name);

        // Get all buffered vectors (move out to avoid clone)
        let buffer_snapshot: Vec<(i64, Vec<f32>)> = {
            let buffer = index_data.vector_buffer.read().await;
            buffer.clone()
        };

        let vector_count = buffer_snapshot.len();
        let dimension = index_data.dimension;

        if upgrade_type == INDEX_TYPE_DESCARTES {
            // Create Descartes index (pure Rust, no FAISS)
            let descartes_result = tokio::task::spawn_blocking(move || {
                let config = DescartesConfig::new(dimension as usize)
                    .with_m(32)
                    .with_ef_construction(200)
                    .with_ef_search(64);

                let mut index = DescartesIndex::new(config);
                let vectors: Vec<Vec<f32>> = buffer_snapshot.iter().map(|(_, v)| v.clone()).collect();
                let ids: Vec<i64> = buffer_snapshot.iter().map(|(id, _)| *id).collect();
                index.build_with_ids(&vectors, &ids);
                index
            })
            .await
            .map_err(|e| format!("Task join error: {}", e))?;

            // Store Descartes index
            {
                let mut descartes_guard = index_data.descartes_index.write().await;
                *descartes_guard = Some(descartes_result);
            }
            index_data.index_type.store(INDEX_TYPE_DESCARTES, Ordering::SeqCst);
            info!("Successfully upgraded to Descartes with {} vectors", vector_count);
        } else {
            // Create FAISS-based upgraded index
            let new_index_result = tokio::task::spawn_blocking(move || {
                match upgrade_type {
                    INDEX_TYPE_FASTSCAN => create_fastscan_index(dimension, buffer_snapshot),
                    INDEX_TYPE_HNSW_SQ8 => create_hnsw_sq8_index(dimension, buffer_snapshot),
                    _ => create_fastscan_index(dimension, buffer_snapshot),
                }
            })
            .await
            .map_err(|e| format!("Task join error: {}", e))?;

            match new_index_result {
                Ok(new_wrapper) => {
                    let old_arc = index_data.index.swap(Arc::new(new_wrapper));
                    let final_type = match upgrade_type {
                        INDEX_TYPE_FASTSCAN => INDEX_TYPE_FASTSCAN,
                        INDEX_TYPE_HNSW_SQ8 => INDEX_TYPE_HNSW_SQ8,
                        _ => INDEX_TYPE_FASTSCAN,
                    };
                    index_data.index_type.store(final_type, Ordering::SeqCst);
                    drop(old_arc);
                    info!("Successfully upgraded to {} with {} vectors", upgrade_name, vector_count);
                }
                Err(e) => {
                    error!("Failed to upgrade to {}: {}. Continuing with HNSW.", upgrade_name, e);
                }
            }
        }
    }

    Ok(())
}

/// Delete vectors from FAISS (CPU-intensive)
async fn faiss_delete_batch(
    index_data: Arc<VectorIndexData>,
    ids: Vec<i64>,
) -> Result<(), String> {
    tokio::task::spawn_blocking(move || {
        // FAISS remove_ids requires IDSelector, which is complex
        // For now, we'll just remove from text_map and mark as deleted
        // TODO: Implement proper FAISS deletion with IDSelector

        // Remove from text map
        for id in &ids {
            index_data.text_map.remove(id);
        }

        Ok(())
    })
    .await
    .unwrap()
}

/// Unified search function - uses Descartes if available, otherwise FAISS
async fn vector_search(
    faiss_pool: Arc<rayon::ThreadPool>,
    index_data: Arc<VectorIndexData>,
    query: Arc<Vec<f32>>,
    k: c_longlong,
) -> Result<Vec<(i64, f32)>, String> {
    // Check if using Descartes backend
    if index_data.is_descartes() {
        let descartes_guard = index_data.descartes_index.read().await;
        if let Some(ref descartes) = *descartes_guard {
            let results = descartes.search(&query, k as usize);
            return Ok(results.iter().map(|r| (r.id, r.distance)).collect());
        }
    }

    // Fall back to FAISS search
    faiss_search(faiss_pool, index_data, query, k).await
}

/// Search FAISS index (CPU-intensive, uses dedicated Rayon pool)
async fn faiss_search(
    faiss_pool: Arc<rayon::ThreadPool>,
    index_data: Arc<VectorIndexData>,
    query: Arc<Vec<f32>>,  // Arc to avoid 16KB clone per request
    k: c_longlong,
) -> Result<Vec<(i64, f32)>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();

    faiss_pool.spawn(move || {
        let nq = 1;
        let k_usize = k as usize;
        let mut distances = vec![0.0; k_usize];
        let mut labels = vec![-1; k_usize];

        // Lock-free access via ArcSwap
        let index_arc = index_data.index.load();
        let ptr = index_arc.0;

        // Check if index is empty first (before unsafe block)
        let ntotal = unsafe { faiss_Index_ntotal(ptr) };
        if ntotal == 0 {
            let _ = tx.send(Err("The index is empty. Add vectors before searching.".to_string()));
            return;
        }

        let result = unsafe {
            let status = faiss_Index_search(
                ptr,
                nq,
                query.as_ptr(),
                k,
                distances.as_mut_ptr(),
                labels.as_mut_ptr(),
            );

            if status != 0 {
                let error_ptr = faiss_get_last_error();
                let error_message = std::ffi::CStr::from_ptr(error_ptr)
                    .to_string_lossy()
                    .to_string();
                Err(error_message)
            } else {
                let results: Vec<(i64, f32)> = labels
                    .into_iter()
                    .zip(distances.into_iter())
                    .filter(|(id, _)| *id != -1)
                    .collect();
                Ok(results)
            }
        };

        let _ = tx.send(result);
    });

    rx.await.map_err(|e| format!("Channel receive error: {}", e))?
}

/// Batch vector search - process multiple queries in one FAISS call for higher throughput
async fn faiss_batch_search(
    faiss_pool: Arc<rayon::ThreadPool>,
    index_data: Arc<VectorIndexData>,
    queries: Vec<Vec<f32>>,  // Multiple query vectors
    k: c_longlong,
) -> Result<Vec<Vec<(i64, f32)>>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();
    let nq = queries.len();
    let dimension = index_data.dimension as usize;

    faiss_pool.spawn(move || {
        let k_usize = k as usize;

        // Lock-free access via ArcSwap
        let index_arc = index_data.index.load();
        let ptr = index_arc.0;

        // Check if index is empty
        let ntotal = unsafe { faiss_Index_ntotal(ptr) };
        if ntotal == 0 {
            let _ = tx.send(Err("The index is empty. Add vectors before searching.".to_string()));
            return;
        }

        // Flatten queries into contiguous array
        let flat_queries: Vec<f32> = queries.iter().flatten().copied().collect();
        if flat_queries.len() != nq * dimension {
            let _ = tx.send(Err("Query dimension mismatch".to_string()));
            return;
        }

        // Allocate output buffers for all queries
        let mut distances = vec![0.0f32; nq * k_usize];
        let mut labels = vec![-1i64; nq * k_usize];

        let result = unsafe {
            let status = faiss_Index_search(
                ptr,
                nq as c_longlong,
                flat_queries.as_ptr(),
                k,
                distances.as_mut_ptr(),
                labels.as_mut_ptr(),
            );

            if status != 0 {
                let error_ptr = faiss_get_last_error();
                let error_message = std::ffi::CStr::from_ptr(error_ptr)
                    .to_string_lossy()
                    .to_string();
                Err(error_message)
            } else {
                // Split results back into per-query vectors
                let mut all_results = Vec::with_capacity(nq);
                for i in 0..nq {
                    let start = i * k_usize;
                    let end = start + k_usize;
                    let query_results: Vec<(i64, f32)> = labels[start..end]
                        .iter()
                        .zip(distances[start..end].iter())
                        .filter(|(id, _)| **id != -1)
                        .map(|(id, dist)| (*id, *dist))
                        .collect();
                    all_results.push(query_results);
                }
                Ok(all_results)
            }
        };

        let _ = tx.send(result);
    });

    rx.await.map_err(|e| format!("Channel receive error: {}", e))?
}

// ============================================================================
// TEXT INDEX OPERATIONS
// ============================================================================

async fn create_text_index(index_name: &str, index_path: &Path) -> Result<IndexArc, String> {
    let schema_json = r#"
    [{"field":"body","field_type":"Text","stored":true,"indexed":true},
    {"field":"id","field_type":"I64","stored":true,"indexed":false}]"#;
    let schema = serde_json::from_str(schema_json).expect("Invalid schema JSON");

    // Match SeekStorm test example exactly
    use seekstorm::index::NgramSet;
    let meta = IndexMetaObject {
        id: 0,
        name: index_name.into(),
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
    let num_cores = std::thread::available_parallelism()
        .map(|p| p.get())
        .unwrap_or(8);
    let segment_number_bits1 = (num_cores as f64).log2().ceil() as usize;
    let new_index = create_index(
        index_path,
        meta,
        &schema,
        &Vec::new(),
        segment_number_bits1,
        false,
        None,
    )
    .await
    .map_err(|e| format!("Failed to create text index: {}", e))?;

    Ok(new_index)
}

async fn text_search(
    text_index: IndexArc,
    query: &str,
    offset: u64,
    length: u64,
) -> Result<Vec<(i64, f32)>, String> {
    let query_string = query.to_string();

    let result_object = text_index.search(
        query_string,
        QueryType::Union,  // Union is faster than Intersection
        offset as usize,
        length as usize,
        ResultType::Topk,  // Topk is faster than TopkCount
        false,             // Disable highlights for performance
        Vec::new(),
        Vec::new(),
        Vec::new(),
        Vec::new(),
    ).await;

    let search_results: Vec<(i64, f32)> = result_object
        .results
        .iter()
        .map(|result| {
            // Use SeekStorm's internal doc_id as our ID
            (result.doc_id as i64, result.score)
        })
        .collect();

    Ok(search_results)
}

/// Blocking text search for use with spawn_blocking - enables true CPU parallelism
fn text_search_blocking(
    text_index: IndexArc,
    query: String,
    offset: u64,
    length: u64,
) -> Result<Vec<(i64, f32)>, String> {
    // Use tokio's block_on to run async SeekStorm search in blocking context
    let handle = tokio::runtime::Handle::current();
    handle.block_on(async move {
        let result_object = text_index.search(
            query,
            QueryType::Union,
            offset as usize,
            length as usize,
            ResultType::Topk,
            false,
            Vec::new(),
            Vec::new(),
            Vec::new(),
            Vec::new(),
        ).await;

        let search_results: Vec<(i64, f32)> = result_object
            .results
            .iter()
            .map(|result| (result.doc_id as i64, result.score))
            .collect();

        Ok(search_results)
    })
}

// ============================================================================
// FILTER PREDICATES
// ============================================================================

/// Check if a document passes all filter predicates
fn passes_filters(
    filter_metadata: &FilterMetadata,
    filter_tags: &[String],
    created_after: Option<i64>,
    created_before: Option<i64>,
    numeric_filters: &[NumericFilter],
) -> bool {
    // Check filter tags (document must have ALL specified tags)
    if !filter_tags.is_empty() {
        for required_tag in filter_tags {
            if !filter_metadata.filter_tags.contains(required_tag) {
                return false;
            }
        }
    }

    // Check created_after
    if let Some(after) = created_after {
        if filter_metadata.created_at < after {
            return false;
        }
    }

    // Check created_before
    if let Some(before) = created_before {
        if filter_metadata.created_at > before {
            return false;
        }
    }

    // Check numeric filters
    for nf in numeric_filters {
        if let Some(&value) = filter_metadata.filter_numerics.get(&nf.field) {
            if let Some(min) = nf.min {
                if value < min {
                    return false;
                }
            }
            if let Some(max) = nf.max {
                if value > max {
                    return false;
                }
            }
        } else {
            // Document doesn't have this numeric field - filter it out
            return false;
        }
    }

    true
}

/// Apply filters to a list of search results
fn apply_filters(
    results: Vec<(i64, f32)>,
    filter_map: &DashMap<i64, FilterMetadata>,
    filter_tags: &[String],
    created_after: Option<i64>,
    created_before: Option<i64>,
    numeric_filters: &[NumericFilter],
) -> Vec<(i64, f32)> {
    // Skip filtering if no filters specified
    if filter_tags.is_empty() && created_after.is_none() && created_before.is_none() && numeric_filters.is_empty() {
        return results;
    }

    results
        .into_iter()
        .filter(|(id, _)| {
            if let Some(filter_metadata) = filter_map.get(id) {
                passes_filters(&filter_metadata, filter_tags, created_after, created_before, numeric_filters)
            } else {
                // No filter metadata - include by default (backwards compatibility)
                true
            }
        })
        .collect()
}

// ============================================================================
// WEIGHTED RRF (Reciprocal Rank Fusion)
// ============================================================================

fn weighted_rrf(
    vector_results: Vec<(i64, f32)>,
    text_results: Vec<(i64, f32)>,
    vector_weight: f32,
    text_weight: f32,
    text_map: &DashMap<i64, Arc<str>>,
) -> Vec<RRFSearchResult> {
    let mut combined_scores: HashMap<i64, (f32, Option<usize>, Option<usize>)> = HashMap::new();

    // Add vector results with reciprocal rank
    for (rank, (id, _dist)) in vector_results.iter().enumerate() {
        let rrf_score = vector_weight / (DEFAULT_RRF_K + rank as f32);
        combined_scores.insert(*id, (rrf_score, Some(rank), None));
    }

    // Add text results with reciprocal rank
    for (rank, (id, _score)) in text_results.iter().enumerate() {
        let rrf_score = text_weight / (DEFAULT_RRF_K + rank as f32);
        combined_scores
            .entry(*id)
            .and_modify(|(score, _v_rank, t_rank)| {
                *score += rrf_score;
                *t_rank = Some(rank);
            })
            .or_insert((rrf_score, None, Some(rank)));
    }

    // Convert to results and sort by combined score
    let mut results: Vec<RRFSearchResult> = combined_scores
        .into_iter()
        .map(|(id, (score, vector_rank, text_rank))| {
            let text = text_map
                .get(&id)
                .map(|t| t.as_ref().to_string())
                .unwrap_or_else(|| "Unknown".to_string());

            let source = match (vector_rank, text_rank) {
                (Some(_), Some(_)) => "both",
                (Some(_), None) => "vector",
                (None, Some(_)) => "text",
                _ => "unknown",
            };

            RRFSearchResult {
                id,
                text,
                score,
                vector_rank,
                text_rank,
                source: source.to_string(),
                metadata: None, // Will be enriched later if include_metadata=true
            }
        })
        .collect();

    results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());
    results
}

/// Enrich search results with metadata from FDB
async fn enrich_with_metadata(
    results: &mut [RRFSearchResult],
    index_name: &str,
    fdb: &OptionalFdbClient,
) {
    if results.is_empty() || !fdb.is_available() {
        return;
    }

    let ids: Vec<i64> = results.iter().map(|r| r.id).collect();
    let metadata_map = fdb.get_metadata_batch(index_name, &ids).await;

    for result in results.iter_mut() {
        if let Some(doc_meta) = metadata_map.get(&result.id) {
            result.metadata = Some(RichMetadata {
                title: doc_meta.title.clone(),
                author: doc_meta.author.clone(),
                source_url: doc_meta.source_url.clone(),
                custom_fields: doc_meta.custom_fields.clone(),
            });
        }
    }
}

// ============================================================================
// PERSISTENCE OPERATIONS
// ============================================================================

async fn load_bridge_index(index_name: &str, base_path: &Path) -> Result<BridgeIndex, String> {
    info!("Loading index: {}", index_name);

    let index_name_owned = index_name.to_string();
    let base_path_owned = base_path.to_path_buf();

    let (faiss_index, metadata) = {
        // Load synchronously without spawn_blocking to avoid Send issues
        load_snapshot(&index_name_owned, &base_path_owned)
            .map_err(|e| format!("Failed to load snapshot: {}", e))?
    };

    // Note: HNSW_SQ8 doesn't need nprobe (it's not an IVF index)
    // The efSearch parameter is already part of the HNSW structure
    if metadata.index_type == INDEX_TYPE_HNSW_SQ8 {
        info!("Loaded HNSW_SQ8 index: {}", index_name);
    }

    let vector_index = Arc::new(VectorIndexData::from_metadata(faiss_index, metadata));

    let index_path = base_path.join(index_name);

    // OPEN existing text index instead of creating a new one
    let text_index = open_index(&index_path, false)
        .await
        .map_err(|e| format!("Failed to open text index: {}", e))?;

    let wal_path = index_path.join("wal.log");
    let wal = Arc::new(WalWriter::new(&wal_path).map_err(|e| e.to_string())?);

    // Create dedicated thread pool for FAISS operations
    let faiss_pool = Arc::new(
        ThreadPoolBuilder::new()
            .num_threads(std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4))
            .build()
            .map_err(|e| format!("Failed to create FAISS thread pool: {}", e))?
    );

    Ok(BridgeIndex {
        name: index_name.to_string(),
        vector_index,
        text_index,
        wal,
        faiss_pool,
        // SeekStorm race condition at index.rs:3875 requires single-threaded writes
        text_write_semaphore: Arc::new(tokio::sync::Semaphore::new(1)),
    })
}

async fn save_bridge_index(bridge_index: &BridgeIndex, base_path: &Path) -> Result<(), String> {
    info!("Saving index: {}", bridge_index.name);

    let index_type = bridge_index.vector_index.index_type.load(Ordering::SeqCst);
    let upgrade_type = bridge_index.vector_index.upgrade_type.load(Ordering::SeqCst);
    let metadata = IndexMetadata::from_runtime(
        bridge_index.name.clone(),
        bridge_index.vector_index.dimension,
        bridge_index.vector_index.k,
        &bridge_index.vector_index.next_id,
        &bridge_index.vector_index.text_map,
        &bridge_index.vector_index.filter_map,
        index_type,
        upgrade_type,
    );

    // Lock-free access via ArcSwap
    let index_arc = bridge_index.vector_index.index.load();
    let index_ptr = index_arc.0;
    let index_name = bridge_index.name.clone();
    let base_path_owned = base_path.to_path_buf();

    // Save synchronously without spawn_blocking to avoid Send issues
    save_snapshot(&index_name, index_ptr, &metadata, &base_path_owned)
        .map_err(|e| format!("Failed to save snapshot: {}", e))?;

    bridge_index.wal.flush().map_err(|e| e.to_string())?;

    info!("Index saved: {}", bridge_index.name);
    Ok(())
}

// ============================================================================
// HTTP HANDLERS
// ============================================================================

async fn health() -> impl Responder {
    HttpResponse::Ok().json(json!({ "status": "healthy" }))
}

async fn create_bridge_index_handler(
    state: web::Data<AppState>,
    req: web::Json<CreateIndexRequest>,
) -> impl Responder {
    let index_name = format!("{}_d{}", req.name.trim(), req.dimension);
    let dimension = req.dimension;
    let k = req.k.unwrap_or(10);

    // Parse upgrade_type: "fastscan" (default), "hnsw_sq8", or "descartes"
    let upgrade_type = parse_upgrade_type(&req.upgrade_type);
    let upgrade_type_name = match upgrade_type {
        INDEX_TYPE_HNSW_SQ8 => "hnsw_sq8",
        INDEX_TYPE_DESCARTES => "descartes",
        _ => "fastscan",
    };

    // Check if exists
    {
        let indices = state.indices.read().await;
        if indices.contains_key(&index_name) {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: format!("Index '{}' already exists", index_name),
            });
        }
    }

    let index_path = PathBuf::from(INDICES_PATH).join(&index_name);
    std::fs::create_dir_all(&index_path).ok();

    let vector_index = match create_faiss_index_async(dimension, k, upgrade_type).await {
        Ok(idx) => idx,
        Err(e) => return HttpResponse::InternalServerError().json(ErrorResponse { error: e }),
    };

    let text_index = match create_text_index(&index_name, &index_path).await {
        Ok(idx) => idx,
        Err(e) => return HttpResponse::InternalServerError().json(ErrorResponse { error: e }),
    };

    let wal_path = index_path.join("wal.log");
    let wal = match WalWriter::new(&wal_path) {
        Ok(w) => Arc::new(w),
        Err(e) => return HttpResponse::InternalServerError().json(ErrorResponse {
            error: format!("Failed to create WAL: {}", e),
        }),
    };

    // Create dedicated thread pool for FAISS operations
    let faiss_pool = match ThreadPoolBuilder::new()
        .num_threads(std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4))
        .build()
    {
        Ok(pool) => Arc::new(pool),
        Err(e) => return HttpResponse::InternalServerError().json(ErrorResponse {
            error: format!("Failed to create FAISS thread pool: {}", e),
        }),
    };

    let bridge_index = BridgeIndex {
        name: index_name.clone(),
        vector_index,
        text_index,
        wal,
        faiss_pool,
        // SeekStorm race condition at index.rs:3875 requires single-threaded writes
        text_write_semaphore: Arc::new(tokio::sync::Semaphore::new(1)),
    };

    // Log to WAL
    if let Err(e) = bridge_index.wal.append(Operation::create_index(
        index_name.clone(),
        dimension,
        k,
    )) {
        error!("Failed to write to WAL: {}", e);
    }

    {
        let mut indices = state.indices.write().await;
        indices.insert(index_name.clone(), bridge_index);
    }

    HttpResponse::Ok().json(json!({
        "message": format!("Index '{}' created successfully", index_name),
        "upgrade_type": upgrade_type_name
    }))
}

async fn add_document(
    state: web::Data<AppState>,
    req: web::Json<AddRequest>,
) -> impl Responder {
    let index_name = req.index.trim();

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Index '{}' not found", index_name),
            }),
        }
    };

    if req.vector.len() as c_int != bridge_index.vector_index.dimension {
        return HttpResponse::BadRequest().json(ErrorResponse {
            error: format!(
                "Vector dimension mismatch: expected {}, got {}",
                bridge_index.vector_index.dimension,
                req.vector.len()
            ),
        });
    }

    let id = bridge_index.vector_index.next_id.fetch_add(1, Ordering::SeqCst);
    let text_arc: Arc<str> = Arc::from(req.text.as_str());

    // Build filter metadata for in-memory storage
    let filter_metadata = FilterMetadata {
        filter_tags: req.filter_tags.clone(),
        created_at: req.created_at.unwrap_or_else(|| {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs() as i64
        }),
        filter_numerics: req.filter_numerics.clone(),
    };

    // Serialize ALL writes (FAISS + SeekStorm) to prevent concurrency issues
    {
        let _permit = bridge_index.text_write_semaphore.acquire().await.unwrap();

        // Add to FAISS
        if let Err(e) = faiss_add_batch(
            bridge_index.faiss_pool.clone(),
            bridge_index.vector_index.clone(),
            vec![req.vector.clone()],
            vec![id],
        ).await {
            return HttpResponse::InternalServerError().json(ErrorResponse { error: e });
        }

        // Add to text map
        bridge_index.vector_index.text_map.insert(id, text_arc.clone());

        // Add to filter map (in-memory for search-time filtering)
        bridge_index.vector_index.filter_map.insert(id, filter_metadata.clone());

        // Add to text index
        let mut doc: Document = HashMap::new();
        doc.insert("body".to_string(), json!(req.text));
        doc.insert("id".to_string(), json!(id));

        bridge_index.text_index.index_documents(vec![doc]).await;
    }

    // Store rich metadata in FDB (best-effort, async)
    if let Some(ref rich_meta) = req.metadata {
        let fdb = state.fdb.clone();
        let index_name_owned = index_name.to_string();
        let doc_metadata = DocumentMetadata {
            title: rich_meta.title.clone(),
            author: rich_meta.author.clone(),
            source_url: rich_meta.source_url.clone(),
            custom_fields: rich_meta.custom_fields.clone(),
        };
        // Fire and forget - don't block on FDB
        tokio::spawn(async move {
            fdb.store_metadata_best_effort(&index_name_owned, id, &doc_metadata).await;
        });
    }

    // Log to WAL (commented out for high-throughput benchmarking)
    // Uncomment for durability guarantees
    // if let Err(e) = bridge_index.wal.append(Operation::add(
    //     index_name.to_string(),
    //     id,
    //     req.text.clone(),
    //     req.vector.clone(),
    //     Some(filter_metadata),
    // )) {
    //     error!("Failed to write to WAL: {}", e);
    // }

    HttpResponse::Ok().json(json!({ "id": id }))
}

async fn add_batch(
    state: web::Data<AppState>,
    req: web::Json<BatchAddRequest>,
) -> impl Responder {
    let index_name = req.index.trim();

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Index '{}' not found", index_name),
            }),
        }
    };

    let mut ids = Vec::new();
    let mut vectors = Vec::new();
    let mut docs = Vec::new();
    let mut fdb_metadata_batch: Vec<(i64, DocumentMetadata)> = Vec::new();

    let now_ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;

    for doc_req in &req.documents {
        if doc_req.vector.len() as c_int != bridge_index.vector_index.dimension {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: format!(
                    "Vector dimension mismatch: expected {}, got {}",
                    bridge_index.vector_index.dimension,
                    doc_req.vector.len()
                ),
            });
        }

        let id = bridge_index.vector_index.next_id.fetch_add(1, Ordering::SeqCst);
        let text_arc: Arc<str> = Arc::from(doc_req.text.as_str());

        // Build filter metadata
        let filter_metadata = FilterMetadata {
            filter_tags: doc_req.filter_tags.clone(),
            created_at: doc_req.created_at.unwrap_or(now_ts),
            filter_numerics: doc_req.filter_numerics.clone(),
        };

        ids.push(id);
        vectors.push(doc_req.vector.clone());

        let mut doc: Document = HashMap::new();
        doc.insert("body".to_string(), json!(doc_req.text));
        doc.insert("id".to_string(), json!(id));
        docs.push(doc);

        // Store text and filter metadata
        bridge_index.vector_index.text_map.insert(id, text_arc);
        bridge_index.vector_index.filter_map.insert(id, filter_metadata);

        // Collect FDB metadata if present
        if let Some(ref rich_meta) = doc_req.metadata {
            fdb_metadata_batch.push((id, DocumentMetadata {
                title: rich_meta.title.clone(),
                author: rich_meta.author.clone(),
                source_url: rich_meta.source_url.clone(),
                custom_fields: rich_meta.custom_fields.clone(),
            }));
        }
    }

    // Serialize ALL writes (FAISS + SeekStorm) to prevent concurrency issues
    {
        let _permit = bridge_index.text_write_semaphore.acquire().await.unwrap();

        // Batch add to FAISS
        if let Err(e) = faiss_add_batch(bridge_index.faiss_pool.clone(), bridge_index.vector_index.clone(), vectors.clone(), ids.clone()).await {
            return HttpResponse::InternalServerError().json(ErrorResponse { error: e });
        }

        // Batch add to text index
        bridge_index.text_index.index_documents(docs).await;
    }

    // Store rich metadata in FDB (best-effort, async)
    if !fdb_metadata_batch.is_empty() {
        let fdb = state.fdb.clone();
        let index_name_owned = index_name.to_string();
        tokio::spawn(async move {
            fdb.store_metadata_batch_best_effort(&index_name_owned, &fdb_metadata_batch).await;
        });
    }

    // Log to WAL (commented out for high-throughput benchmarking)
    // Uncomment for durability guarantees
    // for (id, doc_req) in ids.iter().zip(&req.documents) {
    //     if let Err(e) = bridge_index.wal.append(Operation::add(
    //         index_name.to_string(),
    //         *id,
    //         doc_req.text.clone(),
    //         doc_req.vector.clone(),
    //         Some(FilterMetadata { ... }),
    //     )) {
    //         error!("Failed to write to WAL: {}", e);
    //     }
    // }

    HttpResponse::Ok().json(json!({
        "message": format!("Added {} documents", ids.len()),
        "ids": ids
    }))
}

async fn delete_documents(
    state: web::Data<AppState>,
    req: web::Json<DeleteRequest>,
) -> impl Responder {
    let index_name = req.index.trim();

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Index '{}' not found", index_name),
            }),
        }
    };

    // Delete from FAISS, text map, and filter map
    if let Err(e) = faiss_delete_batch(bridge_index.vector_index.clone(), req.ids.clone()).await {
        return HttpResponse::InternalServerError().json(ErrorResponse { error: e });
    }

    // Also remove from filter_map
    for id in &req.ids {
        bridge_index.vector_index.filter_map.remove(id);
    }

    // Delete from FDB (best-effort, async)
    let fdb = state.fdb.clone();
    let index_name_owned = index_name.to_string();
    let ids_clone = req.ids.clone();
    tokio::spawn(async move {
        fdb.delete_documents_best_effort(&index_name_owned, &ids_clone).await;
    });

    // TODO: SeekStorm delete support when available

    // Log to WAL (commented out for high-throughput benchmarking)
    // Uncomment for durability guarantees
    // if let Err(e) = bridge_index.wal.append(Operation::delete(
    //     index_name.to_string(),
    //     req.ids.clone(),
    // )) {
    //     error!("Failed to write to WAL: {}", e);
    // }

    HttpResponse::Ok().json(json!({
        "message": format!("Deleted {} documents", req.ids.len())
    }))
}

async fn search(
    state: web::Data<AppState>,
    req: web::Json<SearchRequest>,
) -> impl Responder {
    let index_name = req.index.trim();

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Index '{}' not found", index_name),
            }),
        }
    };

    // Fetch more results than k to account for filtering
    let has_filters = !req.filter_tags.is_empty()
        || req.created_after.is_some()
        || req.created_before.is_some()
        || !req.numeric_filters.is_empty();

    // Fetch 3x k if filtering, to have enough results after filtering
    let fetch_k = if has_filters { (req.k * 3) as c_longlong } else { req.k as c_longlong };

    // True parallel search execution - vector on rayon pool, text on blocking pool
    // This achieves CPU parallelism since both searches are CPU-bound
    let text_index = bridge_index.text_index.clone();
    let text_query = req.text_query.clone();
    let text_offset = req.text_offset;
    let text_length = req.text_length.max(fetch_k as u64);

    let text_handle = match text_query {
        Some(query) if !query.is_empty() => {
            Some(tokio::task::spawn_blocking(move || {
                text_search_blocking(text_index, query, text_offset, text_length).ok()
            }))
        },
        _ => None,
    };

    // Vector search runs on dedicated rayon pool (already parallel)
    let vector_results = match &req.vector_query {
        Some(query) => {
            let query_arc = Arc::new(query.clone());
            vector_search(bridge_index.faiss_pool.clone(), bridge_index.vector_index.clone(), query_arc, fetch_k).await.ok()
        },
        None => None,
    };

    // Await text search completion (runs in parallel with vector search above)
    let text_results = match text_handle {
        Some(handle) => handle.await.ok().flatten(),
        None => None,
    };

    // Apply filters to raw results before RRF fusion
    let filtered_vector = vector_results.map(|v| {
        apply_filters(
            v,
            &bridge_index.vector_index.filter_map,
            &req.filter_tags,
            req.created_after,
            req.created_before,
            &req.numeric_filters,
        )
    });

    let filtered_text = text_results.map(|t| {
        apply_filters(
            t,
            &bridge_index.vector_index.filter_map,
            &req.filter_tags,
            req.created_after,
            req.created_before,
            &req.numeric_filters,
        )
    });

    let mut results = match (filtered_vector, filtered_text) {
        (Some(v), Some(t)) => {
            // Weighted RRF fusion
            weighted_rrf(v, t, req.vector_weight, req.text_weight, &bridge_index.vector_index.text_map)
        },
        (Some(v), None) => {
            // Vector only
            v.into_iter()
                .enumerate()
                .map(|(rank, (id, _dist))| RRFSearchResult {
                    id,
                    text: bridge_index.vector_index.text_map
                        .get(&id)
                        .map(|t| t.as_ref().to_string())
                        .unwrap_or_else(|| "Unknown".to_string()),
                    score: 1.0 / (DEFAULT_RRF_K + rank as f32),
                    vector_rank: Some(rank),
                    text_rank: None,
                    source: "vector".to_string(),
                    metadata: None,
                })
                .collect()
        },
        (None, Some(t)) => {
            // Text only
            t.into_iter()
                .enumerate()
                .map(|(rank, (id, _score))| RRFSearchResult {
                    id,
                    text: bridge_index.vector_index.text_map
                        .get(&id)
                        .map(|t| t.as_ref().to_string())
                        .unwrap_or_else(|| "Unknown".to_string()),
                    score: 1.0 / (DEFAULT_RRF_K + rank as f32),
                    vector_rank: None,
                    text_rank: Some(rank),
                    source: "text".to_string(),
                    metadata: None,
                })
                .collect()
        },
        (None, None) => {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: "At least one of vector_query or text_query must be provided".to_string(),
            });
        }
    };

    // Truncate to requested k
    results.truncate(req.k);

    // Enrich with FDB metadata if requested
    if req.include_metadata && !results.is_empty() {
        enrich_with_metadata(&mut results, index_name, &state.fdb).await;
    }

    HttpResponse::Ok().json(SearchResults {
        total: results.len(),
        results,
    })
}

/// MessagePack search endpoint - faster parsing for high-throughput scenarios
async fn search_msgpack(
    state: web::Data<AppState>,
    body: web::Bytes,
) -> impl Responder {
    // Deserialize from MessagePack
    let req: SearchRequest = match rmp_serde::from_slice(&body) {
        Ok(r) => r,
        Err(e) => return HttpResponse::BadRequest().json(ErrorResponse {
            error: format!("MessagePack parse error: {}", e),
        }),
    };

    let index_name = req.index.trim();

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Index '{}' not found", index_name),
            }),
        }
    };

    let k = req.k as c_longlong;

    // Parallel search execution
    let (vector_results, text_results) = tokio::join!(
        async {
            match &req.vector_query {
                Some(query) => {
                    let query_arc = Arc::new(query.clone());
                    vector_search(bridge_index.faiss_pool.clone(), bridge_index.vector_index.clone(), query_arc, k).await.ok()
                },
                None => None,
            }
        },
        async {
            match &req.text_query {
                Some(query) if !query.is_empty() => {
                    text_search(
                        bridge_index.text_index.clone(),
                        query,
                        req.text_offset,
                        req.text_length,
                    ).await.ok()
                },
                _ => None,
            }
        }
    );

    let results = match (vector_results, text_results) {
        (Some(v), Some(t)) => {
            weighted_rrf(v, t, req.vector_weight, req.text_weight, &bridge_index.vector_index.text_map)
        },
        (Some(v), None) => {
            v.into_iter()
                .enumerate()
                .map(|(rank, (id, _dist))| RRFSearchResult {
                    id,
                    text: bridge_index.vector_index.text_map
                        .get(&id)
                        .map(|t| t.as_ref().to_string())
                        .unwrap_or_else(|| "Unknown".to_string()),
                    score: 1.0 / (DEFAULT_RRF_K + rank as f32),
                    vector_rank: Some(rank),
                    text_rank: None,
                    source: "vector".to_string(),
                    metadata: None,
                })
                .collect()
        },
        (None, Some(t)) => {
            t.into_iter()
                .enumerate()
                .map(|(rank, (id, _score))| RRFSearchResult {
                    id,
                    text: bridge_index.vector_index.text_map
                        .get(&id)
                        .map(|t| t.as_ref().to_string())
                        .unwrap_or_else(|| "Unknown".to_string()),
                    score: 1.0 / (DEFAULT_RRF_K + rank as f32),
                    vector_rank: None,
                    text_rank: Some(rank),
                    source: "text".to_string(),
                    metadata: None,
                })
                .collect()
        },
        (None, None) => {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: "At least one of vector_query or text_query must be provided".to_string(),
            });
        }
    };

    // Return MessagePack response for consistency
    match rmp_serde::to_vec(&SearchResults { total: results.len(), results }) {
        Ok(bytes) => HttpResponse::Ok()
            .content_type("application/msgpack")
            .body(bytes),
        Err(_) => HttpResponse::InternalServerError().json(ErrorResponse {
            error: "Failed to serialize response".to_string(),
        }),
    }
}

/// Batch search endpoint - execute multiple queries in one call for maximum throughput
/// With window_ms > 0, the server will wait to accumulate more queries before executing
async fn batch_search(
    state: web::Data<AppState>,
    req: web::Json<BatchSearchRequest>,
) -> impl Responder {
    let start_time = std::time::Instant::now();
    let index_name = req.index.trim();

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Index '{}' not found", index_name),
            }),
        }
    };

    // Optional: wait for more queries if window_ms > 0
    if req.window_ms > 0 {
        tokio::time::sleep(tokio::time::Duration::from_millis(req.window_ms)).await;
    }

    let k = req.k as c_longlong;
    let num_queries = req.queries.len();

    // Collect all vector queries
    let vector_queries: Vec<Vec<f32>> = req.queries
        .iter()
        .filter_map(|q| q.vector_query.clone())
        .collect();

    // Execute batch vector search if we have any vector queries
    let batch_vector_results = if !vector_queries.is_empty() {
        match faiss_batch_search(
            bridge_index.faiss_pool.clone(),
            bridge_index.vector_index.clone(),
            vector_queries,
            k,
        ).await {
            Ok(results) => Some(results),
            Err(e) => {
                return HttpResponse::InternalServerError().json(ErrorResponse {
                    error: format!("Batch search failed: {}", e),
                });
            }
        }
    } else {
        None
    };

    // Build results for each query
    let mut all_results = Vec::with_capacity(num_queries);
    let mut vector_result_idx = 0;

    for query_item in &req.queries {
        let vector_results = if query_item.vector_query.is_some() {
            let results = batch_vector_results
                .as_ref()
                .map(|r| r.get(vector_result_idx).cloned())
                .flatten();
            vector_result_idx += 1;
            results
        } else {
            None
        };

        // Text search (still sequential for now - could be batched too)
        let text_results = match &query_item.text_query {
            Some(query) if !query.is_empty() => {
                text_search(
                    bridge_index.text_index.clone(),
                    query,
                    0,
                    100,
                ).await.ok()
            },
            _ => None,
        };

        let results = match (vector_results, text_results) {
            (Some(v), Some(t)) => {
                weighted_rrf(v, t, query_item.vector_weight, query_item.text_weight, &bridge_index.vector_index.text_map)
            },
            (Some(v), None) => {
                v.into_iter()
                    .enumerate()
                    .map(|(rank, (id, _dist))| RRFSearchResult {
                        id,
                        text: bridge_index.vector_index.text_map
                            .get(&id)
                            .map(|t| t.as_ref().to_string())
                            .unwrap_or_else(|| "Unknown".to_string()),
                        score: 1.0 / (DEFAULT_RRF_K + rank as f32),
                        vector_rank: Some(rank),
                        text_rank: None,
                        source: "vector".to_string(),
                        metadata: None,
                    })
                    .collect()
            },
            (None, Some(t)) => {
                t.into_iter()
                    .enumerate()
                    .map(|(rank, (id, _score))| RRFSearchResult {
                        id,
                        text: bridge_index.vector_index.text_map
                            .get(&id)
                            .map(|t| t.as_ref().to_string())
                            .unwrap_or_else(|| "Unknown".to_string()),
                        score: 1.0 / (DEFAULT_RRF_K + rank as f32),
                        vector_rank: None,
                        text_rank: Some(rank),
                        source: "text".to_string(),
                        metadata: None,
                    })
                    .collect()
            },
            (None, None) => Vec::new(),
        };

        all_results.push(SearchResults {
            total: results.len(),
            results,
        });
    }

    let elapsed_ms = start_time.elapsed().as_secs_f64() * 1000.0;

    HttpResponse::Ok().json(BatchSearchResponse {
        results: all_results,
        batch_size: num_queries,
        total_time_ms: elapsed_ms,
    })
}

async fn save_all_indices(state: web::Data<AppState>) -> impl Responder {
    let indices = state.indices.read().await;
    let base_path = PathBuf::from(INDICES_PATH);

    for (name, bridge_index) in indices.iter() {
        if let Err(e) = save_bridge_index(bridge_index, &base_path).await {
            error!("Failed to save index {}: {}", name, e);
        }
    }

    HttpResponse::Ok().json(json!({
        "message": format!("Saved {} indices", indices.len())
    }))
}

// ============================================================================
// FDB VIEWER ENDPOINTS
// ============================================================================

/// Serve the FDB viewer HTML page
async fn fdb_viewer() -> impl Responder {
    let html = include_str!("../static/fdb_viewer.html");
    HttpResponse::Ok()
        .content_type("text/html; charset=utf-8")
        .body(html)
}

/// List all available indices
async fn fdb_list_indices(state: web::Data<AppState>) -> impl Responder {
    let indices = state.indices.read().await;
    let index_names: Vec<&String> = indices.keys().collect();
    HttpResponse::Ok().json(json!({
        "indices": index_names
    }))
}

/// Query parameters for FDB list endpoint
#[derive(Deserialize)]
struct FdbListQuery {
    index: String,
}

/// List documents in an index (shows IDs and whether they have FDB metadata)
async fn fdb_list_documents(
    state: web::Data<AppState>,
    query: web::Query<FdbListQuery>,
) -> impl Responder {
    let index_name = query.index.trim();

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(json!({
                "error": format!("Index '{}' not found", index_name)
            })),
        }
    };

    // Get all document IDs from the text_map (in-memory)
    let mut documents: Vec<serde_json::Value> = Vec::new();
    for entry in bridge_index.vector_index.text_map.iter() {
        let id = *entry.key();
        let text = entry.value().as_ref();
        let title = text.chars().take(50).collect::<String>();

        // Check if filter metadata exists
        let has_filter = bridge_index.vector_index.filter_map.contains_key(&id);

        documents.push(json!({
            "id": id,
            "title": if title.len() < text.len() { format!("{}...", title) } else { title },
            "has_metadata": has_filter
        }));
    }

    // Sort by ID
    documents.sort_by(|a, b| {
        a["id"].as_i64().unwrap_or(0).cmp(&b["id"].as_i64().unwrap_or(0))
    });

    HttpResponse::Ok().json(json!({
        "index": index_name,
        "count": documents.len(),
        "documents": documents
    }))
}

/// Query parameters for FDB get endpoint
#[derive(Deserialize)]
struct FdbGetQuery {
    index: String,
    id: i64,
}

/// Get a specific document's metadata (both in-memory filter metadata and FDB rich metadata)
async fn fdb_get_document(
    state: web::Data<AppState>,
    query: web::Query<FdbGetQuery>,
) -> impl Responder {
    let index_name = query.index.trim();
    let doc_id = query.id;

    let bridge_index = {
        let indices = state.indices.read().await;
        match indices.get(index_name) {
            Some(idx) => idx.clone(),
            None => return HttpResponse::NotFound().json(json!({
                "error": format!("Index '{}' not found", index_name)
            })),
        }
    };

    // Get text from in-memory map
    let text = bridge_index.vector_index.text_map
        .get(&doc_id)
        .map(|t| t.as_ref().to_string());

    // Get filter metadata from in-memory map
    let filter_metadata = bridge_index.vector_index.filter_map
        .get(&doc_id)
        .map(|f| json!({
            "filter_tags": f.filter_tags,
            "created_at": f.created_at,
            "filter_numerics": f.filter_numerics
        }));

    // Get rich metadata from FDB (if available)
    let fdb_metadata = state.fdb.get_metadata(index_name, doc_id).await;

    let metadata_json = fdb_metadata.map(|m| json!({
        "title": m.title,
        "author": m.author,
        "source_url": m.source_url,
        "custom_fields": m.custom_fields
    }));

    if text.is_none() && filter_metadata.is_none() && metadata_json.is_none() {
        return HttpResponse::NotFound().json(json!({
            "error": format!("Document {} not found in index '{}'", doc_id, index_name)
        }));
    }

    HttpResponse::Ok().json(json!({
        "id": doc_id,
        "index": index_name,
        "text": text,
        "filter_metadata": filter_metadata,
        "metadata": metadata_json,
        "fdb_available": state.fdb.is_available()
    }))
}

// ============================================================================
// MAIN
// ============================================================================

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // CRITICAL: Disable OpenMP parallelism to avoid thread contention
    // FAISS uses OpenMP internally, which conflicts with Actix workers + Rayon pools
    // By setting OMP_NUM_THREADS=1, each FAISS search uses single-threaded SIMD (NEON/AVX)
    // while request-level parallelism is handled by Actix workers
    // This gives 30-40x better throughput on high-concurrency workloads
    std::env::set_var("OMP_NUM_THREADS", "1");

    env_logger::init();

    info!("Starting Bridge Search Server (OMP_NUM_THREADS=1 for optimal throughput)...");

    // Try to connect to FDB (best-effort - continues without it if unavailable)
    // FDB network initialization is handled inside OptionalFdbClient::try_new()
    let fdb_client = OptionalFdbClient::try_new();
    if fdb_client.is_available() {
        info!("FoundationDB connected - rich metadata storage enabled");
    } else {
        #[cfg(feature = "fdb")]
        info!("FoundationDB not available - continuing without rich metadata storage");
        #[cfg(not(feature = "fdb"))]
        info!("FoundationDB support not compiled - filter metadata stored in-memory only");
    }

    // Load existing indices on startup
    let base_path = PathBuf::from(INDICES_PATH);
    std::fs::create_dir_all(&base_path).ok();

    let mut loaded_indices = HashMap::new();

    if let Ok(entries) = std::fs::read_dir(&base_path) {
        for entry in entries.flatten() {
            if entry.path().is_dir() {
                if let Some(index_name) = entry.file_name().to_str() {
                    info!("Attempting to load index: {}", index_name);
                    match load_bridge_index(index_name, &base_path).await {
                        Ok(bridge_index) => {
                            info!("Successfully loaded index: {}", index_name);
                            loaded_indices.insert(index_name.to_string(), bridge_index);
                        },
                        Err(e) => {
                            error!("Failed to load index {}: {}", index_name, e);
                        }
                    }
                }
            }
        }
    }

    info!("Loaded {} indices", loaded_indices.len());

    let app_state = web::Data::new(AppState {
        indices: Arc::new(RwLock::new(loaded_indices)),
        op_counter: Arc::new(AtomicU64::new(0)),
        fdb: Arc::new(fdb_client),
    });

    // Clone for shutdown handler before moving into HttpServer
    let state_for_shutdown = app_state.clone();

    let server = HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .app_data(web::JsonConfig::default().limit(50 * 1024 * 1024))  // 50MB JSON limit for batch ops
            .app_data(web::PayloadConfig::default().limit(50 * 1024 * 1024))  // 50MB payload limit
            .route("/health", web::get().to(health))
            .route("/create_index", web::post().to(create_bridge_index_handler))
            .route("/add", web::post().to(add_document))
            .route("/add_batch", web::post().to(add_batch))
            .route("/delete", web::post().to(delete_documents))
            .route("/search", web::post().to(search))
            .route("/search_msgpack", web::post().to(search_msgpack))
            .route("/search_batch", web::post().to(batch_search))
            .route("/save", web::post().to(save_all_indices))
            // FDB Viewer endpoints
            .route("/fdb", web::get().to(fdb_viewer))
            .route("/fdb/indices", web::get().to(fdb_list_indices))
            .route("/fdb/list", web::get().to(fdb_list_documents))
            .route("/fdb/get", web::get().to(fdb_get_document))
    })
    .workers(16)      // Explicit worker count for high concurrency
    .backlog(4096)    // Handle burst traffic better
    .bind(("0.0.0.0", 8080))?;

    info!("Server running on http://0.0.0.0:8080");

    let server_handle = server.run();

    // Graceful shutdown handler
    tokio::spawn(async move {
        tokio::signal::ctrl_c().await.ok();
        info!("Shutting down gracefully...");

        let indices = state_for_shutdown.indices.read().await;
        let base_path = PathBuf::from(INDICES_PATH);

        for (name, bridge_index) in indices.iter() {
            if let Err(e) = save_bridge_index(bridge_index, &base_path).await {
                error!("Failed to save index {} during shutdown: {}", name, e);
            }
        }

        info!("All indices saved. Exiting.");
        std::process::exit(0);
    });

    server_handle.await
}
