// Persistence for Descartes index
// Save/load graph, quantizer, and storage to disk

use crate::descartes::{
    graph::FullyNavigatableGraph,
    quantization::{ScalarQuantizer, QuantizedVectorStorage},
    ContiguousVectorStorage, DescartesConfig, DescartesIndex,
};
use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs::File;
use std::io::{BufReader, BufWriter};
use std::path::Path;

/// Serializable snapshot of a Descartes index
#[derive(Serialize, Deserialize)]
pub struct DescartesSnapshot {
    /// Configuration
    pub config: DescartesConfig,
    /// Quantizer state
    pub quantizer: ScalarQuantizer,
    /// Quantized vector storage
    pub storage: QuantizedVectorStorage,
    /// Graph structure
    pub graph: FullyNavigatableGraph,
    /// Original vectors for reranking
    pub original_vectors: Vec<Vec<f32>>,
    /// ID mapping
    pub id_map: Vec<i64>,
}

impl DescartesSnapshot {
    /// Create snapshot from index
    pub fn from_index(index: &DescartesIndex) -> Self {
        // Convert ContiguousVectorStorage to Vec<Vec<f32>> for serialization
        let original_vectors: Vec<Vec<f32>> = (0..index.original_vectors.len())
            .map(|i| index.original_vectors.get_vector(i).to_vec())
            .collect();

        Self {
            config: index.config.clone(),
            quantizer: index.quantizer.clone(),
            storage: index.storage.clone(),
            graph: index.graph.clone(),
            original_vectors,
            id_map: index.id_map.clone(),
        }
    }

    /// Restore index from snapshot
    pub fn into_index(self) -> DescartesIndex {
        let mut reverse_id_map = std::collections::HashMap::new();
        for (idx, &id) in self.id_map.iter().enumerate() {
            reverse_id_map.insert(id, idx);
        }

        // Convert Vec<Vec<f32>> back to ContiguousVectorStorage
        let original_vectors = ContiguousVectorStorage::from_vectors(
            &self.original_vectors,
            self.config.dimension,
        );

        DescartesIndex {
            config: self.config,
            quantizer: self.quantizer,
            storage: self.storage,
            graph: self.graph,
            original_vectors,
            id_map: self.id_map,
            reverse_id_map,
        }
    }
}

/// Save Descartes index to a file using bincode
pub fn save_descartes_index(index: &DescartesIndex, path: &Path) -> Result<()> {
    let snapshot = DescartesSnapshot::from_index(index);

    let file = File::create(path)
        .with_context(|| format!("Failed to create file: {:?}", path))?;
    let writer = BufWriter::new(file);

    bincode::serialize_into(writer, &snapshot)
        .with_context(|| "Failed to serialize Descartes index")?;

    Ok(())
}

/// Load Descartes index from a file
pub fn load_descartes_index(path: &Path) -> Result<DescartesIndex> {
    let file = File::open(path)
        .with_context(|| format!("Failed to open file: {:?}", path))?;
    let reader = BufReader::new(file);

    let snapshot: DescartesSnapshot = bincode::deserialize_from(reader)
        .with_context(|| "Failed to deserialize Descartes index")?;

    Ok(snapshot.into_index())
}

/// Save Descartes index to snapshot directory (compatible with existing snapshot system)
pub fn save_descartes_snapshot(
    index: &DescartesIndex,
    index_name: &str,
    base_path: &Path,
) -> Result<std::path::PathBuf> {
    use std::time::{SystemTime, UNIX_EPOCH};

    let snapshot_dir = base_path.join(index_name).join("snapshots");
    std::fs::create_dir_all(&snapshot_dir)?;

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64;

    let snapshot_path = snapshot_dir.join(format!("{}", timestamp));
    std::fs::create_dir_all(&snapshot_path)?;

    // Save Descartes index
    let descartes_path = snapshot_path.join("descartes.bin");
    save_descartes_index(index, &descartes_path)?;

    // Save metadata for compatibility
    let metadata = DescartesMetadata {
        name: index_name.to_string(),
        dimension: index.config.dimension,
        num_vectors: index.len(),
        timestamp,
    };

    let metadata_path = snapshot_path.join("metadata.json");
    let metadata_json = serde_json::to_string_pretty(&metadata)?;
    std::fs::write(&metadata_path, metadata_json)?;

    // Create "latest" symlink
    let latest_path = snapshot_dir.join("latest");
    let _ = std::fs::remove_file(&latest_path);

    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(&snapshot_path, &latest_path)?;
    }

    #[cfg(not(unix))]
    {
        std::fs::write(&latest_path, snapshot_path.to_str().unwrap())?;
    }

    Ok(snapshot_path)
}

/// Load Descartes index from snapshot directory
pub fn load_descartes_snapshot(
    index_name: &str,
    base_path: &Path,
) -> Result<DescartesIndex> {
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
            std::path::PathBuf::from(std::fs::read_to_string(&latest_path)?)
        }
    } else {
        // Fallback: find most recent snapshot
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

    let descartes_path = snapshot_path.join("descartes.bin");
    load_descartes_index(&descartes_path)
}

/// Metadata for Descartes snapshots
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DescartesMetadata {
    pub name: String,
    pub dimension: usize,
    pub num_vectors: usize,
    pub timestamp: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::descartes::DescartesIndex;
    use tempfile::tempdir;

    #[test]
    fn test_save_load_roundtrip() {
        let config = crate::descartes::DescartesConfig::new(4);
        let mut index = DescartesIndex::new(config);

        let vectors = vec![
            vec![1.0, 0.0, 0.0, 0.0],
            vec![0.0, 1.0, 0.0, 0.0],
            vec![0.0, 0.0, 1.0, 0.0],
        ];
        let ids = vec![100, 101, 102];

        index.build_with_ids(&vectors, &ids);

        // Save
        let dir = tempdir().unwrap();
        let path = dir.path().join("test_index.bin");
        save_descartes_index(&index, &path).unwrap();

        // Load
        let loaded = load_descartes_index(&path).unwrap();

        assert_eq!(loaded.len(), index.len());
        assert_eq!(loaded.config.dimension, index.config.dimension);
        assert_eq!(loaded.id_map, index.id_map);
    }

    #[test]
    fn test_snapshot_system() {
        let config = crate::descartes::DescartesConfig::new(4);
        let mut index = DescartesIndex::new(config);

        let vectors = vec![
            vec![1.0, 2.0, 3.0, 4.0],
            vec![5.0, 6.0, 7.0, 8.0],
        ];
        let ids = vec![1, 2];

        index.build_with_ids(&vectors, &ids);

        let dir = tempdir().unwrap();
        let base_path = dir.path();

        // Save snapshot
        save_descartes_snapshot(&index, "test_index", base_path).unwrap();

        // Load snapshot
        let loaded = load_descartes_snapshot("test_index", base_path).unwrap();

        assert_eq!(loaded.len(), 2);

        // Search should work
        let results = loaded.search(&[1.0, 2.0, 3.0, 4.0], 1);
        assert!(!results.is_empty());
    }
}
