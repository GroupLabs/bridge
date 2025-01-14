// src/main.rs

#[allow(non_upper_case_globals)]
#[allow(non_camel_case_types)]
#[allow(dead_code)]
mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

use actix_web::rt::{self, System};
use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use bindings::*;
use libc::{c_int, c_longlong};
use libc::{fclose, fopen, FILE};
use log::{error, info};
use seekstorm::commit::Commit;
use seekstorm::highlighter::{highlighter, Highlight};
use seekstorm::index::{
    create_index, AccessType, DistanceField, Document, FileType, Index, IndexDocument,
    IndexDocuments, IndexMetaObject, SimilarityType, TokenizerType,
};
use seekstorm::search::{QueryType, ResultType, Search};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::HashMap;
use std::collections::HashSet;
use std::ffi::CString;
// use std::fmt::Result;
use std::fs;
use std::marker::PhantomData;
use std::path::{Path, PathBuf};
use std::ptr;
use std::sync::Arc;
use tokio::sync::Mutex as AsyncMutex;
use tokio::sync::RwLock;

// Wrapper around the raw FAISS index pointer
struct FaissIndexWrapper(*mut FaissIndex, PhantomData<*const ()>);

// Implement Send and Sync for the wrapper
unsafe impl Send for FaissIndexWrapper {}
unsafe impl Sync for FaissIndexWrapper {}

// Structure representing each FAISS index and its associated data
struct VectorIndexData {
    index: FaissIndexWrapper,
    dimension: c_int,
    k: c_longlong,
    text_map: std::sync::Mutex<HashMap<c_longlong, String>>,
    next_id: std::sync::Mutex<c_longlong>,
}

// Structure for creating a new index
#[derive(Deserialize)]
struct CreateIndexRequest {
    name: String,          // Unique name for the index (without dimension)
    dimension: c_int,      // Dimension of the vectors
    k: Option<c_longlong>, // Optional: number of nearest neighbors to retrieve
}

// Structure for adding vectors with text to a specific index
#[derive(Deserialize)]
struct AddRequest {
    index: String, // Name of the index to add the vector to (without dimension)
    text: String,
    vector: Vec<f32>,
}

// Structure for searching within a specific index
#[derive(Deserialize)]
struct SearchRequest {
    index: String,          // Name of the index to search in (without dimension)
    queries: Vec<Vec<f32>>, // List of query vectors
}

// Structure for search results
#[derive(Debug, Serialize, Deserialize)]
struct SearchResult {
    neighbors: Vec<Neighbor>,
}

#[derive(Debug, Serialize, Deserialize)]
struct Neighbor {
    text: String,
    distance: f32,
}

// Structure for error responses
#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

#[derive(Clone)]
struct BridgeIndex {
    // Vector index (FAISS)
    vector_index: Arc<VectorIndexData>,
    // Text index (SeekStorm)
    text_index: Arc<RwLock<Index>>,
}

