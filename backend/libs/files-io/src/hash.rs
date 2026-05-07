use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::Path;
use crate::error::FileError;

/// Compute SHA-256 hash of a file, reading in chunks.
pub fn hash_file(path: &Path) -> Result<String, FileError> {
    let mut file = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 1024 * 1024]; // 1MB chunks for hashing
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 { break; }
        hasher.update(&buf[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

/// Compute SHA-256 hash of bytes.
pub fn hash_bytes(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}
