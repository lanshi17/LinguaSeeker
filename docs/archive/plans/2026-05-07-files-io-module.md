# files-io Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a PyO3 native extension (`files_io`) providing unified local + S3 file I/O, folder compress/extract, parallel batch operations, and hash-based deduplication for the LinguaSeeker backend.

**Architecture:** Trait-based backend abstraction (`FileOps`) with local (`std::fs`) and S3 (`aws-sdk-s3`) implementations. `File` Python class auto-dispatches by path scheme (`/local/path` vs `s3://bucket/key`). Core operations are sync; heavy operations (large copy, compress, extract, parallel batch) provide async versions via `tokio::task::spawn_blocking`. Hash dedup uses SHA-256 content hashing.

**Tech Stack:** Rust, PyO3 0.28, tokio, aws-sdk-s3, zip, tar, sha2, hex

---

## Confirmed Requirements

| Requirement | Decision |
|---|---|
| File "改" | rename / move / copy only |
| File "查" | read content + metadata |
| Compress/Extract | zip + tar + tar.gz |
| Large file | chunk-based, auto chunk size by file size |
| Sync/Async | core sync, heavy ops async via `spawn_blocking` |
| Parallel batch | yes, return success/failure lists |
| Callers | `src/` Python code only |
| Error handling | unified `PyRuntimeError` |
| Interface | class style with context manager (`with`) |
| read() | default bytes, `as_text=True` for str |
| Chunk size | auto based on file size |
| Parallel failure | skip failed, return success/failure lists |
| metadata() | Python dict, consistent keys across backends |
| S3 rename | transparent copy + delete |
| S3 auth | constructor params (access_key, secret_key, endpoint, region) |
| S3 paths | `s3://bucket/key` scheme |
| Local mkdir | auto create parent dirs |
| Hash dedup | SHA-256 content hashing for dedup |

---

## Directory Structure

```
backend/libs/files-io/
├── Cargo.toml
├── pyproject.toml
├── src/
│   ├── lib.rs              # PyO3 module entry, registers all functions/classes
│   ├── error.rs            # FileError enum + Into<PyErr>
│   ├── hash.rs             # SHA-256 hashing utilities
│   ├── archive/
│   │   ├── mod.rs          # Archive trait + dispatch
│   │   ├── zip.rs          # zip compress/extract
│   │   └── tar_gz.rs       # tar + tar.gz compress/extract
│   ├── backends/
│   │   ├── mod.rs          # FileOps trait definition
│   │   ├── local.rs        # std::fs implementation
│   │   └── s3.rs           # aws-sdk-s3 implementation
│   └── py/
│       ├── mod.rs          # py/ module root
│       └── file.rs         # File Python class (PyO3)
└── tests/
    └── test_files_io.py    # Python integration tests
```

---

### Task 1: Project Skeleton — Cargo.toml + Module Stubs

**Files:**
- Modify: `backend/libs/files-io/Cargo.toml`
- Create: `backend/libs/files-io/src/error.rs`
- Create: `backend/libs/files-io/src/hash.rs`
- Create: `backend/libs/files-io/src/backends/mod.rs`
- Create: `backend/libs/files-io/src/archive/mod.rs`
- Create: `backend/libs/files-io/src/py/mod.rs`
- Modify: `backend/libs/files-io/src/lib.rs`

**Step 1: Update Cargo.toml with all dependencies**

```toml
[package]
name = "files-io"
version = "0.1.0"
edition = "2024"
description = "Unified local + S3 file I/O for LinguaSeeker"

[lib]
name = "files_io"
crate-type = ["cdylib", "rlib"]

[dependencies]
pyo3 = { version = "0.28.2", features = ["extension-module"] }
pyo3-async-runtimes = { version = "0.28", features = ["tokio-runtime"] }
tokio = { version = "1", features = ["rt-multi-thread", "macros", "fs"] }
aws-sdk-s3 = "1"
aws-config = "1"
aws-credential-types = "1"
zip = "2"
tar = "0.4"
flate2 = "1"
sha2 = "0.10"
hex = "0.4"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
pythonize = "0.28"
thiserror = "2"
```

**Step 2: Create error.rs**

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum FileError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("S3 error: {0}")]
    S3(String),

    #[error("Path error: {0}")]
    Path(String),

    #[error("Archive error: {0}")]
    Archive(String),

    #[error("Hash error: {0}")]
    Hash(String),

    #[error("{0}")]
    Other(String),
}

impl From<FileError> for pyo3::PyErr {
    fn from(err: FileError) -> Self {
        pyo3::exceptions::PyRuntimeError::new_err(err.to_string())
    }
}
```

**Step 3: Create hash.rs stub**

```rust
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
```

**Step 4: Create backends/mod.rs stub**

```rust
pub mod local;
pub mod s3;
```

**Step 5: Create archive/mod.rs stub**

```rust
pub mod zip;
pub mod tar_gz;
```

**Step 6: Create py/mod.rs stub**

```rust
pub mod file;
```

**Step 7: Update lib.rs**

```rust
mod error;
mod hash;
mod backends;
mod archive;
mod py;

use pyo3::prelude::*;

#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<py::file::File>()?;
    Ok(())
}
```

**Step 8: Verify it compiles**

Run: `cd backend/libs/files-io && cargo check`
Expected: compiles (may have warnings about unused imports)

**Step 9: Commit**

```bash
git add backend/libs/files-io/
git commit -m "feat(files-io): project skeleton with module stubs and dependencies"
```

---

### Task 2: FileOps Trait + Local Backend — Core Read/Write/Metadata

**Files:**
- Create: `backend/libs/files-io/src/backends/local.rs`

**Step 1: Define FileOps trait in backends/mod.rs**

```rust
pub mod local;
pub mod s3;

use crate::error::FileError;
use std::collections::HashMap;

/// Metadata returned as a Python-compatible dict.
#[derive(Debug, Clone)]
pub struct FileMetadata {
    pub size: u64,
    pub mtime: f64,       // unix timestamp seconds
    pub is_file: bool,
    pub is_dir: bool,
    pub is_symlink: bool,
    pub permissions: String, // e.g. "0o644"
    pub extra: HashMap<String, String>, // backend-specific fields
}

