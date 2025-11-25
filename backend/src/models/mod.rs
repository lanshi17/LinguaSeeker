//! Data models for the evidence platform
//!
//! This module follows a layered architecture with:
//! - Entity models in separate files
//! - DTOs for API serialization in the `dto` submodule
//! - Error types in `error.rs`

pub mod analysis;
pub mod classification;
pub mod clinvar;
pub mod document;
pub mod dto;
pub mod error;
pub mod evidence;
pub mod language;

// Re-export main types for convenience
pub use analysis::AnalysisResult;
pub use classification::{AcmgCriteria, VariantClassification};
pub use clinvar::ClinVarResult;
pub use document::{Document, DocumentStatus};
pub use error::{AppError, AppResult};
pub use evidence::Evidence;
pub use language::Language;
