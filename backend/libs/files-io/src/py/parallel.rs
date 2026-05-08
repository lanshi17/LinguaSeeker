use crate::backends::{local::LocalBackend, s3::S3Backend, FileOps};
use crate::error::FileError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::sync::Arc;

struct OpResult {
    path: String,
    success: bool,
    message: String,
}

fn make_result_dict(py: Python<'_>, results: &[OpResult]) -> PyResult<Py<PyAny>> {
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

/// Copy multiple files sequentially. Returns {success: [...], failed: [{path, error}]}.
#[pyfunction]
#[pyo3(name = "batch_copy", signature = (sources, destinations, access_key=None, secret_key=None, endpoint=None, region=None))]
pub fn batch_copy(
    py: Python<'_>,
    sources: Vec<String>,
    destinations: Vec<String>,
    access_key: Option<String>,
    secret_key: Option<String>,
    endpoint: Option<String>,
    region: Option<String>,
) -> PyResult<Py<PyAny>> {
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

/// Compress multiple directories sequentially. Returns {success: [...], failed: [{path, error}]}.
#[pyfunction]
#[pyo3(name = "batch_compress", signature = (dir_paths, output_paths, format="zip"))]
pub fn batch_compress(
    py: Python<'_>,
    dir_paths: Vec<String>,
    output_paths: Vec<String>,
    format: &str,
) -> PyResult<Py<PyAny>> {
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

/// Async batch copy using spawn_blocking.
#[pyfunction]
#[pyo3(name = "batch_copy_async", signature = (sources, destinations, access_key=None, secret_key=None, endpoint=None, region=None))]
pub fn batch_copy_async<'py>(
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
            Python::attach(|py| {
                batch_copy(py, sources, destinations, access_key, secret_key, endpoint, region)
            })
        }).await.map_err(|e| FileError::Other(e.to_string()))??;
        Ok(result)
    })
}