/// Trait for local and S3 backends.
pub trait FileOps: Send + Sync {
    fn read_all(&self, path: &str) -> Result<Vec<u8>, FileError>;
    fn read_chunk(&self, path: &str, offset: u64, size: u64) -> Result<Vec<u8>, FileError>;
    fn write(&self, path: &str, data: &[u8], create_parents: bool) -> Result<(), FileError>;
    fn write_stream(&self, path: &str, reader: &mut dyn std::io::Read, create_parents: bool) -> Result<(), FileError>;
    fn exists(&self, path: &str) -> Result<bool, FileError>;
    fn metadata(&self, path: &str) -> Result<FileMetadata, FileError>;
    fn rename(&self, src: &str, dst: &str) -> Result<(), FileError>;
    fn copy(&self, src: &str, dst: &str) -> Result<(), FileError>;
    fn remove(&self, path: &str) -> Result<(), FileError>;
    fn remove_dir_all(&self, path: &str) -> Result<(), FileError>;
    fn list_dir(&self, path: &str) -> Result<Vec<String>, FileError>;
    fn ensure_dir(&self, path: &str) -> Result<(), FileError>;
}
```

**Step 2: Implement local.rs**

```rust
use super::{FileMetadata, FileOps};
use crate::error::FileError;
use std::collections::HashMap;
use std::fs;
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::Path;

pub struct LocalBackend;

impl LocalBackend {
    pub fn new() -> Self { Self }
}

fn auto_chunk_size(file_size: u64) -> u64 {
    if file_size < 64 * 1024 { file_size }           // < 64KB: read all
    else if file_size < 10 * 1024 * 1024 { 64 * 1024 } // < 10MB: 64KB chunks
    else { 1024 * 1024 }                                // >= 10MB: 1MB chunks
}

impl FileOps for LocalBackend {
    fn read_all(&self, path: &str) -> Result<Vec<u8>, FileError> {
        Ok(fs::read(path)?)
    }

    fn read_chunk(&self, path: &str, offset: u64, size: u64) -> Result<Vec<u8>, FileError> {
        let mut file = fs::File::open(path)?;
        file.seek(SeekFrom::Start(offset))?;
        let mut buf = vec![0u8; size as usize];
        let n = file.read(&mut buf)?;
        buf.truncate(n);
        Ok(buf)
    }

    fn write(&self, path: &str, data: &[u8], create_parents: bool) -> Result<(), FileError> {
        if create_parents {
            if let Some(parent) = Path::new(path).parent() {
                fs::create_dir_all(parent)?;
            }
        }
        fs::write(path, data)?;
        Ok(())
    }

    fn write_stream(&self, path: &str, reader: &mut dyn Read, create_parents: bool) -> Result<(), FileError> {
        if create_parents {
            if let Some(parent) = Path::new(path).parent() {
                fs::create_dir_all(parent)?;
            }
        }
        let mut file = fs::File::create(path)?;
        let mut buf = [0u8; 1024 * 1024];
        loop {
            let n = reader.read(&mut buf)?;
            if n == 0 { break; }
            file.write_all(&buf[..n])?;
        }
        Ok(())
    }

    fn exists(&self, path: &str) -> Result<bool, FileError> {
        Ok(Path::new(path).exists())
    }

    fn metadata(&self, path: &str) -> Result<FileMetadata, FileError> {
        let meta = fs::metadata(path)?;
        let mtime = meta.modified()
            .map(|t| t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs_f64())
            .unwrap_or(0.0);
        let perms = format!("{:o}", meta.permissions().mode() & 0o777);
        let mut extra = HashMap::new();
        extra.insert("mode".to_string(), format!("{:o}", meta.permissions().mode()));
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            extra.insert("inode".to_string(), meta.ino().to_string());
            extra.insert("nlink".to_string(), meta.nlink().to_string());
            extra.insert("uid".to_string(), meta.uid().to_string());
            extra.insert("gid".to_string(), meta.gid().to_string());
        }
        Ok(FileMetadata {
            size: meta.len(),
            mtime,
            is_file: meta.is_file(),
            is_dir: meta.is_dir(),
            is_symlink: meta.file_type().is_symlink(),
            permissions: perms,
            extra,
        })
    }

    fn rename(&self, src: &str, dst: &str) -> Result<(), FileError> {
        fs::rename(src, dst)?;
        Ok(())
    }

    fn copy(&self, src: &str, dst: &str) -> Result<(), FileError> {
        // Chunked copy for large files
        let src_meta = fs::metadata(src)?;
        let chunk = auto_chunk_size(src_meta.len());
        if let Some(parent) = Path::new(dst).parent() {
            fs::create_dir_all(parent)?;
        }
        let mut reader = fs::File::open(src)?;
        let mut writer = fs::File::create(dst)?;
        let mut buf = vec![0u8; chunk as usize];
        loop {
            let n = reader.read(&mut buf)?;
            if n == 0 { break; }
            writer.write_all(&buf[..n])?;
        }
        Ok(())
    }

    fn remove(&self, path: &str) -> Result<(), FileError> {
        fs::remove_file(path)?;
        Ok(())
    }

    fn remove_dir_all(&self, path: &str) -> Result<(), FileError> {
        fs::remove_dir_all(path)?;
        Ok(())
    }

    fn list_dir(&self, path: &str) -> Result<Vec<String>, FileError> {
        let entries = fs::read_dir(path)?
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().to_string())
            .collect();
        Ok(entries)
    }

    fn ensure_dir(&self, path: &str) -> Result<(), FileError> {
        fs::create_dir_all(path)?;
        Ok(())
    }
}
```

**Step 3: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`
Expected: compiles successfully

**Step 4: Commit**

```bash
git add backend/libs/files-io/src/backends/
git commit -m "feat(files-io): FileOps trait and local backend implementation"
```

---

### Task 3: S3 Backend

**Files:**
- Create: `backend/libs/files-io/src/backends/s3.rs`

**Step 1: Implement s3.rs**

