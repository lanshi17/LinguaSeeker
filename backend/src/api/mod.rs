//! API routes and handlers for the evidence platform

use axum::{
    extract::{Multipart, Path, State},
    http::StatusCode,
    response::{Html, IntoResponse, Json},
    routing::{get, post},
    Router,
};
use chrono::Utc;
use serde::Serialize;
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use std::sync::Arc;
use uuid::Uuid;

use crate::config::Config;
use crate::db;
use crate::error::AppError;
use crate::models::{Document, DocumentStatus, Language};
use crate::services::EvidenceService;

/// Application state shared across handlers
pub struct AppState {
    pub pool: PgPool,
    pub config: Config,
    pub evidence_service: EvidenceService,
}

impl AppState {
    pub fn new(pool: PgPool, config: Config) -> Self {
        let evidence_service = EvidenceService::new(pool.clone(), &config);
        Self {
            pool,
            config,
            evidence_service,
        }
    }
}

/// Create the API router
pub fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/", get(index_handler))
        .route("/api/health", get(health_check))
        .route("/api/documents", get(list_documents))
        .route("/api/documents", post(upload_document))
        .route("/api/documents/{id}", get(get_document))
        .route("/api/documents/{id}/analyze", post(analyze_document))
        .route("/api/documents/{id}/results", get(get_analysis_results))
        .with_state(state)
}

/// Index page handler - serves interactive HTML interface
async fn index_handler() -> Html<&'static str> {
    Html(include_str!("../static/index.html"))
}

/// Health check endpoint
async fn health_check(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    // Check database connection
    match sqlx::query("SELECT 1").execute(&state.pool).await {
        Ok(_) => (
            StatusCode::OK,
            Json(serde_json::json!({
                "status": "healthy",
                "database": "connected",
                "version": env!("CARGO_PKG_VERSION")
            })),
        ),
        Err(_) => (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(serde_json::json!({
                "status": "unhealthy",
                "database": "disconnected"
            })),
        ),
    }
}

/// List all documents response
#[derive(Debug, Serialize)]
struct DocumentListResponse {
    documents: Vec<DocumentResponse>,
    total: usize,
}

/// Single document response
#[derive(Debug, Serialize)]
struct DocumentResponse {
    id: String,
    filename: String,
    language: String,
    upload_time: String,
    status: String,
}

impl From<Document> for DocumentResponse {
    fn from(doc: Document) -> Self {
        Self {
            id: doc.id.to_string(),
            filename: doc.filename,
            language: doc.language.to_string(),
            upload_time: doc.upload_time.to_rfc3339(),
            status: format!("{:?}", doc.status).to_lowercase(),
        }
    }
}

/// List all documents
async fn list_documents(
    State(state): State<Arc<AppState>>,
) -> Result<Json<DocumentListResponse>, AppError> {
    let documents = db::documents::list(&state.pool).await?;
    let total = documents.len();
    let documents: Vec<DocumentResponse> = documents.into_iter().map(Into::into).collect();

    Ok(Json(DocumentListResponse { documents, total }))
}

/// Upload document request
#[derive(Debug, Serialize)]
struct UploadResponse {
    id: String,
    filename: String,
    language: String,
    status: String,
    message: String,
}

