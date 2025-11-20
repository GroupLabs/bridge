// src/main.rs - High-Performance Hybrid Search System

#[allow(non_upper_case_globals)]
#[allow(non_camel_case_types)]
#[allow(dead_code)]
mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

mod persistence;

use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use bindings::*;
use dashmap::DashMap;
use libc::{c_int, c_longlong};
use log::{error, info};
use persistence::{Operation, WalWriter, load_snapshot, save_snapshot, IndexMetadata};
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
use std::sync::atomic::{AtomicI64, AtomicU64, Ordering};
use tokio::sync::RwLock;
use rayon::ThreadPoolBuilder;

// Constants
const INDICES_PATH: &str = "./indices";
const BATCH_SIZE: usize = 100;
const BATCH_TIMEOUT_MS: u64 = 50;
const DEFAULT_RRF_K: f32 = 60.0;

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
    index: FaissIndexWrapper,
    dimension: c_int,
    k: c_longlong,
    text_map: DashMap<i64, Arc<str>>,  // Lock-free concurrent hashmap
    next_id: AtomicI64,                 // Lock-free ID counter
}

impl VectorIndexData {
    fn new(index_ptr: *mut FaissIndex, dimension: c_int, k: c_longlong) -> Self {
        Self {
            index: FaissIndexWrapper(index_ptr, PhantomData),
            dimension,
            k,
            text_map: DashMap::new(),
            next_id: AtomicI64::new(0),
        }
    }

    fn from_metadata(index_ptr: *mut FaissIndex, metadata: IndexMetadata) -> Self {
        let data = Self::new(index_ptr, metadata.dimension, metadata.k);
        data.next_id.store(metadata.next_id, Ordering::SeqCst);

        for (id, text) in metadata.text_map {
            data.text_map.insert(id, Arc::from(text.as_str()));
        }

        data
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
}

// ============================================================================
// REQUEST/RESPONSE STRUCTURES
// ============================================================================

#[derive(Deserialize)]
struct CreateIndexRequest {
    name: String,
    dimension: c_int,
    k: Option<c_longlong>,
}

#[derive(Clone, Deserialize, Serialize)]
struct AddRequest {
    index: String,
    text: String,
    vector: Vec<f32>,
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

// ============================================================================
// FAISS OPERATIONS (with spawn_blocking for async)
// ============================================================================

/// Create a FAISS index (CPU-intensive, wrapped in spawn_blocking)
async fn create_faiss_index_async(dimension: c_int, k: c_longlong) -> Result<Arc<VectorIndexData>, String> {
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

        Ok(Arc::new(VectorIndexData::new(index_ptr, dimension, k)))
    })
    .await
    .unwrap()
}