```rust
use super::{FileMetadata, FileOps};
use crate::error::FileError;
use aws_sdk_s3::Client;
use aws_sdk_s3::config::{Credentials, Region};
use std::collections::HashMap;
use std::io::Read;
use tokio::runtime::Runtime;

pub struct S3Backend {
    client: Client,
    rt: Runtime,
}

/// Parse s3://bucket/key into (bucket, key).
fn parse_s3_path(path: &str) -> Result<(&str, &str), FileError> {
    let stripped = path.strip_prefix("s3://").ok_or_else(|| {
        FileError::Path(format!("not an S3 path: {path}"))
    })?;
    let slash = stripped.find('/').ok_or_else(|| {
        FileError::Path(format!("S3 path missing key: {path}"))
    })?;
    Ok((&stripped[..slash], &stripped[slash + 1..]))
}

impl S3Backend {
    pub fn new(access_key: &str, secret_key: &str, endpoint: Option<&str>, region: Option<&str>) -> Result<Self, FileError> {
        let rt = Runtime::new().map_err(|e| FileError::Other(e.to_string()))?;
        let credentials = Credentials::new(
            access_key, secret_key, None, None, "files-io",
        );
        let mut config_builder = aws_config::SdkConfig::builder()
            .credentials_provider(credentials)
            .region(Region::new(region.unwrap_or("us-east-1").to_string()));
        if let Some(ep) = endpoint {
            config_builder = config_builder.endpoint_url(ep);
        }
        let config = rt.block_on(config_builder.build());
        let client = Client::new(&config);
        Ok(Self { client, rt })
    }
}

impl FileOps for S3Backend {
    fn read_all(&self, path: &str) -> Result<Vec<u8>, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let resp = self.rt.block_on(
            self.client.get_object().bucket(bucket).key(key).send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        let bytes = self.rt.block_on(resp.body.collect())
            .map_err(|e| FileError::S3(e.to_string()))?;
        Ok(bytes.to_vec())
    }

    fn read_chunk(&self, path: &str, offset: u64, size: u64) -> Result<Vec<u8>, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let range = format!("bytes={}-{}", offset, offset + size - 1);
        let resp = self.rt.block_on(
            self.client.get_object().bucket(bucket).key(key).range(range).send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        let bytes = self.rt.block_on(resp.body.collect())
            .map_err(|e| FileError::S3(e.to_string()))?;
        Ok(bytes.to_vec())
    }

    fn write(&self, path: &str, data: &[u8], _create_parents: bool) -> Result<(), FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let body = aws_sdk_s3::primitives::ByteStream::from(data.to_vec());
        self.rt.block_on(
            self.client.put_object().bucket(bucket).key(key).body(body).send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        Ok(())
    }

    fn write_stream(&self, path: &str, reader: &mut dyn Read, _create_parents: bool) -> Result<(), FileError> {
        let mut data = Vec::new();
        reader.read_to_end(&mut data)?;
        self.write(path, &data, false)
    }

    fn exists(&self, path: &str) -> Result<bool, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let result = self.rt.block_on(
            self.client.head_object().bucket(bucket).key(key).send()
        );
        match result {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }

    fn metadata(&self, path: &str) -> Result<FileMetadata, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let resp = self.rt.block_on(
            self.client.head_object().bucket(bucket).key(key).send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        let size = resp.content_length().unwrap_or(0) as u64;
        let mtime = resp.last_modified()
            .map(|t| t.secs() as f64)
            .unwrap_or(0.0);
        let mut extra = HashMap::new();
        if let Some(etag) = resp.e_tag() {
            extra.insert("etag".to_string(), etag.to_string());
        }
        if let Some(ct) = resp.content_type() {
            extra.insert("content_type".to_string(), ct.to_string());
        }
        if let Some(storage) = resp.storage_class().map(|s| s.as_str()) {
            extra.insert("storage_class".to_string(), storage.to_string());
        }
        Ok(FileMetadata {
            size,
            mtime,
            is_file: true, // S3 objects are always "files"
            is_dir: false,
            is_symlink: false,
            permissions: String::new(),
            extra,
        })
    }

    fn rename(&self, src: &str, dst: &str) -> Result<(), FileError> {
        // S3 has no native rename: copy + delete
        self.copy(src, dst)?;
        self.remove(src)?;
        Ok(())
    }

    fn copy(&self, src: &str, dst: &str) -> Result<(), FileError> {
        let (src_bucket, src_key) = parse_s3_path(src)?;
        let (dst_bucket, dst_key) = parse_s3_path(dst)?;
        let copy_source = format!("{src_bucket}/{src_key}");
        self.rt.block_on(
            self.client.copy_object()
                .bucket(dst_bucket)
                .key(dst_key)
                .copy_source(&copy_source)
                .send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        Ok(())
    }

    fn remove(&self, path: &str) -> Result<(), FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        self.rt.block_on(
            self.client.delete_object().bucket(bucket).key(key).send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        Ok(())
    }

    fn remove_dir_all(&self, path: &str) -> Result<(), FileError> {
        // S3 has no real directories; list and delete all objects with prefix
        let (bucket, key) = parse_s3_path(path)?;
        let prefix = if key.ends_with('/') { key.to_string() } else { format!("{key}/") };
        let resp = self.rt.block_on(
            self.client.list_objects_v2().bucket(bucket).prefix(&prefix).send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        for obj in resp.contents() {
            if let Some(k) = obj.key() {
                self.rt.block_on(
                    self.client.delete_object().bucket(bucket).key(k).send()
                ).map_err(|e| FileError::S3(e.to_string()))?;
            }
        }
        Ok(())
    }

    fn list_dir(&self, path: &str) -> Result<Vec<String>, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let prefix = if key.ends_with('/') { key.to_string() } else { format!("{key}/") };
        let resp = self.rt.block_on(
            self.client.list_objects_v2().bucket(bucket).prefix(&prefix).delimiter("/").send()
        ).map_err(|e| FileError::S3(e.to_string()))?;
        let mut entries = Vec::new();
        for prefix in resp.common_prefixes() {
            if let Some(p) = prefix.prefix() {
                entries.push(p.trim_start_matches(&prefix[..prefix.len()]).to_string());
            }
        }
        for obj in resp.contents() {
            if let Some(k) = obj.key() {
                let name = k.strip_prefix(&prefix).unwrap_or(k);
                if !name.is_empty() {
                    entries.push(name.to_string());
                }
            }
        }
        Ok(entries)
    }

    fn ensure_dir(&self, _path: &str) -> Result<(), FileError> {
        // S3 has no real directories; no-op
        Ok(())
    }
}
```

**Step 2: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`
Expected: compiles (may need to adjust AWS SDK API calls based on exact version)

**Step 3: Commit**

```bash
git add backend/libs/files-io/src/backends/s3.rs
git commit -m "feat(files-io): S3 backend implementation with transparent rename"
```

---

### Task 4: Archive — zip compress/extract

**Files:**
- Create: `backend/libs/files-io/src/archive/zip.rs`

**Step 1: Implement zip.rs**

```rust
use crate::error::FileError;
use std::fs;
use std::io::{Read, Write};
use std::path::Path;
use zip::write::SimpleFileOptions;

