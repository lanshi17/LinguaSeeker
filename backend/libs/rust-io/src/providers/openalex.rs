use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};

pub struct OpenAlexProvider;

impl OpenAlexProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let base_url = "https://api.openalex.org/works";
        let params = serde_json::json!({
            "search": query,
            "per-page": limit.unwrap_or(25),
        });

        let json = client.get_json(base_url, &params).await?;
        
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
