use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct JstageProvider;

impl JstageProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let params = serde_json::json!({
            "keyword": query,
            "count": limit.unwrap_or(20).min(100),
        });
        let json = client
            .get_json("https://www.jstage.jst.go.jp/search/global/_search", &params)
            .await?;
        let items = json
            .get("articles")
            .and_then(|articles| articles.as_array())
            .map(|articles| articles.to_vec())
            .unwrap_or_default();

        Ok(FetchResult {
            provider: "jstage".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }

    pub async fn download_urls(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        if let Some(detail_link) = &params.detail_link {
            return Ok(Self::downloads_from_link(detail_link, None));
        }

        let query = params.query.as_deref().unwrap_or_default();
        let search_result = Self::search(client, query, params.limit).await?;
        if search_result.items.is_empty() {
            return Ok(FetchResult::failure(
                "jstage",
                vec!["jstage_no_results".into()],
            ));
        }

        let selected_index = params.selected_index.unwrap_or(0) as usize;
        let item = &search_result.items[selected_index.min(search_result.items.len() - 1)];
        let detail_link = item.get("link").and_then(|value| value.as_str()).unwrap_or_default();
        Ok(Self::downloads_from_link(detail_link, search_result.raw))
    }

    fn downloads_from_link(detail_link: &str, raw: Option<serde_json::Value>) -> FetchResult {
        let candidates = pdf_candidates(detail_link);
        let downloads = candidates
            .iter()
            .map(|url| serde_json::json!({ "pdf_url": url }))
            .collect::<Vec<_>>();
        let warnings = if downloads.is_empty() {
            vec!["jstage_no_pdf_candidates".into()]
        } else {
            vec![]
        };

        FetchResult {
            provider: "jstage".into(),
            success: !downloads.is_empty(),
            items: vec![],
            downloads,
            warnings,
            raw,
            meta: None,
        }
    }
}

fn pdf_candidates(detail_link: &str) -> Vec<String> {
    if detail_link.is_empty() {
        return vec![];
    }

    let mut candidates = Vec::new();

    // Strip -char/lang suffix to get base URL
    let base = if let Some(idx) = detail_link.find("/-char/") {
        &detail_link[..idx]
    } else {
        detail_link
    };

    // Try _pdf from base (most likely to return direct PDF)
    if base.contains("/_article") {
        candidates.push(base.replace("/_article", "/_pdf"));
    }

    // Try original URL
    candidates.push(detail_link.to_string());

    // Try _pdf with -char suffix
    if detail_link.contains("/_article") {
        candidates.push(detail_link.replace("/_article", "/_pdf"));
    }

    candidates.dedup();
    candidates
}
