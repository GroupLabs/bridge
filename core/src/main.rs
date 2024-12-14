// src/main.rs

#[allow(non_upper_case_globals)] // Suppress non upper case globals warning
#[allow(non_camel_case_types)] // Suppress non camel case warning
#[allow(dead_code)] // Suppress function not used warning
mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

use actix_web::rt::{self, System};
use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use bindings::__sFILE;
use bindings::*;
use libc::{c_int, c_longlong};
use libc::{fclose, fopen, FILE};
use log::{error, info};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::ffi::CString;
use std::fs;
use std::marker::PhantomData;
use std::path::{Path, PathBuf};
use std::ptr;
use std::sync::{Arc, Mutex};

// Wrapper around the raw FAISS index pointer
struct FaissIndexWrapper(*mut FaissIndex_H, PhantomData<*const ()>);

// Implement Send and Sync for the wrapper
unsafe impl Send for FaissIndexWrapper {}
unsafe impl Sync for FaissIndexWrapper {}

// Structure representing each FAISS index and its associated data
struct IndexData {
    index: FaissIndexWrapper,
    dimension: c_int,
    k: c_longlong,
    text_map: Mutex<HashMap<c_longlong, String>>,
    next_id: Mutex<c_longlong>,
}

// Shared state for the Actix application managing multiple indices
struct AppState {
    indices: Arc<Mutex<HashMap<String, Arc<IndexData>>>>, // Map of index name to IndexData
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
#[derive(Serialize)]
struct SearchResult {
    neighbors: Vec<Neighbor>,
}

#[derive(Serialize)]
struct Neighbor {
    text: String,
    distance: f32,
}

// Structure for error responses
#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

// Handler for health
async fn health() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy"
    }))
}

// Handler for creating a new FAISS index
async fn create_vector_index(
    state: web::Data<AppState>,
    req: web::Json<CreateIndexRequest>,
) -> impl Responder {
    let raw_index_name = req.name.trim();
    let dimension = req.dimension;
    let k = req.k.unwrap_or(5); // Default k to 5 if not provided

    if raw_index_name.is_empty() {
        let response = ErrorResponse {
            error: "Index name cannot be empty.".to_string(),
        };
        return HttpResponse::BadRequest().json(response);
    }

    // Enforce naming convention: name_dXXXX
    let index_name = format!("{}_d{}", raw_index_name, dimension);

    let mut indices = state.indices.lock().unwrap();
    if indices.contains_key(&index_name) {
        let response = ErrorResponse {
            error: format!("Index '{}' already exists.", index_name),
        };
        return HttpResponse::BadRequest().json(response);
    }

    // **Updated Metric Description to include IDMap**
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
            let error_message = std::ffi::CStr::from_ptr(error).to_string_lossy();
            let response = ErrorResponse {
                error: format!("Error creating FAISS index: {}", error_message),
            };
            return HttpResponse::InternalServerError().json(response);
        }
    }

    // Initialize IndexData
    let index_data = Arc::new(IndexData {
        index: FaissIndexWrapper(index_ptr, PhantomData),
        dimension,
        k,
        text_map: Mutex::new(HashMap::new()),
        next_id: Mutex::new(0), // Start IDs from 0 for each index
    });

    // Insert the new index into the indices map
    indices.insert(index_name.clone(), index_data);

    HttpResponse::Ok().json(serde_json::json!({
        "message": format!("Index '{}' created successfully.", index_name)
    }))
}

// Handler for adding vectors with associated text to a specific index
async fn add(state: web::Data<AppState>, item: web::Json<AddRequest>) -> impl Responder {
    let raw_index_name = item.index.trim();
    let text = item.text.clone();
    let vector = item.vector.clone();

    // Retrieve all indices to find matches with the specified name (regardless of dimension)
    let indices = state.indices.lock().unwrap();
    let matching_indices: Vec<(String, Arc<IndexData>)> = indices
        .iter()
        .filter(|(name, _)| name.starts_with(raw_index_name))
        .map(|(name, data)| (name.clone(), data.clone()))
        .collect();

    if matching_indices.is_empty() {
        let response = ErrorResponse {
            error: format!("No index found with base name '{}'.", raw_index_name),
        };
        return HttpResponse::BadRequest().json(response);
    } else if matching_indices.len() > 1 {
        let response = ErrorResponse {
            error: format!(
                "Multiple indices found with base name '{}'. Please specify the dimension.",
                raw_index_name
            ),
        };
        return HttpResponse::BadRequest().json(response);
    }

    let (index_name, index_data) = &matching_indices[0];
    drop(indices); // Release the lock early

    // Validate vector dimension
    if vector.len() as c_int != index_data.dimension {
        let error_message = format!(
            "Vector has incorrect dimension: expected {}, got {}",
            index_data.dimension,
            vector.len()
        );
        let response = ErrorResponse {
            error: error_message,
        };
        return HttpResponse::BadRequest().json(response);
    }

    // Assign a unique ID
    let id = {
        let mut id_lock = index_data.next_id.lock().unwrap();
        let current_id = *id_lock;
        *id_lock += 1;
        current_id
    };

    // Add the vector to FAISS
    unsafe {
        let index_ptr = index_data.index.0;

        // FAISS uses labels as IDs; ensure labels are unique
        faiss_Index_add_with_ids(
            index_ptr,
            1,                        // Number of vectors to add
            vector.as_ptr(),          // Pointer to the vector data
            &id as *const c_longlong, // Pointer to the ID
        );

        // **Debugging: Check the total number of vectors after addition**
        let ntotal = faiss_Index_ntotal(index_ptr);
        println!(
            "Added vector with ID {} to index '{}'. Total vectors in index: {}",
            id, index_name, ntotal
        );
    }

    // Associate the text with the ID
    {
        let mut map = index_data.text_map.lock().unwrap();
        map.insert(id, text);
    }

    // Respond with success and the assigned ID
    HttpResponse::Ok().json(serde_json::json!({ "id": id }))
}

