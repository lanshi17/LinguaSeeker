use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct DoajProvider;

impl DoajProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let limit = params.limit;
        let url = format!(
            "https://doaj.org/api/search/articles/{}",
            urlencoding::encode(query)
        );
        let limit = limit.unwrap_or(20).min(100);
        let params = serde_json::json!({
            "page": 1,
            "pageSize": limit,
        });

        let json = client.get_json(&url, &params).await?;
        let items = json
            .get("results")
            .and_then(|results| results.as_array())
            .map(|items| items.to_vec())
            .unwrap_or_default();
        let total = json
            .get("total")
            .and_then(|value| value.as_u64())
            .unwrap_or(0);

        Ok(FetchResult {
            provider: "doaj".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: Some(serde_json::json!({ "total_results": total })),
        })
    }

    pub async fn download_urls(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let search_result = Self::search(client, query, params.limit).await?;
        if search_result.items.is_empty() {
            return Ok(FetchResult::failure("doaj", vec!["doaj_no_results".into()]));
        }

        let selected_index = params.selected_index.unwrap_or(0) as usize;
        let item = &search_result.items[selected_index.min(search_result.items.len() - 1)];
        let links = extract_doaj_links(item);
        let downloads = links
            .iter()
            .map(|url| serde_json::json!({ "pdf_url": url }))
            .collect::<Vec<_>>();
        let warnings = if downloads.is_empty() {
            vec!["doaj_no_pdf_url".into()]
        } else {
            vec![]
        };

        Ok(FetchResult {
            provider: "doaj".into(),
            success: !downloads.is_empty(),
            items: vec![],
            downloads,
            warnings,
            raw: search_result.raw,
            meta: None,
        })
    }
}

fn extract_doaj_links(item: &serde_json::Value) -> Vec<String> {
    let mut links = Vec::new();
    let Some(bibjson) = item.get("bibjson") else {
        return links;
    };

    if let Some(values) = bibjson.get("link").and_then(|value| value.as_array()) {
        for link in values {
            if let Some(url) = link.get("url").and_then(|value| value.as_str()) {
                let content_type = link
                    .get("content_type")
                    .and_then(|value| value.as_str())
                    .unwrap_or_default();
                if content_type.contains("pdf") {
                    links.insert(0, url.into());
                } else {
                    links.push(url.into());
                }
            }
        }
    }

    if let Some(identifiers) = bibjson.get("identifier").and_then(|value| value.as_array()) {
        for identifier in identifiers {
            if identifier.get("type").and_then(|value| value.as_str()) == Some("doi")
                && let Some(doi) = identifier.get("id").and_then(|value| value.as_str())
            {
                links.push(format!("https://doi.org/{doi}"));
            }
        }
    }

    links
}
