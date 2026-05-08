use crate::hash;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;
use std::path::Path;

#[pyfunction]
pub fn check_duplicate(file_path: &str, known_hashes: Vec<String>) -> PyResult<Py<PyAny>> {
    let file_hash = hash::hash_file(Path::new(file_path))?;
    let is_dup = known_hashes.contains(&file_hash);
    Python::attach(|py| {
        let dict = PyDict::new(py);
        dict.set_item("hash", &file_hash)?;
        dict.set_item("is_duplicate", is_dup)?;
        Ok(dict.into_any().unbind())
    })
}

#[pyfunction]
pub fn batch_hash(file_paths: Vec<String>) -> PyResult<Py<PyAny>> {
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
