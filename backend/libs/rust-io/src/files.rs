use pyo3::prelude::*;
use sha2::{Digest, Sha256};
use std::io::Write;

#[pyfunction]
pub fn compute_sha256(file_path: &str) -> PyResult<String> {
    let data = std::fs::read(file_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
    let mut hasher = Sha256::new();
    hasher.update(&data);
    Ok(format!("{:x}", hasher.finalize()))
}

#[pyfunction]
pub fn write_file(file_path: &str, data: &[u8]) -> PyResult<()> {
    let mut file = std::fs::File::create(file_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
    file.write_all(data)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
    Ok(())
}

#[pyfunction]
pub fn validate_pdf_magic(data: &[u8]) -> PyResult<bool> {
    Ok(data.len() >= 4 && &data[..4] == b"%PDF")
}
