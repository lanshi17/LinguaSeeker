//! Analysis Data Transfer Objects

use serde::Serialize;

use crate::models::{AcmgCriteria, AnalysisResult};

/// Response DTO for analysis results
#[derive(Debug, Serialize)]
pub struct AnalysisResponse {
    pub id: String,
    pub document_id: String,
    pub evidence: Vec<EvidenceResponse>,
    pub clinvar_results: Vec<ClinVarResponse>,
    pub final_classification: Option<String>,
    pub confidence_score: f64,
    pub analysis_time: String,
}

/// Response DTO for extracted evidence
#[derive(Debug, Serialize)]
pub struct EvidenceResponse {
    pub id: String,
    pub variant_id: String,
    pub gene: String,
    pub transcript: Option<String>,
    pub hgvs_c: Option<String>,
    pub hgvs_p: Option<String>,
    pub evidence_text: String,
    pub acmg_criteria: AcmgCriteria,
    pub suggested_classification: Option<String>,
    pub confidence_score: f64,
}

/// Response DTO for ClinVar validation results
#[derive(Debug, Serialize)]
pub struct ClinVarResponse {
    pub variant_id: String,
    pub clinvar_id: Option<String>,
    pub review_status: Option<String>,
    pub classification: Option<String>,
    pub last_evaluated: Option<String>,
    pub submitter_count: u32,
    pub condition: Option<String>,
}

impl From<AnalysisResult> for AnalysisResponse {
    fn from(result: AnalysisResult) -> Self {
        Self {
            id: result.id.to_string(),
            document_id: result.document_id.to_string(),
            evidence: result
                .evidence
                .into_iter()
                .map(|e| EvidenceResponse {
                    id: e.id.to_string(),
                    variant_id: e.variant_id,
                    gene: e.gene,
                    transcript: e.transcript,
                    hgvs_c: e.hgvs_c,
                    hgvs_p: e.hgvs_p,
                    evidence_text: e.evidence_text,
                    acmg_criteria: e.acmg_criteria,
                    suggested_classification: e.suggested_classification.map(|c| c.to_string()),
                    confidence_score: e.confidence_score,
                })
                .collect(),
            clinvar_results: result
                .clinvar_results
                .into_iter()
                .map(|c| ClinVarResponse {
                    variant_id: c.variant_id,
                    clinvar_id: c.clinvar_id,
                    review_status: c.review_status,
                    classification: c.classification.map(|cl| cl.to_string()),
                    last_evaluated: c.last_evaluated.map(|d| d.to_rfc3339()),
                    submitter_count: c.submitter_count,
                    condition: c.condition,
                })
                .collect(),
            final_classification: result.final_classification.map(|c| c.to_string()),
            confidence_score: result.confidence_score,
            analysis_time: result.analysis_time.to_rfc3339(),
        }
    }
}
