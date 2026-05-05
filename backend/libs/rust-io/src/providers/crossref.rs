use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};

pub struct CrossrefProvider;

impl CrossrefProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let base_url = "https://api.crossref.org/works";
        let params = serde_json::json!({
            "query": query,
            "rows": limit.unwrap_or(10),
        });

        let json = client.get_json(base_url, &params).await?;
        
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
