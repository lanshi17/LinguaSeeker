//! ClinVar API integration for variant validation

use crate::config::Config;
use crate::error::{AppError, AppResult};
use crate::models::{ClinVarResult, VariantClassification};
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::Deserialize;

const CLINVAR_API_BASE: &str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils";

/// ClinVar API client
pub struct ClinVarClient {
    client: Client,
    api_key: Option<String>,
}

/// ClinVar search response
#[derive(Debug, Deserialize)]
struct ESearchResult {
    esearchresult: ESearchData,
}

#[derive(Debug, Deserialize)]
struct ESearchData {
    #[serde(default)]
    idlist: Vec<String>,
    count: String,
}

/// ClinVar summary response
#[derive(Debug, Deserialize)]
struct ESummaryResult {
    result: Option<ESummaryData>,
}

#[derive(Debug, Deserialize)]
struct ESummaryData {
    #[serde(default)]
    uids: Vec<String>,
    #[serde(flatten)]
    entries: std::collections::HashMap<String, ClinVarEntry>,
}

/// ClinVar entry data
#[derive(Debug, Deserialize)]
struct ClinVarEntry {
    uid: Option<String>,
    #[serde(default)]
    title: String,
    #[serde(default)]
    clinical_significance: Option<ClinicalSignificance>,
    #[serde(default)]
    variation_set: Option<Vec<VariationSet>>,
    #[serde(default)]
    germline_classification: Option<GermlineClassification>,
}

#[derive(Debug, Deserialize)]
struct ClinicalSignificance {
    #[serde(default)]
    description: String,
    #[serde(default)]
    review_status: String,
    #[serde(default)]
    last_evaluated: Option<String>,
}

#[derive(Debug, Deserialize)]
struct GermlineClassification {
    #[serde(default)]
    description: String,
    #[serde(default)]
    review_status: String,
    #[serde(default)]
    last_evaluated: Option<String>,
}

#[derive(Debug, Deserialize)]
struct VariationSet {
    #[serde(default)]
    variation_name: String,
    #[serde(default)]
    cdna_change: Option<String>,
}

impl ClinVarClient {
    /// Create a new ClinVar client
    pub fn new(config: &Config) -> Self {
        Self {
            client: Client::new(),
            api_key: config.clinvar_api_key.clone(),
        }
    }

    /// Build API URL with optional API key
    fn build_url(&self, endpoint: &str, params: &[(&str, &str)]) -> String {
        let mut url = format!("{}/{}", CLINVAR_API_BASE, endpoint);
        let mut query_params: Vec<(&str, &str)> = params.to_vec();
        
        if let Some(ref key) = self.api_key {
            // Add api_key if available (for higher rate limits)
            query_params.push(("api_key", key.as_str()));
        }
        
        if !query_params.is_empty() {
            let params_str: Vec<String> = query_params
                .iter()
                .map(|(k, v)| format!("{}={}", k, urlencoding::encode(v)))
                .collect();
            url = format!("{}?{}", url, params_str.join("&"));
        }
        
        url
    }

