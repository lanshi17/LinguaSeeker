//! API layer for the evidence platform
//!
//! This module follows a layered architecture with:
//! - `routes.rs`: Route definitions
//! - `handlers/`: Request handlers organized by domain
//! - `validators.rs`: Request parameter validation

pub mod handlers;
pub mod routes;
pub mod validators;

use sqlx::PgPool;

use crate::config::Config;
use crate::services::EvidenceService;

// Re-export route creation function
pub use routes::create_router;

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
