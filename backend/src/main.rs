//! Multilingual Document Evidence Collection Platform
//!
//! This platform assists researchers in automating gene variant classification
//! based on ACMG/AMP guidelines. It parses multilingual PDF documents (Chinese,
//! Japanese, German, French, English), extracts evidence using LLM, integrates
//! with ClinVar for validation, and outputs results in an interactive HTML interface.
//!
//! ## Architecture
//!
//! The codebase follows a layered architecture:
//! - **API Layer** (`api/`): HTTP handlers, routes, validators
//! - **Service Layer** (`services/`): Business logic
//! - **Data Layer** (`repositories/`, `db/`): Data access and persistence
//! - **Model Layer** (`models/`): Data structures, DTOs, errors
//! - **Config Layer** (`config/`): Configuration management

mod api;
mod clinvar;
mod config;
mod db;
mod error;
mod llm;
mod models;
mod repositories;
mod services;

use std::net::SocketAddr;
use std::sync::Arc;

use axum::http::{header, Method};
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::api::AppState;
use crate::config::Config;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "evidence_platform=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Load environment variables
    dotenvy::dotenv().ok();

    // Load configuration
    let config = Config::from_env().unwrap_or_default();
    let addr: SocketAddr = format!("{}:{}", config.server.host, config.server.port).parse()?;

    tracing::info!("Starting Evidence Platform server on {}", addr);

    // Initialize database connection pool
    let pool = db::init_pool(&config).await?;

    // Run database migrations
    db::run_migrations(&pool).await?;

    // Create application state
    let state = Arc::new(AppState::new(pool, config));

    // Configure CORS
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE])
        .allow_headers([header::CONTENT_TYPE, header::AUTHORIZATION]);

    // Build the router
    let app = api::create_router(state)
        .layer(TraceLayer::new_for_http())
        .layer(cors);

    // Start the server
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!("Server listening on http://{}", addr);

    axum::serve(listener, app).await?;

    Ok(())
}

