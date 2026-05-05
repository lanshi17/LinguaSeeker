use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use scraper::{Html, Selector};

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
                    "html": el.outer_html(),
                })
            })
            .collect();
        
        Ok(items)
    }
}
