//! Evidence-related models

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use super::classification::{AcmgCriteria, VariantClassification};

/// Extracted evidence from document
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Evidence {
    pub id: Uuid,
    pub document_id: Uuid,
    pub variant_id: String,
    pub gene: String,
    pub transcript: Option<String>,
    pub hgvs_c: Option<String>,
    pub hgvs_p: Option<String>,
    pub evidence_text: String,
    pub acmg_criteria: AcmgCriteria,
    pub suggested_classification: Option<VariantClassification>,
    pub confidence_score: f64,
    pub extracted_at: DateTime<Utc>,
}