// Handler for searching within a specific FAISS index
async fn search_vector_index(
    state: web::Data<AppState>,
    req: web::Json<SearchRequest>,
) -> impl Responder {
    let raw_index_name = req.index.trim();
    let queries = req.queries.clone();

    // Retrieve all indices to find matches with the specified name (regardless of dimension)
    let indices = state.indices.lock().unwrap();
    let matching_indices: Vec<(String, Arc<IndexData>)> = indices
        .iter()
        .filter(|(name, _)| name.starts_with(raw_index_name))
        .map(|(name, data)| (name.clone(), data.clone()))
        .collect();

    if matching_indices.is_empty() {
        let response = ErrorResponse {
            error: format!("No index found with base name '{}'.", raw_index_name),
        };
        return HttpResponse::BadRequest().json(response);
    } else if matching_indices.len() > 1 {
        let response = ErrorResponse {
            error: format!(
                "Multiple indices found with base name '{}'. Please specify the dimension.",
                raw_index_name
            ),
        };
        return HttpResponse::BadRequest().json(response);
    }

    let (index_name, index_data) = &matching_indices[0];
    drop(indices); // Release the lock early

    // **Debugging: Check the total number of vectors before search**
    unsafe {
        let ntotal = faiss_Index_ntotal(index_data.index.0);
        println!(
            "Performing search on index '{}'. Total vectors in index: {}",
            index_name, ntotal
        );
        if ntotal == 0 {
            let response = ErrorResponse {
                error: "The index is empty. Add vectors before searching.".to_string(),
            };
            return HttpResponse::BadRequest().json(response);
        }
    }

    let nq = queries.len() as c_longlong;
    let k = index_data.k;

    if nq == 0 {
        let response = ErrorResponse {
            error: "No query vectors provided.".to_string(),
        };
        return HttpResponse::BadRequest().json(response);
    }

    // Validate query vectors
    for (i, vec) in queries.iter().enumerate() {
        if vec.len() as c_int != index_data.dimension {
            let error_message = format!(
                "Query vector {} has incorrect dimension: expected {}, got {}",
                i,
                index_data.dimension,
                vec.len()
            );
            let response = ErrorResponse {
                error: error_message,
            };
            return HttpResponse::BadRequest().json(response);
        }
    }

    // Flatten the query vectors
    let flat_queries: Vec<f32> = queries.into_iter().flatten().collect();

    let mut distances = vec![0.0; (nq * k) as usize];
    let mut labels = vec![-1; (nq * k) as usize];

    // Perform the search
    unsafe {
        let index_ptr = index_data.index.0;

        let search_status = faiss_Index_search(
            index_ptr,
            nq,
            flat_queries.as_ptr(),
            k,
            distances.as_mut_ptr(),
            labels.as_mut_ptr(),
        );

        if search_status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error).to_string_lossy();
            let response = ErrorResponse {
                error: error_message.to_string(),
            };
            return HttpResponse::InternalServerError().json(response);
        }
    }

    // Retrieve the text associated with each neighbor ID
    let text_map = index_data.text_map.lock().unwrap();
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

    HttpResponse::Ok().json(results)
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

    // Initialize shared state with an empty indices map
    let app_state = web::Data::new(AppState {
        indices: Arc::new(Mutex::new(HashMap::new())),
    });

    // Load existing indices from the storage directory
    load_existing_indices(storage_dir, &app_state).await;

    // Clone `app_state` for use in the shutdown handler
    let app_state_for_shutdown = app_state.clone();

    // Set up the Actix Web server
    let server = HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .route("/health", web::get().to(health))
            .route("/create_vector_index", web::post().to(create_vector_index))
            .route("/vector_search", web::post().to(search_vector_index))
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

        info!("Shutdown signal received. Saving all indices...");

        // Save all indices to disk
        if let Ok(indices) = app_state_for_shutdown.indices.lock() {
            if let Err(err) = save_all_indices(&indices) {
                error!("Error saving indices during shutdown: {}", err);
            } else {
                info!("All indices saved successfully.");
            }
        } else {
            error!("Failed to acquire lock on indices during shutdown.");
        }

        // Stop the Actix system
        System::current().stop();
    });

    // Await the server's completion
    server.await
}

