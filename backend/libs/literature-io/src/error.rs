use thiserror::Error;

#[derive(Error, Debug)]
pub enum GatewayError {
    #[error("HTTP request failed: {0}")]
    Http(#[from] reqwest::Error),

    #[error("JSON parse error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("URL parse error: {0}")]
    Url(#[from] url::ParseError),

    #[error("Provider '{provider}' error: {message}")]
    Provider { provider: String, message: String },

    #[error("{0}")]
    Other(String),
}

impl From<GatewayError> for pyo3::PyErr {
    fn from(err: GatewayError) -> Self {
        pyo3::exceptions::PyRuntimeError::new_err(err.to_string())
    }
}
