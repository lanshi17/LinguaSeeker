//! Document repository for data access

use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{AppResult, Document, DocumentStatus, Language};

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
                status: parse_status(&status),
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
                status: parse_status(&status),
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

/// Parse status string to DocumentStatus enum
fn parse_status(status: &str) -> DocumentStatus {
    match status {
        "uploaded" => DocumentStatus::Uploaded,
        "processing" => DocumentStatus::Processing,
        "processed" => DocumentStatus::Processed,
        "failed" => DocumentStatus::Failed,
        _ => DocumentStatus::Uploaded,
    }
}
