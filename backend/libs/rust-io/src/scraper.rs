use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use scraper::{Html, Selector};

/// Parse HTML with a CSS selector and return matched elements with metadata.
pub fn scrape_html(
    html: &str,
    css_selector: &str,
) -> Result<Vec<serde_json::Value>, GatewayError> {
    let document = Html::parse_document(html);
    let sel = Selector::parse(css_selector).map_err(|e| GatewayError::Other(e.to_string()))?;

    let items: Vec<serde_json::Value> = document
        .select(&sel)
        .map(|el| {
            let attrs: std::collections::HashMap<&str, &str> = el.value().attrs().collect();
            serde_json::json!({
                "text": el.text().collect::<Vec<_>>().join(" "),
                "html": el.inner_html(),
                "tag_name": el.value().name(),
                "attrs": attrs,
            })
        })
        .collect();

    Ok(items)
}

/// Resolve a potentially relative URL against a base.
fn resolve_url(base: &str, href: &str) -> String {
    if href.starts_with("http://") || href.starts_with("https://") {
        return href.to_string();
    }
    match url::Url::parse(base) {
        Ok(base_url) => match base_url.join(href) {
            Ok(resolved) => resolved.to_string(),
            Err(_) => href.to_string(),
        },
        Err(_) => href.to_string(),
    }
}

/// Extract PDF links from HTML by scanning <a href> and <meta citation_pdf_url>.
pub fn extract_pdf_links(html: &str, base_url: &str) -> Vec<String> {
    let document = Html::parse_document(html);
    let mut links = Vec::new();

    if let Ok(sel) = Selector::parse("a[href]") {
        for el in document.select(&sel) {
            if let Some(href) = el.value().attr("href") {
                let lower = href.to_lowercase();
                if lower.contains(".pdf")
                    || (lower.contains("download") && lower.contains("pdf"))
                {
                    let absolute = resolve_url(base_url, href);
                    if !links.contains(&absolute) {
                        links.push(absolute);
                    }
                }
            }
        }
    }

    if let Ok(sel) = Selector::parse("meta[name='citation_pdf_url']") {
        for el in document.select(&sel) {
            if let Some(content) = el.value().attr("content") {
                let absolute = resolve_url(base_url, content);
                if !links.contains(&absolute) {
                    links.push(absolute);
                }
            }
        }
    }

    links
}

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
