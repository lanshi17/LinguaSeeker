use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use scraper::{Html, Selector};

pub async fn scrape_provider(
    client: &HttpClient,
    provider: &str,
    action: &Action,
    params: &FetchParams,
) -> Result<FetchResult, GatewayError> {
    let _ = (provider, action);
    let url = params
        .detail_link
        .as_deref()
        .or(params.query.as_deref())
        .unwrap_or_default();

    if url.is_empty() {
        return Ok(FetchResult::failure(
            provider,
            vec!["scrape_requires_url".into()],
        ));
    }

    let scraper = WebScraper;
    let items = scraper.scrape(client, url, "body").await?;

    Ok(FetchResult {
        provider: provider.into(),
        success: !items.is_empty(),
        items,
        downloads: vec![],
        warnings: vec![],
        raw: None,
        meta: None,
    })
}

pub struct WebScraper;

impl WebScraper {
    pub async fn scrape(
        &self,
        client: &HttpClient,
        url: &str,
        selector: &str,
    ) -> Result<Vec<serde_json::Value>, GatewayError> {
        let html = client.get_text(url).await?;
        
        let document = Html::parse_document(&html);
        let sel = Selector::parse(selector).map_err(|e| GatewayError::Other(e.to_string()))?;
        
        let items: Vec<serde_json::Value> = document
            .select(&sel)
            .map(|el| {
                serde_json::json!({
                    "text": el.text().collect::<Vec<_>>().join(" "),
                    "html": el.inner_html(),
                })
            })
            .collect();
        
        Ok(items)
    }
}
