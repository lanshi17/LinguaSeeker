//! Document Data Transfer Objects

use serde::{Deserialize, Serialize};

use crate::models::{Document, DocumentStatus, Language};

/// Response DTO for a single document
#[derive(Debug, Serialize)]
pub struct DocumentResponse {
    pub id: String,
    pub filename: String,
    pub language: String,
    pub upload_time: String,
    pub status: String,
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

/// Response DTO for document list
#[derive(Debug, Serialize)]
pub struct DocumentListResponse {
    pub documents: Vec<DocumentResponse>,
    pub total: usize,
}

/// Response DTO for document upload
#[derive(Debug, Serialize)]
pub struct UploadResponse {
    pub id: String,
    pub filename: String,
    pub language: String,
    pub status: String,
    pub message: String,
}

/// Request DTO for document upload (language field from form)
#[derive(Debug, Deserialize)]
pub struct UploadRequest {
    #[serde(default)]
    pub language: Option<String>,
}

impl UploadRequest {
    /// Parse language from request, defaulting to English
    pub fn get_language(&self) -> Language {
        self.language
            .as_ref()
            .and_then(|s| s.parse().ok())
            .unwrap_or(Language::English)
    }
}