#[derive(Debug, Serialize, Deserialize)]
struct CombinedSearchResults {
    vector_results: Vec<SearchResult>, // or whatever your vector results struct is
    text_results: Vec<TextSearchDoc>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TextSearchDoc {
    pub doc_id: u64,
    pub score: f32,
    pub body: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct CombinedSearchRequest {
    pub index_name: String,
    pub vector_queries: Vec<Vec<f32>>,
    pub text_query: String,
    pub text_offset: u64,
    pub text_length: u64,
}

// Application state containing all indices
struct AppState {
    indices: Arc<AsyncMutex<HashMap<String, BridgeIndex>>>, // Unified index storage
}

// Handler for health
async fn health() -> impl Responder {
    HttpResponse::Ok().json(json!({ "status": "healthy" }))
}

// load bridge index (load on boot)
// save bridge index
// add
// delete
// search
// close indices and save on down

// create faiss index
fn create_faiss_index(dimension: c_int, k: c_longlong) -> Result<Arc<VectorIndexData>, String> {
    let metric_description = CString::new("IDMap,Flat").unwrap();
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

    let faiss_index_data = Arc::new(VectorIndexData {
        index: FaissIndexWrapper(index_ptr, PhantomData),
        dimension,
        k,
        text_map: std::sync::Mutex::new(HashMap::new()),
        next_id: std::sync::Mutex::new(0),
    });

    Ok(faiss_index_data)
}

// create text index
fn create_seekstorm_index(
    index_name: &str,
    index_path: &Path,
) -> Result<Arc<RwLock<Index>>, String> {
    let schema_json = r#"
    [{"field":"body","field_type":"Text","stored":true,"indexed":true}]"#;
    let schema = serde_json::from_str(schema_json).expect("Invalid schema JSON");

    let meta = IndexMetaObject {
        id: 0,
        name: index_name.to_string(),
        similarity: SimilarityType::Bm25f,
        tokenizer: TokenizerType::AsciiAlphabetic,
        access_type: AccessType::Mmap,
    };

    let serialize_schema = true;
    let segment_number_bits = 11;

    let new_index = create_index(
        index_path,
        meta,
        &schema,
        serialize_schema,
        &Vec::new(),
        segment_number_bits,
        false,
    )
    .expect("Failed to create index");

    let text_index = Arc::new(RwLock::new(new_index));

    Ok(text_index)
}

// create bridge index
async fn create_bridge_index(
    state: web::Data<AppState>,
    req: web::Json<CreateIndexRequest>,
) -> impl Responder {
    let raw_index_name = req.name.trim();
    let dimension = req.dimension;
    let k = req.k.unwrap_or(5);

    // Construct a "full" index name, e.g., "my_index_d768"
    let index_name = format!("{}_d{}", raw_index_name, dimension);

    // Check if index already exists in memory
    {
        let indices = state.indices.lock().await;
        if indices.contains_key(&index_name) {
            let response = json!({ "error": format!("Index '{}' already exists.", index_name) });
            return HttpResponse::BadRequest().json(response);
        }
    }

    // Create the directory structure for storing the index files
    let index_path_string = format!("./indices/{}", index_name);
    let index_path = Path::new(&index_path_string);

    if !index_path.exists() {
        fs::create_dir_all(index_path).expect("Failed to create index directory");
    }

    // Create the FAISS index
    let faiss_index = match create_faiss_index(dimension, k) {
        Ok(idx) => idx,
        Err(e) => {
            let response = json!({ "error": e });
            return HttpResponse::InternalServerError().json(response);
        }
    };

    // Create the SeekStorm text index
    let text_index = match create_seekstorm_index(&index_name, index_path) {
        Ok(tidx) => tidx,
        Err(e) => {
            let response = json!({ "error": e });
            return HttpResponse::InternalServerError().json(response);
        }
    };

    // Create the combined BridgeIndex and store it in AppState
    {
        let mut indices = state.indices.lock().await;
        indices.insert(
            index_name.clone(),
            BridgeIndex {
                vector_index: faiss_index.clone(),
                text_index: text_index.clone(),
            },
        );
    }

    // Return a success response
    HttpResponse::Ok().json(json!({
        "message": format!("Index '{}' created successfully.", index_name)
    }))
}

// Helper function to find an index by base name
async fn find_index(
    state: &web::Data<AppState>,
    raw_index_name: &str,
) -> Result<(String, BridgeIndex), ErrorResponse> {
    let indices = state.indices.lock().await;
    let matching_indices: Vec<(String, BridgeIndex)> = indices
        .iter()
        .filter(|(name, _)| name.starts_with(raw_index_name))
        .map(|(name, data)| (name.clone(), data.clone()))
        .collect();
    drop(indices);

    match matching_indices.len() {
        0 => Err(ErrorResponse {
            error: format!("No index found with base name '{}'.", raw_index_name),
        }),
        1 => Ok(matching_indices[0].clone()),
        _ => Err(ErrorResponse {
            error: format!(
                "Multiple indices found with base name '{}'. Please specify the dimension.",
                raw_index_name
            ),
        }),
    }
}

// Add handler
async fn add(state: web::Data<AppState>, item: web::Json<AddRequest>) -> impl Responder {
    let raw_index_name = item.index.trim();
    let text = item.text.clone();
    let vector = item.vector.clone();

    let (_, bridge_index) = match find_index(&state, raw_index_name).await {
        Ok(res) => res,
        Err(err) => return HttpResponse::BadRequest().json(err),
    };

    // Validate vector dimension
    if vector.len() as c_int != bridge_index.vector_index.dimension {
        let error_message = format!(
            "Vector has incorrect dimension: expected {}, got {}",
            bridge_index.vector_index.dimension,
            vector.len()
        );
        return HttpResponse::BadRequest().json(ErrorResponse {
            error: error_message,
        });
    }

    // Assign a unique ID
    let id = {
        let mut id_lock = bridge_index.vector_index.next_id.lock().unwrap();
        let current_id = *id_lock;
        *id_lock += 1;
        current_id
    };

    // Add the vector to FAISS
    unsafe {
        let index_ptr = bridge_index.vector_index.index.0;
        faiss_Index_add_with_ids(
            index_ptr,
            1, // Number of vectors
            vector.as_ptr(),
            &id as *const c_longlong,
        );
    }

    // Associate the text with the ID
    {
        let mut map = bridge_index.vector_index.text_map.lock().unwrap();
        map.insert(id, text.clone());
    }

    println!("Adding to text index");

    // Index documents
    let mut text_idx = bridge_index.text_index;

    // let document_json = r#"
    //     {"body":"body1 here"}
    // "#;

    // let document: Document = serde_json::from_str(document_json).unwrap();

    // text_idx.index_document(document, FileType::None).await;
    // text_idx.commit().await; // unneccessary

    // Add the document to the SeekStorm text index
    let mut doc: Document = HashMap::new();
    doc.insert("body".to_string(), json!(text.clone()));
    doc.insert("id".to_string(), json!(id));

    text_idx.index_documents(vec![doc]).await;
    text_idx.commit().await; // unneccessary

    println!("Added vector with ID {} to index", id);

    HttpResponse::Ok().json(json!({ "id": id }))
}

// Handler for searching within a specific FAISS index
/// A pure function that takes a `BridgeIndex` plus query vectors, and returns either
/// a list of `SearchResult` objects or an error string.
///
/// This function does **not** deal with any HTTP/Actix or concurrency logic.
///
/// - `index_data`: reference to the combined `BridgeIndex` (which includes Faiss & SeekStorm)
/// - `queries`: a list of vectors (each a `Vec<f32>`) that we want to search against the Faiss index.
fn vector_search(
    index_data: &BridgeIndex,
    queries: Vec<Vec<f32>>,
) -> Result<Vec<SearchResult>, String> {
    use std::ffi::CStr;

    let nq = queries.len() as c_longlong;
    if nq == 0 {
        return Err("No query vectors provided.".into());
    }

    // Check that each query matches the dimension of the index
    for (i, q) in queries.iter().enumerate() {
        if q.len() as c_int != index_data.vector_index.dimension {
            let msg = format!(
                "Query vector {} has incorrect dimension: expected {}, got {}",
                i,
                index_data.vector_index.dimension,
                q.len()
            );
            return Err(msg);
        }
    }

    // Flatten the queries: e.g., from Vec<Vec<f32>> into a single Vec<f32>
    let flat_queries: Vec<f32> = queries.into_iter().flatten().collect();

    // Prepare buffers for distances and labels
    let nq_usize = nq as usize;
    let k = index_data.vector_index.k;
    let total_size = nq_usize * (k as usize);

    let mut distances = vec![0.0; total_size];
    let mut labels = vec![-1; total_size];

    // Perform the Faiss search
    unsafe {
        let faiss_idx_ptr = index_data.vector_index.index.0;

        // Check total vectors in the index
        let ntotal = faiss_Index_ntotal(faiss_idx_ptr);
        if ntotal == 0 {
            return Err("The index is empty. Add vectors before searching.".to_string());
        }

        // Actually call Faiss
        let search_status = faiss_Index_search(
            faiss_idx_ptr,
            nq,
            flat_queries.as_ptr(),
            k,
            distances.as_mut_ptr(),
            labels.as_mut_ptr(),
        );

        if search_status != 0 {
            let error_ptr = faiss_get_last_error();
            let error_message = CStr::from_ptr(error_ptr).to_string_lossy().to_string();
            return Err(error_message);
        }
    }

    // Retrieve the text associated with each neighbor ID
    let text_map = index_data.vector_index.text_map.lock().unwrap();

    let results: Vec<SearchResult> = (0..nq)
        .map(|i| {
            let start = (i * k) as usize;
            let end = start + k as usize;
            let neighbors = labels[start..end]
                .iter()
                .zip(distances[start..end].iter())
                .filter(|(&id, _)| id != -1)
                .map(|(&id, &dist)| Neighbor {
                    text: text_map
                        .get(&id)
                        .cloned()
                        .unwrap_or_else(|| "Unknown".to_string()),
                    distance: dist,
                })
                .collect();
            SearchResult { neighbors }
        })
        .collect();

    Ok(results)
}

async fn text_search(
    index_data: &BridgeIndex,
    query: &str,
    offset: u64,
    length: u64,
) -> Result<Vec<TextSearchDoc>, String> {
    // Parameters for the search
    let query_type = QueryType::Intersection;
    let result_type = ResultType::TopkCount;
    let include_uncommitted = true;
    let field_filter = Vec::new();
    let query_facets = Vec::new();
    let facet_filter = Vec::new();
    let highlight_config = vec![Highlight {
        field: "body".to_string(),
        name: String::new(),
        fragment_number: 2,
        fragment_size: 160,
        highlight_markup: true,
    }];

    let index_arc = index_data.text_index.clone();

    // Perform the search
    let result_object = index_arc
        .search(
            query.to_owned(),
            query_type,
            offset.try_into().unwrap(),
            length.try_into().unwrap(),
            result_type,
            include_uncommitted,
            field_filter,
            query_facets,
            facet_filter,
            Vec::new(), // distance_fields
        )
        .await;

    // Log search details
    println!("Search complete");
    println!("Number of results: {}", result_object.results.len());
    println!("Result Object: {:#?}", result_object);

    // Prepare highlighter
    let highlighter = Some(
        highlighter(
            &index_arc,
            highlight_config,
            result_object.query_terms.clone(),
        )
        .await,
    );

    let return_fields_filter = HashSet::new();
    let distance_fields: &[DistanceField] = &[];

    // Acquire write lock to retrieve documents
    let index = index_arc.write().await;

    // Collect document results
    let mut docs = Vec::new();
    for result in result_object.results.iter() {
        let doc = match index.get_document(
            result.doc_id,
            false,
            &highlighter,
            &return_fields_filter,
            distance_fields,
        ) {
            Ok(d) => d,
            Err(e) => {
                return Err(format!(
                    "Failed to retrieve document {}: {}",
                    result.doc_id, e
                ));
            }
        };

        let body_field = doc.get("body").and_then(|v| v.as_str().map(String::from));

        docs.push(TextSearchDoc {
            doc_id: result.doc_id as u64, // Explicit conversion
            score: result.score,
            body: body_field,
        });
    }

    Ok(docs)
}

pub async fn search_both_indexes(
    state: web::Data<AppState>,
    req: web::Json<CombinedSearchRequest>,
) -> impl Responder {
    let index_name = req.index_name.trim();

    // 1. Find the BridgeIndex
    let (_, index_data) = match find_index(&state, index_name).await {
        Ok(res) => res,
        Err(err) => return HttpResponse::BadRequest().json(err),
    };

    // 2. Vector search (pure function)
    let vector_results = match vector_search(&index_data, req.vector_queries.clone()) {
        Ok(r) => r,
        Err(msg) => return HttpResponse::BadRequest().json(ErrorResponse { error: msg }),
    };

    // 3. Text search (pure async function)
    let text_results = match text_search(
        &index_data,
        &req.text_query,
        req.text_offset,
        req.text_length,
    )
    .await
    {
        Ok(r) => r,
        Err(msg) => return HttpResponse::BadRequest().json(ErrorResponse { error: msg }),
    };

    // 4. Combine or return them in a single response
    let combined_results = CombinedSearchResults {
        vector_results,
        text_results,
    };

    HttpResponse::Ok().json(json!({
        "results": combined_results
    }))
}

// Function to load a FAISS index from a given path
fn load_faiss_index(path: &PathBuf, dimension: c_int) -> Result<*mut FaissIndex, String> {
    let path_str = path.to_str().ok_or("Invalid path string")?;
    let c_path = CString::new(path_str).map_err(|e| e.to_string())?;

    unsafe {
        // Open the file in binary read mode
        let mode = CString::new("rb").unwrap();
        let file: *mut FILE = libc::fopen(c_path.as_ptr(), mode.as_ptr());
        if file.is_null() {
            return Err("Failed to open index file.".to_string());
        }

        let mut index_ptr: *mut FaissIndex = ptr::null_mut();
        let status = faiss_read_index(file as *mut __sFILE, 0, &mut index_ptr);

        // Close the file after reading
        libc::fclose(file);

        if status != 0 {
            let error = faiss_get_last_error();
            let error_message = if !error.is_null() {
                std::ffi::CStr::from_ptr(error)
                    .to_string_lossy()
                    .into_owned()
            } else {
                "Unknown error occurred while reading the index.".to_string()
            };
            return Err(error_message);
        }

        if index_ptr.is_null() {
            return Err("FAISS returned a null index pointer.".to_string());
        }

        let index_dimension = faiss_Index_d(index_ptr);
        if index_dimension != dimension {
            return Err(format!(
                "Dimension mismatch: expected {}, got {}.",
                dimension, index_dimension
            ));
        }

        Ok(index_ptr)
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Initialize the logger
    env_logger::init();

    // Define the indices storage directory
    let storage_dir = Path::new("indices");
    if !storage_dir.exists() {
        fs::create_dir(storage_dir)?;
        info!("Created storage directory at '{:?}'.", storage_dir);
    } else {
        info!("Using existing storage directory at '{:?}'.", storage_dir);
    }

    // Initialize shared state with an empty indices map using async-aware Mutex
    let app_state = web::Data::new(AppState {
        indices: Arc::new(AsyncMutex::new(HashMap::new())),
    });

    // Set up the Actix Web server
    let server = HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .route("/health", web::get().to(health))
            .route("/create_index", web::post().to(create_bridge_index))
            .route("/search", web::post().to(search_both_indexes))
            .route("/add", web::post().to(add))
    })
    .bind(("127.0.0.1", 8080))?;

    // Spawn a shutdown handler
    let server = server.run();
    rt::spawn(async move {
        // Wait for a shutdown signal (Ctrl+C)
        rt::signal::ctrl_c()
            .await
            .expect("Failed to listen for shutdown signal");

        info!("Shutdown signal received. Cleanup if necessary...");

        // Stop the Actix system
        System::current().stop();
    });

    // Await the server's completion
    server.await
}