/// Upload a document
async fn upload_document(
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<Json<UploadResponse>, AppError> {
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
        extracted_text: None, // Will be populated by PDF extraction
        status: DocumentStatus::Uploaded,
    };

    // Store document metadata
    db::documents::insert(&state.pool, &document).await?;

    // For now, store raw content as extracted text (placeholder for actual PDF extraction)
    // In production, this would use a PDF parsing library
    let extracted_text = String::from_utf8_lossy(&content).to_string();
    if !extracted_text.is_empty() {
        db::documents::update_extracted_text(&state.pool, document_id, &extracted_text).await?;
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
async fn get_document(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<DocumentResponse>, AppError> {
    let uuid = Uuid::parse_str(&id)
        .map_err(|_| AppError::InvalidInput(format!("Invalid document ID: {}", id)))?;

    let document = db::documents::get_by_id(&state.pool, uuid)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("Document not found: {}", id)))?;

    Ok(Json(document.into()))
}

/// Analysis response
#[derive(Debug, Serialize)]
struct AnalysisResponse {
    id: String,
    document_id: String,
    evidence: Vec<EvidenceResponse>,
    clinvar_results: Vec<ClinVarResponse>,
    final_classification: Option<String>,
    confidence_score: f64,
    analysis_time: String,
}

#[derive(Debug, Serialize)]
struct EvidenceResponse {
    id: String,
    variant_id: String,
    gene: String,
    transcript: Option<String>,
    hgvs_c: Option<String>,
    hgvs_p: Option<String>,
    evidence_text: String,
    acmg_criteria: crate::models::AcmgCriteria,
    suggested_classification: Option<String>,
    confidence_score: f64,
}

#[derive(Debug, Serialize)]
struct ClinVarResponse {
    variant_id: String,
    clinvar_id: Option<String>,
    review_status: Option<String>,
    classification: Option<String>,
    last_evaluated: Option<String>,
    submitter_count: u32,
    condition: Option<String>,
}

/// Analyze a document
async fn analyze_document(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<AnalysisResponse>, AppError> {
    let uuid = Uuid::parse_str(&id)
        .map_err(|_| AppError::InvalidInput(format!("Invalid document ID: {}", id)))?;

    let result = state.evidence_service.process_document(uuid).await?;

    let response = AnalysisResponse {
        id: result.id.to_string(),
        document_id: result.document_id.to_string(),
        evidence: result
            .evidence
            .into_iter()
            .map(|e| EvidenceResponse {
                id: e.id.to_string(),
                variant_id: e.variant_id,
                gene: e.gene,
                transcript: e.transcript,
                hgvs_c: e.hgvs_c,
                hgvs_p: e.hgvs_p,
                evidence_text: e.evidence_text,
                acmg_criteria: e.acmg_criteria,
                suggested_classification: e.suggested_classification.map(|c| c.to_string()),
                confidence_score: e.confidence_score,
            })
            .collect(),
        clinvar_results: result
            .clinvar_results
            .into_iter()
            .map(|c| ClinVarResponse {
                variant_id: c.variant_id,
                clinvar_id: c.clinvar_id,
                review_status: c.review_status,
                classification: c.classification.map(|cl| cl.to_string()),
                last_evaluated: c.last_evaluated.map(|d| d.to_rfc3339()),
                submitter_count: c.submitter_count,
                condition: c.condition,
            })
            .collect(),
        final_classification: result.final_classification.map(|c| c.to_string()),
        confidence_score: result.confidence_score,
        analysis_time: result.analysis_time.to_rfc3339(),
    };

    Ok(Json(response))
}

/// Get analysis results for a document
async fn get_analysis_results(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<AnalysisResponse>, AppError> {
    let uuid = Uuid::parse_str(&id)
        .map_err(|_| AppError::InvalidInput(format!("Invalid document ID: {}", id)))?;

    let result = state
        .evidence_service
        .get_analysis(uuid)
        .await?
        .ok_or_else(|| {
            AppError::NotFound(format!("Analysis results not found for document: {}", id))
        })?;

    let response = AnalysisResponse {
        id: result.id.to_string(),
        document_id: result.document_id.to_string(),
        evidence: result
            .evidence
            .into_iter()
            .map(|e| EvidenceResponse {
                id: e.id.to_string(),
                variant_id: e.variant_id,
                gene: e.gene,
                transcript: e.transcript,
                hgvs_c: e.hgvs_c,
                hgvs_p: e.hgvs_p,
                evidence_text: e.evidence_text,
                acmg_criteria: e.acmg_criteria,
                suggested_classification: e.suggested_classification.map(|c| c.to_string()),
                confidence_score: e.confidence_score,
            })
            .collect(),
        clinvar_results: result
            .clinvar_results
            .into_iter()
            .map(|c| ClinVarResponse {
                variant_id: c.variant_id,
                clinvar_id: c.clinvar_id,
                review_status: c.review_status,
                classification: c.classification.map(|cl| cl.to_string()),
                last_evaluated: c.last_evaluated.map(|d| d.to_rfc3339()),
                submitter_count: c.submitter_count,
                condition: c.condition,
            })
            .collect(),
        final_classification: result.final_classification.map(|c| c.to_string()),
        confidence_score: result.confidence_score,
        analysis_time: result.analysis_time.to_rfc3339(),
    };

    Ok(Json(response))
}
