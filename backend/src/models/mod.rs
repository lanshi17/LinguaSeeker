//! Data models for the evidence platform

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Supported languages for document parsing
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    Chinese,
    Japanese,
    German,
    French,
    English,
}

impl std::fmt::Display for Language {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Language::Chinese => write!(f, "chinese"),
            Language::Japanese => write!(f, "japanese"),
            Language::German => write!(f, "german"),
            Language::French => write!(f, "french"),
            Language::English => write!(f, "english"),
        }
    }
}

impl std::str::FromStr for Language {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "chinese" | "zh" | "中文" => Ok(Language::Chinese),
            "japanese" | "ja" | "日本語" => Ok(Language::Japanese),
            "german" | "de" | "deutsch" => Ok(Language::German),
            "french" | "fr" | "français" => Ok(Language::French),
            "english" | "en" => Ok(Language::English),
            _ => Err(format!("Unknown language: {}", s)),
        }
    }
}

/// ACMG/AMP variant classification categories
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VariantClassification {
    Pathogenic,
    LikelyPathogenic,
    UncertainSignificance,
    LikelyBenign,
    Benign,
}

impl std::fmt::Display for VariantClassification {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VariantClassification::Pathogenic => write!(f, "Pathogenic"),
            VariantClassification::LikelyPathogenic => write!(f, "Likely Pathogenic"),
            VariantClassification::UncertainSignificance => write!(f, "Uncertain Significance"),
            VariantClassification::LikelyBenign => write!(f, "Likely Benign"),
            VariantClassification::Benign => write!(f, "Benign"),
        }
    }
}

/// ACMG/AMP evidence criteria
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcmgCriteria {
    /// Very strong pathogenic criteria (PVS1)
    pub pvs1: bool,
    /// Strong pathogenic criteria (PS1-PS4)
    pub ps: Vec<String>,
    /// Moderate pathogenic criteria (PM1-PM6)
    pub pm: Vec<String>,
    /// Supporting pathogenic criteria (PP1-PP5)
    pub pp: Vec<String>,
    /// Stand-alone benign criteria (BA1)
    pub ba1: bool,
    /// Strong benign criteria (BS1-BS4)
    pub bs: Vec<String>,
    /// Supporting benign criteria (BP1-BP7)
    pub bp: Vec<String>,
}

impl Default for AcmgCriteria {
    fn default() -> Self {
        Self {
            pvs1: false,
            ps: Vec::new(),
            pm: Vec::new(),
            pp: Vec::new(),
            ba1: false,
            bs: Vec::new(),
            bp: Vec::new(),
        }
    }
}

/// Uploaded document metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    pub id: Uuid,
    pub filename: String,
    pub language: Language,
    pub upload_time: DateTime<Utc>,
    pub content_hash: String,
    pub extracted_text: Option<String>,
    pub status: DocumentStatus,
}

/// Document processing status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DocumentStatus {
    Uploaded,
    Processing,
    Processed,
    Failed,
}

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
