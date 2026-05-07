use crate::backends::{local::LocalBackend, s3::S3Backend, FileMetadata, FileOps};
use crate::error::FileError;
use crate::hash;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

enum Backend {
    Local(LocalBackend),
    S3(S3Backend),
}

#[pyclass]
pub struct File {
    path: String,
    backend: Backend,
}

impl File {
    fn ops(&self) -> &dyn FileOps {
        match &self.backend {
            Backend::Local(b) => b,
            Backend::S3(b) => b,
        }
    }
}

#[pymethods]
impl File {
    #[new]
    #[pyo3(signature = (path, access_key=None, secret_key=None, endpoint=None, region=None))]
    fn new(
        path: &str,
        access_key: Option<&str>,
        secret_key: Option<&str>,
        endpoint: Option<&str>,
        region: Option<&str>,
    ) -> PyResult<Self> {
        if path.starts_with("s3://") {
            let ak = access_key.ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>("access_key required for S3 paths")
            })?;
            let sk = secret_key.ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>("secret_key required for S3 paths")
            })?;
            let backend = S3Backend::new(ak, sk, endpoint, region)?;
            Ok(Self { path: path.to_string(), backend: Backend::S3(backend) })
        } else {
            Ok(Self { path: path.to_string(), backend: Backend::Local(LocalBackend::new()) })
        }
    }

    fn __enter__(slf: Py<Self>) -> Py<Self> { slf }

    fn __exit__(
        &mut self,
        _exc_type: Option<&Bound<'_, PyAny>>,
        _exc_value: Option<&Bound<'_, PyAny>>,
        _traceback: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<bool> {
        Ok(false)
    }

    #[pyo3(signature = (as_text=false))]
    fn read(&self, as_text: bool) -> PyResult<Py<PyAny>> {
        let data = self.ops().read_all(&self.path)?;
        Python::attach(|py| {
            if as_text {
                let s = String::from_utf8(data)
                    .map_err(|e| FileError::Other(format!("UTF-8 decode error: {e}")))?;
                Ok(s.into_pyobject(py)?.unbind().into_any())
            } else {
                Ok(PyBytes::new(py, &data).into_any().unbind())
            }
        })
    }

    fn read_chunk(&self, offset: u64, size: u64) -> PyResult<Py<PyAny>> {
        let data = self.ops().read_chunk(&self.path, offset, size)?;
        Python::attach(|py| Ok(PyBytes::new(py, &data).into_any().unbind()))
    }

    fn write(&self, data: &Bound<'_, PyAny>) -> PyResult<()> {
        let bytes: Vec<u8> = if let Ok(b) = data.extract::<Vec<u8>>() {
            b
        } else if let Ok(s) = data.extract::<String>() {
            s.into_bytes()
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "write() accepts bytes or str",
            ));
        };
        self.ops().write(&self.path, &bytes, true)?;
        Ok(())
    }

    fn exists(&self) -> PyResult<bool> {
        Ok(self.ops().exists(&self.path)?)
    }

    fn metadata<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let meta = self.ops().metadata(&self.path)?;
        let dict = PyDict::new(py);
        dict.set_item("size", meta.size)?;
        dict.set_item("mtime", meta.mtime)?;
        dict.set_item("is_file", meta.is_file)?;
        dict.set_item("is_dir", meta.is_dir)?;
        dict.set_item("is_symlink", meta.is_symlink)?;
        dict.set_item("permissions", &meta.permissions)?;
        for (k, v) in &meta.extra {
            dict.set_item(k, v)?;
        }
        Ok(dict)
    }

    fn rename(&self, dst: &str) -> PyResult<()> {
        self.ops().rename(&self.path, dst)?;
        Ok(())
    }

    fn copy(&self, dst: &str) -> PyResult<()> {
        self.ops().copy(&self.path, dst)?;
        Ok(())
    }

    fn remove(&self) -> PyResult<()> {
        self.ops().remove(&self.path)?;
        Ok(())
    }

    fn remove_dir_all(&self) -> PyResult<()> {
        self.ops().remove_dir_all(&self.path)?;
        Ok(())
    }

    fn list_dir(&self) -> PyResult<Vec<String>> {
        Ok(self.ops().list_dir(&self.path)?)
    }

    fn content_hash(&self) -> PyResult<String> {
        match &self.backend {
            Backend::Local(_) => {
                Ok(hash::hash_file(std::path::Path::new(&self.path))?)
            }
            Backend::S3(_) => {
                let data = self.ops().read_all(&self.path)?;
                Ok(hash::hash_bytes(&data))
            }
        }
    }
}
