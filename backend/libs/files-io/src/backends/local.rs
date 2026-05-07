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
    if file_size < 64 * 1024 { file_size }
    else if file_size < 10 * 1024 * 1024 { 64 * 1024 }
    else { 1024 * 1024 }
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
        if create_parents && let Some(parent) = Path::new(path).parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(path, data)?;
        Ok(())
    }

    fn write_stream(&self, path: &str, reader: &mut dyn Read, create_parents: bool) -> Result<(), FileError> {
        if create_parents && let Some(parent) = Path::new(path).parent() {
            fs::create_dir_all(parent)?;
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
        let mut extra = HashMap::new();
        let perms;
        #[cfg(unix)]
        {
            use std::os::unix::fs::{MetadataExt, PermissionsExt};
            let mode = meta.permissions().mode();
            perms = format!("{:o}", mode & 0o777);
            extra.insert("mode".to_string(), format!("{:o}", mode));
            extra.insert("inode".to_string(), meta.ino().to_string());
            extra.insert("nlink".to_string(), meta.nlink().to_string());
            extra.insert("uid".to_string(), meta.uid().to_string());
            extra.insert("gid".to_string(), meta.gid().to_string());
        }
        #[cfg(not(unix))]
        {
            perms = String::new();
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
