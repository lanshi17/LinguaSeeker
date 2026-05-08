use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct EuropePmcProvider;

impl EuropePmcProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let limit = params.limit.unwrap_or(25);
        let base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search";
        let search_query = search_query(params);

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

fn search_query(params: &FetchParams) -> String {
    let query = params.query.as_deref().unwrap_or_default();
    params
        .identifiers
        .as_ref()
        .and_then(|ids| {
            ids.doi
                .as_deref()
                .filter(|doi| !doi.is_empty())
                .map(|doi| format!("DOI:{doi}"))
                .or_else(|| {
                    ids.pmid
                        .as_deref()
                        .filter(|pmid| !pmid.is_empty())
                        .map(|pmid| format!("EXT_ID:{pmid}"))
                })
        })
        .unwrap_or_else(|| query.to_string())
}

fn parse_europepmc_response(
    json: &serde_json::Value,
) -> Result<Vec<serde_json::Value>, GatewayError> {
    let results = json
        .get("resultList")
        .and_then(|r| r.get("result"))
        .and_then(|r| r.as_array())
        .map(|arr| arr.to_vec())
        .unwrap_or_default();
    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::Identifiers;

    #[test]
    fn search_query_prefers_doi_then_pmid_then_query() {
        let params = FetchParams {
            query: Some("fallback".into()),
            identifiers: Some(Identifiers {
                doi: Some("10.1234/example".into()),
                pmid: Some("12345".into()),
                pmcid: None,
                issn: None,
            }),
            limit: None,
            raw: None,
            selected_index: None,
            selected_title: None,
            detail_link: None,
        };

        assert_eq!(search_query(&params), "DOI:10.1234/example");
    }

    #[test]
    fn search_query_uses_pmid_when_doi_is_empty() {
        let params = FetchParams {
            query: Some("fallback".into()),
            identifiers: Some(Identifiers {
                doi: Some("".into()),
                pmid: Some("12345".into()),
                pmcid: None,
                issn: None,
            }),
            limit: None,
            raw: None,
            selected_index: None,
            selected_title: None,
            detail_link: None,
        };

        assert_eq!(search_query(&params), "EXT_ID:12345");
    }

    #[test]
    fn search_query_falls_back_to_query_without_identifiers() {
        let params = FetchParams {
            query: Some("fallback".into()),
            identifiers: None,
            limit: None,
            raw: None,
            selected_index: None,
            selected_title: None,
            detail_link: None,
        };

        assert_eq!(search_query(&params), "fallback");
    }
}
