use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::FetchResult;

pub struct CiniiProvider;

const CINII_API_URL: &str = "https://cir.nii.ac.jp/opensearch/articles";

impl CiniiProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let count = limit.unwrap_or(10).min(100);

        let params = serde_json::json!({
            "q": query,
            "format": "json",
            "count": count.to_string(),
        });

        let json = client.get_json(CINII_API_URL, &params).await?;

        let mut items = Vec::new();

        // CiNii returns results in @graph array
        if let Some(graph) = json.get("@graph").and_then(|g| g.as_array()) {
            for entry in graph {
                // Check if this is a result item (has @type "item")
                let item_type = entry.get("@type").and_then(|t| t.as_str()).unwrap_or("");
                if item_type != "item" {
                    continue;
                }

                let title = entry
                    .get("title")
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string();
                let doi = entry
                    .get("doi")
                    .and_then(|d| d.as_str())
                    .map(String::from);
                let year = entry
                    .get("publicationDate")
                    .or_else(|| entry.get("publicationName"))
                    .and_then(|d| d.as_str())
                    .and_then(|s| s.get(0..4))
                    .map(String::from);
                let authors: Vec<String> = entry
                    .get("creator")
                    .or_else(|| entry.get("dc:creator"))
                    .and_then(|c| c.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|a| {
                                if let Some(name) = a.as_str() {
                                    Some(name.to_string())
                                } else if let Some(obj) = a.as_object() {
                                    obj.get("name")
                                        .and_then(|n| n.as_str())
                                        .map(String::from)
                                } else {
                                    None
                                }
                            })
                            .collect()
                    })
                    .unwrap_or_default();
                let url = entry
                    .get("link")
                    .and_then(|l| l.as_str())
                    .or_else(|| entry.get("@id").and_then(|id| id.as_str()))
                    .map(String::from);

                if !title.is_empty() {
                    items.push(serde_json::json!({
                        "source": "cinii",
                        "title": title,
                        "authors": authors,
                        "doi": doi,
                        "url": url,
                        "year": year,
                    }));
                }
            }
        }

        Ok(FetchResult {
            provider: "cinii".into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}
