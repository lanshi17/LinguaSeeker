//! Database module for PostgreSQL operations
//!
//! This module handles database connection pool management and migrations.
//! Repository operations are in the `repositories` module.

pub mod migrations;

use sqlx::{postgres::PgPoolOptions, PgPool};
use crate::config::Config;
use crate::models::AppResult;

// Re-export repository modules for backward compatibility
pub use crate::repositories::{documents, evidence};

/// Initialize database connection pool
pub async fn init_pool(config: &Config) -> AppResult<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(config.database.max_connections)
        .connect(&config.database.url)
        .await?;

    tracing::info!("Database connection pool initialized");
    Ok(pool)
}

/// Run database migrations (creates tables if they don't exist)
pub async fn run_migrations(pool: &PgPool) -> AppResult<()> {
    migrations::run_all(pool).await
}
