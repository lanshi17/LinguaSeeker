//! ClinVar result models

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::classification::VariantClassification;

/// ClinVar validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClinVarResult {
    pub variant_id: String,
    pub clinvar_id: Option<String>,
    pub review_status: Option<String>,
    pub classification: Option<VariantClassification>,
    pub last_evaluated: Option<DateTime<Utc>>,
    pub submitter_count: u32,
    pub condition: Option<String>,
}
