//! Error handling for the evidence platform

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

/// Application error types
#[derive(Debug, Error)]
pub enum AppError {
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),

    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),

    #[error("HTTP request error: {0}")]
    Request(#[from] reqwest::Error),

    #[error("Invalid input: {0}")]
    InvalidInput(String),

    #[error("Document not found: {0}")]
    NotFound(String),

    #[error("Processing error: {0}")]
    Processing(String),

    #[error("LLM error: {0}")]
    Llm(String),

    #[error("ClinVar API error: {0}")]
    ClinVar(String),

    #[error("Internal error: {0}")]
    Internal(String),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, error_message) = match &self {
            AppError::Database(e) => {
                tracing::error!("Database error: {:?}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Database error occurred".to_string())
            }
            AppError::Redis(e) => {
                tracing::error!("Redis error: {:?}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Cache error occurred".to_string())
            }
            AppError::Request(e) => {
                tracing::error!("Request error: {:?}", e);
                (StatusCode::BAD_GATEWAY, "External service error".to_string())
            }
            AppError::InvalidInput(msg) => (StatusCode::BAD_REQUEST, msg.clone()),
            AppError::NotFound(msg) => (StatusCode::NOT_FOUND, msg.clone()),
            AppError::Processing(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg.clone()),
            AppError::Llm(_) => (StatusCode::SERVICE_UNAVAILABLE, "LLM service unavailable".to_string()),
            AppError::ClinVar(_) => (StatusCode::BAD_GATEWAY, "ClinVar API error".to_string()),
            AppError::Internal(e) => {
                tracing::error!("Internal error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal server error".to_string())
            }
        };

        let body = Json(json!({
            "error": error_message,
            "details": self.to_string()
        }));

        (status, body).into_response()
    }
}

/// Result type alias for application operations
pub type AppResult<T> = Result<T, AppError>;
