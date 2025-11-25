//! Database migrations
//!
//! This module contains database migration logic.
//! Migration scripts are executed in order to create/modify database schema.

use sqlx::PgPool;
use crate::error::AppResult;

/// Run all database migrations
pub async fn run_all(pool: &PgPool) -> AppResult<()> {
    // Migration 001: Create documents table
    create_documents_table(pool).await?;
    
    // Migration 002: Create evidence table
    create_evidence_table(pool).await?;
    
    // Migration 003: Create clinvar_results table
    create_clinvar_results_table(pool).await?;
    
    // Migration 004: Create analysis_results table
    create_analysis_results_table(pool).await?;
    
    tracing::info!("All database migrations completed successfully");
    Ok(())
}

/// Migration 001: Create documents table
async fn create_documents_table(pool: &PgPool) -> AppResult<()> {
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            language VARCHAR(50) NOT NULL,
            upload_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            content_hash VARCHAR(64) NOT NULL,
            extracted_text TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'uploaded'
        )
        "#,
    )
    .execute(pool)
    .await?;
    
    Ok(())
}

/// Migration 002: Create evidence table
async fn create_evidence_table(pool: &PgPool) -> AppResult<()> {
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS evidence (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            variant_id VARCHAR(255) NOT NULL,
            gene VARCHAR(100) NOT NULL,
            transcript VARCHAR(100),
            hgvs_c VARCHAR(255),
            hgvs_p VARCHAR(255),
            evidence_text TEXT NOT NULL,
            acmg_criteria JSONB NOT NULL,
            suggested_classification VARCHAR(50),
            confidence_score DOUBLE PRECISION NOT NULL,
            extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        "#,
    )
    .execute(pool)
    .await?;
    
    Ok(())
}

/// Migration 003: Create clinvar_results table
async fn create_clinvar_results_table(pool: &PgPool) -> AppResult<()> {
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS clinvar_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            variant_id VARCHAR(255) NOT NULL,
            clinvar_id VARCHAR(50),
            review_status VARCHAR(100),
            classification VARCHAR(50),
            last_evaluated TIMESTAMPTZ,
            submitter_count INTEGER NOT NULL DEFAULT 0,
            condition TEXT,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        "#,
    )
    .execute(pool)
    .await?;
    
    Ok(())
}

/// Migration 004: Create analysis_results table
async fn create_analysis_results_table(pool: &PgPool) -> AppResult<()> {
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS analysis_results (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            final_classification VARCHAR(50),
            confidence_score DOUBLE PRECISION NOT NULL,
            analysis_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        "#,
    )
    .execute(pool)
    .await?;
    
    Ok(())
}
