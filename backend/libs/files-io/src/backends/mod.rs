pub mod local;
pub mod s3;

use crate::error::FileError;
use std::collections::HashMap;

/// Metadata returned as a Python-compatible dict.
#[derive(Debug, Clone)]
pub struct FileMetadata {
    pub size: u64,
    pub mtime: f64,
    pub is_file: bool,
    pub is_dir: bool,
    pub is_symlink: bool,
    pub permissions: String,
    pub extra: HashMap<String, String>,
}

/// Trait for local and S3 backends.
pub trait FileOps: Send + Sync {
    fn read_all(&self, path: &str) -> Result<Vec<u8>, FileError>;
    fn read_chunk(&self, path: &str, offset: u64, size: u64) -> Result<Vec<u8>, FileError>;
    fn write(&self, path: &str, data: &[u8], create_parents: bool) -> Result<(), FileError>;
    #[allow(dead_code)]
    fn write_stream(&self, path: &str, reader: &mut dyn std::io::Read, create_parents: bool) -> Result<(), FileError>;
    fn exists(&self, path: &str) -> Result<bool, FileError>;
    fn metadata(&self, path: &str) -> Result<FileMetadata, FileError>;
    fn rename(&self, src: &str, dst: &str) -> Result<(), FileError>;
    fn copy(&self, src: &str, dst: &str) -> Result<(), FileError>;
    fn remove(&self, path: &str) -> Result<(), FileError>;
    fn remove_dir_all(&self, path: &str) -> Result<(), FileError>;
    fn list_dir(&self, path: &str) -> Result<Vec<String>, FileError>;
    #[allow(dead_code)]
    fn ensure_dir(&self, path: &str) -> Result<(), FileError>;
}
