//! API route definitions
//!
//! This module defines all API routes and connects them to their handlers

use axum::{
    routing::{get, post},
    Router,
};
use std::sync::Arc;

use super::handlers;
use super::AppState;

/// Create the API router with all routes
pub fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/", get(index_handler))
        .route("/api/health", get(handlers::health_check))
        .route("/api/documents", get(handlers::list_documents))
        .route("/api/documents", post(handlers::upload_document))
        .route("/api/documents/{id}", get(handlers::get_document))
        .route("/api/documents/{id}/analyze", post(handlers::analyze_document))
        .route("/api/documents/{id}/results", get(handlers::get_analysis_results))
        .with_state(state)
}

/// Index page handler - serves interactive HTML interface
async fn index_handler() -> axum::response::Html<&'static str> {
    axum::response::Html(include_str!("../static/index.html"))
}
