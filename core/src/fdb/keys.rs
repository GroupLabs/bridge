// FDB key schema helpers
// Key format: bridge/indices/{index_name}/docs/{document_id}/{suffix}
// Using simple byte encoding for keys

const BRIDGE_PREFIX: &[u8] = b"bridge";
const INDICES_PREFIX: &[u8] = b"indices";
const DOCS_PREFIX: &[u8] = b"docs";
const META_PREFIX: &[u8] = b"meta";
const SEPARATOR: u8 = b'/';

/// Create key for document metadata
/// Format: bridge/indices/{index_name}/docs/{doc_id}/metadata
pub fn doc_metadata_key(index_name: &str, doc_id: i64) -> Vec<u8> {
    let mut key = Vec::with_capacity(64);
    key.extend_from_slice(BRIDGE_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(INDICES_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(index_name.as_bytes());
    key.push(SEPARATOR);
    key.extend_from_slice(DOCS_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(&doc_id.to_be_bytes());
    key.push(SEPARATOR);
    key.extend_from_slice(b"metadata");
    key
}

/// Create key for document content (large text)
/// Format: bridge/indices/{index_name}/docs/{doc_id}/content
pub fn doc_content_key(index_name: &str, doc_id: i64) -> Vec<u8> {
    let mut key = Vec::with_capacity(64);
    key.extend_from_slice(BRIDGE_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(INDICES_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(index_name.as_bytes());
    key.push(SEPARATOR);
    key.extend_from_slice(DOCS_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(&doc_id.to_be_bytes());
    key.push(SEPARATOR);
    key.extend_from_slice(b"content");
    key
}

/// Create key for index configuration/info
/// Format: bridge/indices/{index_name}/meta/info
pub fn index_info_key(index_name: &str) -> Vec<u8> {
    let mut key = Vec::with_capacity(64);
    key.extend_from_slice(BRIDGE_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(INDICES_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(index_name.as_bytes());
    key.push(SEPARATOR);
    key.extend_from_slice(META_PREFIX);
    key.push(SEPARATOR);
    key.extend_from_slice(b"info");
    key
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_key_formats() {
        let meta_key = doc_metadata_key("my_index", 123);
        assert!(!meta_key.is_empty());

        let content_key = doc_content_key("my_index", 123);
        assert!(!content_key.is_empty());

        let info_key = index_info_key("my_index");
        assert!(!info_key.is_empty());

        // Keys should be different
        assert_ne!(meta_key, content_key);
        assert_ne!(meta_key, info_key);
    }

    #[test]
    fn test_key_ordering() {
        // Same index, different doc IDs should be ordered (using big-endian)
        let key1 = doc_metadata_key("test", 1);
        let key2 = doc_metadata_key("test", 2);
        let key3 = doc_metadata_key("test", 100);

        assert!(key1 < key2);
        assert!(key2 < key3);
    }
}
