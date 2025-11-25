//! LLM module for multilingual document parsing and evidence extraction

use crate::config::Config;
use crate::error::{AppError, AppResult};
use crate::models::{AcmgCriteria, Evidence, Language, VariantClassification};
use chrono::Utc;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// LLM client for evidence extraction
pub struct LlmClient {
    client: Client,
    api_url: String,
    api_key: String,
    model: String,
}

/// Request payload for LLM API
#[derive(Debug, Serialize)]
struct LlmRequest {
    model: String,
    prompt: String,
    stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    format: Option<String>,
}

/// Response from LLM API
#[derive(Debug, Deserialize)]
struct LlmResponse {
    response: String,
    #[serde(default)]
    done: bool,
}

/// Extracted variant information from LLM
#[derive(Debug, Deserialize)]
pub struct ExtractedVariant {
    pub gene: String,
    #[serde(default)]
    pub transcript: Option<String>,
    #[serde(default)]
    pub hgvs_c: Option<String>,
    #[serde(default)]
    pub hgvs_p: Option<String>,
    pub evidence_text: String,
    #[serde(default)]
    pub acmg_criteria: ExtractedAcmgCriteria,
    #[serde(default)]
    pub suggested_classification: Option<String>,
    #[serde(default)]
    pub confidence: f64,
}

/// Extracted ACMG criteria from LLM
#[derive(Debug, Default, Deserialize)]
pub struct ExtractedAcmgCriteria {
    #[serde(default)]
    pub pvs1: bool,
    #[serde(default)]
    pub ps: Vec<String>,
    #[serde(default)]
    pub pm: Vec<String>,
    #[serde(default)]
    pub pp: Vec<String>,
    #[serde(default)]
    pub ba1: bool,
    #[serde(default)]
    pub bs: Vec<String>,
    #[serde(default)]
    pub bp: Vec<String>,
}

impl LlmClient {
    /// Create a new LLM client
    pub fn new(config: &Config) -> Self {
        Self {
            client: Client::new(),
            api_url: config.llm.api_url.clone(),
            api_key: config.llm.api_key.clone(),
            model: config.llm.model.clone(),
        }
    }

    /// Generate the extraction prompt based on language
    fn generate_prompt(&self, text: &str, language: Language) -> String {
        let language_instruction = match language {
            Language::Chinese => "The document is in Chinese (中文). Please analyze it in Chinese context.",
            Language::Japanese => "The document is in Japanese (日本語). Please analyze it in Japanese context.",
            Language::German => "The document is in German (Deutsch). Please analyze it in German context.",
            Language::French => "The document is in French (Français). Please analyze it in French context.",
            Language::English => "The document is in English. Please analyze it in English context.",
        };

        format!(
            r#"You are an expert in genetic variant classification following ACMG/AMP guidelines.
{}

Analyze the following document text and extract all genetic variants mentioned along with their evidence.
For each variant found, provide:
1. Gene name
2. Transcript (if available)
3. HGVS.c notation (if available)
4. HGVS.p notation (if available)
5. Evidence text (the relevant passage from the document)
6. ACMG/AMP criteria that apply based on the evidence:
   - PVS1: Very strong pathogenic (null variant in gene where LOF is a known mechanism)
   - PS1-PS4: Strong pathogenic criteria
   - PM1-PM6: Moderate pathogenic criteria
   - PP1-PP5: Supporting pathogenic criteria
   - BA1: Stand-alone benign (allele frequency > 5%)
   - BS1-BS4: Strong benign criteria
   - BP1-BP7: Supporting benign criteria
7. Suggested classification (Pathogenic, Likely Pathogenic, Uncertain Significance, Likely Benign, Benign)
8. Confidence score (0.0 to 1.0)

Return your response as a JSON array of variants.

Document text:
{}

Response format (JSON array):
[
  {{
    "gene": "GENE_NAME",
    "transcript": "NM_XXXXXX.X",
    "hgvs_c": "c.XXX",
    "hgvs_p": "p.XXX",
    "evidence_text": "Relevant text from document...",
    "acmg_criteria": {{
      "pvs1": false,
      "ps": ["PS1"],
      "pm": ["PM2"],
      "pp": [],
      "ba1": false,
      "bs": [],
      "bp": []
    }},
    "suggested_classification": "Likely Pathogenic",
    "confidence": 0.85
  }}
]"#,
            language_instruction, text
        )
    }

