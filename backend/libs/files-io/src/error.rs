use thiserror::Error;

#[derive(Error, Debug)]
pub enum FileError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("S3 error: {0}")]
    S3(String),

    #[error("Path error: {0}")]
    Path(String),

    #[error("Archive error: {0}")]
    Archive(String),

    #[error("Zip error: {0}")]
    Zip(#[from] zip::result::ZipError),

    #[error("Hash error: {0}")]
    Hash(String),

    #[error("Task join error: {0}")]
    TaskJoin(#[from] tokio::task::JoinError),

    #[error("{0}")]
    Other(String),
}

impl From<FileError> for pyo3::PyErr {
    fn from(err: FileError) -> Self {
        match err {
            FileError::Io(err) => pyo3::exceptions::PyIOError::new_err(err.to_string()),
            FileError::S3(message) => pyo3::exceptions::PyConnectionError::new_err(message),
            FileError::Path(message) => pyo3::exceptions::PyValueError::new_err(message),
            FileError::Archive(message) => pyo3::exceptions::PyValueError::new_err(message),
            FileError::Zip(err) => pyo3::exceptions::PyValueError::new_err(err.to_string()),
            FileError::Hash(message) => pyo3::exceptions::PyRuntimeError::new_err(message),
            FileError::TaskJoin(err) => pyo3::exceptions::PyRuntimeError::new_err(err.to_string()),
            FileError::Other(message) => pyo3::exceptions::PyRuntimeError::new_err(message),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::exceptions::{PyConnectionError, PyIOError, PyRuntimeError, PyValueError};
    use pyo3::prelude::*;

    #[test]
    fn io_errors_map_to_io_error() {
        let py_err: PyErr =
            FileError::Io(std::io::Error::from(std::io::ErrorKind::NotFound)).into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyIOError>(py)));
    }

    #[test]
    fn path_errors_map_to_value_error() {
        let py_err: PyErr = FileError::Path("bad path".into()).into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyValueError>(py)));
    }

    #[test]
    fn archive_errors_map_to_value_error() {
        let py_err: PyErr = FileError::Archive("bad archive".into()).into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyValueError>(py)));
    }

    #[test]
    fn s3_errors_map_to_connection_error() {
        let py_err: PyErr = FileError::S3("unavailable".into()).into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyConnectionError>(py)));
    }

    #[test]
    fn task_join_errors_stay_runtime_errors() {
        let py_err: PyErr = FileError::Other("unexpected".into()).into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyRuntimeError>(py)));
    }
}
