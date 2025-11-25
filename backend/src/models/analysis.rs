//! Analysis result models

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use super::classification::VariantClassification;
use super::clinvar::ClinVarResult;
use super::evidence::Evidence;

/// Analysis result combining document evidence and ClinVar validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisResult {
    pub id: Uuid,
    pub document_id: Uuid,
    pub evidence: Vec<Evidence>,
    pub clinvar_results: Vec<ClinVarResult>,
    pub final_classification: Option<VariantClassification>,
    pub confidence_score: f64,
    pub analysis_time: DateTime<Utc>,
}