/// Compress a directory into a .zip archive.
pub fn compress_dir(dir_path: &str, output_path: &str) -> Result<u64, FileError> {
    let dir = Path::new(dir_path);
    if !dir.is_dir() {
        return Err(FileError::Archive(format!("not a directory: {dir_path}")));
    }
    let file = fs::File::create(output_path)?;
    let mut zip = zip::ZipWriter::new(file);
    let options = SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated);
    let mut file_count: u64 = 0;
    add_dir_to_zip(&mut zip, dir, dir, &options, &mut file_count)?;
    zip.finish()?;
    Ok(file_count)
}

fn add_dir_to_zip(
    zip: &mut zip::ZipWriter<fs::File>,
    base: &Path,
    current: &Path,
    options: &SimpleFileOptions,
    count: &mut u64,
) -> Result<(), FileError> {
    for entry in fs::read_dir(current)? {
        let entry = entry?;
        let path = entry.path();
        let name = path.strip_prefix(base).unwrap();
        if path.is_dir() {
            zip.add_directory(name.to_string_lossy(), *options)?;
            add_dir_to_zip(zip, base, &path, options, count)?;
        } else {
            zip.start_file(name.to_string_lossy(), *options)?;
            let mut f = fs::File::open(&path)?;
            let mut buf = Vec::new();
            f.read_to_end(&mut buf)?;
            zip.write_all(&buf)?;
            *count += 1;
        }
    }
    Ok(())
}

/// Extract a .zip archive to a directory.
pub fn extract(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let file = fs::File::open(archive_path)?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| FileError::Archive(e.to_string()))?;
    fs::create_dir_all(output_dir)?;
    let mut count: u64 = 0;
    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| FileError::Archive(e.to_string()))?;
        let outpath = Path::new(output_dir).join(file.mangled_name());
        if file.name().ends_with('/') {
            fs::create_dir_all(&outpath)?;
        } else {
            if let Some(parent) = outpath.parent() {
                fs::create_dir_all(parent)?;
            }
            let mut outfile = fs::File::create(&outpath)?;
            std::io::copy(&mut file, &mut outfile)?;
            count += 1;
        }
    }
    Ok(count)
}
```

**Step 2: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`

**Step 3: Commit**

```bash
git add backend/libs/files-io/src/archive/zip.rs
git commit -m "feat(files-io): zip compress and extract"
```

---

### Task 5: Archive — tar + tar.gz compress/extract

**Files:**
- Create: `backend/libs/files-io/src/archive/tar_gz.rs`

**Step 1: Implement tar_gz.rs**

```rust
use crate::error::FileError;
use flate2::read::GzDecoder;
use flate2::write::GzEncoder;
use flate2::Compression;
use std::fs;
use std::path::Path;
use tar::{Archive, Builder};

/// Compress a directory into a .tar archive.
pub fn compress_tar(dir_path: &str, output_path: &str) -> Result<u64, FileError> {
    let dir = Path::new(dir_path);
    if !dir.is_dir() {
        return Err(FileError::Archive(format!("not a directory: {dir_path}")));
    }
    let file = fs::File::create(output_path)?;
    let mut builder = Builder::new(file);
    builder.append_dir_all("", dir)?;
    builder.finish()?;
    // Count files
    let count = count_dir_entries(dir)?;
    Ok(count)
}

/// Compress a directory into a .tar.gz archive.
pub fn compress_tar_gz(dir_path: &str, output_path: &str) -> Result<u64, FileError> {
    let dir = Path::new(dir_path);
    if !dir.is_dir() {
        return Err(FileError::Archive(format!("not a directory: {dir_path}")));
    }
    let file = fs::File::create(output_path)?;
    let enc = GzEncoder::new(file, Compression::default());
    let mut builder = Builder::new(enc);
    builder.append_dir_all("", dir)?;
    builder.finish()?;
    let count = count_dir_entries(dir)?;
    Ok(count)
}

/// Extract a .tar archive to a directory.
pub fn extract_tar(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let file = fs::File::open(archive_path)?;
    let mut archive = Archive::new(file);
    fs::create_dir_all(output_dir)?;
    archive.unpack(output_dir)?;
    let count = count_dir_entries(Path::new(output_dir))?;
    Ok(count)
}

/// Extract a .tar.gz archive to a directory.
pub fn extract_tar_gz(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let file = fs::File::open(archive_path)?;
    let dec = GzDecoder::new(file);
    let mut archive = Archive::new(dec);
    fs::create_dir_all(output_dir)?;
    archive.unpack(output_dir)?;
    let count = count_dir_entries(Path::new(output_dir))?;
    Ok(count)
}

fn count_dir_entries(dir: &Path) -> Result<u64, FileError> {
    let mut count = 0u64;
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        if entry.path().is_file() {
            count += 1;
        } else if entry.path().is_dir() {
            count += count_dir_entries(&entry.path())?;
        }
    }
    Ok(count)
}
```

**Step 2: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`

**Step 3: Commit**

```bash
git add backend/libs/files-io/src/archive/tar_gz.rs
git commit -m "feat(files-io): tar and tar.gz compress and extract"
```

---

### Task 6: File Python Class — Core API

**Files:**
- Create: `backend/libs/files-io/src/py/file.rs`

**Step 1: Implement File class**

```rust
use crate::backends::{local::LocalBackend, s3::S3Backend, FileMetadata, FileOps};
use crate::error::FileError;
use crate::hash;
use pyo3::prelude::*;
use pyo3::types::PyDict;

enum Backend {
    Local(LocalBackend),
    S3(S3Backend),
}

#[pyclass]
struct File {
    path: String,
    backend: Backend,
}

impl File {
    fn ops(&self) -> &dyn FileOps {
        match &self.backend {
            Backend::Local(b) => b,
            Backend::S3(b) => b,
        }
    }
}

