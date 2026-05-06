use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::FetchResult;

pub struct EuropePmcProvider;

impl EuropePmcProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search";
        let params = serde_json::json!({
            "query": query,
            "pageSize": limit.unwrap_or(25),
            "format": "json",
        });

        let json = client.get_json(base_url, &params).await?;
        
        let items = parse_europepmc_response(&json)?;
        Ok(FetchResult {
            provider: "europepmc".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}

fn parse_europepmc_response(json: &serde_json::Value) -> Result<Vec<serde_json::Value>, GatewayError> {
    let results = json
        .get("resultList")
        .and_then(|r| r.get("result"))
        .and_then(|r| r.as_array())
        .map(|arr| arr.to_vec())
        .unwrap_or_default();
    Ok(results)
}
