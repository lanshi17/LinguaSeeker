use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct CrossrefProvider;

impl CrossrefProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit.unwrap_or(10);

        // If DOI is provided, use the DOI-specific endpoint
        if let Some(doi) = params.identifiers.as_ref().and_then(|ids| ids.doi.as_deref()) {
            if !doi.is_empty() {
                let url = format!("https://api.crossref.org/works/{}", doi);
                let json = client.get_json(&url, &serde_json::json!({})).await?;
                // DOI endpoint returns a single item in "message"
                let items = json
                    .get("message")
                    .map(|msg| vec![msg.clone()])
                    .unwrap_or_default();
                return Ok(FetchResult {
                    provider: "crossref".into(),
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
        let base_url = "https://api.crossref.org/works";
        let search_params = serde_json::json!({
            "query": query,
            "rows": limit,
        });

        let json = client.get_json(base_url, &search_params).await?;

        let items = parse_crossref_response(&json)?;
        Ok(FetchResult {
            provider: "crossref".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}

fn parse_crossref_response(json: &serde_json::Value) -> Result<Vec<serde_json::Value>, GatewayError> {
    let items = json
        .get("message")
        .and_then(|m| m.get("items"))
        .and_then(|i| i.as_array())
        .map(|arr| arr.to_vec())
        .unwrap_or_default();
    Ok(items)
}