#[pymethods]
impl File {
    /// Create a File instance. Auto-detects local vs S3 by path prefix.
    /// For S3: `File("s3://bucket/key", access_key="...", secret_key="...", endpoint=None, region=None)`
    #[new]
    #[pyo3(signature = (path, access_key=None, secret_key=None, endpoint=None, region=None))]
    fn new(
        path: &str,
        access_key: Option<&str>,
        secret_key: Option<&str>,
        endpoint: Option<&str>,
        region: Option<&str>,
    ) -> PyResult<Self> {
        if path.starts_with("s3://") {
            let ak = access_key.ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>("access_key required for S3 paths")
            })?;
            let sk = secret_key.ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>("secret_key required for S3 paths")
            })?;
            let backend = S3Backend::new(ak, sk, endpoint, region)?;
            Ok(Self { path: path.to_string(), backend: Backend::S3(backend) })
        } else {
            Ok(Self { path: path.to_string(), backend: Backend::Local(LocalBackend::new()) })
        }
    }

    fn __enter__(slf: Py<Self>) -> Py<Self> { slf }

    fn __exit__(
        &mut self,
        _exc_type: Option<&Bound<'_, PyAny>>,
        _exc_value: Option<&Bound<'_, PyAny>>,
        _traceback: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<bool> {
        Ok(false) // don't suppress exceptions
    }

    /// Read file contents. Returns bytes by default, str if as_text=True.
    #[pyo3(signature = (as_text=false))]
    fn read(&self, as_text: bool) -> PyResult<PyObject> {
        let data = self.ops().read_all(&self.path)?;
        Python::attach(|py| {
            if as_text {
                let s = String::from_utf8(data)
                    .map_err(|e| FileError::Other(format!("UTF-8 decode error: {e}")))?;
                Ok(s.into_pyobject(py)?.unbind().into_any())
            } else {
                Ok(PyBytes::new(py, &data).into_any().unbind())
            }
        })
    }

    /// Read a chunk of the file at offset with given size.
    fn read_chunk(&self, offset: u64, size: u64) -> PyResult<PyObject> {
        let data = self.ops().read_chunk(&self.path, offset, size)?;
        Python::attach(|py| Ok(PyBytes::new(py, &data).into_any().unbind()))
    }

    /// Write data (bytes or str) to file. Auto-creates parent dirs for local paths.
    fn write(&self, data: &Bound<'_, PyAny>) -> PyResult<()> {
        let bytes: Vec<u8> = if let Ok(b) = data.extract::<Vec<u8>>() {
            b
        } else if let Ok(s) = data.extract::<String>() {
            s.into_bytes()
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "write() accepts bytes or str",
            ));
        };
        self.ops().write(&self.path, &bytes, true)?;
        Ok(())
    }

    /// Check if path exists.
    fn exists(&self) -> PyResult<bool> {
        Ok(self.ops().exists(&self.path)?)
    }

    /// Return metadata as dict.
    fn metadata<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let meta = self.ops().metadata(&self.path)?;
        let dict = PyDict::new(py);
        dict.set_item("size", meta.size)?;
        dict.set_item("mtime", meta.mtime)?;
        dict.set_item("is_file", meta.is_file)?;
        dict.set_item("is_dir", meta.is_dir)?;
        dict.set_item("is_symlink", meta.is_symlink)?;
        dict.set_item("permissions", &meta.permissions)?;
        for (k, v) in &meta.extra {
            dict.set_item(k, v)?;
        }
        Ok(dict)
    }

    /// Rename/move file.
    fn rename(&self, dst: &str) -> PyResult<()> {
        self.ops().rename(&self.path, dst)?;
        Ok(())
    }

    /// Copy file to destination.
    fn copy(&self, dst: &str) -> PyResult<()> {
        self.ops().copy(&self.path, dst)?;
        Ok(())
    }

    /// Remove file.
    fn remove(&self) -> PyResult<()> {
        self.ops().remove(&self.path)?;
        Ok(())
    }

    /// Remove directory and all contents.
    fn remove_dir_all(&self) -> PyResult<()> {
        self.ops().remove_dir_all(&self.path)?;
        Ok(())
    }

    /// List directory entries.
    fn list_dir(&self) -> PyResult<Vec<String>> {
        Ok(self.ops().list_dir(&self.path)?)
    }

    /// Compute SHA-256 hash of file content (local only).
    fn content_hash(&self) -> PyResult<String> {
        match &self.backend {
            Backend::Local(_) => {
                Ok(hash::hash_file(std::path::Path::new(&self.path))?)
            }
            Backend::S3(_) => {
                // For S3: download to temp, hash, cleanup
                let data = self.ops().read_all(&self.path)?;
                Ok(hash::hash_bytes(&data))
            }
        }
    }
}
```

**Step 2: Update lib.rs to use the correct module path**

```rust
mod error;
mod hash;
mod backends;
mod archive;
mod py;

use pyo3::prelude::*;

#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<py::file::File>()?;
    Ok(())
}
```

**Step 3: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`

**Step 4: Commit**

```bash
git add backend/libs/files-io/src/py/
git commit -m "feat(files-io): File Python class with read, write, metadata, hash"
```

---

### Task 7: File Class — Archive Operations

**Files:**
- Modify: `backend/libs/files-io/src/py/file.rs`

**Step 1: Add archive methods to File class**

Add these methods inside the `#[pymethods]` block of `File`:

```rust
    /// Compress directory to archive. Format: "zip", "tar", "tar.gz".
    /// Returns number of files compressed.
    fn compress(&self, output_path: &str, format: &str) -> PyResult<u64> {
        let count = match format {
            "zip" => crate::archive::zip::compress_dir(&self.path, output_path)?,
            "tar" => crate::archive::tar_gz::compress_tar(&self.path, output_path)?,
            "tar.gz" | "tgz" => crate::archive::tar_gz::compress_tar_gz(&self.path, output_path)?,
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("unsupported format: {format}. Use zip, tar, or tar.gz")
            )),
        };
        Ok(count)
    }

    /// Extract archive to output directory. Auto-detects format from extension.
    /// Returns number of files extracted.
    fn extract(&self, output_dir: &str) -> PyResult<u64> {
        let path_lower = self.path.to_lowercase();
        let count = if path_lower.ends_with(".zip") {
            crate::archive::zip::extract(&self.path, output_dir)?
        } else if path_lower.ends_with(".tar.gz") || path_lower.ends_with(".tgz") {
            crate::archive::tar_gz::extract_tar_gz(&self.path, output_dir)?
        } else if path_lower.ends_with(".tar") {
            crate::archive::tar_gz::extract_tar(&self.path, output_dir)?
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("cannot detect archive format from path: {}", self.path)
            ));
        };
        Ok(count)
    }
```

**Step 2: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`

**Step 3: Commit**

```bash
git add backend/libs/files-io/src/py/file.rs
git commit -m "feat(files-io): compress and extract methods on File class"
```

---

### Task 8: Parallel Batch Operations

**Files:**
- Modify: `backend/libs/files-io/src/py/file.rs`
- Modify: `backend/libs/files-io/src/py/mod.rs`

**Step 1: Add parallel module to py/mod.rs**

```rust
pub mod file;
pub mod parallel;
```

**Step 2: Create py/parallel.rs**

```rust
use crate::backends::{local::LocalBackend, s3::S3Backend, FileOps};
use crate::error::FileError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::sync::Arc;

