// Snapshot persistence for FAISS indices and metadata
use anyhow::{Context, Result};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::ffi::CString;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicI64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::bindings::*;

// Wrapper to make FaissIndex pointer Send-safe
struct SendFaissIndex(*mut FaissIndex);
unsafe impl Send for SendFaissIndex {}

/// Metadata for a Bridge index (FAISS + SeekStorm)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexMetadata {
    pub name: String,
    pub dimension: i32,
    pub k: i64,
    pub next_id: i64,
    pub text_map: HashMap<i64, String>,
    pub snapshot_id: u64,
    pub timestamp: u64,
}

impl IndexMetadata {
    pub fn new(name: String, dimension: i32, k: i64) -> Self {
        Self {
            name,
            dimension,
            k,
            next_id: 0,
            text_map: HashMap::new(),
            snapshot_id: Self::current_timestamp(),
            timestamp: Self::current_timestamp(),
        }
    }

    fn current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64
    }

    pub fn from_runtime(
        name: String,
        dimension: i32,
        k: i64,
        next_id: &AtomicI64,
        text_map: &DashMap<i64, Arc<str>>,
    ) -> Self {
        let mut map = HashMap::new();
        for entry in text_map.iter() {
            map.insert(*entry.key(), entry.value().as_ref().to_string());
        }

        Self {
            name,
            dimension,
            k,
            next_id: next_id.load(Ordering::SeqCst),
            text_map: map,
            snapshot_id: Self::current_timestamp(),
            timestamp: Self::current_timestamp(),
        }
    }
}

/// Save a FAISS index and its metadata to disk
pub fn save_snapshot(
    index_name: &str,
    faiss_index: *mut FaissIndex,
    metadata: &IndexMetadata,
    base_path: &Path,
) -> Result<PathBuf> {
    let snapshot_dir = base_path.join(index_name).join("snapshots");
    std::fs::create_dir_all(&snapshot_dir)?;

    let snapshot_id = metadata.snapshot_id;
    let snapshot_path = snapshot_dir.join(format!("{}", snapshot_id));
    std::fs::create_dir_all(&snapshot_path)?;

    // Save FAISS index
    let faiss_path = snapshot_path.join("faiss.index");
    let c_path = CString::new(faiss_path.to_str().unwrap())
        .context("Failed to create CString")?;
    let mode = CString::new("wb").unwrap();

    unsafe {
        use libc::fopen;
        let file = fopen(c_path.as_ptr(), mode.as_ptr());
        if file.is_null() {
            anyhow::bail!("Failed to open file for writing FAISS index");
        }

        let result = faiss_write_index(faiss_index, file as *mut crate::bindings::FILE);
        libc::fclose(file);

        if result != 0 {
            anyhow::bail!("Failed to write FAISS index, error code: {}", result);
        }
    }

    // Save metadata
    let metadata_path = snapshot_path.join("metadata.json");
    let metadata_json = serde_json::to_string_pretty(metadata)
        .context("Failed to serialize metadata")?;
    std::fs::write(&metadata_path, metadata_json)
        .context("Failed to write metadata file")?;

    // Create "latest" symlink (or marker file on Windows)
    let latest_path = snapshot_dir.join("latest");
    let _ = std::fs::remove_file(&latest_path); // Ignore if doesn't exist

    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(&snapshot_path, &latest_path)?;
    }

    #[cfg(not(unix))]
    {
        // On Windows, write the path to a text file
        std::fs::write(&latest_path, snapshot_path.to_str().unwrap())?;
    }

    Ok(snapshot_path)
}

/// Load a FAISS index and its metadata from disk
pub fn load_snapshot(
    index_name: &str,
    base_path: &Path,
) -> Result<(*mut FaissIndex, IndexMetadata)> {
    let snapshot_dir = base_path.join(index_name).join("snapshots");

    if !snapshot_dir.exists() {
        anyhow::bail!("No snapshots found for index: {}", index_name);
    }

    // Find latest snapshot
    let latest_path = snapshot_dir.join("latest");
    let snapshot_path = if latest_path.exists() {
        #[cfg(unix)]
        {
            std::fs::read_link(&latest_path)?
        }

        #[cfg(not(unix))]
        {
            PathBuf::from(std::fs::read_to_string(&latest_path)?)
        }
    } else {
        // Fallback: find the most recent snapshot by timestamp
        let mut snapshots: Vec<_> = std::fs::read_dir(&snapshot_dir)?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .collect();

        snapshots.sort_by_key(|e| {
            e.path()
                .file_name()
                .and_then(|n| n.to_str())
                .and_then(|n| n.parse::<u64>().ok())
                .unwrap_or(0)
        });

        snapshots
            .last()
            .ok_or_else(|| anyhow::anyhow!("No valid snapshots found"))?
            .path()
    };

    // Load metadata
    let metadata_path = snapshot_path.join("metadata.json");
    let metadata_json = std::fs::read_to_string(&metadata_path)
        .context("Failed to read metadata file")?;
    let metadata: IndexMetadata = serde_json::from_str(&metadata_json)
        .context("Failed to parse metadata")?;

    // Load FAISS index
    let faiss_path = snapshot_path.join("faiss.index");
    let c_path = CString::new(faiss_path.to_str().unwrap())
        .context("Failed to create CString")?;
    let mode = CString::new("rb").unwrap();

    let faiss_index = unsafe {
        use libc::fopen;
        let file = fopen(c_path.as_ptr(), mode.as_ptr());
        if file.is_null() {
            anyhow::bail!("Failed to open file for reading FAISS index");
        }

        let mut index_ptr: *mut FaissIndex = std::ptr::null_mut();
        let result = faiss_read_index(file as *mut crate::bindings::FILE, 0, &mut index_ptr);

        libc::fclose(file);

        if result != 0 {
            anyhow::bail!("Failed to read FAISS index, error code: {}", result);
        }

        if index_ptr.is_null() {
            anyhow::bail!("FAISS index pointer is null");
        }

        index_ptr
    };

    Ok((faiss_index, metadata))
}

/// List all available snapshots for an index
pub fn list_snapshots(index_name: &str, base_path: &Path) -> Result<Vec<u64>> {
    let snapshot_dir = base_path.join(index_name).join("snapshots");

    if !snapshot_dir.exists() {
        return Ok(Vec::new());
    }

    let mut snapshot_ids = Vec::new();

    for entry in std::fs::read_dir(&snapshot_dir)? {
        let entry = entry?;
        if entry.path().is_dir() {
            if let Some(name) = entry.file_name().to_str() {
                if let Ok(id) = name.parse::<u64>() {
                    snapshot_ids.push(id);
                }
            }
        }
    }

    snapshot_ids.sort_unstable();
    Ok(snapshot_ids)
}

/// Clean up old snapshots, keeping only the N most recent
pub fn cleanup_old_snapshots(
    index_name: &str,
    base_path: &Path,
    keep_count: usize,
) -> Result<()> {
    let mut snapshots = list_snapshots(index_name, base_path)?;

    if snapshots.len() <= keep_count {
        return Ok(());
    }

    snapshots.sort_unstable();
    let to_delete = snapshots.len() - keep_count;

    let snapshot_dir = base_path.join(index_name).join("snapshots");

    for &snapshot_id in &snapshots[..to_delete] {
        let snapshot_path = snapshot_dir.join(snapshot_id.to_string());
        if snapshot_path.exists() {
            std::fs::remove_dir_all(&snapshot_path)?;
        }
    }

    Ok(())
}
