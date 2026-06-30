use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct BaseProvider;

const BASE_API_URL: &str = "https://api.base-search.net/BaseSearch";

impl BaseProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit;
        let count = limit.unwrap_or(10).min(100);
        let api_key = std::env::var("BASE_API_KEY").unwrap_or_default();

        let auth = if api_key.is_empty() {
            None
        } else {
            Some(format!("Bearer {}", api_key))
        };

        let url = format!(
            "{}/search?query={}&format=json&limit={}",
            BASE_API_URL,
            urlencoding::encode(query),
            count
        );

        let json = if let Some(auth_header) = auth {
            client.get_json_with_auth(&url, Some(&auth_header)).await?
        } else {
            client.get_json(&url, &serde_json::json!({})).await?
        };

        let mut items = Vec::new();
        if let Some(docs) = json
            .get("response")
            .and_then(|r| r.get("docs"))
            .and_then(|d| d.as_array())
        {
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
                    .get("year")
                    .and_then(|y| y.as_str())
                    .map(String::from);
                let authors: Vec<String> = doc
                    .get("creator")
                    .and_then(|c| c.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|v| v.as_str().map(String::from))
                            .collect()
                    })
                    .unwrap_or_default();
                let url = doc
                    .get("dcIdentifier")
                    .and_then(|u| u.as_str())
                    .map(String::from);

                items.push(serde_json::json!({
                    "source": "base",
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "url": url,
                    "year": year,
                }));
            }
        }

        Ok(FetchResult::of_items("base", items, Some(json)))
    }
}
