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

impl std::fmt::Display for DocumentStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DocumentStatus::Uploaded => write!(f, "uploaded"),
            DocumentStatus::Processing => write!(f, "processing"),
            DocumentStatus::Processed => write!(f, "processed"),
            DocumentStatus::Failed => write!(f, "failed"),
        }
    }
}

impl std::str::FromStr for DocumentStatus {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "uploaded" => Ok(DocumentStatus::Uploaded),
            "processing" => Ok(DocumentStatus::Processing),
            "processed" => Ok(DocumentStatus::Processed),
            "failed" => Ok(DocumentStatus::Failed),
            _ => Err(format!("Unknown document status: {}", s)),
        }
    }
}
