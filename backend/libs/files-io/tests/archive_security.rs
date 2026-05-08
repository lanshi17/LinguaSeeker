use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use files_io::archive::{tar_gz, zip as zip_archive};
use zip::write::SimpleFileOptions;

struct TestDir {
    path: PathBuf,
}

impl TestDir {
    fn new(name: &str) -> Self {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!("files_io_{name}_{suffix}"));
        fs::create_dir(&path).unwrap();
        Self { path }
    }

    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TestDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}

fn create_zip_with_file(archive_path: &Path, name: &str, contents: &[u8]) {
    let file = fs::File::create(archive_path).unwrap();
    let mut archive = zip::ZipWriter::new(file);
    archive
        .start_file(name, SimpleFileOptions::default())
        .unwrap();
    archive.write_all(contents).unwrap();
    archive.finish().unwrap();
}

fn write_u16(bytes: &mut Vec<u8>, value: u16) {
    bytes.extend_from_slice(&value.to_le_bytes());
}

fn write_u32(bytes: &mut Vec<u8>, value: u32) {
    bytes.extend_from_slice(&value.to_le_bytes());
}

fn create_zip_with_symlink_entry(archive_path: &Path) {
    let name = b"link";
    let mut bytes = Vec::new();

    write_u32(&mut bytes, 0x0403_4b50);
    write_u16(&mut bytes, 20);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u32(&mut bytes, 0);
    write_u32(&mut bytes, 0);
    write_u32(&mut bytes, 0);
    write_u16(&mut bytes, name.len() as u16);
    write_u16(&mut bytes, 0);
    bytes.extend_from_slice(name);

    let central_directory_offset = bytes.len() as u32;
    write_u32(&mut bytes, 0x0201_4b50);
    write_u16(&mut bytes, 0x0314);
    write_u16(&mut bytes, 20);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u32(&mut bytes, 0);
    write_u32(&mut bytes, 0);
    write_u32(&mut bytes, 0);
    write_u16(&mut bytes, name.len() as u16);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u32(&mut bytes, 0o120777 << 16);
    write_u32(&mut bytes, 0);
    bytes.extend_from_slice(name);

    let central_directory_size = bytes.len() as u32 - central_directory_offset;
    write_u32(&mut bytes, 0x0605_4b50);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 0);
    write_u16(&mut bytes, 1);
    write_u16(&mut bytes, 1);
    write_u32(&mut bytes, central_directory_size);
    write_u32(&mut bytes, central_directory_offset);
    write_u16(&mut bytes, 0);

    fs::write(archive_path, bytes).unwrap();
}

#[cfg(unix)]
#[test]
fn zip_extract_rejects_entries_that_write_through_existing_symlink_parent() {
    let dir = TestDir::new("zip_existing_symlink_parent");
    let archive_path = dir.path().join("archive.zip");
    let output_dir = dir.path().join("output");
    let outside_dir = dir.path().join("outside");
    fs::create_dir(&output_dir).unwrap();
    fs::create_dir(&outside_dir).unwrap();
    std::os::unix::fs::symlink(&outside_dir, output_dir.join("link")).unwrap();
    create_zip_with_file(&archive_path, "link/pwned.txt", b"pwned");

    let err = zip_archive::extract(archive_path.to_str().unwrap(), output_dir.to_str().unwrap())
        .unwrap_err();

    assert!(
        err.to_string()
            .contains("resolves outside output directory")
    );
    assert!(!outside_dir.join("pwned.txt").exists());
}

#[test]
fn zip_extract_rejects_symlink_entries() {
    let dir = TestDir::new("zip_symlink_entry");
    let archive_path = dir.path().join("archive.zip");
    let output_dir = dir.path().join("output");
    create_zip_with_symlink_entry(&archive_path);

    let err = zip_archive::extract(archive_path.to_str().unwrap(), output_dir.to_str().unwrap())
        .unwrap_err();

    assert!(
        err.to_string()
            .contains("symlink entries are not supported")
    );
}

#[test]
fn tar_extract_rejects_symlink_entries() {
    let dir = TestDir::new("tar_symlink_entry");
    let archive_path = dir.path().join("archive.tar");
    let output_dir = dir.path().join("output");
    let outside_dir = dir.path().join("outside");
    fs::create_dir(&outside_dir).unwrap();
    let file = fs::File::create(&archive_path).unwrap();
    let mut archive = tar::Builder::new(file);
    let mut header = tar::Header::new_gnu();
    header.set_entry_type(tar::EntryType::Symlink);
    header.set_size(0);
    header.set_path("link").unwrap();
    header.set_link_name(&outside_dir).unwrap();
    header.set_cksum();
    archive.append(&header, std::io::empty()).unwrap();
    archive.finish().unwrap();

    let err = tar_gz::extract_tar(archive_path.to_str().unwrap(), output_dir.to_str().unwrap())
        .unwrap_err();

    assert!(
        err.to_string()
            .contains("symlink entries are not supported")
    );
    assert!(!output_dir.join("link").exists());
}

#[test]
fn tar_gz_extract_rejects_symlink_entries() {
    let dir = TestDir::new("tar_gz_symlink_entry");
    let archive_path = dir.path().join("archive.tar.gz");
    let output_dir = dir.path().join("output");
    let outside_dir = dir.path().join("outside");
    fs::create_dir(&outside_dir).unwrap();
    let file = fs::File::create(&archive_path).unwrap();
    let enc = flate2::write::GzEncoder::new(file, flate2::Compression::default());
    let mut archive = tar::Builder::new(enc);
    let mut header = tar::Header::new_gnu();
    header.set_entry_type(tar::EntryType::Symlink);
    header.set_size(0);
    header.set_path("link").unwrap();
    header.set_link_name(&outside_dir).unwrap();
    header.set_cksum();
    archive.append(&header, std::io::empty()).unwrap();
    archive.finish().unwrap();
    archive.into_inner().unwrap().finish().unwrap();

    let err = tar_gz::extract_tar_gz(archive_path.to_str().unwrap(), output_dir.to_str().unwrap())
        .unwrap_err();

    assert!(
        err.to_string()
            .contains("symlink entries are not supported")
    );
    assert!(!output_dir.join("link").exists());
}
