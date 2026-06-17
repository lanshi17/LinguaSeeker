use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct PmcProvider;

impl PmcProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit.unwrap_or(25);

        // Build search term with identifier filters
        let search_term = if let Some(ids) = &params.identifiers {
            if let Some(pmcid) = ids.pmcid.as_deref()
                && !pmcid.is_empty()
            {
                return Self::fetch_by_pmcid(client, pmcid).await;
            }
            if let Some(pmid) = ids.pmid.as_deref()
                && !pmid.is_empty()
            {
                return Self::fetch_by_pmid(client, pmid).await;
            }
            query.to_string()
        } else {
            query.to_string()
        };

        // Step 1: esearch to get IDs
        let esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi";
        let mut esearch_params = serde_json::json!({
            "db": "pmc",
            "term": search_term,
            "retmax": limit,
            "retmode": "json",
        });
        insert_api_key(&mut esearch_params);

        let esearch_json = client.get_json(esearch_url, &esearch_params).await?;
        let ids = extract_ids(&esearch_json);

        if ids.is_empty() {
            return Ok(FetchResult {
                provider: "pmc".into(),
                success: true,
                items: vec![],
                downloads: vec![],
                warnings: vec![],
                raw: Some(esearch_json),
                meta: None,
            });
        }

        // Step 2: esummary to get metadata
        let items = Self::fetch_summaries(client, &ids).await?;
        Ok(FetchResult {
            provider: "pmc".into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(esearch_json),
            meta: None,
        })
    }

    async fn fetch_by_pmcid(client: &HttpClient, pmcid: &str) -> Result<FetchResult, GatewayError> {
        let clean_id = pmcid.strip_prefix("PMC").unwrap_or(pmcid);
        let esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi";
        let mut esearch_params = serde_json::json!({
            "db": "pmc",
            "term": format!("{}[uid]", clean_id),
            "retmax": 1,
            "retmode": "json",
        });
        insert_api_key(&mut esearch_params);

        let esearch_json = client.get_json(esearch_url, &esearch_params).await?;
        let ids = extract_ids(&esearch_json);

        if ids.is_empty() {
            return Ok(FetchResult {
                provider: "pmc".into(),
                success: false,
                items: vec![],
                downloads: vec![],
                warnings: vec!["pmc_id_not_found".into()],
                raw: Some(esearch_json),
                meta: None,
            });
        }

        let items = Self::fetch_summaries(client, &ids).await?;
        Ok(FetchResult {
            provider: "pmc".into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(esearch_json),
            meta: None,
        })
    }

    async fn fetch_by_pmid(client: &HttpClient, pmid: &str) -> Result<FetchResult, GatewayError> {
        let esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi";
        let mut esearch_params = serde_json::json!({
            "db": "pmc",
            "term": format!("{}[uid]", pmid),
            "retmax": 1,
            "retmode": "json",
        });
        insert_api_key(&mut esearch_params);

        let esearch_json = client.get_json(esearch_url, &esearch_params).await?;
        let ids = extract_ids(&esearch_json);

        if ids.is_empty() {
            return Ok(FetchResult {
                provider: "pmc".into(),
                success: false,
                items: vec![],
                downloads: vec![],
                warnings: vec!["pmid_not_found_in_pmc".into()],
                raw: Some(esearch_json),
                meta: None,
            });
        }

        let items = Self::fetch_summaries(client, &ids).await?;
        Ok(FetchResult {
            provider: "pmc".into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(esearch_json),
            meta: None,
        })
    }

    async fn fetch_summaries(
        client: &HttpClient,
        ids: &[String],
    ) -> Result<Vec<serde_json::Value>, GatewayError> {
        let id_list = ids.join(",");
        let esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi";
        let mut esummary_params = serde_json::json!({
            "db": "pmc",
            "id": id_list,
            "retmode": "json",
        });
        insert_api_key(&mut esummary_params);

        let json = client.get_json(esummary_url, &esummary_params).await?;

        // esummary returns { "result": { "uids": [...], "<uid>": {...}, ... } }
        let mut items = Vec::new();
        if let Some(result) = json.get("result")
            && let Some(uids) = result.get("uids").and_then(|u| u.as_array())
        {
            for uid in uids {
                if let Some(uid_str) = uid.as_str()
                    && let Some(summary) = result.get(uid_str)
                {
                    let mut item = summary.clone();
                    // Ensure pmcid is set
                    if let Some(obj) = item.as_object_mut() {
                        obj.insert(
                            "pmcid".into(),
                            serde_json::Value::String(format!("PMC{}", uid_str)),
                        );
                    }
                    items.push(item);
                }
            }
        }

        Ok(items)
    }
}

/// Read the NCBI API key from the `PUBMED_API_KEY` environment variable.
///
/// When present, NCBI E-utilities raise the per-IP rate limit from 3 to 10
/// requests/second. The key is optional — without it the API still works but
/// is subject to the lower limit.
fn ncbi_api_key() -> Option<String> {
    std::env::var("PUBMED_API_KEY")
        .ok()
        .filter(|k| !k.is_empty())
}

/// Insert `api_key` into an E-utilities query params object if available.
fn insert_api_key(params: &mut serde_json::Value) {
    if let Some(key) = ncbi_api_key() {
        if let Some(obj) = params.as_object_mut() {
            obj.insert("api_key".into(), serde_json::Value::String(key));
        }
    }
}

fn extract_ids(json: &serde_json::Value) -> Vec<String> {
    json.get("esearchresult")
        .and_then(|r| r.get("idlist"))
        .and_then(|i| i.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default()
}
