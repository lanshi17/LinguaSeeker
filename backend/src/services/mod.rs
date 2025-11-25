//! Business logic services for the evidence platform
//!
//! This module contains the core business logic organized by domain:
//! - `evidence_service.rs`: Document analysis and variant classification
//! - `auth_service.rs`: Authentication and authorization (placeholder)

pub mod auth_service;
pub mod evidence_service;

// Re-export main service types
pub use auth_service::AuthService;
pub use evidence_service::EvidenceService;
