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
}
