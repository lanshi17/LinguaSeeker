use crate::hash;
use pyo3::exceptions::PyIOError;
use pyo3::prelude::*;
use std::path::Path;

#[pyfunction]
pub fn compute_sha256(file_path: &str) -> PyResult<String> {
    hash::hash_file(Path::new(file_path)).map_err(|e| PyIOError::new_err(e.to_string()))
}

#[pyfunction]
pub fn write_file(file_path: &str, data: &[u8]) -> PyResult<()> {
    std::fs::write(file_path, data).map_err(|e| PyIOError::new_err(e.to_string()))
}

#[pyfunction]
pub fn validate_pdf_magic(data: &[u8]) -> PyResult<bool> {
    Ok(data.len() >= 4 && &data[..4] == b"%PDF")
}
