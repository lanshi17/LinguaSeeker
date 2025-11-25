//! Database module for PostgreSQL operations

use sqlx::{postgres::PgPoolOptions, PgPool};
use crate::config::Config;
use crate::error::AppResult;

/// Initialize database connection pool
pub async fn init_pool(config: &Config) -> AppResult<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(10)
        .connect(&config.database_url)
        .await?;

    tracing::info!("Database connection pool initialized");
    Ok(pool)
}

/// Run database migrations (creates tables if they don't exist)
pub async fn run_migrations(pool: &PgPool) -> AppResult<()> {
    // Create documents table
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

    // Create evidence table
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

    // Create clinvar_results table
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

    // Create analysis_results table
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

    tracing::info!("Database migrations completed");
    Ok(())
}

/// Document repository operations
pub mod documents {
    use super::*;
    use crate::models::{Document, DocumentStatus, Language};
    use chrono::Utc;
    use uuid::Uuid;

    /// Insert a new document
    pub async fn insert(pool: &PgPool, doc: &Document) -> AppResult<()> {
        sqlx::query(
            r#"
            INSERT INTO documents (id, filename, language, upload_time, content_hash, extracted_text, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            "#,
        )
        .bind(doc.id)
        .bind(&doc.filename)
        .bind(doc.language.to_string())
        .bind(doc.upload_time)
        .bind(&doc.content_hash)
        .bind(&doc.extracted_text)
        .bind(format!("{:?}", doc.status).to_lowercase())
        .execute(pool)
        .await?;
        
        Ok(())
    }

    /// Get document by ID
    pub async fn get_by_id(pool: &PgPool, id: Uuid) -> AppResult<Option<Document>> {
        let row = sqlx::query_as::<_, (Uuid, String, String, chrono::DateTime<Utc>, String, Option<String>, String)>(
            r#"
            SELECT id, filename, language, upload_time, content_hash, extracted_text, status
            FROM documents
            WHERE id = $1
            "#,
        )
        .bind(id)
        .fetch_optional(pool)
        .await?;

        match row {
            Some((id, filename, language, upload_time, content_hash, extracted_text, status)) => {
                Ok(Some(Document {
                    id,
                    filename,
                    language: language.parse().unwrap_or(Language::English),
                    upload_time,
                    content_hash,
                    extracted_text,
                    status: match status.as_str() {
                        "uploaded" => DocumentStatus::Uploaded,
                        "processing" => DocumentStatus::Processing,
                        "processed" => DocumentStatus::Processed,
                        "failed" => DocumentStatus::Failed,
                        _ => DocumentStatus::Uploaded,
                    },
                }))
            }
            None => Ok(None),
        }
    }

    /// List all documents
    pub async fn list(pool: &PgPool) -> AppResult<Vec<Document>> {
        let rows = sqlx::query_as::<_, (Uuid, String, String, chrono::DateTime<Utc>, String, Option<String>, String)>(
            r#"
            SELECT id, filename, language, upload_time, content_hash, extracted_text, status
            FROM documents
            ORDER BY upload_time DESC
            "#,
        )
        .fetch_all(pool)
        .await?;

        let documents = rows
            .into_iter()
            .map(|(id, filename, language, upload_time, content_hash, extracted_text, status)| {
                Document {
                    id,
                    filename,
                    language: language.parse().unwrap_or(Language::English),
                    upload_time,
                    content_hash,
                    extracted_text,
                    status: match status.as_str() {
                        "uploaded" => DocumentStatus::Uploaded,
                        "processing" => DocumentStatus::Processing,
                        "processed" => DocumentStatus::Processed,
                        "failed" => DocumentStatus::Failed,
                        _ => DocumentStatus::Uploaded,
                    },
                }
            })
            .collect();

        Ok(documents)
    }

    /// Update document status
    pub async fn update_status(pool: &PgPool, id: Uuid, status: DocumentStatus) -> AppResult<()> {
        sqlx::query(
            r#"
            UPDATE documents SET status = $1 WHERE id = $2
            "#,
        )
        .bind(format!("{:?}", status).to_lowercase())
        .bind(id)
        .execute(pool)
        .await?;
        
        Ok(())
    }

    /// Update document extracted text
    pub async fn update_extracted_text(pool: &PgPool, id: Uuid, text: &str) -> AppResult<()> {
        sqlx::query(
            r#"
            UPDATE documents SET extracted_text = $1 WHERE id = $2
            "#,
        )
        .bind(text)
        .bind(id)
        .execute(pool)
        .await?;
        
        Ok(())
    }
}

/// Evidence repository operations
pub mod evidence {
    use super::*;
    use crate::models::{Evidence, VariantClassification};
    use chrono::Utc;
    use uuid::Uuid;

    /// Insert new evidence
    pub async fn insert(pool: &PgPool, evidence: &Evidence) -> AppResult<()> {
        sqlx::query(
            r#"
            INSERT INTO evidence (id, document_id, variant_id, gene, transcript, hgvs_c, hgvs_p, 
                                  evidence_text, acmg_criteria, suggested_classification, 
                                  confidence_score, extracted_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            "#,
        )
        .bind(evidence.id)
        .bind(evidence.document_id)
        .bind(&evidence.variant_id)
        .bind(&evidence.gene)
        .bind(&evidence.transcript)
        .bind(&evidence.hgvs_c)
        .bind(&evidence.hgvs_p)
        .bind(&evidence.evidence_text)
        .bind(serde_json::to_value(&evidence.acmg_criteria).unwrap_or_default())
        .bind(evidence.suggested_classification.as_ref().map(|c| c.to_string()))
        .bind(evidence.confidence_score)
        .bind(evidence.extracted_at)
        .execute(pool)
        .await?;
        
        Ok(())
    }

    /// Get evidence by document ID
    pub async fn get_by_document_id(pool: &PgPool, document_id: Uuid) -> AppResult<Vec<Evidence>> {
        let rows = sqlx::query_as::<_, (Uuid, Uuid, String, String, Option<String>, Option<String>, Option<String>, String, serde_json::Value, Option<String>, f64, chrono::DateTime<Utc>)>(
            r#"
            SELECT id, document_id, variant_id, gene, transcript, hgvs_c, hgvs_p,
                   evidence_text, acmg_criteria, suggested_classification, confidence_score, extracted_at
            FROM evidence
            WHERE document_id = $1
            ORDER BY extracted_at DESC
            "#,
        )
        .bind(document_id)
        .fetch_all(pool)
        .await?;

        let evidence_list = rows
            .into_iter()
            .map(|(id, document_id, variant_id, gene, transcript, hgvs_c, hgvs_p, evidence_text, acmg_criteria, suggested_classification, confidence_score, extracted_at)| {
                Evidence {
                    id,
                    document_id,
                    variant_id,
                    gene,
                    transcript,
                    hgvs_c,
                    hgvs_p,
                    evidence_text,
                    acmg_criteria: serde_json::from_value(acmg_criteria).unwrap_or_default(),
                    suggested_classification: suggested_classification.and_then(|s| match s.as_str() {
                        "Pathogenic" => Some(VariantClassification::Pathogenic),
                        "Likely Pathogenic" => Some(VariantClassification::LikelyPathogenic),
                        "Uncertain Significance" => Some(VariantClassification::UncertainSignificance),
                        "Likely Benign" => Some(VariantClassification::LikelyBenign),
                        "Benign" => Some(VariantClassification::Benign),
                        _ => None,
                    }),
                    confidence_score,
                    extracted_at,
                }
            })
            .collect();

        Ok(evidence_list)
    }
}
