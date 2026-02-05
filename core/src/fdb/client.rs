// FDB client implementation using raw FFI bindings
// Only compiled with `fdb` feature

use super::bindings::*;
use super::keys::{doc_content_key, doc_metadata_key};
use super::DocumentMetadata;
use log::{error, info, warn};
use std::collections::HashMap;
use std::ffi::CString;
use std::ptr;
use std::sync::Arc;

/// FDB API version to use
const FDB_API_VERSION: i32 = 730;

/// Wrapper around FDB database handle
struct FdbDatabase {
    db: *mut FDBDatabase,
}

unsafe impl Send for FdbDatabase {}
unsafe impl Sync for FdbDatabase {}

impl Drop for FdbDatabase {
    fn drop(&mut self) {
        if !self.db.is_null() {
            unsafe {
                fdb_database_destroy(self.db);
            }
        }
    }
}

/// Wrapper around FDB transaction handle
struct FdbTransaction {
    tr: *mut FDBTransaction,
}

impl Drop for FdbTransaction {
    fn drop(&mut self) {
        if !self.tr.is_null() {
            unsafe {
                fdb_transaction_destroy(self.tr);
            }
        }
    }
}

/// Wrapper around FDB future handle
struct FdbFuture {
    future: *mut FDBFuture,
}

impl Drop for FdbFuture {
    fn drop(&mut self) {
        if !self.future.is_null() {
            unsafe {
                fdb_future_destroy(self.future);
            }
        }
    }
}

impl FdbFuture {
    /// Block until the future is ready
    fn wait(&self) -> Result<(), String> {
        unsafe {
            let err = fdb_future_block_until_ready(self.future);
            if err != 0 {
                return Err(format!("FDB future wait error: {}", err));
            }
            let err = fdb_future_get_error(self.future);
            if err != 0 {
                return Err(format!("FDB future error: {}", err));
            }
            Ok(())
        }
    }

    /// Get value from a get future
    fn get_value(&self) -> Result<Option<Vec<u8>>, String> {
        self.wait()?;
        unsafe {
            let mut present: fdb_bool_t = 0;
            let mut value: *const u8 = ptr::null();
            let mut value_length: i32 = 0;

            let err = fdb_future_get_value(self.future, &mut present, &mut value, &mut value_length);
            if err != 0 {
                return Err(format!("FDB get_value error: {}", err));
            }

            if present != 0 && !value.is_null() && value_length > 0 {
                let slice = std::slice::from_raw_parts(value, value_length as usize);
                Ok(Some(slice.to_vec()))
            } else {
                Ok(None)
            }
        }
    }
}

/// FDB client wrapper for Bridge
pub struct FdbClient {
    db: Arc<FdbDatabase>,
}

impl FdbClient {
    /// Initialize FDB network and create a client
    pub fn new() -> Result<Self, String> {
        unsafe {
            // Select API version
            let err = fdb_select_api_version_impl(FDB_API_VERSION, FDB_API_VERSION);
            if err != 0 {
                return Err(format!("Failed to select FDB API version: {}", err));
            }

            // Setup network
            let err = fdb_setup_network();
            if err != 0 {
                return Err(format!("Failed to setup FDB network: {}", err));
            }

            // Start network thread
            std::thread::spawn(|| {
                fdb_run_network();
            });

            // Create database connection (uses default cluster file)
            let mut db: *mut FDBDatabase = ptr::null_mut();

            // Use default cluster file path
            let cluster_file = CString::new("/usr/local/etc/foundationdb/fdb.cluster")
                .map_err(|_| "Invalid cluster file path")?;

            let err = fdb_create_database(cluster_file.as_ptr(), &mut db);
            if err != 0 {
                return Err(format!("Failed to create FDB database: {}", err));
            }

            if db.is_null() {
                return Err("FDB database is null".to_string());
            }

            Ok(Self {
                db: Arc::new(FdbDatabase { db }),
            })
        }
    }

    /// Create a new transaction
    fn create_transaction(&self) -> Result<FdbTransaction, String> {
        unsafe {
            let mut tr: *mut FDBTransaction = ptr::null_mut();
            let err = fdb_database_create_transaction(self.db.db, &mut tr);
            if err != 0 {
                return Err(format!("Failed to create transaction: {}", err));
            }
            Ok(FdbTransaction { tr })
        }
    }

