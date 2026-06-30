use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct SciEloProvider;

const BASE_URL: &str = "https://search.scielo.org";

impl SciEloProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit;
        let count = limit.unwrap_or(10).min(100);
        let url = format!(
            "{}/?q={}&lang=en&count={}&output=json",
            BASE_URL,
            urlencoding::encode(query),
            count
        );

        let json = client.get_json(&url, &serde_json::json!({})).await?;

        let mut items = Vec::new();
        if let Some(docs) = json.get("documents").and_then(|d| d.as_array()) {
            for doc in docs {
                let title = doc
                    .get("title")
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string();
                let doi = doc
                    .get("doi")
                    .and_then(|d| d.as_str())
                    .map(String::from);
                let year = doc
                    .get("publication_date")
                    .and_then(|d| d.as_str())
                    .and_then(|s| s.get(0..4))
                    .map(String::from);
                let authors: Vec<String> = doc
                    .get("authors")
                    .and_then(|a| a.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|a| a.as_str().map(String::from))
                            .collect()
                    })
                    .unwrap_or_default();
                let url = doc
                    .get("url")
                    .and_then(|u| u.as_str())
                    .map(String::from);

                items.push(serde_json::json!({
                    "source": "scielo",
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "url": url,
                    "year": year,
                }));
            }
        }

        Ok(FetchResult::of_items("scielo", items, Some(json)))
    }
}
