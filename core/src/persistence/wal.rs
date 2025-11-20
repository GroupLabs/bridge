// Write-Ahead Log for durable operation logging
use anyhow::{Context, Result};
use crc32fast::Hasher;
use serde::{Deserialize, Serialize};
use std::fs::{File, OpenOptions};
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

/// Operations that can be logged to the WAL
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Operation {
    CreateIndex {
        name: String,
        dimension: i32,
        k: i64,
        timestamp: u64,
    },
    Add {
        index: String,
        id: i64,
        text: String,
        vector: Vec<f32>,
        timestamp: u64,
    },
    Delete {
        index: String,
        ids: Vec<i64>,
        timestamp: u64,
    },
    Checkpoint {
        snapshot_id: u64,
        timestamp: u64,
    },
}

impl Operation {
    fn timestamp(&self) -> u64 {
        match self {
            Operation::CreateIndex { timestamp, .. } => *timestamp,
            Operation::Add { timestamp, .. } => *timestamp,
            Operation::Delete { timestamp, .. } => *timestamp,
            Operation::Checkpoint { timestamp, .. } => *timestamp,
        }
    }

    fn current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64
    }

    pub fn create_index(name: String, dimension: i32, k: i64) -> Self {
        Operation::CreateIndex {
            name,
            dimension,
            k,
            timestamp: Self::current_timestamp(),
        }
    }

    pub fn add(index: String, id: i64, text: String, vector: Vec<f32>) -> Self {
        Operation::Add {
            index,
            id,
            text,
            vector,
            timestamp: Self::current_timestamp(),
        }
    }

    pub fn delete(index: String, ids: Vec<i64>) -> Self {
        Operation::Delete {
            index,
            ids,
            timestamp: Self::current_timestamp(),
        }
    }

    pub fn checkpoint(snapshot_id: u64) -> Self {
        Operation::Checkpoint {
            snapshot_id,
            timestamp: Self::current_timestamp(),
        }
    }
}

/// WAL entry format: [length: u32][crc32: u32][data: bytes]
#[derive(Debug)]
struct WalEntry {
    data: Vec<u8>,
    crc32: u32,
}

impl WalEntry {
    fn new(op: &Operation) -> Result<Self> {
        let data = serde_json::to_vec(op).context("Failed to serialize operation")?;
        let crc32 = Self::compute_crc32(&data);
        Ok(Self { data, crc32 })
    }

    fn compute_crc32(data: &[u8]) -> u32 {
        let mut hasher = Hasher::new();
        hasher.update(data);
        hasher.finalize()
    }

    fn write_to<W: Write>(&self, writer: &mut W) -> Result<()> {
        let len = self.data.len() as u32;
        writer.write_all(&len.to_le_bytes())?;
        writer.write_all(&self.crc32.to_le_bytes())?;
        writer.write_all(&self.data)?;
        Ok(())
    }

    fn read_from<R: Read>(reader: &mut R) -> Result<Option<Self>> {
        let mut len_bytes = [0u8; 4];
        match reader.read_exact(&mut len_bytes) {
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => return Ok(None),
            Err(e) => return Err(e.into()),
        }

        let len = u32::from_le_bytes(len_bytes) as usize;

        let mut crc_bytes = [0u8; 4];
        reader.read_exact(&mut crc_bytes)?;
        let expected_crc = u32::from_le_bytes(crc_bytes);

        let mut data = vec![0u8; len];
        reader.read_exact(&mut data)?;

        let actual_crc = Self::compute_crc32(&data);
        if actual_crc != expected_crc {
            anyhow::bail!("CRC32 mismatch: expected {}, got {}", expected_crc, actual_crc);
        }

        Ok(Some(Self {
            data,
            crc32: actual_crc,
        }))
    }

    fn to_operation(&self) -> Result<Operation> {
        serde_json::from_slice(&self.data).context("Failed to deserialize operation")
    }
}

/// Thread-safe WAL writer with buffering and periodic flushing
pub struct WalWriter {
    file: Arc<Mutex<BufWriter<File>>>,
    path: PathBuf,
    op_count: Arc<Mutex<u64>>,
}

impl WalWriter {
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        let path = path.as_ref().to_path_buf();

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)?;

        Ok(Self {
            file: Arc::new(Mutex::new(BufWriter::new(file))),
            path,
            op_count: Arc::new(Mutex::new(0)),
        })
    }

    pub fn append(&self, op: Operation) -> Result<()> {
        let entry = WalEntry::new(&op)?;

        let mut file = self.file.lock().unwrap();
        entry.write_to(&mut *file)?;

        let mut count = self.op_count.lock().unwrap();
        *count += 1;

        // Auto-flush every 100 operations for durability
        if *count % 100 == 0 {
            file.flush()?;
        }

        Ok(())
    }

    pub fn flush(&self) -> Result<()> {
        let mut file = self.file.lock().unwrap();
        file.flush()?;
        file.get_mut().sync_all()?;
        Ok(())
    }

    pub fn truncate(&self) -> Result<()> {
        let mut file = self.file.lock().unwrap();
        file.flush()?;
        drop(file);

        // Create new empty file
        let new_file = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&self.path)?;

        *self.file.lock().unwrap() = BufWriter::new(new_file);
        *self.op_count.lock().unwrap() = 0;

        Ok(())
    }
}

/// WAL reader for replaying operations
pub struct WalReader {
    reader: BufReader<File>,
}

impl WalReader {
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        let file = File::open(path)?;
        Ok(Self {
            reader: BufReader::new(file),
        })
    }

    pub fn read_all(&mut self) -> Result<Vec<Operation>> {
        let mut operations = Vec::new();

        loop {
            match WalEntry::read_from(&mut self.reader)? {
                Some(entry) => {
                    let op = entry.to_operation()?;
                    operations.push(op);
                }
                None => break,
            }
        }

        Ok(operations)
    }

    /// Read operations after a specific checkpoint
    pub fn read_since_checkpoint(&mut self, checkpoint_id: u64) -> Result<Vec<Operation>> {
        let all_ops = self.read_all()?;

        // Find the last checkpoint with this ID
        let mut checkpoint_idx = None;
        for (i, op) in all_ops.iter().enumerate().rev() {
            if let Operation::Checkpoint { snapshot_id, .. } = op {
                if *snapshot_id == checkpoint_id {
                    checkpoint_idx = Some(i);
                    break;
                }
            }
        }

        match checkpoint_idx {
            Some(idx) => Ok(all_ops.into_iter().skip(idx + 1).collect()),
            None => Ok(all_ops), // No checkpoint found, return all
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_wal_write_read() {
        let temp_dir = std::env::temp_dir().join("wal_test");
        fs::create_dir_all(&temp_dir).unwrap();
        let wal_path = temp_dir.join("test.wal");

        // Write operations
        {
            let writer = WalWriter::new(&wal_path).unwrap();
            writer.append(Operation::create_index("test".to_string(), 768, 10)).unwrap();
            writer.append(Operation::add(
                "test".to_string(),
                1,
                "hello world".to_string(),
                vec![1.0, 2.0, 3.0],
            )).unwrap();
            writer.flush().unwrap();
        }

        // Read operations
        {
            let mut reader = WalReader::new(&wal_path).unwrap();
            let ops = reader.read_all().unwrap();
            assert_eq!(ops.len(), 2);
        }

        // Cleanup
        fs::remove_dir_all(&temp_dir).unwrap();
    }
}
