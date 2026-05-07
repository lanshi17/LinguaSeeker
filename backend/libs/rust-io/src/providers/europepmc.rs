use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct EuropePmcProvider;

impl EuropePmcProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit.unwrap_or(25);
        let base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search";

        // Build query with identifier filters
        let search_query = if let Some(ids) = &params.identifiers {
            if let Some(doi) = ids.doi.as_deref() {
                if !doi.is_empty() {
                    format!("DOI:{}", doi)
                } else if let Some(pmid) = ids.pmid.as_deref() {
                    if !pmid.is_empty() {
                        format!("EXT_ID:{}", pmid)
                    } else {
                        query.to_string()
                    }
                } else {
                    query.to_string()
                }
            } else if let Some(pmid) = ids.pmid.as_deref() {
                if !pmid.is_empty() {
                    format!("EXT_ID:{}", pmid)
                } else {
                    query.to_string()
                }
            } else {
                query.to_string()
            }
        } else {
            query.to_string()
        };

        let search_params = serde_json::json!({
            "query": search_query,
            "pageSize": limit,
            "format": "json",
        });

        let json = client.get_json(base_url, &search_params).await?;

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
