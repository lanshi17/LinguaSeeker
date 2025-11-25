//! Analysis-related API handlers

use axum::{
    extract::{Path, State},
    Json,
};
use std::sync::Arc;
use uuid::Uuid;

use crate::api::AppState;
use crate::models::dto::AnalysisResponse;
use crate::models::{AppError, AppResult};

/// Analyze a document
pub async fn analyze_document(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> AppResult<Json<AnalysisResponse>> {
    let uuid = Uuid::parse_str(&id)
        .map_err(|_| AppError::InvalidInput(format!("Invalid document ID: {}", id)))?;

    let result = state.evidence_service.process_document(uuid).await?;
    Ok(Json(result.into()))
}

/// Get analysis results for a document
pub async fn get_analysis_results(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> AppResult<Json<AnalysisResponse>> {
    let uuid = Uuid::parse_str(&id)
        .map_err(|_| AppError::InvalidInput(format!("Invalid document ID: {}", id)))?;

    let result = state
        .evidence_service
        .get_analysis(uuid)
        .await?
        .ok_or_else(|| {
            AppError::NotFound(format!("Analysis results not found for document: {}", id))
        })?;

    Ok(Json(result.into()))
}
