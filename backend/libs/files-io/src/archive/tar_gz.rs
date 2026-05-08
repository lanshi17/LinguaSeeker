use crate::error::FileError;
use flate2::Compression;
use flate2::read::GzDecoder;
use flate2::write::GzEncoder;
use std::fs;
use std::io::Read;
use std::path::{Component, Path};
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

fn is_safe_path(path: &Path) -> bool {
    path.components().all(|component| {
        !matches!(
            component,
            Component::ParentDir | Component::RootDir | Component::Prefix(_)
        )
    })
}

fn validate_entry_path(entry_path: &Path, out_root: &Path) -> Result<(), FileError> {
    if !is_safe_path(entry_path) {
        return Err(FileError::Archive(format!(
            "path traversal attempt: entry '{}' contains unsafe components",
            entry_path.display()
        )));
    }

    let mut current = out_root.to_path_buf();
    for component in entry_path.components() {
        current.push(component.as_os_str());
        if current.exists() {
            let canonical = fs::canonicalize(&current)?;
            if !canonical.starts_with(out_root) {
                return Err(FileError::Archive(format!(
                    "path traversal attempt: entry '{}' resolves outside output directory",
                    entry_path.display()
                )));
            }
        }
    }
    Ok(())
}

fn reject_link_entry(entry_type: tar::EntryType, entry_path: &Path) -> Result<(), FileError> {
    if entry_type.is_symlink() {
        return Err(FileError::Archive(format!(
            "symlink entries are not supported: '{}'",
            entry_path.display()
        )));
    }
    if entry_type.is_hard_link() {
        return Err(FileError::Archive(format!(
            "hardlink entries are not supported: '{}'",
            entry_path.display()
        )));
    }
    Ok(())
}

fn extract_archive<R: Read>(mut archive: Archive<R>, output_dir: &str) -> Result<u64, FileError> {
    fs::create_dir_all(output_dir)?;
    let out_root = fs::canonicalize(output_dir)?;
    let mut count: u64 = 0;

    for entry in archive
        .entries()
        .map_err(|e| FileError::Archive(e.to_string()))?
    {
        let mut entry = entry.map_err(|e| FileError::Archive(e.to_string()))?;
        let entry_path = entry
            .path()
            .map_err(|e| FileError::Archive(e.to_string()))?
            .to_path_buf();
        let entry_type = entry.header().entry_type();
        reject_link_entry(entry_type, &entry_path)?;
        validate_entry_path(&entry_path, &out_root)?;
        entry
            .unpack_in(output_dir)
            .map_err(|e| FileError::Archive(e.to_string()))?;
        if entry_type.is_file() {
            count += 1;
        }
    }
    Ok(count)
}

/// Extract a .tar archive to a directory.
///
/// Validates that all extracted paths remain within `output_dir` to prevent
/// path traversal attacks (e.g. entries containing `..`).
pub fn extract_tar(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let file = fs::File::open(archive_path)?;
    extract_archive(Archive::new(file), output_dir)
}

/// Extract a .tar.gz archive to a directory.
///
/// Validates that all extracted paths remain within `output_dir` to prevent
/// path traversal attacks (e.g. entries containing `..`).
pub fn extract_tar_gz(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let file = fs::File::open(archive_path)?;
    let dec = GzDecoder::new(file);
    extract_archive(Archive::new(dec), output_dir)
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