    /// Search ClinVar for a variant by gene and HGVS notation
    pub async fn search_variant(
        &self,
        gene: &str,
        hgvs_c: Option<&str>,
        hgvs_p: Option<&str>,
    ) -> AppResult<Option<ClinVarResult>> {
        // Build search term
        let search_term = if let Some(hgvs) = hgvs_c.or(hgvs_p) {
            format!("{}[gene] AND {}[variant]", gene, hgvs)
        } else {
            format!("{}[gene]", gene)
        };

        // Search for variant ID
        let search_url = self.build_url(
            "esearch.fcgi",
            &[
                ("db", "clinvar"),
                ("term", &search_term),
                ("retmode", "json"),
                ("retmax", "1"),
            ],
        );

        let search_response = self
            .client
            .get(&search_url)
            .send()
            .await
            .map_err(|e| AppError::ClinVar(format!("Failed to search ClinVar: {}", e)))?;

        if !search_response.status().is_success() {
            return Err(AppError::ClinVar(format!(
                "ClinVar search returned error: {}",
                search_response.status()
            )));
        }

        let search_result: ESearchResult = search_response
            .json()
            .await
            .map_err(|e| AppError::ClinVar(format!("Failed to parse search response: {}", e)))?;

        if search_result.esearchresult.idlist.is_empty() {
            return Ok(None);
        }

        let clinvar_id = &search_result.esearchresult.idlist[0];

        // Fetch variant details
        let summary_url = self.build_url(
            "esummary.fcgi",
            &[
                ("db", "clinvar"),
                ("id", clinvar_id),
                ("retmode", "json"),
            ],
        );

        let summary_response = self
            .client
            .get(&summary_url)
            .send()
            .await
            .map_err(|e| AppError::ClinVar(format!("Failed to fetch variant details: {}", e)))?;

        if !summary_response.status().is_success() {
            return Err(AppError::ClinVar(format!(
                "ClinVar summary returned error: {}",
                summary_response.status()
            )));
        }

        let summary_result: ESummaryResult = summary_response
            .json()
            .await
            .map_err(|e| AppError::ClinVar(format!("Failed to parse summary response: {}", e)))?;

        // Extract relevant data
        if let Some(data) = summary_result.result {
            if let Some(entry) = data.entries.get(clinvar_id) {
                let (classification_desc, review_status, last_evaluated) = 
                    if let Some(ref gc) = entry.germline_classification {
                        (gc.description.clone(), gc.review_status.clone(), gc.last_evaluated.clone())
                    } else if let Some(ref cs) = entry.clinical_significance {
                        (cs.description.clone(), cs.review_status.clone(), cs.last_evaluated.clone())
                    } else {
                        (String::new(), String::new(), None)
                    };

                let classification = Self::parse_classification(&classification_desc);

                let last_evaluated_dt: Option<DateTime<Utc>> = last_evaluated.and_then(|s| {
                    chrono::NaiveDate::parse_from_str(&s, "%Y-%m-%d")
                        .ok()
                        .map(|d| d.and_hms_opt(0, 0, 0).unwrap())
                        .map(|dt| DateTime::from_naive_utc_and_offset(dt, Utc))
                });

                let variant_id = format!(
                    "{}:{}",
                    gene,
                    hgvs_c.or(hgvs_p).unwrap_or("unknown")
                );

                return Ok(Some(ClinVarResult {
                    variant_id,
                    clinvar_id: Some(clinvar_id.clone()),
                    review_status: Some(review_status),
                    classification,
                    last_evaluated: last_evaluated_dt,
                    submitter_count: 1, // Would need additional API call for accurate count
                    condition: Some(entry.title.clone()),
                }));
            }
        }

        Ok(None)
    }

    /// Parse ClinVar classification string to enum
    fn parse_classification(desc: &str) -> Option<VariantClassification> {
        let lower = desc.to_lowercase();
        if lower.contains("pathogenic") && !lower.contains("likely") {
            Some(VariantClassification::Pathogenic)
        } else if lower.contains("likely pathogenic") {
            Some(VariantClassification::LikelyPathogenic)
        } else if lower.contains("uncertain") || lower.contains("vus") {
            Some(VariantClassification::UncertainSignificance)
        } else if lower.contains("likely benign") {
            Some(VariantClassification::LikelyBenign)
        } else if lower.contains("benign") && !lower.contains("likely") {
            Some(VariantClassification::Benign)
        } else {
            None
        }
    }

    /// Validate multiple variants against ClinVar
    pub async fn validate_variants(
        &self,
        variants: &[(String, Option<String>, Option<String>)], // (gene, hgvs_c, hgvs_p)
    ) -> AppResult<Vec<ClinVarResult>> {
        let mut results = Vec::new();

        for (gene, hgvs_c, hgvs_p) in variants {
            match self
                .search_variant(gene, hgvs_c.as_deref(), hgvs_p.as_deref())
                .await
            {
                Ok(Some(result)) => results.push(result),
                Ok(None) => {
                    // Variant not found in ClinVar
                    results.push(ClinVarResult {
                        variant_id: format!(
                            "{}:{}",
                            gene,
                            hgvs_c.as_deref().or(hgvs_p.as_deref()).unwrap_or("unknown")
                        ),
                        clinvar_id: None,
                        review_status: None,
                        classification: None,
                        last_evaluated: None,
                        submitter_count: 0,
                        condition: None,
                    });
                }
                Err(e) => {
                    tracing::warn!("Failed to validate variant {}: {}", gene, e);
                    // Continue with other variants
                }
            }
        }

        Ok(results)
    }
}

/// URL encoding helper module
mod urlencoding {
    pub fn encode(s: &str) -> String {
        s.chars()
            .map(|c| match c {
                'A'..='Z' | 'a'..='z' | '0'..='9' | '-' | '_' | '.' | '~' => c.to_string(),
                ' ' => "+".to_string(),
                _ => format!("%{:02X}", c as u8),
            })
            .collect()
    }
}
