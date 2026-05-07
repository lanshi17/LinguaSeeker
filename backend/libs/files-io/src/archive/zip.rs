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
