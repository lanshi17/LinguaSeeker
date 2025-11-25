//! API handlers module
//!
//! This module contains handlers organized by domain

pub mod analysis;
pub mod document;
pub mod health;

// Re-export handlers for convenience
pub use analysis::{analyze_document, get_analysis_results};
pub use document::{get_document, list_documents, upload_document};
pub use health::health_check;
