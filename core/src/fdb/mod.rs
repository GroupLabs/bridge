// FoundationDB integration for rich metadata storage
// Bridge stores filter-critical metadata in-memory, FDB stores rich metadata
//
// This module provides both real FDB client (with `fdb` feature) and a no-op
// stub that allows the system to work without FDB installed.

#[cfg(feature = "fdb")]
mod bindings {
    #![allow(non_upper_case_globals)]
    #![allow(non_camel_case_types)]
    #![allow(non_snake_case)]
    #![allow(dead_code)]
    include!(concat!(env!("OUT_DIR"), "/fdb_bindings.rs"));
}

#[cfg(feature = "fdb")]
pub mod client;

#[cfg(feature = "fdb")]
pub mod keys;

#[cfg(feature = "fdb")]
pub use client::OptionalFdbClient;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Rich metadata stored in FoundationDB (not needed for filtering)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DocumentMetadata {
    pub title: Option<String>,
    pub author: Option<String>,
    pub source_url: Option<String>,
    #[serde(default)]
    pub custom_fields: HashMap<String, serde_json::Value>,
}

impl Default for DocumentMetadata {
    fn default() -> Self {
        Self {
            title: None,
            author: None,
            source_url: None,
            custom_fields: HashMap::new(),
        }
    }
}

// Stub implementation when FDB feature is not enabled
#[cfg(not(feature = "fdb"))]
pub struct OptionalFdbClient;

#[cfg(not(feature = "fdb"))]
impl OptionalFdbClient {
    pub fn try_new() -> Self {
        OptionalFdbClient
    }

    pub fn is_available(&self) -> bool {
        false
    }

    pub async fn store_metadata_best_effort(
        &self,
        _index_name: &str,
        _doc_id: i64,
        _metadata: &DocumentMetadata,
    ) {
        // No-op when FDB is not available
    }

    pub async fn store_metadata_batch_best_effort(
        &self,
        _index_name: &str,
        _docs: &[(i64, DocumentMetadata)],
    ) {
        // No-op when FDB is not available
    }

    pub async fn get_metadata(
        &self,
        _index_name: &str,
        _doc_id: i64,
    ) -> Option<DocumentMetadata> {
        None
    }

    pub async fn get_metadata_batch(
        &self,
        _index_name: &str,
        _doc_ids: &[i64],
    ) -> HashMap<i64, DocumentMetadata> {
        HashMap::new()
    }

    pub async fn delete_documents_best_effort(
        &self,
        _index_name: &str,
        _doc_ids: &[i64],
    ) {
        // No-op when FDB is not available
    }
}

#[cfg(not(feature = "fdb"))]
impl Clone for OptionalFdbClient {
    fn clone(&self) -> Self {
        OptionalFdbClient
    }
}
