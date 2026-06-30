use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct CoreProvider;

const CORE_API_URL: &str = "https://api.core.ac.uk/v3";

impl CoreProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit;
        let count = limit.unwrap_or(10).min(100);
        let api_key = std::env::var("CORE_API_KEY").unwrap_or_default();

        let auth = if api_key.is_empty() {
            None
        } else {
            Some(format!("Bearer {}", api_key))
        };

        let url = format!(
            "{}/search/works?q={}&limit={}",
            CORE_API_URL,
            urlencoding::encode(query),
            count
        );

        let json = if let Some(auth_header) = auth {
            client.get_json_with_auth(&url, Some(&auth_header)).await?
        } else {
            client.get_json(&url, &serde_json::json!({})).await?
        };

        let mut items = Vec::new();
        if let Some(results) = json.get("results").and_then(|r| r.as_array()) {
            for result in results {
                let title = result
                    .get("title")
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string();
                let doi = result
                    .get("doi")
                    .and_then(|d| d.as_str())
                    .map(String::from);
                let year = result
                    .get("yearPublished")
                    .and_then(|y| y.as_i64())
                    .map(|y| y.to_string());
                let authors: Vec<String> = result
                    .get("authors")
                    .and_then(|a| a.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|a| {
                                a.get("name")
                                    .and_then(|n| n.as_str())
                                    .map(String::from)
                            })
                            .collect()
                    })
                    .unwrap_or_default();
                let url = result
                    .get("downloadUrl")
                    .or_else(|| result.get("sourceFulltextUrls").and_then(|u| u.as_array()).and_then(|a| a.first()))
                    .and_then(|u| u.as_str())
                    .map(String::from);

                items.push(serde_json::json!({
                    "source": "core",
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "url": url,
                    "year": year,
                }));
            }
        }

        Ok(FetchResult::of_items("core", items, Some(json)))
}