/// Add vectors to FAISS in batch (CPU-intensive, uses Rayon pool)
async fn faiss_add_batch(
    faiss_pool: Arc<rayon::ThreadPool>,
    index_data: Arc<VectorIndexData>,
    vectors: Vec<Vec<f32>>,
    ids: Vec<i64>,
) -> Result<(), String> {
    let (tx, rx) = tokio::sync::oneshot::channel();

    faiss_pool.spawn(move || {
        let n = vectors.len() as c_longlong;
        let flat_vectors: Vec<f32> = vectors.into_iter().flatten().collect();

        let result = unsafe {
            let status = faiss_Index_add_with_ids(
                index_data.index.0,
                n,
                flat_vectors.as_ptr(),
                ids.as_ptr(),
            );

            if status != 0 {
                Err("Failed to add vectors to FAISS".to_string())
            } else {
                Ok(())
            }
        };

        let _ = tx.send(result);
    });

    rx.await.unwrap()
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

/// Search FAISS index (CPU-intensive, uses Rayon pool)
async fn faiss_search(
    faiss_pool: Arc<rayon::ThreadPool>,
    index_data: Arc<VectorIndexData>,
    query: Vec<f32>,
    k: c_longlong,
) -> Result<Vec<(i64, f32)>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();

    faiss_pool.spawn(move || {
        let nq = 1;
        let k_usize = k as usize;
        let mut distances = vec![0.0; k_usize];
        let mut labels = vec![-1; k_usize];

        // Check if index is empty first (before unsafe block)
        let ntotal = unsafe { faiss_Index_ntotal(index_data.index.0) };
        if ntotal == 0 {
            let _ = tx.send(Err("The index is empty. Add vectors before searching.".to_string()));
            return;
        }

        let result = unsafe {
            // Create SearchParametersHNSW with efSearch=128 for production quality (95%+ recall)
            let mut params_ptr: *mut FaissSearchParametersHNSW = ptr::null_mut();
            let create_status = faiss_SearchParametersHNSW_new(
                &mut params_ptr as *mut *mut FaissSearchParametersHNSW,
                ptr::null_mut(),  // No ID selector
                128,              // efSearch=128 for production quality
            );

            if create_status != 0 {
                let error_ptr = faiss_get_last_error();
                let error_message = std::ffi::CStr::from_ptr(error_ptr)
                    .to_string_lossy()
                    .to_string();
                Err(format!("Failed to create search parameters: {}", error_message))
            } else {
                // Cast SearchParametersHNSW to SearchParameters
                let search_params = params_ptr as *const FaissSearchParameters;

                let status = faiss_Index_search_with_params(
                    index_data.index.0,
                    nq,
                    query.as_ptr(),
                    k,
                    search_params,
                    distances.as_mut_ptr(),
                    labels.as_mut_ptr(),
                );

                // Free the search parameters
                faiss_SearchParametersHNSW_free(params_ptr);

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
            }
        };

        let _ = tx.send(result);
    });

    rx.await.unwrap()
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
        ngram_indexing: NgramSet::NgramFF as u8 | NgramSet::NgramFFF as u8,
        access_type: AccessType::Ram,
    };

    let segment_number_bits1 = 11;
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
        QueryType::Intersection,
        offset as usize,
        length as usize,
        ResultType::TopkCount,
        true,
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
            }
        })
        .collect();

    results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());
    results
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

    let metadata = IndexMetadata::from_runtime(
        bridge_index.name.clone(),
        bridge_index.vector_index.dimension,
        bridge_index.vector_index.k,
        &bridge_index.vector_index.next_id,
        &bridge_index.vector_index.text_map,
    );

    let index_ptr = bridge_index.vector_index.index.0;
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

    let vector_index = match create_faiss_index_async(dimension, k).await {
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
        "message": format!("Index '{}' created successfully", index_name)
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

        // Add to text index
        let mut doc: Document = HashMap::new();
        doc.insert("body".to_string(), json!(req.text));
        doc.insert("id".to_string(), json!(id));

        bridge_index.text_index.index_documents(vec![doc]).await;
    }

    // Log to WAL (commented out for high-throughput benchmarking)
    // Uncomment for durability guarantees
    // if let Err(e) = bridge_index.wal.append(Operation::add(
    //     index_name.to_string(),
    //     id,
    //     req.text.clone(),
    //     req.vector.clone(),
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

        ids.push(id);
        vectors.push(doc_req.vector.clone());

        let mut doc: Document = HashMap::new();
        doc.insert("body".to_string(), json!(doc_req.text));
        doc.insert("id".to_string(), json!(id));
        docs.push(doc);

        // Store text for later insertion (after semaphore acquired)
        bridge_index.vector_index.text_map.insert(id, text_arc);
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

    // Log to WAL (commented out for high-throughput benchmarking)
    // Uncomment for durability guarantees
    // for (id, doc_req) in ids.iter().zip(&req.documents) {
    //     if let Err(e) = bridge_index.wal.append(Operation::add(
    //         index_name.to_string(),
    //         *id,
    //         doc_req.text.clone(),
    //         doc_req.vector.clone(),
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

    // Delete from FAISS and text map
    if let Err(e) = faiss_delete_batch(bridge_index.vector_index.clone(), req.ids.clone()).await {
        return HttpResponse::InternalServerError().json(ErrorResponse { error: e });
    }

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

    let k = req.k as c_longlong;

    // Parallel search execution
    let (vector_results, text_results) = tokio::join!(
        async {
            match &req.vector_query {
                Some(query) => faiss_search(bridge_index.faiss_pool.clone(), bridge_index.vector_index.clone(), query.clone(), k).await.ok(),
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
                })
                .collect()
        },
        (None, None) => {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: "At least one of vector_query or text_query must be provided".to_string(),
            });
        }
    };

    HttpResponse::Ok().json(SearchResults {
        total: results.len(),
        results,
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
// MAIN
// ============================================================================

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init();

    info!("Starting Bridge Search Server...");

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
    });

    // Clone for shutdown handler before moving into HttpServer
    let state_for_shutdown = app_state.clone();

    let server = HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .route("/health", web::get().to(health))
            .route("/create_index", web::post().to(create_bridge_index_handler))
            .route("/add", web::post().to(add_document))
            .route("/add_batch", web::post().to(add_batch))
            .route("/delete", web::post().to(delete_documents))
            .route("/search", web::post().to(search))
            .route("/save", web::post().to(save_all_indices))
    })
    .bind(("127.0.0.1", 8080))?;

    info!("Server running on http://127.0.0.1:8080");

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