    /// Set a key-value pair
    fn set(&self, key: &[u8], value: &[u8]) -> Result<(), String> {
        let tr = self.create_transaction()?;
        unsafe {
            fdb_transaction_set(
                tr.tr,
                key.as_ptr(),
                key.len() as i32,
                value.as_ptr(),
                value.len() as i32,
            );

            let future = FdbFuture {
                future: fdb_transaction_commit(tr.tr),
            };
            future.wait()
        }
    }

    /// Get a value by key
    fn get(&self, key: &[u8]) -> Result<Option<Vec<u8>>, String> {
        let tr = self.create_transaction()?;
        unsafe {
            let future = FdbFuture {
                future: fdb_transaction_get(tr.tr, key.as_ptr(), key.len() as i32, 0),
            };
            future.get_value()
        }
    }

    /// Clear a key
    fn clear(&self, key: &[u8]) -> Result<(), String> {
        let tr = self.create_transaction()?;
        unsafe {
            fdb_transaction_clear(tr.tr, key.as_ptr(), key.len() as i32);

            let future = FdbFuture {
                future: fdb_transaction_commit(tr.tr),
            };
            future.wait()
        }
    }

    /// Store document metadata
    pub async fn store_metadata(
        &self,
        index_name: &str,
        doc_id: i64,
        metadata: &DocumentMetadata,
    ) -> Result<(), String> {
        let key = doc_metadata_key(index_name, doc_id);
        let value = rmp_serde::to_vec(metadata)
            .map_err(|e| format!("Failed to serialize metadata: {}", e))?;

        // Run blocking FDB operation in a separate thread
        let db = self.db.clone();
        tokio::task::spawn_blocking(move || {
            let client = FdbClient { db };
            client.set(&key, &value)
        })
        .await
        .map_err(|e| format!("Task join error: {}", e))?
    }

    /// Batch store metadata
    pub async fn store_metadata_batch(
        &self,
        index_name: &str,
        docs: &[(i64, DocumentMetadata)],
    ) -> Result<(), String> {
        if docs.is_empty() {
            return Ok(());
        }

        // Prepare all key-value pairs
        let kvs: Vec<(Vec<u8>, Vec<u8>)> = docs
            .iter()
            .filter_map(|(doc_id, metadata)| {
                let key = doc_metadata_key(index_name, *doc_id);
                rmp_serde::to_vec(metadata).ok().map(|v| (key, v))
            })
            .collect();

        let db = self.db.clone();
        tokio::task::spawn_blocking(move || {
            let client = FdbClient { db };
            for (key, value) in kvs {
                client.set(&key, &value)?;
            }
            Ok(())
        })
        .await
        .map_err(|e| format!("Task join error: {}", e))?
    }

    /// Get document metadata
    pub async fn get_metadata(
        &self,
        index_name: &str,
        doc_id: i64,
    ) -> Result<Option<DocumentMetadata>, String> {
        let key = doc_metadata_key(index_name, doc_id);

        let db = self.db.clone();
        let result = tokio::task::spawn_blocking(move || {
            let client = FdbClient { db };
            client.get(&key)
        })
        .await
        .map_err(|e| format!("Task join error: {}", e))??;

        match result {
            Some(value) => {
                let metadata: DocumentMetadata = rmp_serde::from_slice(&value)
                    .map_err(|e| format!("Failed to deserialize metadata: {}", e))?;
                Ok(Some(metadata))
            }
            None => Ok(None),
        }
    }

    /// Batch get metadata
    pub async fn get_metadata_batch(
        &self,
        index_name: &str,
        doc_ids: &[i64],
    ) -> Result<HashMap<i64, DocumentMetadata>, String> {
        if doc_ids.is_empty() {
            return Ok(HashMap::new());
        }

        let keys: Vec<(i64, Vec<u8>)> = doc_ids
            .iter()
            .map(|id| (*id, doc_metadata_key(index_name, *id)))
            .collect();

        let db = self.db.clone();
        tokio::task::spawn_blocking(move || {
            let client = FdbClient { db };
            let mut results = HashMap::new();
            for (id, key) in keys {
                if let Ok(Some(value)) = client.get(&key) {
                    if let Ok(metadata) = rmp_serde::from_slice::<DocumentMetadata>(&value) {
                        results.insert(id, metadata);
                    }
                }
            }
            Ok(results)
        })
        .await
        .map_err(|e| format!("Task join error: {}", e))?
    }

