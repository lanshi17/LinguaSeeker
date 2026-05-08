use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn compatibility_utils_match_legacy_rust_io_files_behavior() {
    let suffix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("files_io_py_utils_{suffix}"));
    fs::create_dir(&dir).unwrap();
    let path = dir.join("sample.bin");
    let path_str = path.to_str().unwrap();

    files_io::py::utils::write_file(path_str, b"abc").unwrap();

    assert_eq!(fs::read(&path).unwrap(), b"abc");
    assert_eq!(
        files_io::py::utils::compute_sha256(path_str).unwrap(),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
    assert!(files_io::py::utils::validate_pdf_magic(b"%PDF-1.7").unwrap());
    assert!(!files_io::py::utils::validate_pdf_magic(b"not a pdf").unwrap());

    fs::remove_file(path).unwrap();
    fs::remove_dir(dir).unwrap();
}
