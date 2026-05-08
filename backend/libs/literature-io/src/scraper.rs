use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use scraper::{Html, Selector};
use std::collections::HashSet;

/// Parse HTML with a CSS selector and return matched elements with metadata.
pub fn scrape_html(html: &str, css_selector: &str) -> Result<Vec<serde_json::Value>, GatewayError> {
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
    let mut seen = HashSet::new();

    if let Ok(sel) = Selector::parse("a[href]") {
        for el in document.select(&sel) {
            if let Some(href) = el.value().attr("href") {
                let lower = href.to_lowercase();
                if lower.contains(".pdf") || (lower.contains("download") && lower.contains("pdf")) {
                    let absolute = resolve_url(base_url, href);
                    if seen.insert(absolute.clone()) {
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
                if seen.insert(absolute.clone()) {
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
    _action: &Action,
    params: &FetchParams,
) -> Result<FetchResult, GatewayError> {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scrape_html_finds_elements() {
        let html = r#"<html><body><div class="item">Hello</div><div class="item">World</div></body></html>"#;
        let result = scrape_html(html, "div.item").unwrap();
        assert_eq!(result.len(), 2);
        assert_eq!(result[0]["text"], "Hello");
        assert_eq!(result[1]["text"], "World");
    }

    #[test]
    fn test_scrape_html_empty_selector() {
        let html = "<html><body><p>Test</p></body></html>";
        let result = scrape_html(html, "div.missing").unwrap();
        assert!(result.is_empty());
    }

    #[test]
    fn test_scrape_html_invalid_selector() {
        let html = "<html><body></body></html>";
        let result = scrape_html(html, ">>invalid");
        assert!(result.is_err());
    }

    #[test]
    fn test_scrape_html_preserves_attrs() {
        let html = r#"<a href="https://example.com" class="link">Click</a>"#;
        let result = scrape_html(html, "a").unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["attrs"]["href"], "https://example.com");
        assert_eq!(result[0]["attrs"]["class"], "link");
    }

    #[test]
    fn test_extract_pdf_links_from_anchor() {
        let html = r#"<html><body><a href="paper.pdf">Download</a><a href="other.html">Link</a></body></html>"#;
        let links = extract_pdf_links(html, "https://example.com");
        assert_eq!(links.len(), 1);
        assert!(links[0].contains("paper.pdf"));
    }

    #[test]
    fn test_extract_pdf_links_from_meta() {
        let html = r#"<html><head><meta name="citation_pdf_url" content="https://example.com/paper.pdf"></head></html>"#;
        let links = extract_pdf_links(html, "https://example.com");
        assert_eq!(links.len(), 1);
        assert_eq!(links[0], "https://example.com/paper.pdf");
    }

    #[test]
    fn test_extract_pdf_links_resolves_relative() {
        let html = r#"<a href="/files/paper.pdf">PDF</a>"#;
        let links = extract_pdf_links(html, "https://example.com/page");
        assert_eq!(links.len(), 1);
        assert_eq!(links[0], "https://example.com/files/paper.pdf");
    }

    #[test]
    fn test_extract_pdf_links_dedupes() {
        let html = r#"<a href="paper.pdf">A</a><a href="paper.pdf">B</a>"#;
        let links = extract_pdf_links(html, "https://example.com");
        assert_eq!(links.len(), 1);
    }

    #[test]
    fn test_extract_pdf_links_empty() {
        let html = "<html><body><a href=\"page.html\">Link</a></body></html>";
        let links = extract_pdf_links(html, "https://example.com");
        assert!(links.is_empty());
    }

    #[test]
    fn test_extract_pdf_links_download_pdf_pattern() {
        let html = r#"<a href="/download/pdf/12345">Download PDF</a>"#;
        let links = extract_pdf_links(html, "https://example.com");
        assert_eq!(links.len(), 1);
        assert!(links[0].contains("download/pdf/12345"));
    }
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
