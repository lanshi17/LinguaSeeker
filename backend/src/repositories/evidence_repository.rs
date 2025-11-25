//! Evidence repository for data access

use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{AppResult, Evidence, VariantClassification};

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
                suggested_classification: suggested_classification.and_then(|s| parse_classification(&s)),
                confidence_score,
                extracted_at,
            }
        })
        .collect();

    Ok(evidence_list)
}

/// Parse classification string to enum
fn parse_classification(s: &str) -> Option<VariantClassification> {
    match s {
        "Pathogenic" => Some(VariantClassification::Pathogenic),
        "Likely Pathogenic" => Some(VariantClassification::LikelyPathogenic),
        "Uncertain Significance" => Some(VariantClassification::UncertainSignificance),
        "Likely Benign" => Some(VariantClassification::LikelyBenign),
        "Benign" => Some(VariantClassification::Benign),
        _ => None,
    }
}
