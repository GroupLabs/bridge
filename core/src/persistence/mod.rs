// Persistence layer for Bridge indices
pub mod wal;
pub mod snapshot;

pub use wal::{WalWriter, Operation};
pub use snapshot::{save_snapshot, load_snapshot, IndexMetadata};
