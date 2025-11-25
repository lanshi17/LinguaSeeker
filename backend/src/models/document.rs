//! Document-related models

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use super::language::Language;

/// Uploaded document metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    pub id: Uuid,
    pub filename: String,
    pub language: Language,
    pub upload_time: DateTime<Utc>,
    pub content_hash: String,
    pub extracted_text: Option<String>,
    pub status: DocumentStatus,
}

/// Document processing status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DocumentStatus {
    Uploaded,
    Processing,
    Processed,
    Failed,
}
