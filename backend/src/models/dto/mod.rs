//! Data Transfer Objects (DTOs)
//!
//! This module contains DTOs for API request/response serialization

pub mod analysis_dto;
pub mod document_dto;

// Re-export DTOs for convenience
pub use analysis_dto::{AnalysisResponse, ClinVarResponse, EvidenceResponse};
pub use document_dto::{DocumentListResponse, DocumentResponse, UploadRequest, UploadResponse};
