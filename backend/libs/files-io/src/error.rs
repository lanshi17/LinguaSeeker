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

    #[error("{0}")]
    Other(String),
}

impl From<FileError> for pyo3::PyErr {
    fn from(err: FileError) -> Self {
        pyo3::exceptions::PyRuntimeError::new_err(err.to_string())
    }
}
