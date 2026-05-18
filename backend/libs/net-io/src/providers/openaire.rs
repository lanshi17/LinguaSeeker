use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::FetchResult;

pub struct OpenAireProvider;

const OPENAIRE_API_URL: &str = "https://api.openaire.eu/search/publications";

impl OpenAireProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let count = limit.unwrap_or(10).min(100);

        let params = serde_json::json!({
            "title": query,
            "format": "json",
            "limit": count.to_string(),
        });

        let json = client.get_json(OPENAIRE_API_URL, &params).await?;

        let mut items = Vec::new();
        if let Some(results) = json
            .get("response")
            .and_then(|r| r.get("results"))
            .and_then(|r| r.as_array())
        {
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
                    .get("publicationDate")
                    .and_then(|d| d.as_str())
                    .and_then(|s| s.get(0..4))
                    .map(String::from);
                let authors: Vec<String> = result
                    .get("authors")
                    .and_then(|a| a.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|a| {
                                a.get("name")
                                    .or_else(|| a.get("fullname"))
                                    .and_then(|n| n.as_str())
                                    .map(String::from)
                            })
                            .collect()
                    })
                    .unwrap_or_default();
                let url = result
                    .get("url")
                    .or_else(|| result.get("fullTextUrl"))
                    .and_then(|u| u.as_str())
                    .map(String::from);

                items.push(serde_json::json!({
                    "source": "openaire",
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "url": url,
                    "year": year,
                }));
            }
        }

        Ok(FetchResult {
            provider: "openaire".into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}