    /// Extract evidence from document text using LLM
    pub async fn extract_evidence(
        &self,
        document_id: Uuid,
        text: &str,
        language: Language,
    ) -> AppResult<Vec<Evidence>> {
        let prompt = self.generate_prompt(text, language);

        let request = LlmRequest {
            model: self.model.clone(),
            prompt,
            stream: false,
            format: Some("json".to_string()),
        };

        let response = self
            .client
            .post(&self.api_url)
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&request)
            .send()
            .await
            .map_err(|e| AppError::Llm(format!("Failed to connect to LLM: {}", e)))?;

        if !response.status().is_success() {
            return Err(AppError::Llm(format!(
                "LLM API returned error status: {}",
                response.status()
            )));
        }

        let llm_response: LlmResponse = response
            .json()
            .await
            .map_err(|e| AppError::Llm(format!("Failed to parse LLM response: {}", e)))?;

        // Parse the JSON response
        let variants: Vec<ExtractedVariant> = serde_json::from_str(&llm_response.response)
            .map_err(|e| AppError::Llm(format!("Failed to parse extracted variants: {}", e)))?;

        // Convert to Evidence structs
        let evidence_list = variants
            .into_iter()
            .map(|v| Evidence {
                id: Uuid::new_v4(),
                document_id,
                variant_id: format!("{}:{}", v.gene, v.hgvs_c.as_deref().unwrap_or("unknown")),
                gene: v.gene,
                transcript: v.transcript,
                hgvs_c: v.hgvs_c,
                hgvs_p: v.hgvs_p,
                evidence_text: v.evidence_text,
                acmg_criteria: AcmgCriteria {
                    pvs1: v.acmg_criteria.pvs1,
                    ps: v.acmg_criteria.ps,
                    pm: v.acmg_criteria.pm,
                    pp: v.acmg_criteria.pp,
                    ba1: v.acmg_criteria.ba1,
                    bs: v.acmg_criteria.bs,
                    bp: v.acmg_criteria.bp,
                },
                suggested_classification: v.suggested_classification.and_then(|s| {
                    match s.to_lowercase().as_str() {
                        "pathogenic" => Some(VariantClassification::Pathogenic),
                        "likely pathogenic" => Some(VariantClassification::LikelyPathogenic),
                        "uncertain significance" | "vus" => {
                            Some(VariantClassification::UncertainSignificance)
                        }
                        "likely benign" => Some(VariantClassification::LikelyBenign),
                        "benign" => Some(VariantClassification::Benign),
                        _ => None,
                    }
                }),
                confidence_score: v.confidence.clamp(0.0, 1.0),
                extracted_at: Utc::now(),
            })
            .collect();

        Ok(evidence_list)
    }

    /// Detect language from text using LLM
    pub async fn detect_language(&self, text: &str) -> AppResult<Language> {
        let prompt = format!(
            r#"Detect the primary language of the following text. 
Return only one word: chinese, japanese, german, french, or english.

Text:
{}

Language:"#,
            &text[..text.len().min(1000)]
        );

        let request = LlmRequest {
            model: self.model.clone(),
            prompt,
            stream: false,
            format: None,
        };

        let response = self
            .client
            .post(&self.api_url)
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&request)
            .send()
            .await
            .map_err(|e| AppError::Llm(format!("Failed to detect language: {}", e)))?;

        if !response.status().is_success() {
            return Ok(Language::English); // Default to English on error
        }

        let llm_response: LlmResponse = response
            .json()
            .await
            .map_err(|_| AppError::Llm("Failed to parse language detection response".to_string()))?;

        let detected = llm_response.response.trim().to_lowercase();
        detected.parse().map_err(|_| {
            tracing::warn!("Unknown language detected: {}, defaulting to English", detected);
            AppError::Llm("Unknown language detected".to_string())
        }).or(Ok(Language::English))
    }
}
