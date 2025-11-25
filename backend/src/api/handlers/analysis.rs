//! Analysis-related API handlers

use axum::{
    extract::{Path, State},
    Json,
};
use std::sync::Arc;

use crate::api::AppState;
use crate::api::validators;
use crate::models::dto::AnalysisResponse;
use crate::models::{AppError, AppResult};

/// Analyze a document
pub async fn analyze_document(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> AppResult<Json<AnalysisResponse>> {
    let uuid = validators::validate_uuid(&id)?;

    let result = state.evidence_service.process_document(uuid).await?;
    Ok(Json(result.into()))
}

/// Get analysis results for a document
pub async fn get_analysis_results(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> AppResult<Json<AnalysisResponse>> {
    let uuid = validators::validate_uuid(&id)?;

    let result = state
        .evidence_service
        .get_analysis(uuid)
        .await?
        .ok_or_else(|| {
            AppError::NotFound(format!("Analysis results not found for document: {}", id))
        })?;

    Ok(Json(result.into()))
}
