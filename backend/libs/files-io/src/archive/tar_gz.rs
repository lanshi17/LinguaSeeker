use crate::error::FileError;
use flate2::read::GzDecoder;
use flate2::write::GzEncoder;
use flate2::Compression;
use std::fs;
use std::path::{Path, Component};
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

/// Check if a tar entry path is safe (no path traversal).
fn is_safe_path(path: &Path) -> bool {
    for component in path.components() {
        match component {
            Component::ParentDir | Component::RootDir | Component::Prefix(_) => return false,
            _ => {}
        }
    }
    true
}

/// Extract a .tar archive to a directory.
///
/// Validates that all extracted paths remain within `output_dir` to prevent
/// path traversal attacks (e.g. entries containing `..`).
pub fn extract_tar(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let file = fs::File::open(archive_path)?;
    let mut archive = Archive::new(file);
    fs::create_dir_all(output_dir)?;
    let out_root = fs::canonicalize(output_dir)?;
    let mut count: u64 = 0;

    for entry in archive.entries().map_err(|e| FileError::Archive(e.to_string()))? {
        let mut entry = entry.map_err(|e| FileError::Archive(e.to_string()))?;
        let entry_path = entry.path().map_err(|e| FileError::Archive(e.to_string()))?.to_path_buf();
        if !is_safe_path(&entry_path) {
            return Err(FileError::Archive(format!(
                "path traversal attempt: entry '{}' contains unsafe components",
                entry_path.display()
            )));
        }
        let outpath = out_root.join(&entry_path);
        // Verify resolved path stays within output_dir
        if let Some(parent) = outpath.parent()
            && parent.exists()
        {
            let canon = fs::canonicalize(parent).unwrap_or(parent.to_path_buf());
            if !canon.starts_with(&out_root) {
                return Err(FileError::Archive(format!(
                    "path traversal attempt: entry '{}' resolves outside output directory",
                    entry_path.display()
                )));
            }
        }
        entry.unpack_in(output_dir).map_err(|e| FileError::Archive(e.to_string()))?;
        if entry_path.is_file() || !entry_path.to_string_lossy().ends_with('/') {
            count += 1;
        }
    }
    Ok(count)
}

/// Extract a .tar.gz archive to a directory.
///
/// Validates that all extracted paths remain within `output_dir` to prevent
/// path traversal attacks (e.g. entries containing `..`).
pub fn extract_tar_gz(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let file = fs::File::open(archive_path)?;
    let dec = GzDecoder::new(file);
    let mut archive = Archive::new(dec);
    fs::create_dir_all(output_dir)?;
    let out_root = fs::canonicalize(output_dir)?;
    let mut count: u64 = 0;

    for entry in archive.entries().map_err(|e| FileError::Archive(e.to_string()))? {
        let mut entry = entry.map_err(|e| FileError::Archive(e.to_string()))?;
        let entry_path = entry.path().map_err(|e| FileError::Archive(e.to_string()))?.to_path_buf();
        if !is_safe_path(&entry_path) {
            return Err(FileError::Archive(format!(
                "path traversal attempt: entry '{}' contains unsafe components",
                entry_path.display()
            )));
        }
        let outpath = out_root.join(&entry_path);
        if let Some(parent) = outpath.parent()
            && parent.exists()
        {
            let canon = fs::canonicalize(parent).unwrap_or(parent.to_path_buf());
            if !canon.starts_with(&out_root) {
                return Err(FileError::Archive(format!(
                    "path traversal attempt: entry '{}' resolves outside output directory",
                    entry_path.display()
                )));
            }
        }
        entry.unpack_in(output_dir).map_err(|e| FileError::Archive(e.to_string()))?;
        if entry_path.is_file() || !entry_path.to_string_lossy().ends_with('/') {
            count += 1;
        }
    }
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
