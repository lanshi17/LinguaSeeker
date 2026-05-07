use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct OpenAlexProvider;

impl OpenAlexProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit.unwrap_or(25);
        let base_url = "https://api.openalex.org/works";

        // If DOI is provided, use DOI filter for exact lookup
        if let Some(doi) = params.identifiers.as_ref().and_then(|ids| ids.doi.as_deref()) {
            if !doi.is_empty() {
                let filter = format!("doi:{}", doi);
                let search_params = serde_json::json!({
                    "filter": filter,
                    "per-page": 1,
                });
                let json = client.get_json(base_url, &search_params).await?;
                let items = parse_openalex_response(&json)?;
                return Ok(FetchResult {
                    provider: "openalex".into(),
                    success: !items.is_empty(),
                    items,
                    downloads: vec![],
                    warnings: vec![],
                    raw: Some(json),
                    meta: None,
                });
            }
        }

        // Fallback: text search
        let search_params = serde_json::json!({
            "search": query,
            "per-page": limit,
        });

        let json = client.get_json(base_url, &search_params).await?;

        let items = parse_openalex_response(&json)?;
        Ok(FetchResult {
            provider: "openalex".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}

fn parse_openalex_response(json: &serde_json::Value) -> Result<Vec<serde_json::Value>, GatewayError> {
    let items = json
        .get("results")
        .and_then(|r| r.as_array())
        .map(|arr| arr.to_vec())
        .unwrap_or_default();
    Ok(items)
}
