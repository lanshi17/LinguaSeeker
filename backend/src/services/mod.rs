//! Business logic services for the evidence platform

use crate::clinvar::ClinVarClient;
use crate::config::Config;
use crate::db;
use crate::error::{AppError, AppResult};
use crate::llm::LlmClient;
use crate::models::{
    AnalysisResult, DocumentStatus, Evidence, VariantClassification,
};
use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

/// Evidence extraction and classification service
pub struct EvidenceService {
    pool: PgPool,
    llm_client: LlmClient,
    clinvar_client: ClinVarClient,
}

impl EvidenceService {
    /// Create a new evidence service
    pub fn new(pool: PgPool, config: &Config) -> Self {
        Self {
            pool,
            llm_client: LlmClient::new(config),
            clinvar_client: ClinVarClient::new(config),
        }
    }

    /// Process a document: extract text, analyze with LLM, validate with ClinVar
    pub async fn process_document(&self, document_id: Uuid) -> AppResult<AnalysisResult> {
        // Get document from database
        let document = db::documents::get_by_id(&self.pool, document_id)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("Document not found: {}", document_id)))?;

        // Update status to processing
        db::documents::update_status(&self.pool, document_id, DocumentStatus::Processing).await?;

        // Get extracted text (should be populated during upload)
        let text = document.extracted_text.ok_or_else(|| {
            AppError::Processing("Document text not extracted yet".to_string())
        })?;

        // Extract evidence using LLM
        let evidence_list = match self
            .llm_client
            .extract_evidence(document_id, &text, document.language)
            .await
        {
            Ok(evidence) => evidence,
            Err(e) => {
                db::documents::update_status(&self.pool, document_id, DocumentStatus::Failed)
                    .await?;
                return Err(e);
            }
        };

        // Store extracted evidence
        for evidence in &evidence_list {
            db::evidence::insert(&self.pool, evidence).await?;
        }

        // Prepare variants for ClinVar validation
        let variants: Vec<(String, Option<String>, Option<String>)> = evidence_list
            .iter()
            .map(|e| (e.gene.clone(), e.hgvs_c.clone(), e.hgvs_p.clone()))
            .collect();

        // Validate with ClinVar
        let clinvar_results = self.clinvar_client.validate_variants(&variants).await?;

        // Determine final classification based on evidence and ClinVar
        let final_classification = Self::determine_classification(&evidence_list, &clinvar_results);
        let confidence_score = Self::calculate_confidence(&evidence_list, &clinvar_results);

        // Update document status
        db::documents::update_status(&self.pool, document_id, DocumentStatus::Processed).await?;

        Ok(AnalysisResult {
            id: Uuid::new_v4(),
            document_id,
            evidence: evidence_list,
            clinvar_results,
            final_classification,
            confidence_score,
            analysis_time: Utc::now(),
        })
    }

    /// Determine final variant classification based on ACMG/AMP criteria
    fn determine_classification(
        evidence_list: &[Evidence],
        clinvar_results: &[crate::models::ClinVarResult],
    ) -> Option<VariantClassification> {
        // Aggregate ACMG criteria from all evidence
        let mut pvs1_count = 0;
        let mut ps_count = 0;
        let mut pm_count = 0;
        let mut pp_count = 0;
        let mut ba1 = false;
        let mut bs_count = 0;
        let mut bp_count = 0;

        for evidence in evidence_list {
            if evidence.acmg_criteria.pvs1 {
                pvs1_count += 1;
            }
            ps_count += evidence.acmg_criteria.ps.len();
            pm_count += evidence.acmg_criteria.pm.len();
            pp_count += evidence.acmg_criteria.pp.len();
            if evidence.acmg_criteria.ba1 {
                ba1 = true;
            }
            bs_count += evidence.acmg_criteria.bs.len();
            bp_count += evidence.acmg_criteria.bp.len();
        }

        // BA1 alone = Benign
        if ba1 {
            return Some(VariantClassification::Benign);
        }

        // Apply ACMG/AMP combining rules (simplified version)
        // Pathogenic: PVS1 + PS1 OR PVS1 + 1PM + 1PP OR 2PS OR PS1 + 3PM OR 2PM + 2PP
        if pvs1_count >= 1 && (ps_count >= 1 || (pm_count >= 1 && pp_count >= 1)) {
            return Some(VariantClassification::Pathogenic);
        }
        if ps_count >= 2 {
            return Some(VariantClassification::Pathogenic);
        }
        if ps_count >= 1 && pm_count >= 3 {
            return Some(VariantClassification::Pathogenic);
        }

        // Likely Pathogenic: PVS1 + 1PM OR PS1 + 1-2PM OR PS1 + 2PP OR 1PM + 4PP
        if pvs1_count >= 1 && pm_count >= 1 {
            return Some(VariantClassification::LikelyPathogenic);
        }
        if ps_count >= 1 && pm_count >= 1 {
            return Some(VariantClassification::LikelyPathogenic);
        }
        if ps_count >= 1 && pp_count >= 2 {
            return Some(VariantClassification::LikelyPathogenic);
        }

        // Benign: BS1 + BS2 OR 2 BS
        if bs_count >= 2 {
            return Some(VariantClassification::Benign);
        }

        // Likely Benign: 1BS + 1BP OR 2BP
        if bs_count >= 1 && bp_count >= 1 {
            return Some(VariantClassification::LikelyBenign);
        }
        if bp_count >= 2 {
            return Some(VariantClassification::LikelyBenign);
        }

        // Check ClinVar consensus
        let clinvar_classifications: Vec<_> = clinvar_results
            .iter()
            .filter_map(|r| r.classification)
            .collect();

        if !clinvar_classifications.is_empty() {
            // Return the most common classification from ClinVar
            return clinvar_classifications.into_iter().next();
        }

        // Default to VUS if no clear evidence
        if evidence_list.is_empty() {
            None
        } else {
            Some(VariantClassification::UncertainSignificance)
        }
    }

    /// Calculate confidence score based on evidence quantity and quality
    fn calculate_confidence(
        evidence_list: &[Evidence],
        clinvar_results: &[crate::models::ClinVarResult],
    ) -> f64 {
        if evidence_list.is_empty() {
            return 0.0;
        }

        let mut total_confidence: f64 = 0.0;
        let mut weight_sum: f64 = 0.0;

        // Weight evidence by individual confidence scores
        for evidence in evidence_list {
            total_confidence += evidence.confidence_score;
            weight_sum += 1.0;
        }

        // Boost confidence if ClinVar validates findings
        let clinvar_matches: usize = clinvar_results
            .iter()
            .filter(|r| r.clinvar_id.is_some())
            .count();

        let clinvar_boost = (clinvar_matches as f64 / evidence_list.len().max(1) as f64) * 0.2;

        let base_confidence = total_confidence / weight_sum.max(1.0);
        (base_confidence + clinvar_boost).clamp(0.0, 1.0)
    }

    /// Get analysis result for a document
    pub async fn get_analysis(&self, document_id: Uuid) -> AppResult<Option<AnalysisResult>> {
        let document = db::documents::get_by_id(&self.pool, document_id).await?;

        match document {
            Some(doc) if doc.status == DocumentStatus::Processed => {
                let evidence = db::evidence::get_by_document_id(&self.pool, document_id).await?;

                if evidence.is_empty() {
                    return Ok(None);
                }

                // Fetch ClinVar results for the variants
                let variants: Vec<(String, Option<String>, Option<String>)> = evidence
                    .iter()
                    .map(|e| (e.gene.clone(), e.hgvs_c.clone(), e.hgvs_p.clone()))
                    .collect();

                let clinvar_results = self.clinvar_client.validate_variants(&variants).await?;

                let final_classification =
                    Self::determine_classification(&evidence, &clinvar_results);
                let confidence_score = Self::calculate_confidence(&evidence, &clinvar_results);

                Ok(Some(AnalysisResult {
                    id: Uuid::new_v4(),
                    document_id,
                    evidence,
                    clinvar_results,
                    final_classification,
                    confidence_score,
                    analysis_time: doc.upload_time,
                }))
            }
            _ => Ok(None),
        }
    }
}
