use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Search,
    Download,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Identifiers {
    pub doi: Option<String>,
    pub pmid: Option<String>,
    pub pmcid: Option<String>,
    pub issn: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FetchParams {
    pub query: Option<String>,
    pub identifiers: Option<Identifiers>,
    pub limit: Option<u32>,
    pub raw: Option<bool>,
    pub selected_index: Option<u32>,
    pub selected_title: Option<String>,
    pub detail_link: Option<String>,
}

/// Matches Python ApiGatewayResult / WebGatewayResult
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FetchResult {
    pub provider: String,
    pub success: bool,
    pub items: Vec<serde_json::Value>,
    pub downloads: Vec<serde_json::Value>,
    pub warnings: Vec<String>,
    pub raw: Option<serde_json::Value>,
    pub meta: Option<serde_json::Value>,
}

impl FetchResult {
    pub fn failure(provider: &str, warnings: Vec<String>) -> Self {
        Self {
            provider: provider.into(),
            success: false,
            items: vec![],
            downloads: vec![],
            warnings,
            raw: None,
            meta: None,
        }
    }

    /// Build a successful result from parsed items.
    pub fn of_items(
        provider: &str,
        items: Vec<serde_json::Value>,
        raw: Option<serde_json::Value>,
    ) -> Self {
        FetchResult {
            provider: provider.into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw,
            meta: None,
        }
    }

    /// Build an empty (no-results) result for a provider.
    pub fn empty(provider: &str) -> Self {
        FetchResult {
            provider: provider.into(),
            success: false,
            items: vec![],
            downloads: vec![],
            warnings: vec![],
            raw: None,
            meta: None,
        }
    }
}

// ── MinerU API types ─────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUCreateTaskRequest {
    pub url: String,
    pub model_version: Option<String>,
    pub is_ocr: Option<bool>,
    pub enable_formula: Option<bool>,
    pub enable_table: Option<bool>,
    pub language: Option<String>,
    pub data_id: Option<String>,
    pub page_ranges: Option<String>,
    pub no_cache: Option<bool>,
    pub cache_tolerance: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUBatchFileEntry {
    pub url: String,
    pub data_id: Option<String>,
    pub is_ocr: Option<bool>,
    pub page_ranges: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUBatchSubmitRequest {
    pub files: Vec<MinerUBatchFileEntry>,
    pub model_version: Option<String>,
    pub enable_formula: Option<bool>,
    pub enable_table: Option<bool>,
    pub language: Option<String>,
    pub no_cache: Option<bool>,
    pub cache_tolerance: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerULocalFileEntry {
    pub name: String,
    pub data_id: Option<String>,
    pub is_ocr: Option<bool>,
    pub page_ranges: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUBatchUploadUrlRequest {
    pub files: Vec<MinerULocalFileEntry>,
    pub model_version: Option<String>,
    pub enable_formula: Option<bool>,
    pub enable_table: Option<bool>,
    pub language: Option<String>,
    pub callback: Option<String>,
    pub seed: Option<String>,
    pub extra_formats: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUUploadUrlRequest {
    pub filename: String,
    pub content_type: Option<String>,
    pub model_version: Option<String>,
    pub is_ocr: Option<bool>,
    pub enable_formula: Option<bool>,
    pub enable_table: Option<bool>,
    pub language: Option<String>,
    pub data_id: Option<String>,
    pub page_ranges: Option<String>,
    pub no_cache: Option<bool>,
    pub cache_tolerance: Option<u32>,
}