enum BackendRef {
    Local(Arc<LocalBackend>),
    S3(Arc<S3Backend>),
}

/// Result of a single file operation in a batch.
struct OpResult {
    path: String,
    success: bool,
    message: String,
}

fn make_result_dict(py: Python<'_>, results: &[OpResult]) -> PyResult<PyObject> {
    let success = PyList::empty(py);
    let failed = PyList::empty(py);
    for r in results {
        if r.success {
            success.append(&r.path)?;
        } else {
            let dict = PyDict::new(py);
            dict.set_item("path", &r.path)?;
            dict.set_item("error", &r.message)?;
            failed.append(dict)?;
        }
    }
    let result = PyDict::new(py);
    result.set_item("success", success)?;
    result.set_item("failed", failed)?;
    Ok(result.into_any().unbind())
}

/// Copy multiple files in parallel. Returns {success: [...], failed: [{path, error}]}.
#[pyfunction]
#[pyo3(signature = (sources, destinations, access_key=None, secret_key=None, endpoint=None, region=None))]
pub fn parallel_copy(
    py: Python<'_>,
    sources: Vec<String>,
    destinations: Vec<String>,
    access_key: Option<String>,
    secret_key: Option<String>,
    endpoint: Option<String>,
    region: Option<String>,
) -> PyResult<PyObject> {
    if sources.len() != destinations.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "sources and destinations must have same length"
        ));
    }
    let local = Arc::new(LocalBackend::new());
    let s3: Option<Arc<S3Backend>> = if let (Some(ak), Some(sk)) = (&access_key, &secret_key) {
        Some(Arc::new(S3Backend::new(ak, sk, endpoint.as_deref(), region.as_deref())?))
    } else {
        None
    };

    let results: Vec<OpResult> = sources.into_iter().zip(destinations).map(|(src, dst)| {
        let ops: &dyn FileOps = if src.starts_with("s3://") || dst.starts_with("s3://") {
            match &s3 {
                Some(b) => b.as_ref(),
                None => return OpResult { path: src, success: false, message: "S3 credentials required".into() },
            }
        } else {
            local.as_ref()
        };
        match ops.copy(&src, &dst) {
            Ok(()) => OpResult { path: src, success: true, message: String::new() },
            Err(e) => OpResult { path: src, success: false, message: e.to_string() },
        }
    }).collect();

    make_result_dict(py, &results)
}

/// Compress multiple directories in parallel.
#[pyfunction]
#[pyo3(signature = (dir_paths, output_paths, format="zip"))]
pub fn parallel_compress(
    py: Python<'_>,
    dir_paths: Vec<String>,
    output_paths: Vec<String>,
    format: &str,
) -> PyResult<PyObject> {
    if dir_paths.len() != output_paths.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "dir_paths and output_paths must have same length"
        ));
    }
    let results: Vec<OpResult> = dir_paths.into_iter().zip(output_paths).map(|(dir, out)| {
        let r = match format {
            "zip" => crate::archive::zip::compress_dir(&dir, &out),
            "tar" => crate::archive::tar_gz::compress_tar(&dir, &out),
            "tar.gz" | "tgz" => crate::archive::tar_gz::compress_tar_gz(&dir, &out),
            _ => Err(FileError::Archive(format!("unsupported format: {format}"))),
        };
        match r {
            Ok(_) => OpResult { path: dir, success: true, message: String::new() },
            Err(e) => OpResult { path: dir, success: false, message: e.to_string() },
        }
    }).collect();

    make_result_dict(py, &results)
}
```

**Step 3: Register parallel functions in lib.rs**

```rust
mod error;
mod hash;
mod backends;
mod archive;
mod py;

use pyo3::prelude::*;

#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<py::file::File>()?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_copy, m)?)?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_compress, m)?)?;
    Ok(())
}
```

**Step 4: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`

**Step 5: Commit**

```bash
git add backend/libs/files-io/src/py/ backend/libs/files-io/src/lib.rs
git commit -m "feat(files-io): parallel batch copy and compress operations"
```

---

### Task 9: Async Versions of Heavy Operations

**Files:**
- Modify: `backend/libs/files-io/src/py/file.rs`
- Modify: `backend/libs/files-io/src/py/parallel.rs`

**Step 1: Add async methods to File class**

Add inside `#[pymethods]` block:

```rust
    /// Async version of copy. Uses spawn_blocking.
    fn copy_async<'py>(&self, py: Python<'py>, dst: String) -> PyResult<Bound<'py, PyAny>> {
        let path = self.path.clone();
        let is_s3 = path.starts_with("s3://");
        // For now, use sync copy in spawn_blocking
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            tokio::task::spawn_blocking(move || {
                let local = LocalBackend::new();
                local.copy(&path, &dst).map_err(FileError::from)
            }).await.map_err(|e| FileError::Other(e.to_string()))?
            .map_err(FileError::from)?;
            Ok(())
        })
    }

    /// Async version of compress. Uses spawn_blocking.
    fn compress_async<'py>(&self, py: Python<'py>, output_path: String, format: String) -> PyResult<Bound<'py, PyAny>> {
        let dir = self.path.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let count = tokio::task::spawn_blocking(move || {
                match format.as_str() {
                    "zip" => crate::archive::zip::compress_dir(&dir, &output_path),
                    "tar" => crate::archive::tar_gz::compress_tar(&dir, &output_path),
                    "tar.gz" | "tgz" => crate::archive::tar_gz::compress_tar_gz(&dir, &output_path),
                    _ => Err(FileError::Archive(format!("unsupported format: {format}"))),
                }
            }).await.map_err(|e| FileError::Other(e.to_string()))??;
            Ok(count)
        })
    }

    /// Async version of extract. Uses spawn_blocking.
    fn extract_async<'py>(&self, py: Python<'py>, output_dir: String) -> PyResult<Bound<'py, PyAny>> {
        let path = self.path.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let count = tokio::task::spawn_blocking(move || {
                let path_lower = path.to_lowercase();
                if path_lower.ends_with(".zip") {
                    crate::archive::zip::extract(&path, &output_dir)
                } else if path_lower.ends_with(".tar.gz") || path_lower.ends_with(".tgz") {
                    crate::archive::tar_gz::extract_tar_gz(&path, &output_dir)
                } else if path_lower.ends_with(".tar") {
                    crate::archive::tar_gz::extract_tar(&path, &output_dir)
                } else {
                    Err(FileError::Archive(format!("cannot detect format: {path}")))
                }
            }).await.map_err(|e| FileError::Other(e.to_string()))??;
            Ok(count)
        })
    }
```

