use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::FetchResult;

pub struct BioRxivProvider;
pub struct MedRxivProvider;

const BIORXIV_API_URL: &str = "https://api.biorxiv.org/details/biorxiv";
const MEDRXIV_API_URL: &str = "https://api.biorxiv.org/details/medrxiv";

impl BioRxivProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        search_preprint_server(client, query, limit, BIORXIV_API_URL, "biorxiv").await
    }
}

impl MedRxivProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        search_preprint_server(client, query, limit, MEDRXIV_API_URL, "medrxiv").await
    }
}

async fn search_preprint_server(
    client: &HttpClient,
    query: &str,
    limit: Option<u32>,
    api_url: &str,
    source: &str,
) -> Result<FetchResult, GatewayError> {
    let count = limit.unwrap_or(10).min(100);

    // bioRxiv/medRxiv /details endpoint requires date range
    // Use full history: bioRxiv started 2013, medRxiv started 2019
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let days_since_epoch = now / 86400;
    let end_date = epoch_days_to_date(days_since_epoch);
    let start_date = if source == "medrxiv" { "2019-01-01" } else { "2013-01-01" };

    let url = format!("{}/{}/{}/{}", api_url, start_date, end_date, count);

    let json = client.get_json(&url, &serde_json::json!({})).await?;

    let mut items = Vec::new();
    if let Some(collection) = json.get("collection").and_then(|c| c.as_array()) {
        for result in collection {
            let title = result
                .get("title")
                .and_then(|t| t.as_str())
                .unwrap_or("")
                .to_string();

            // Simple query matching - filter by title containing query terms
            let query_lower = query.to_lowercase();
            let title_lower = title.to_lowercase();
            let matches = query_lower
                .split_whitespace()
                .any(|term| title_lower.contains(term));

            if !matches && !query.is_empty() {
                continue;
            }

            let doi = result
                .get("doi")
                .and_then(|d| d.as_str())
                .map(String::from);
            let year = result
                .get("date")
                .and_then(|d| d.as_str())
                .and_then(|s| s.get(0..4))
                .map(String::from);
            let authors: Vec<String> = result
                .get("authors")
                .and_then(|a| a.as_str())
                .map(|s| {
                    s.split(';')
                        .map(|name| name.trim().to_string())
                        .filter(|name| !name.is_empty())
                        .collect()
                })
                .unwrap_or_default();
            let url = result
                .get("jatsxml")
                .or_else(|| result.get("href"))
                .and_then(|u| u.as_str())
                .map(String::from);

            items.push(serde_json::json!({
                "source": source,
                "title": title,
                "authors": authors,
                "doi": doi,
                "url": url,
                "year": year,
            }));
        }
    }

    Ok(FetchResult {
        provider: source.into(),
        success: !items.is_empty(),
        items,
        downloads: vec![],
        warnings: vec![],
        raw: Some(json),
        meta: None,
    })
}

fn epoch_days_to_date(days: u64) -> String {
    // Simple date calculation from days since epoch
    let mut y = 1970;
    let mut remaining = days;

    loop {
        let days_in_year = if is_leap_year(y) { 366 } else { 365 };
        if remaining < days_in_year {
            break;
        }
        remaining -= days_in_year;
        y += 1;
    }

    let leap = is_leap_year(y);
    let days_in_month = [31, if leap { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let mut m = 0;
    for (i, &days_in_m) in days_in_month.iter().enumerate() {
        if remaining < days_in_m as u64 {
            m = i + 1;
            break;
        }
        remaining -= days_in_m as u64;
    }

    format!("{:04}-{:02}-{:02}", y, m, remaining + 1)
}

fn is_leap_year(year: u64) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}
