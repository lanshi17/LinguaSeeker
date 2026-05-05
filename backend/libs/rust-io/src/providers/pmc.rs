use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};

pub struct PmcProvider;

impl PmcProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi";
        let params = serde_json::json!({
            "db": "pmc",
            "term": query,
            "retmax": limit.unwrap_or(25),
            "retmode": "json",
        });

        let json = client.get_json(base_url, &params).await?;
        
        let items = parse_pmc_response(&json)?;
        Ok(FetchResult {
            provider: "pmc".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}

fn parse_pmc_response(json: &serde_json::Value) -> Result<Vec<serde_json::Value>, GatewayError> {
    let ids = json
        .get("esearchresult")
        .and_then(|r| r.get("idlist"))
        .and_then(|i| i.as_array())
        .map(|arr| arr.to_vec())
        .unwrap_or_default();
    Ok(ids)
}