**Step 2: Add async versions of parallel functions to parallel.rs**

```rust
/// Async parallel copy using spawn_blocking.
#[pyfunction]
#[pyo3(signature = (sources, destinations, access_key=None, secret_key=None, endpoint=None, region=None))]
pub fn parallel_copy_async<'py>(
    py: Python<'py>,
    sources: Vec<String>,
    destinations: Vec<String>,
    access_key: Option<String>,
    secret_key: Option<String>,
    endpoint: Option<String>,
    region: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = tokio::task::spawn_blocking(move || {
            // Same logic as parallel_copy but returns raw result
            Python::attach(|py| {
                parallel_copy(py, sources, destinations, access_key, secret_key, endpoint, region)
            })
        }).await.map_err(|e| FileError::Other(e.to_string()))??;
        Ok(result)
    })
}
```

**Step 3: Register async functions in lib.rs**

```rust
#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<py::file::File>()?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_copy, m)?)?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_compress, m)?)?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_copy_async, m)?)?;
    Ok(())
}
```

**Step 4: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`

**Step 5: Commit**

```bash
git add backend/libs/files-io/src/
git commit -m "feat(files-io): async versions of heavy operations via spawn_blocking"
```

---

### Task 10: Hash Deduplication Utility

**Files:**
- Modify: `backend/libs/files-io/src/py/file.rs`
- Modify: `backend/libs/files-io/src/py/mod.rs`

**Step 1: Create py/dedup.rs**

```rust
use crate::hash;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;
use std::path::Path;

/// Check if a file's content hash matches any hash in a set.
/// Returns {"hash": str, "is_duplicate": bool}.
#[pyfunction]
pub fn check_duplicate(file_path: &str, known_hashes: Vec<String>) -> PyResult<PyObject> {
    let file_hash = hash::hash_file(Path::new(file_path))?;
    let is_dup = known_hashes.contains(&file_hash);
    Python::attach(|py| {
        let dict = PyDict::new(py);
        dict.set_item("hash", &file_hash)?;
        dict.set_item("is_duplicate", is_dup)?;
        Ok(dict.into_any().unbind())
    })
}

/// Batch hash multiple files. Returns {path: hash, ...} for successful files,
/// and {path: error, ...} for failures.
#[pyfunction]
pub fn batch_hash(file_paths: Vec<String>) -> PyResult<PyObject> {
    let mut hashes = HashMap::new();
    let mut errors = HashMap::new();
    for path in &file_paths {
        match hash::hash_file(Path::new(path)) {
            Ok(h) => { hashes.insert(path.clone(), h); }
            Err(e) => { errors.insert(path.clone(), e.to_string()); }
        }
    }
    Python::attach(|py| {
        let dict = PyDict::new(py);
        dict.set_item("hashes", &hashes)?;
        dict.set_item("errors", &errors)?;
        Ok(dict.into_any().unbind())
    })
}
```

**Step 2: Update py/mod.rs**

```rust
pub mod file;
pub mod parallel;
pub mod dedup;
```

**Step 3: Register in lib.rs**

```rust
#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<py::file::File>()?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_copy, m)?)?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_compress, m)?)?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_copy_async, m)?)?;
    m.add_function(wrap_pyfunction!(py::dedup::check_duplicate, m)?)?;
    m.add_function(wrap_pyfunction!(py::dedup::batch_hash, m)?)?;
    Ok(())
}
```

**Step 4: Verify compilation**

Run: `cd backend/libs/files-io && cargo check`

**Step 5: Commit**

```bash
git add backend/libs/files-io/src/
git commit -m "feat(files-io): hash deduplication with check_duplicate and batch_hash"
```

---

### Task 11: Build the Extension + Python Tests

**Files:**
- Create: `backend/libs/files-io/tests/test_files_io.py`

**Step 1: Build the extension**

Run: `cd backend/libs/files-io && maturin develop`
Expected: builds and installs `files_io` into the current Python environment

**Step 2: Write Python tests**

```python
"""Integration tests for files_io module."""
import os
import tempfile
import pytest

