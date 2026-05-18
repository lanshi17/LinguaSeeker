use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::FetchResult;

pub struct ArxivProvider;

const ARXIV_API_URL: &str = "http://export.arxiv.org/api/query";

impl ArxivProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let max_results = limit.unwrap_or(10).min(100);

        let url = format!(
            "{}?search_query={}&max_results={}",
            ARXIV_API_URL,
            urlencoding::encode(query),
            max_results
        );

        let text = client.get_text(&url).await?;

        let mut items = Vec::new();

        // Parse Atom XML using simple string parsing
        // arXiv returns Atom feed format
        let entries: Vec<&str> = text.split("<entry>").collect();
        for entry in entries.iter().skip(1) {
            // Skip first split part (before first entry)
            let title = extract_tag(entry, "title")
                .unwrap_or_default()
                .replace('\n', " ")
                .trim()
                .to_string();
            let id = extract_tag(entry, "id").unwrap_or_default();
            let published = extract_tag(entry, "published").unwrap_or_default();
            let year = published.get(0..4).map(String::from);
            let doi = extract_tag(entry, "arxiv:doi").map(String::from);

            let mut authors = Vec::new();
            let author_parts: Vec<&str> = entry.split("<author>").collect();
            for author_part in author_parts.iter().skip(1) {
                if let Some(name) = extract_tag(author_part, "name") {
                    authors.push(name.to_string());
                }
            }

            // Extract PDF link
            let mut pdf_url = None;
            for line in entry.lines() {
                if line.contains("title=\"pdf\"") {
                    if let Some(href) = extract_attr(line, "href") {
                        pdf_url = Some(href.to_string());
                    }
                }
            }

            if !title.is_empty() {
                items.push(serde_json::json!({
                    "source": "arxiv",
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "url": pdf_url.unwrap_or_else(|| id.to_string()),
                    "year": year,
                }));
            }
        }

        Ok(FetchResult {
            provider: "arxiv".into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw: None,
            meta: None,
        })
    }
}

fn extract_tag<'a>(xml: &'a str, tag: &str) -> Option<&'a str> {
    let start_tag = format!("<{}>", tag);
    let end_tag = format!("</{}>", tag);
    let start = xml.find(&start_tag)? + start_tag.len();
    let end = xml.find(&end_tag)?;
    Some(xml[start..end].trim())
}

fn extract_attr<'a>(line: &'a str, attr: &str) -> Option<&'a str> {
    let pattern = format!("{}=\"", attr);
    let start = line.find(&pattern)? + pattern.len();
    let end = line[start..].find('"')?;
    Some(&line[start..start + end])
}