    /// Delete document metadata and content
    pub async fn delete_documents_batch(
        &self,
        index_name: &str,
        doc_ids: &[i64],
    ) -> Result<(), String> {
        if doc_ids.is_empty() {
            return Ok(());
        }

        let keys: Vec<Vec<u8>> = doc_ids
            .iter()
            .flat_map(|id| {
                vec![
                    doc_metadata_key(index_name, *id),
                    doc_content_key(index_name, *id),
                ]
            })
            .collect();

        let db = self.db.clone();
        tokio::task::spawn_blocking(move || {
            let client = FdbClient { db };
            for key in keys {
                client.clear(&key)?;
            }
            Ok(())
        })
        .await
        .map_err(|e| format!("Task join error: {}", e))?
    }
}

/// Optional FDB client that gracefully degrades if FDB is unavailable
pub struct OptionalFdbClient {
    client: Option<FdbClient>,
}

impl OptionalFdbClient {
    /// Try to create an FDB client, but continue without it if unavailable
    pub fn try_new() -> Self {
        match FdbClient::new() {
            Ok(client) => {
                info!("FoundationDB connected successfully");
                Self { client: Some(client) }
            }
            Err(e) => {
                warn!("FoundationDB unavailable, continuing without metadata storage: {}", e);
                Self { client: None }
            }
        }
    }

    /// Check if FDB is available
    pub fn is_available(&self) -> bool {
        self.client.is_some()
    }

    /// Store metadata (best-effort, logs errors but doesn't fail)
    pub async fn store_metadata_best_effort(
        &self,
        index_name: &str,
        doc_id: i64,
        metadata: &DocumentMetadata,
    ) {
        if let Some(ref client) = self.client {
            if let Err(e) = client.store_metadata(index_name, doc_id, metadata).await {
                error!("Failed to store metadata in FDB: {}", e);
            }
        }
    }

    /// Batch store metadata (best-effort)
    pub async fn store_metadata_batch_best_effort(
        &self,
        index_name: &str,
        docs: &[(i64, DocumentMetadata)],
    ) {
        if let Some(ref client) = self.client {
            if let Err(e) = client.store_metadata_batch(index_name, docs).await {
                error!("Failed to batch store metadata in FDB: {}", e);
            }
        }
    }

    /// Get metadata (returns None if FDB unavailable)
    pub async fn get_metadata(
        &self,
        index_name: &str,
        doc_id: i64,
    ) -> Option<DocumentMetadata> {
        if let Some(ref client) = self.client {
            match client.get_metadata(index_name, doc_id).await {
                Ok(metadata) => metadata,
                Err(e) => {
                    error!("Failed to get metadata from FDB: {}", e);
                    None
                }
            }
        } else {
            None
        }
    }

    /// Batch get metadata (returns empty map if FDB unavailable)
    pub async fn get_metadata_batch(
        &self,
        index_name: &str,
        doc_ids: &[i64],
    ) -> HashMap<i64, DocumentMetadata> {
        if let Some(ref client) = self.client {
            match client.get_metadata_batch(index_name, doc_ids).await {
                Ok(metadata) => metadata,
                Err(e) => {
                    error!("Failed to batch get metadata from FDB: {}", e);
                    HashMap::new()
                }
            }
        } else {
            HashMap::new()
        }
    }

    /// Delete documents (best-effort)
    pub async fn delete_documents_best_effort(
        &self,
        index_name: &str,
        doc_ids: &[i64],
    ) {
        if let Some(ref client) = self.client {
            if let Err(e) = client.delete_documents_batch(index_name, doc_ids).await {
                error!("Failed to delete documents from FDB: {}", e);
            }
        }
    }
}

impl Clone for OptionalFdbClient {
    fn clone(&self) -> Self {
        Self {
            client: self.client.as_ref().map(|c| FdbClient {
                db: c.db.clone(),
            }),
        }
    }
}