import files_io


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestFileReadWrite:
    def test_write_and_read_bytes(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.bin")
        f = files_io.File(path)
        f.write(b"hello world")
        assert f.read() == b"hello world"

    def test_write_and_read_text(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        f = files_io.File(path)
        f.write("hello world")
        assert f.read(as_text=True) == "hello world"

    def test_context_manager(self, tmp_dir):
        path = os.path.join(tmp_dir, "ctx.txt")
        with files_io.File(path) as f:
            f.write("context test")
        assert f.read(as_text=True) == "context test"


class TestFileMetadata:
    def test_metadata_returns_dict(self, tmp_dir):
        path = os.path.join(tmp_dir, "meta.txt")
        f = files_io.File(path)
        f.write("metadata test")
        meta = f.metadata()
        assert isinstance(meta, dict)
        assert meta["size"] == len(b"metadata test")
        assert meta["is_file"] is True
        assert meta["is_dir"] is False
        assert "mtime" in meta
        assert "permissions" in meta


class TestFileOperations:
    def test_exists(self, tmp_dir):
        path = os.path.join(tmp_dir, "exists.txt")
        f = files_io.File(path)
        assert not f.exists()
        f.write("exists")
        assert f.exists()

    def test_rename(self, tmp_dir):
        src = os.path.join(tmp_dir, "src.txt")
        dst = os.path.join(tmp_dir, "dst.txt")
        f = files_io.File(src)
        f.write("rename me")
        f.rename(dst)
        assert not f.exists()
        assert files_io.File(dst).read(as_text=True) == "rename me"

    def test_copy(self, tmp_dir):
        src = os.path.join(tmp_dir, "copy_src.txt")
        dst = os.path.join(tmp_dir, "copy_dst.txt")
        f = files_io.File(src)
        f.write("copy me")
        f.copy(dst)
        assert f.read(as_text=True) == "copy me"
        assert files_io.File(dst).read(as_text=True) == "copy me"

    def test_remove(self, tmp_dir):
        path = os.path.join(tmp_dir, "remove.txt")
        f = files_io.File(path)
        f.write("remove me")
        assert f.exists()
        f.remove()
        assert not f.exists()

    def test_list_dir(self, tmp_dir):
        for name in ["a.txt", "b.txt", "c.txt"]:
            files_io.File(os.path.join(tmp_dir, name)).write("x")
        entries = files_io.File(tmp_dir).list_dir()
        assert set(entries) == {"a.txt", "b.txt", "c.txt"}


class TestContentHash:
    def test_same_content_same_hash(self, tmp_dir):
        p1 = os.path.join(tmp_dir, "h1.txt")
        p2 = os.path.join(tmp_dir, "h2.txt")
        files_io.File(p1).write("same content")
        files_io.File(p2).write("same content")
        assert files_io.File(p1).content_hash() == files_io.File(p2).content_hash()

    def test_different_content_different_hash(self, tmp_dir):
        p1 = os.path.join(tmp_dir, "h1.txt")
        p2 = os.path.join(tmp_dir, "h2.txt")
        files_io.File(p1).write("content A")
        files_io.File(p2).write("content B")
        assert files_io.File(p1).content_hash() != files_io.File(p2).content_hash()


class TestArchive:
    def test_zip_compress_extract(self, tmp_dir):
        src_dir = os.path.join(tmp_dir, "src")
        os.makedirs(src_dir)
        files_io.File(os.path.join(src_dir, "a.txt")).write("file a")
        files_io.File(os.path.join(src_dir, "b.txt")).write("file b")
        archive = os.path.join(tmp_dir, "test.zip")
        count = files_io.File(src_dir).compress(archive, "zip")
        assert count == 2
        out_dir = os.path.join(tmp_dir, "out_zip")
        count = files_io.File(archive).extract(out_dir)
        assert count >= 2
        assert files_io.File(os.path.join(out_dir, "a.txt")).read(as_text=True) == "file a"

    def test_tar_gz_compress_extract(self, tmp_dir):
        src_dir = os.path.join(tmp_dir, "src_tgz")
        os.makedirs(src_dir)
        files_io.File(os.path.join(src_dir, "x.txt")).write("file x")
        archive = os.path.join(tmp_dir, "test.tar.gz")
        count = files_io.File(src_dir).compress(archive, "tar.gz")
        assert count == 1
        out_dir = os.path.join(tmp_dir, "out_tgz")
        count = files_io.File(archive).extract(out_dir)
        assert count >= 1


class TestDedup:
    def test_check_duplicate(self, tmp_dir):
        p1 = os.path.join(tmp_dir, "d1.txt")
        p2 = os.path.join(tmp_dir, "d2.txt")
        files_io.File(p1).write("duplicate content")
        files_io.File(p2).write("duplicate content")
        h1 = files_io.File(p1).content_hash()
        result = files_io.check_duplicate(p2, [h1])
        assert result["is_duplicate"] is True

    def test_batch_hash(self, tmp_dir):
        paths = []
        for i in range(3):
            p = os.path.join(tmp_dir, f"batch_{i}.txt")
            files_io.File(p).write(f"content {i}")
            paths.append(p)
        result = files_io.batch_hash(paths)
        assert len(result["hashes"]) == 3
        assert len(result["errors"]) == 0
```

**Step 3: Run tests**

Run: `cd backend/libs/files-io && uv run pytest tests/test_files_io.py -v`
Expected: all tests pass

**Step 4: Commit**

```bash
git add backend/libs/files-io/tests/
git commit -m "test(files-io): Python integration tests for all features"
```

---

### Task 12: pyproject.toml + Backend Integration

**Files:**
- Modify: `backend/libs/files-io/pyproject.toml`
- Modify: `backend/pyproject.toml` (if needed)

**Step 1: Update pyproject.toml with optional dev deps**

```toml
[build-system]
requires = ["maturin>=1.13,<2.0"]
build-backend = "maturin"

[project]
name = "files-io"
requires-python = ">=3.10"
classifiers = [
    "Programming Language :: Rust",
    "Programming Language :: Python :: Implementation :: CPython",
]
dynamic = ["version"]

[tool.maturin]
features = ["pyo3/extension-module"]
```

**Step 2: Add files-io to backend dependencies if not already present**

Check `backend/pyproject.toml` and add:
```toml
[project]
dependencies = [
    # ... existing deps ...
    "files-io",  # local path dependency
]

[tool.uv.sources]
files-io = { path = "libs/files-io", editable = true }
```

**Step 3: Install and verify**

Run: `cd backend && uv pip install -e "libs/files-io"`
Run: `python -c "import files_io; print('files_io imported successfully')"`

**Step 4: Commit**

```bash
git add backend/libs/files-io/pyproject.toml backend/pyproject.toml
git commit -m "chore(files-io): configure pyproject.toml and backend integration"
```

---

### Task 13: Final Verification + Lint

**Step 1: Run Rust clippy**

Run: `cd backend/libs/files-io && cargo clippy -- -D warnings`
Expected: no warnings

**Step 2: Run all Python tests**

Run: `cd backend/libs/files-io && uv run pytest tests/ -v`
Expected: all pass

**Step 3: Run ruff on any Python files**

Run: `cd backend && ruff check`

**Step 4: Final commit if needed**

```bash
git add -A
git commit -m "chore(files-io): lint fixes and final verification"
```

---

## Summary of Public API

### `files_io.File(path, access_key=None, secret_key=None, endpoint=None, region=None)`

| Method | Sync | Async | Description |
|---|---|---|---|
| `read(as_text=False)` | yes | — | Read file, bytes or str |
| `read_chunk(offset, size)` | yes | — | Read partial file |
| `write(data)` | yes | — | Write bytes or str |
| `exists()` | yes | — | Check existence |
| `metadata()` | yes | — | Returns dict with size, mtime, etc. |
| `rename(dst)` | yes | — | Rename/move |
| `copy(dst)` | yes | `copy_async(dst)` | Copy file |
| `remove()` | yes | — | Delete file |
| `remove_dir_all()` | yes | — | Delete dir recursively |
| `list_dir()` | yes | — | List directory entries |
| `content_hash()` | yes | — | SHA-256 hash |
| `compress(output, format)` | yes | `compress_async(output, format)` | Dir → archive |
| `extract(output_dir)` | yes | `extract_async(output_dir)` | Archive → dir |

### `files_io.parallel_copy(sources, destinations, ...)`

Returns `{success: [...], failed: [{path, error}]}`

### `files_io.parallel_compress(dir_paths, output_paths, format)`

Returns `{success: [...], failed: [{path, error}]}`

### `files_io.check_duplicate(file_path, known_hashes)`

Returns `{hash: str, is_duplicate: bool}`

### `files_io.batch_hash(file_paths)`

Returns `{hashes: {path: hash}, errors: {path: error}}`
