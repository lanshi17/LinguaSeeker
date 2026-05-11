use thiserror::Error;

#[derive(Error, Debug)]
pub enum GatewayError {
    #[error("HTTP request failed: {0}")]
    Http(#[from] reqwest::Error),

    #[error("JSON parse error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("URL parse error: {0}")]
    Url(#[from] url::ParseError),

    #[error("Provider '{provider}' error: {message}")]
    Provider { provider: String, message: String },

    #[error("{0}")]
    Other(String),
}

impl From<GatewayError> for pyo3::PyErr {
    fn from(err: GatewayError) -> Self {
        match err {
            GatewayError::Http(err) => {
                pyo3::exceptions::PyConnectionError::new_err(err.to_string())
            }
            GatewayError::Json(err) => pyo3::exceptions::PyValueError::new_err(err.to_string()),
            GatewayError::Io(err) => pyo3::exceptions::PyOSError::new_err(err.to_string()),
            GatewayError::Url(err) => pyo3::exceptions::PyValueError::new_err(err.to_string()),
            GatewayError::Provider { provider, message } => {
                pyo3::exceptions::PyRuntimeError::new_err(format!(
                    "Provider '{provider}' error: {message}"
                ))
            }
            GatewayError::Other(message) => pyo3::exceptions::PyRuntimeError::new_err(message),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::exceptions::{PyRuntimeError, PyValueError};
    use pyo3::prelude::*;

    #[test]
    fn json_errors_map_to_value_error() {
        let err = serde_json::from_str::<serde_json::Value>("not json").unwrap_err();
        let py_err: PyErr = GatewayError::Json(err).into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyValueError>(py)));
    }

    #[test]
    fn url_errors_map_to_value_error() {
        let err = url::Url::parse("not a url").unwrap_err();
        let py_err: PyErr = GatewayError::Url(err).into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyValueError>(py)));
    }

    #[test]
    fn provider_errors_map_to_runtime_error() {
        let py_err: PyErr = GatewayError::Provider {
            provider: "test".to_string(),
            message: "failed".to_string(),
        }
        .into();
        Python::initialize();
        Python::attach(|py| assert!(py_err.is_instance_of::<PyRuntimeError>(py)));
    }
}
