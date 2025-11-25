//! Document-related API handlers

use axum::{
    extract::{Multipart, Path, State},
    Json,
};
use chrono::Utc;
use sha2::{Digest, Sha256};
use std::sync::Arc;
use uuid::Uuid;

use crate::api::AppState;
use crate::api::validators;
use crate::models::dto::{DocumentListResponse, DocumentResponse, UploadResponse};
use crate::models::{AppError, AppResult, Document, DocumentStatus, Language};
use crate::repositories::documents;

/// List all documents
pub async fn list_documents(
    State(state): State<Arc<AppState>>,
) -> AppResult<Json<DocumentListResponse>> {
    let docs = documents::list(&state.pool).await?;
    let total = docs.len();
    let doc_responses: Vec<DocumentResponse> = docs.into_iter().map(Into::into).collect();

    Ok(Json(DocumentListResponse { documents: doc_responses, total }))
}

/// Upload a document
pub async fn upload_document(
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> AppResult<Json<UploadResponse>> {
    let mut filename = String::new();
    let mut content = Vec::new();
    let mut detected_language = Language::English;

    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| AppError::InvalidInput(format!("Failed to read multipart field: {}", e)))?
    {
        let field_name = field.name().unwrap_or("").to_string();

        match field_name.as_str() {
            "file" => {
                filename = field
                    .file_name()
                    .map(|s| s.to_string())
                    .unwrap_or_else(|| "document.pdf".to_string());

                content = field
                    .bytes()
                    .await
                    .map_err(|e| AppError::InvalidInput(format!("Failed to read file: {}", e)))?
                    .to_vec();
            }
            "language" => {
                let lang_str = field
                    .text()
                    .await
                    .map_err(|e| AppError::InvalidInput(format!("Failed to read language: {}", e)))?;
                detected_language = lang_str.parse().unwrap_or(Language::English);
            }
            _ => {}
        }
    }

    if content.is_empty() {
        return Err(AppError::InvalidInput("No file uploaded".to_string()));
    }

    // Calculate content hash
    let mut hasher = Sha256::new();
    hasher.update(&content);
    let content_hash = format!("{:x}", hasher.finalize());

    // Create document record
    let document_id = Uuid::new_v4();
    let document = Document {
        id: document_id,
        filename: filename.clone(),
        language: detected_language,
        upload_time: Utc::now(),
        content_hash,
        extracted_text: None,
        status: DocumentStatus::Uploaded,
    };

    // Store document metadata via repository
    documents::insert(&state.pool, &document).await?;

    // Store raw content as extracted text (placeholder for actual PDF extraction)
    let extracted_text = String::from_utf8_lossy(&content).to_string();
    if !extracted_text.is_empty() {
        documents::update_extracted_text(&state.pool, document_id, &extracted_text).await?;
    }

    Ok(Json(UploadResponse {
        id: document_id.to_string(),
        filename,
        language: detected_language.to_string(),
        status: "uploaded".to_string(),
        message: "Document uploaded successfully. Use /api/documents/{id}/analyze to process."
            .to_string(),
    }))
}

/// Get document by ID
pub async fn get_document(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> AppResult<Json<DocumentResponse>> {
    let uuid = validators::validate_uuid(&id)?;

    let document = documents::get_by_id(&state.pool, uuid)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("Document not found: {}", id)))?;

    Ok(Json(document.into()))
}
