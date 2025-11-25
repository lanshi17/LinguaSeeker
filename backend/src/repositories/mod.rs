//! Repository modules for data access
//!
//! This module follows the repository pattern for data access abstraction

pub mod document_repository;
pub mod evidence_repository;

// Re-export repository modules for convenience
pub use document_repository as documents;
pub use evidence_repository as evidence;