// Function to load existing indices on startup
async fn load_existing_indices(storage_dir: &Path, app_state: &web::Data<AppState>) {
    let entries = match fs::read_dir(storage_dir) {
        Ok(entries) => entries,
        Err(e) => {
            error!(
                "Failed to read storage directory '{:?}': {}",
                storage_dir, e
            );
            return;
        }
    };

    for entry in entries {
        if let Ok(entry) = entry {
            let path = entry.path();
            if path.is_file() {
                if let Some(extension) = path.extension() {
                    if extension == "index" {
                        let index_name = match path.file_stem() {
                            Some(name) => name.to_string_lossy().into_owned(),
                            None => {
                                error!("Failed to get index name from file '{:?}'.", path);
                                continue;
                            }
                        };

                        // Parse the dimension from the index name (expected format: name_dXXXX)
                        let parts: Vec<&str> = index_name.rsplitn(2, "_d").collect();
                        if parts.len() != 2 {
                            error!(
                                "Index name '{}' does not follow the 'name_dXXXX' format.",
                                index_name
                            );
                            continue;
                        }

                        // let _base_name = parts[1]; // Unused variable removed
                        let dimension_str = parts[0];
                        let dimension: c_int = match dimension_str.parse() {
                            Ok(d) => d,
                            Err(_) => {
                                error!(
                                    "Failed to parse dimension from index name '{}'.",
                                    index_name
                                );
                                continue;
                            }
                        };

                        // Load the index from disk
                        match load_faiss_index(&path, dimension) {
                            Ok(index_ptr) => {
                                // Initialize IndexData
                                let index_data = Arc::new(IndexData {
                                    index: FaissIndexWrapper(index_ptr, PhantomData),
                                    dimension,
                                    k: 5, // Default value; adjust if necessary
                                    text_map: Mutex::new(HashMap::new()),
                                    next_id: Mutex::new(0), // Placeholder; adjust if necessary
                                });

                                // Insert into the indices map
                                let mut indices = app_state.indices.lock().unwrap();
                                indices.insert(index_name.clone(), index_data);
                                info!("Loaded existing index '{}' from '{:?}'.", index_name, path);
                            }
                            Err(e) => {
                                error!("Failed to load FAISS index from '{:?}': {}", path, e);
                            }
                        }
                    }
                }
            }
        }
    }
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

        let index_dimension = { faiss_Index_d(index_ptr) };
        if index_dimension != dimension {
            return Err(format!(
                "Dimension mismatch: expected {}, got {}.",
                dimension, index_dimension
            ));
        }

        Ok(index_ptr)
    }
}

fn save_all_indices(indices: &HashMap<String, Arc<IndexData>>) -> Result<(), String> {
    for (index_name, index_data) in indices.iter() {
        let save_path = format!("indices/{}.index", index_name);
        let index_ptr = index_data.index.0;

        unsafe {
            // Convert the save_path to a C-compatible string
            let c_path = CString::new(save_path.clone()).map_err(|e| e.to_string())?;

            // Open the file in write-binary mode
            let mode = CString::new("wb").unwrap();
            let file: *mut FILE = fopen(c_path.as_ptr(), mode.as_ptr());
            if file.is_null() {
                return Err(format!("Failed to open file '{}' for writing.", save_path));
            }

            // Cast *mut FILE to *mut __sFILE
            let file_ptr = file as *mut __sFILE;

            // Call faiss_write_index with the correct pointer types
            let status = faiss_write_index(index_ptr, file_ptr);
            if status != 0 {
                let error = faiss_get_last_error();
                let error_message = if !error.is_null() {
                    std::ffi::CStr::from_ptr(error)
                        .to_string_lossy()
                        .into_owned()
                } else {
                    "Unknown error occurred while writing the index.".to_string()
                };
                // Close the file before returning
                fclose(file);
                return Err(format!(
                    "Failed to save index '{}': {}",
                    index_name, error_message
                ));
            }

            // Close the file after writing
            fclose(file);
        }
    }
    Ok(())
}
