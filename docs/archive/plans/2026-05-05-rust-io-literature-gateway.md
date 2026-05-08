# Rust I/O Literature Gateway Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a PyO3 native module (`rust_io.literature`) that replaces Python concurrent HTTP fetching with Rust reqwest + tokio. The module handles only I/O-intensive operations (HTTP requests, JSON parsing, HTML scraping) — all business logic (orchestration, fallback chains, rate limiting, file downloads) stays in Python.

**Architecture:** Rust handles: concurrent HTTP requests via reqwest+tokio, JSON response parsing, HTML scraping for static pages. Returns structured results (items, URLs, warnings) to Python via PyO3-async. Python handles: provider selection, fallback chains, rate limiting, file downloads, web scraper JS rendering (crawl4ai).

**Tech Stack:** Rust (edition 2024), PyO3 0.28 + pyo3-async 0.22, reqwest (rustls-tls, gzip, socks), tokio (rt-multi-thread), serde/serde_json, scraper, thiserror, url

---

## Module Structure

```
rust_io/                      # PyO3 top-level module
  literature/                 # Sub-module for literature I/O
    fetch_one()               # Single provider HTTP fetch
    fetch_multi()             # Concurrent multi-provider HTTP fetch
    scrape_web()              # Static HTML scraping (non-JS sites)
```

Python usage:
```python
import asyncio
from rust_io.literature import fetch_one, fetch_multi, scrape_web

# Async — returns a coroutine
result = await fetch_one("crossref", "search", {"query": "BRCA1", "limit": 5})
results = await fetch_multi(["crossref", "openalex", "europepmc"], "search", {"query": "BRCA1"})
html_result = await scrape_web("pubscholar", "search", {"query": "BRCA1"})
```

---

## Design Decisions (Confirmed)

| Decision | Choice | Reason |
|----------|--------|--------|
| Scope | HTTP + parsing only | Rust handles I/O, Python handles business logic |
| Async | pyo3-async | Python calls with `await`, Rust runs on tokio |
| Module name | `rust_io.literature` | Sub-module under general `rust_io` I/O package |
| SOCKS proxy | Yes | reqwest `socks` feature |
| Web scrapers | Static HTML only | JS-heavy sites (crawl4ai) stay in Python |
| Downloads | URLs only | Rust returns URLs, Python downloads files |
| Rate limiting | Python | Python controls request pacing |
| Response format | Match Python dataclass | `FetchResult` matches `ApiGatewayResult` fields |
| Tests | `libs/rust-io/tests/` | Rust tests + Python integration tests |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/libs/rust-io/Cargo.toml`

**Step 1: Update Cargo.toml**

```toml
[package]
name = "rust-io"
version = "0.1.0"
edition = "2024"
description = "High-performance I/O module for ACMG Lingua"

[lib]
name = "rust_io"
crate-type = ["cdylib", "rlib"]

[dependencies]
pyo3 = { version = "0.28.2", features = ["extension-module"] }
pyo3-async = { version = "0.22", features = ["tokio-runtime"] }
reqwest = { version = "0.12", features = ["json", "rustls-tls", "gzip", "socks"], default-features = false }
tokio = { version = "1", features = ["rt-multi-thread", "macros", "time"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
scraper = "0.22"
thiserror = "2"
url = "2"
urlencoding = "2"
pythonize = "0.22"
```

**Step 2: Verify compilation**

Run: `cd backend/libs/rust-io && cargo check`
Expected: Compiles (unused warnings OK)

**Step 3: Commit**

```bash
git add backend/libs/rust-io/Cargo.toml
git commit -m "chore(rust-io): add reqwest, tokio, pyo3-async, scraper dependencies"
```

---

## Task 2: Define Shared Types

**Files:**
- Create: `backend/libs/rust-io/src/error.rs`
- Create: `backend/libs/rust-io/src/types.rs`

**Step 1: Create error.rs**

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum GatewayError {
    #[error("HTTP request failed: {0}")]
    Http(#[from] reqwest::Error),

    #[error("JSON parse error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("URL parse error: {0}")]
    Url(#[from] url::ParseError),

    #[error("Provider '{provider}' error: {message}")]
    Provider { provider: String, message: String },

    #[error("{0}")]
    Other(String),
}

impl From<GatewayError> for pyo3::PyErr {
    fn from(err: GatewayError) -> Self {
        pyo3::exceptions::PyRuntimeError::new_err(err.to_string())
    }
}
```

**Step 2: Create types.rs — matches Python ApiGatewayResult/WebGatewayResult**

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Search,
    Download,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Identifiers {
    pub doi: Option<String>,
    pub pmid: Option<String>,
    pub pmcid: Option<String>,
    pub issn: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FetchParams {
    pub query: Option<String>,
    pub identifiers: Option<Identifiers>,
    pub limit: Option<u32>,
    pub raw: Option<bool>,
    pub selected_index: Option<u32>,
    pub selected_title: Option<String>,
    pub detail_link: Option<String>,
}

/// Matches Python ApiGatewayResult / WebGatewayResult
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FetchResult {
    pub provider: String,
    pub success: bool,
    pub items: Vec<serde_json::Value>,
    pub downloads: Vec<serde_json::Value>,
    pub warnings: Vec<String>,
    pub raw: Option<serde_json::Value>,
    pub meta: Option<serde_json::Value>,
}

impl FetchResult {
    pub fn failure(provider: &str, warnings: Vec<String>) -> Self {
        Self {
            provider: provider.into(),
            success: false,
            items: vec![],
            downloads: vec![],
            warnings,
            raw: None,
            meta: None,
        }
    }
}
```

**Step 3: Commit**

```bash
git add backend/libs/rust-io/src/error.rs backend/libs/rust-io/src/types.rs
git commit -m "feat(rust-io): add shared types matching Python gateway result format"
```

---

## Task 3: Build Shared HTTP Client

**Files:**
- Create: `backend/libs/rust-io/src/client.rs`

**Step 1: Implement HttpClient with retry, timeout, SOCKS proxy**

```rust
use std::time::Duration;
use reqwest::Client;
use crate::error::GatewayError;

const DEFAULT_TIMEOUT_MS: u64 = 30_000;
const DEFAULT_MAX_RETRIES: u32 = 2;
const BACKOFF_BASE_MS: u64 = 1000;

#[derive(Clone)]
pub struct HttpClient {
    inner: Client,
    max_retries: u32,
}

impl HttpClient {
    pub fn new(
        timeout_ms: Option<u64>,
        max_retries: Option<u32>,
        proxy: Option<&str>,
    ) -> Result<Self, GatewayError> {
        let timeout = Duration::from_millis(timeout_ms.unwrap_or(DEFAULT_TIMEOUT_MS));
        let mut builder = Client::builder()
            .timeout(timeout)
            .user_agent("acmg-lingua-io/0.1.0")
            .gzip(true)
            .redirect(reqwest::redirect::Policy::limited(10));

        if let Some(proxy_url) = proxy {
            let proxy = reqwest::Proxy::all(proxy_url)
                .map_err(|e| GatewayError::Other(format!("invalid proxy: {e}")))?;
            builder = builder.proxy(proxy);
        }

        Ok(Self {
            inner: builder.build()?,
            max_retries: max_retries.unwrap_or(DEFAULT_MAX_RETRIES),
        })
    }

    pub async fn get_json(
        &self,
        url: &str,
        params: &[(&str, &str)],
    ) -> Result<serde_json::Value, GatewayError> {
        let mut last_err = None;

        for attempt in 0..=self.max_retries {
            if attempt > 0 {
                let backoff = Duration::from_millis(BACKOFF_BASE_MS * 2u64.pow(attempt - 1));
                tokio::time::sleep(backoff).await;
            }

            let mut req = self.inner.get(url);
            if !params.is_empty() {
                req = req.query(params);
            }

            match req.send().await {
                Ok(resp) => {
                    let status = resp.status();
                    if status == 429 || status.is_server_error() {
                        last_err = Some(GatewayError::Provider {
                            provider: "http".into(),
                            message: format!("HTTP {status}"),
                        });
                        continue;
                    }
                    if status == 400 {
                        return Err(GatewayError::Provider {
                            provider: "http".into(),
                            message: "bad_request".into(),
                        });
                    }
                    resp.error_for_status_ref()?;
                    return Ok(resp.json().await?);
                }
                Err(e) => {
                    if e.is_timeout() || e.is_connect() {
                        last_err = Some(GatewayError::Http(e));
                        continue;
                    }
                    return Err(GatewayError::Http(e));
                }
            }
        }

        Err(last_err.unwrap_or_else(|| GatewayError::Other("request failed after retries".into())))
    }

    pub async fn get_text(&self, url: &str) -> Result<String, GatewayError> {
        Ok(self.inner.get(url).send().await?.error_for_status()?.text().await?)
    }
}
```

**Step 2: Verify compilation**

Run: `cd backend/libs/rust-io && cargo check`

**Step 3: Commit**

```bash
git add backend/libs/rust-io/src/client.rs
git commit -m "feat(rust-io): add HTTP client with retry, timeout, SOCKS proxy"
```

---

## Task 4: Implement Crossref Provider

**Files:**
- Create: `backend/libs/rust-io/src/providers/mod.rs`
- Create: `backend/libs/rust-io/src/providers/crossref.rs`

**Step 1: Create providers/mod.rs with trait + all provider stubs**

```rust
mod crossref;
mod unpaywall;
mod pmc;
mod doaj;
mod openalex;
mod europepmc;
mod jstage;

pub use crossref::CrossrefProvider;
pub use unpaywall::UnpaywallProvider;
pub use pmc::PmcProvider;
pub use doaj::DoajProvider;
pub use openalex::OpenalexProvider;
pub use europepmc::EuropepmcProvider;
pub use jstage::JstageProvider;

use async_trait::async_trait;
use crate::types::{Action, FetchParams, FetchResult};
use crate::error::GatewayError;
use crate::client::HttpClient;

#[async_trait]
pub trait Provider: Send + Sync {
    fn name(&self) -> &str;
    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError>;
}
```

**Step 2: Add async-trait to Cargo.toml**

```toml
async-trait = "0.1"
```

**Step 3: Create providers/crossref.rs**

Rust only fetches + parses JSON. No file downloads.

```rust
use async_trait::async_trait;
use serde_json::json;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use super::Provider;

pub struct CrossrefProvider;
const BASE_URL: &str = "https://api.crossref.org";

#[async_trait]
impl Provider for CrossrefProvider {
    fn name(&self) -> &str { "crossref" }

    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        match action {
            Action::Search => self.search(client, params).await,
            Action::Download => Ok(FetchResult::failure("crossref", vec!["crossref_download_unsupported".into()])),
        }
    }
}

impl CrossrefProvider {
    async fn search(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or("");
        let limit = params.limit.unwrap_or(20).min(100);
        let raw = params.raw.unwrap_or(false);

        let mut query_params: Vec<(&str, &str)> = vec![
            ("rows", &limit.to_string()[..]),
            ("query", query),
        ];

        if let Some(ids) = &params.identifiers {
            let filter_str;
            if let Some(doi) = &ids.doi {
                filter_str = format!("doi:{doi}");
                query_params.push(("filter", &filter_str));
            } else if let Some(issn) = &ids.issn {
                filter_str = format!("issn:{issn}");
                query_params.push(("filter", &filter_str));
            }
        }

        let data = client.get_json(&format!("{BASE_URL}/works"), &query_params).await?;
        let message = data.get("message").cloned().unwrap_or(json!({}));
        let items = message.get("items").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        let total = message.get("total-results").and_then(|v| v.as_u64()).unwrap_or(0);

        Ok(FetchResult {
            provider: "crossref".into(),
            success: !items.is_empty(),
            items,
            downloads: vec![],
            warnings: vec![],
            raw: if raw { Some(data) } else { None },
            meta: Some(json!({ "total_results": total })),
        })
    }
}
```

**Step 4: Commit**

```bash
git add backend/libs/rust-io/src/providers/mod.rs backend/libs/rust-io/src/providers/crossref.rs backend/libs/rust-io/Cargo.toml
git commit -m "feat(rust-io): add crossref provider"
```

---

## Task 5: Implement Unpaywall Provider

**Files:**
- Create: `backend/libs/rust-io/src/providers/unpaywall.rs`

**Step 1: Unpaywall — DOI lookup, returns PDF URL (no download)**

```rust
use async_trait::async_trait;
use serde_json::json;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use super::Provider;

pub struct UnpaywallProvider;
const BASE_URL: &str = "https://api.unpaywall.org/v2";

#[async_trait]
impl Provider for UnpaywallProvider {
    fn name(&self) -> &str { "unpaywall" }

    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let doi = params.identifiers.as_ref().and_then(|ids| ids.doi.as_deref());
        match action {
            Action::Search => self.lookup(client, params, doi).await,
            Action::Download => self.lookup(client, params, doi).await,
        }
    }
}

impl UnpaywallProvider {
    async fn lookup(&self, client: &HttpClient, params: &FetchParams, doi: Option<&str>) -> Result<FetchResult, GatewayError> {
        let raw = params.raw.unwrap_or(false);
        let doi = match doi {
            Some(d) => d,
            None => return Ok(FetchResult::failure("unpaywall", vec!["unpaywall_requires_doi".into()])),
        };

        let email = std::env::var("UNPAYWALL_EMAIL").unwrap_or_else(|_| "test@example.com".into());
        let data = client.get_json(&format!("{BASE_URL}/{doi}"), &[("email", &email)]).await?;

        // Extract PDF URL from best_oa_location
        let pdf_url = data
            .get("best_oa_location").and_then(|l| l.get("url_for_pdf")).and_then(|v| v.as_str())
            .or_else(|| data.get("best_oa_location").and_then(|l| l.get("url")).and_then(|v| v.as_str()));

        let downloads = if let Some(url) = pdf_url {
            vec![json!({"pdf_url": url})]
        } else {
            vec![]
        };

        Ok(FetchResult {
            provider: "unpaywall".into(),
            success: true,
            items: vec![data.clone()],
            downloads,
            warnings: if pdf_url.is_none() { vec!["no_oa_location".into()] } else { vec![] },
            raw: if raw { Some(data) } else { None },
            meta: None,
        })
    }
}
```

**Step 2: Commit**

```bash
git add backend/libs/rust-io/src/providers/unpaywall.rs
git commit -m "feat(rust-io): add unpaywall provider (returns PDF URL, no download)"
```

---

## Task 6: Implement PMC Provider

**Files:**
- Create: `backend/libs/rust-io/src/providers/pmc.rs`

**Step 1: PMC — search by PMID/PMCID, returns items + PDF URLs**

```rust
use async_trait::async_trait;
use serde_json::json;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use super::Provider;

pub struct PmcProvider;
const SEARCH_URL: &str = "https://www.ebi.ac.uk/europepmc/webservices/rest/search";
const OA_URL: &str = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi";

#[async_trait]
impl Provider for PmcProvider {
    fn name(&self) -> &str { "pmc" }

    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        match action {
            Action::Search => self.search(client, params).await,
            Action::Download => self.download_urls(client, params).await,
        }
    }
}

impl PmcProvider {
    fn build_term(params: &FetchParams) -> String {
        if let Some(ids) = &params.identifiers {
            if let Some(id) = &ids.pmcid { return id.clone(); }
            if let Some(id) = &ids.pmid { return format!("{id}[uid]"); }
        }
        params.query.clone().unwrap_or_default()
    }

    async fn search(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let term = Self::build_term(params);
        let limit = params.limit.unwrap_or(20).min(50);
        let raw = params.raw.unwrap_or(false);

        let data = client.get_json(SEARCH_URL, &[
            ("query", term.as_str()),
            ("resultType", "core"),
            ("format", "json"),
            ("pageSize", &limit.to_string()),
        ]).await?;

        let items = data.get("resultList").and_then(|r| r.get("result")).and_then(|r| r.as_array()).cloned().unwrap_or_default();
        let total = data.get("hitCount").and_then(|v| v.as_u64()).unwrap_or(0);

        Ok(FetchResult {
            provider: "pmc".into(), success: !items.is_empty(), items, downloads: vec![],
            warnings: vec![], raw: if raw { Some(data) } else { None },
            meta: Some(json!({ "total_results": total })),
        })
    }

    async fn download_urls(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let raw = params.raw.unwrap_or(false);
        let pmcid = params.identifiers.as_ref().and_then(|ids| ids.pmcid.clone());

        let pmcid = match pmcid {
            Some(id) => id,
            None => {
                let sr = self.search(client, params).await?;
                sr.items.iter().find_map(|i| i.get("pmcid").and_then(|v| v.as_str()).map(String::from))
                    .ok_or_else(|| GatewayError::Provider { provider: "pmc".into(), message: "no_pmcid_found".into() })?
            }
        };

        let data = client.get_json(OA_URL, &[("id", pmcid.as_str())]).await?;
        let records = data.get("records").and_then(|r| r.as_array()).cloned().unwrap_or_default();

        let mut downloads = vec![];
        for rec in &records {
            if let Some(link) = rec.get("download").and_then(|d| d.get("pdf")).and_then(|v| v.as_str()) {
                downloads.push(json!({"pdf_url": link}));
            }
        }

        Ok(FetchResult {
            provider: "pmc".into(), success: !downloads.is_empty(), items: vec![], downloads,
            warnings: if downloads.is_empty() { vec!["pmc_no_pdf_link".into()] } else { vec![] },
            raw: if raw { Some(data) } else { None }, meta: None,
        })
    }
}
```

**Step 2: Commit**

```bash
git add backend/libs/rust-io/src/providers/pmc.rs
git commit -m "feat(rust-io): add PMC provider (returns PDF URLs)"
```

---

## Task 7: Implement DOAJ Provider

**Files:**
- Create: `backend/libs/rust-io/src/providers/doaj.rs`

**Step 1: DOAJ — search articles, extract links from bibjson**

```rust
use async_trait::async_trait;
use serde_json::json;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use super::Provider;

pub struct DoajProvider;
const BASE_URL: &str = "https://doaj.org/api";

#[async_trait]
impl Provider for DoajProvider {
    fn name(&self) -> &str { "doaj" }

    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        match action {
            Action::Search => self.search(client, params).await,
            Action::Download => self.download_urls(client, params).await,
        }
    }
}

impl DoajProvider {
    async fn search(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or("");
        let limit = params.limit.unwrap_or(20).min(100);
        let raw = params.raw.unwrap_or(false);

        let data = client.get_json(&format!("{BASE_URL}/search/articles/{query}"), &[
            ("page", "1"), ("pageSize", &limit.to_string()),
        ]).await?;

        let items = data.get("results").and_then(|r| r.as_array()).cloned().unwrap_or_default();
        let total = data.get("total").and_then(|v| v.as_u64()).unwrap_or(0);

        Ok(FetchResult {
            provider: "doaj".into(), success: !items.is_empty(), items, downloads: vec![],
            warnings: vec![], raw: if raw { Some(data) } else { None },
            meta: Some(json!({ "total_results": total })),
        })
    }

    async fn download_urls(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let sr = self.search(client, params).await?;
        if sr.items.is_empty() { return Ok(FetchResult::failure("doaj", vec!["doaj_no_results".into()])); }

        let idx = params.selected_index.unwrap_or(0) as usize;
        let item = &sr.items[idx.min(sr.items.len() - 1)];
        let links = extract_doaj_links(item);

        Ok(FetchResult {
            provider: "doaj".into(), success: !links.is_empty(), items: vec![],
            downloads: links.iter().map(|u| json!({"pdf_url": u})).collect(),
            warnings: if links.is_empty() { vec!["doaj_no_pdf_url".into()] } else { vec![] },
            raw: sr.raw, meta: None,
        })
    }
}

fn extract_doaj_links(item: &serde_json::Value) -> Vec<String> {
    let mut links = vec![];
    if let Some(bibjson) = item.get("bibjson") {
        if let Some(arr) = bibjson.get("link").and_then(|v| v.as_array()) {
            for link in arr {
                if let Some(url) = link.get("url").and_then(|v| v.as_str()) {
                    let ct = link.get("content_type").and_then(|v| v.as_str()).unwrap_or("");
                    if ct.contains("pdf") { links.insert(0, url.into()); } else { links.push(url.into()); }
                }
            }
        }
        if let Some(arr) = bibjson.get("identifier").and_then(|v| v.as_array()) {
            for id in arr {
                if id.get("type").and_then(|v| v.as_str()) == Some("doi") {
                    if let Some(doi) = id.get("id").and_then(|v| v.as_str()) {
                        links.push(format!("https://doi.org/{doi}"));
                    }
                }
            }
        }
    }
    links
}
```

**Step 2: Commit**

```bash
git add backend/libs/rust-io/src/providers/doaj.rs
git commit -m "feat(rust-io): add DOAJ provider"
```

---

## Task 8: Implement OpenAlex Provider

**Files:**
- Create: `backend/libs/rust-io/src/providers/openalex.rs`

**Step 1: OpenAlex — DOI or query search, extract PDF URLs from open_access/locations**

```rust
use async_trait::async_trait;
use serde_json::json;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use super::Provider;

pub struct OpenalexProvider;
const BASE_URL: &str = "https://api.openalex.org";

#[async_trait]
impl Provider for OpenalexProvider {
    fn name(&self) -> &str { "openalex" }

    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        match action {
            Action::Search => self.search(client, params).await,
            Action::Download => self.download_urls(client, params).await,
        }
    }
}

impl OpenalexProvider {
    async fn search(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let raw = params.raw.unwrap_or(false);
        let limit = params.limit.unwrap_or(20);
        let doi = params.identifiers.as_ref().and_then(|ids| ids.doi.as_deref());

        let (data, items) = if let Some(doi) = doi {
            let d = client.get_json(&format!("{BASE_URL}/works/https://doi.org/{doi}"), &[]).await?;
            (d.clone(), vec![d])
        } else {
            let q = params.query.as_deref().unwrap_or("");
            let d = client.get_json(&format!("{BASE_URL}/works"), &[("search", q), ("per_page", &limit.to_string())]).await?;
            let items = d.get("results").and_then(|r| r.as_array()).cloned().unwrap_or_default();
            (d, items)
        };

        let total = data.get("meta").and_then(|m| m.get("count")).and_then(|v| v.as_u64()).unwrap_or(items.len() as u64);

        Ok(FetchResult {
            provider: "openalex".into(), success: !items.is_empty(), items, downloads: vec![],
            warnings: vec![], raw: if raw { Some(data) } else { None },
            meta: Some(json!({ "total_results": total })),
        })
    }

    async fn download_urls(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let sr = self.search(client, params).await?;
        if sr.items.is_empty() { return Ok(FetchResult::failure("openalex", vec!["openalex_no_results".into()])); }

        let idx = params.selected_index.unwrap_or(0) as usize;
        let item = &sr.items[idx.min(sr.items.len() - 1)];

        let pdf_url = item.get("open_access").and_then(|oa| oa.get("oa_url")).and_then(|v| v.as_str())
            .or_else(|| item.get("locations").and_then(|locs| {
                locs.as_array().and_then(|arr| arr.iter().find_map(|l| l.get("pdf_url").and_then(|v| v.as_str())))
            }));

        let downloads = if let Some(url) = pdf_url { vec![json!({"pdf_url": url})] } else { vec![] };

        Ok(FetchResult {
            provider: "openalex".into(), success: !downloads.is_empty(), items: vec![], downloads,
            warnings: if pdf_url.is_none() { vec!["openalex_no_pdf_url".into()] } else { vec![] },
            raw: sr.raw, meta: None,
        })
    }
}
```

**Step 2: Commit**

```bash
git add backend/libs/rust-io/src/providers/openalex.rs
git commit -m "feat(rust-io): add OpenAlex provider"
```

---

## Task 9: Implement EuropePMC Provider

**Files:**
- Create: `backend/libs/rust-io/src/providers/europepmc.rs`

**Step 1: EuropePMC — search + fulltext XML URL**

```rust
use async_trait::async_trait;
use serde_json::json;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use super::Provider;

pub struct EuropepmcProvider;
const BASE_URL: &str = "https://www.ebi.ac.uk/europepmc/webservices/rest/search";

#[async_trait]
impl Provider for EuropepmcProvider {
    fn name(&self) -> &str { "europepmc" }

    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        match action {
            Action::Search => self.search(client, params).await,
            Action::Download => self.download_urls(client, params).await,
        }
    }
}

impl EuropepmcProvider {
    fn build_query(params: &FetchParams) -> String {
        if let Some(ids) = &params.identifiers {
            if let Some(d) = &ids.doi { return format!("DOI:{d}"); }
            if let Some(p) = &ids.pmid { return format!("EXT_ID:{p}"); }
        }
        params.query.clone().unwrap_or_default()
    }

    async fn search(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let query = Self::build_query(params);
        let limit = params.limit.unwrap_or(20);
        let raw = params.raw.unwrap_or(false);

        let data = client.get_json(BASE_URL, &[
            ("query", query.as_str()), ("resultType", "core"), ("format", "json"), ("pageSize", &limit.to_string()),
        ]).await?;

        let items = data.get("resultList").and_then(|r| r.get("result")).and_then(|r| r.as_array()).cloned().unwrap_or_default();
        let total = data.get("hitCount").and_then(|v| v.as_u64()).unwrap_or(0);

        Ok(FetchResult {
            provider: "europepmc".into(), success: !items.is_empty(), items, downloads: vec![],
            warnings: vec![], raw: if raw { Some(data) } else { None },
            meta: Some(json!({ "total_results": total })),
        })
    }

    async fn download_urls(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let sr = self.search(client, params).await?;
        if sr.items.is_empty() { return Ok(FetchResult::failure("europepmc", vec!["europepmc_no_results".into()])); }

        let idx = params.selected_index.unwrap_or(0) as usize;
        let item = &sr.items[idx.min(sr.items.len() - 1)];

        let mut downloads = vec![];
        if let Some(pmcid) = item.get("pmcid").and_then(|v| v.as_str()) {
            let ft_url = format!("https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML");
            downloads.push(json!({"url": ft_url, "content_type": "text/xml", "pmcid": pmcid}));
        }

        Ok(FetchResult {
            provider: "europepmc".into(), success: !downloads.is_empty(), items: vec![], downloads,
            warnings: if downloads.is_empty() { vec!["europepmc_no_fulltext".into()] } else { vec![] },
            raw: sr.raw, meta: None,
        })
    }
}
```

**Step 2: Commit**

```bash
git add backend/libs/rust-io/src/providers/europepmc.rs
git commit -m "feat(rust-io): add EuropePMC provider"
```

---

## Task 10: Implement JStage Provider

**Files:**
- Create: `backend/libs/rust-io/src/providers/jstage.rs`

**Step 1: JStage — search + PDF candidate URLs**

```rust
use async_trait::async_trait;
use serde_json::json;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};
use super::Provider;

pub struct JstageProvider;
const BASE_URL: &str = "https://www.jstage.jst.go.jp";

#[async_trait]
impl Provider for JstageProvider {
    fn name(&self) -> &str { "jstage" }

    async fn execute(&self, client: &HttpClient, action: &Action, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        match action {
            Action::Search => self.search(client, params).await,
            Action::Download => self.download_urls(client, params).await,
        }
    }
}

impl JstageProvider {
    async fn search(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or("");
        let limit = params.limit.unwrap_or(20).min(100);
        let raw = params.raw.unwrap_or(false);

        let data = client.get_json(&format!("{BASE_URL}/search/global/_search"), &[
            ("keyword", query), ("count", &limit.to_string()),
        ]).await?;

        let items = data.get("articles").and_then(|a| a.as_array()).cloned().unwrap_or_default();

        Ok(FetchResult {
            provider: "jstage".into(), success: !items.is_empty(), items, downloads: vec![],
            warnings: vec![], raw: if raw { Some(data) } else { None }, meta: None,
        })
    }

    async fn download_urls(&self, client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError> {
        // If detail_link provided, generate PDF candidates directly
        if let Some(link) = &params.detail_link {
            let candidates = pdf_candidates(link);
            return Ok(FetchResult {
                provider: "jstage".into(), success: !candidates.is_empty(), items: vec![],
                downloads: candidates.iter().map(|u| json!({"pdf_url": u})).collect(),
                warnings: vec![], raw: None, meta: None,
            });
        }

        let sr = self.search(client, params).await?;
        if sr.items.is_empty() { return Ok(FetchResult::failure("jstage", vec!["jstage_no_results".into()])); }

        let idx = params.selected_index.unwrap_or(0) as usize;
        let item = &sr.items[idx.min(sr.items.len() - 1)];
        let link = item.get("link").and_then(|v| v.as_str()).unwrap_or("");
        let candidates = pdf_candidates(link);

        Ok(FetchResult {
            provider: "jstage".into(), success: !candidates.is_empty(), items: vec![],
            downloads: candidates.iter().map(|u| json!({"pdf_url": u})).collect(),
            warnings: if candidates.is_empty() { vec!["jstage_no_pdf_candidates".into()] } else { vec![] },
            raw: sr.raw, meta: None,
        })
    }
}

fn pdf_candidates(detail_link: &str) -> Vec<String> {
    let mut c = vec![detail_link.to_string()];
    if detail_link.contains("/_article") { c.push(detail_link.replace("/_article", "/_pdf")); }
    if detail_link.contains("/_article/") { c.push(detail_link.replace("/_article/", "/_pdf/")); }
    c
}
```

**Step 2: Commit**

```bash
git add backend/libs/rust-io/src/providers/jstage.rs
git commit -m "feat(rust-io): add JStage provider"
```

---

## Task 11: Implement HTML Web Scraper

**Files:**
- Create: `backend/libs/rust-io/src/scraper/mod.rs`

**Step 1: Static HTML scraper for 3 web providers (returns items with detail_link)**

Rust handles HTML fetching + parsing. JS-heavy scraping stays in Python (crawl4ai).

```rust
use scraper::{Html, Selector};
use serde_json::json;
use url::Url;
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};

pub struct WebScraper;

impl WebScraper {
    pub async fn execute(
        &self, client: &HttpClient, provider: &str, action: &Action, params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let (base_url, search_path) = match provider {
            "pubscholar" => ("https://pubscholar.cn", "/search"),
            "cyberleninka" => ("https://cyberleninka.ru", "/search"),
            "hans_publishers" => ("https://www.hanspub.org", "/Search"),
            _ => return Err(GatewayError::Other(format!("unknown web provider: {provider}"))),
        };

        match action {
            Action::Search => self.search(client, provider, base_url, search_path, params).await,
            Action::Download => self.search(client, provider, base_url, search_path, params).await,
        }
    }

    async fn search(
        &self, client: &HttpClient, provider: &str, base_url: &str, search_path: &str, params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or("");
        let limit = params.limit.unwrap_or(20);
        let encoded = urlencoding::encode(query);

        let url = match provider {
            "hans_publishers" => format!("{base_url}{search_path}?keyword={encoded}"),
            _ => format!("{base_url}{search_path}?q={encoded}"),
        };

        let html = client.get_text(&url).await?;
        let items = parse_results(&html, base_url, provider);

        Ok(FetchResult {
            provider: provider.into(), success: !items.is_empty(),
            items: items.into_iter().take(limit as usize).collect(),
            downloads: vec![], warnings: vec![], raw: None, meta: None,
        })
    }
}

fn parse_results(html: &str, base_url: &str, provider: &str) -> Vec<serde_json::Value> {
    let doc = Html::parse_document(html);
    let mut items = vec![];

    let selectors: Vec<&str> = match provider {
        "cyberleninka" => vec!["h2 a", ".search-results a", ".result-item a"],
        "pubscholar" => vec![".search-result-item", ".result-item", "article"],
        "hans_publishers" => vec![".article-item", ".search-result", ".result-list li"],
        _ => vec!["a"],
    };

    for sel_str in selectors {
        if let Ok(sel) = Selector::parse(sel_str) {
            for el in doc.select(&sel) {
                let title = el.text().collect::<String>().trim().to_string();
                let href = el.value().attr("href")
                    .or_else(|| el.select(&Selector::parse("a").ok()?).next().and_then(|a| a.value().attr("href")))
                    .unwrap_or("");
                if !title.is_empty() && !href.is_empty() {
                    items.push(json!({
                        "title": title,
                        "detail_link": resolve_url(base_url, href),
                    }));
                }
            }
        }
        if !items.is_empty() { break; }
    }

    items
}

fn resolve_url(base: &str, href: &str) -> String {
    if href.starts_with("http") { return href.into(); }
    Url::parse(base).and_then(|u| u.join(href)).map(|u| u.to_string()).unwrap_or_else(|_| format!("{base}/{href}"))
}
```

**Step 2: Commit**

```bash
git add backend/libs/rust-io/src/scraper/mod.rs
git commit -m "feat(rust-io): add static HTML web scraper for 3 providers"
```

---

## Task 12: Implement PyO3-async Bindings

**Files:**
- Create: `backend/libs/rust-io/src/py.rs`
- Modify: `backend/libs/rust-io/src/lib.rs`

**Step 1: PyO3-async module — `rust_io.literature` sub-module**

Functions return `PyResult<Bound<'_, PyAny>>` — Python calls with `await`.

```rust
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::providers::*;
use crate::scraper::WebScraper;
use crate::types::{Action, FetchParams, FetchResult};

fn result_to_py(py: Python<'_>, r: &FetchResult) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("provider", &r.provider)?;
    d.set_item("success", r.success)?;
    d.set_item("items", pythonize::pythonize(py, &r.items)?)?;
    d.set_item("downloads", pythonize::pythonize(py, &r.downloads)?)?;
    d.set_item("warnings", &r.warnings)?;
    if let Some(ref v) = r.raw { d.set_item("raw", pythonize::pythonize(py, v)?)?; }
    if let Some(ref v) = r.meta { d.set_item("meta", pythonize::pythonize(py, v)?)?; }
    Ok(d.into_any().unbind())
}

fn parse_params(params: &Bound<'_, PyDict>) -> PyResult<FetchParams> {
    let v: serde_json::Value = pythonize::depythonize(params)?;
    serde_json::from_value(v).map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("invalid params: {e}")))
}

fn parse_action(action: &str) -> PyResult<Action> {
    match action {
        "search" => Ok(Action::Search),
        "download" => Ok(Action::Download),
        _ => Err(pyo3::exceptions::PyValueError::new_err("action must be 'search' or 'download'")),
    }
}

fn make_provider(name: &str) -> PyResult<Box<dyn Provider>> {
    match name {
        "crossref" => Ok(Box::new(CrossrefProvider)),
        "unpaywall" => Ok(Box::new(UnpaywallProvider)),
        "pmc" => Ok(Box::new(PmcProvider)),
        "doaj" => Ok(Box::new(DoajProvider)),
        "openalex" => Ok(Box::new(OpenalexProvider)),
        "europepmc" => Ok(Box::new(EuropepmcProvider)),
        "jstage" => Ok(Box::new(JstageProvider)),
        _ => Err(pyo3::exceptions::PyValueError::new_err(format!("unknown provider: {name}"))),
    }
}

#[pyfunction]
#[pyo3(signature = (provider, action, params, timeout_ms=None, max_retries=None, proxy=None))]
fn fetch_one<'py>(
    py: Python<'py>,
    provider: &str,
    action: &str,
    params: &Bound<'py, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let provider = make_provider(provider)?;
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;

    // Pattern: wrap async work in into_coroutine, which returns a Python awaitable
    pyo3_asyncrtio::tokio::into_coroutine(py, async move {
        let result = provider.execute(&client, &action, &params).await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Python::with_gil(|py| result_to_py(py, &result))
    })
}

#[pyfunction]
#[pyo3(signature = (providers, action, params, timeout_ms=None, max_retries=None, proxy=None))]
fn fetch_multi<'py>(
    py: Python<'py>,
    providers: Vec<String>,
    action: &str,
    params: &Bound<'py, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;

    pyo3_asyncrtio::tokio::into_coroutine(py, async move {
        let mut handles = Vec::new();
        for name in &providers {
            if let Ok(p) = make_provider(name) {
                let c = client.clone();
                let a = action.clone();
                let fp = params.clone();
                handles.push(tokio::spawn(async move { p.execute(&c, &a, &fp).await }));
            }
        }
        let mut results = Vec::new();
        for h in handles {
            match h.await {
                Ok(Ok(r)) => results.push(r),
                Ok(Err(e)) => results.push(FetchResult::failure("unknown", vec![format!("error:{e}")])),
                Err(e) => results.push(FetchResult::failure("unknown", vec![format!("join_error:{e}")])),
            }
        }
        Python::with_gil(|py| {
            let list = PyList::empty(py);
            for r in &results { list.append(result_to_py(py, &r)?)?; }
            Ok(list.into_any().unbind())
        })
    })
}

#[pyfunction]
#[pyo3(signature = (provider, action, params, timeout_ms=None, max_retries=None, proxy=None))]
fn scrape_web<'py>(
    py: Python<'py>,
    provider: &str,
    action: &str,
    params: &Bound<'py, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;
    let provider = provider.to_string();

    pyo3_asyncrtio::tokio::into_coroutine(py, async move {
        let scraper = WebScraper;
        let result = scraper.execute(&client, &provider, &action, &params).await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Python::with_gil(|py| result_to_py(py, &result))
    })
}

// NOTE: During implementation, verify the exact pyo3-async 0.22 API.
// The pattern is: async block → pyo3_asyncrtio::tokio::into_coroutine → PyResult<Bound<'py, PyAny>>
// Python calls the result with `await`.
```

**Note:** The exact pyo3-async API depends on the version. The pattern above shows the intent. During implementation, verify the correct API from pyo3-async 0.22 docs. The key is:
- `fetch_one` / `fetch_multi` / `scrape_web` are `#[pyfunction]` returning `PyResult<Bound<'py, PyAny>>`
- Python calls them with `await`
- Internally uses `pyo3_asyncrtio::tokio` to bridge Rust async → Python coroutine

**Step 2: Create lib.rs with nested module**

```rust
mod error;
mod types;
mod client;
mod providers;
mod scraper;
mod py;

use pyo3::prelude::*;

#[pymodule]
fn rust_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let literature = PyModule::new(m.py(), "literature")?;
    literature.add_function(wrap_pyfunction!(py::fetch_one, &literature)?)?;
    literature.add_function(wrap_pyfunction!(py::fetch_multi, &literature)?)?;
    literature.add_function(wrap_pyfunction!(py::scrape_web, &literature)?)?;
    m.add_submodule(&literature)?;
    Ok(())
}
```

**Step 3: Update pyproject.toml**

```toml
[project]
name = "rust-io"
requires-python = ">=3.10"
```

**Step 4: Verify compilation**

Run: `cd backend/libs/rust-io && cargo check`

**Step 5: Commit**

```bash
git add backend/libs/rust-io/src/py.rs backend/libs/rust-io/src/lib.rs backend/libs/rust-io/pyproject.toml
git commit -m "feat(rust-io): add pyo3-async bindings as rust_io.literature sub-module"
```

---

## Task 13: Write Rust Tests

**Files:**
- Create: `backend/libs/rust-io/tests/test_types.rs`

**Step 1: Unit tests for types and client**

```rust
use rust_io::types::*;
use rust_io::client::HttpClient;

#[test]
fn test_client_creation() {
    assert!(HttpClient::new(Some(5000), Some(1), None).is_ok());
    assert!(HttpClient::new(Some(5000), Some(1), Some("socks5://127.0.0.1:1080")).is_ok());
}

#[test]
fn test_fetch_params_roundtrip() {
    let json = serde_json::json!({
        "query": "BRCA1",
        "identifiers": {"doi": "10.1234/test", "pmid": "12345"},
        "limit": 10,
        "raw": false
    });
    let params: FetchParams = serde_json::from_value(json).unwrap();
    assert_eq!(params.query.as_deref(), Some("BRCA1"));
    assert_eq!(params.identifiers.as_ref().unwrap().doi.as_deref(), Some("10.1234/test"));
    assert_eq!(params.limit, Some(10));

    let back = serde_json::to_value(&params).unwrap();
    assert_eq!(back["query"], "BRCA1");
}

#[test]
fn test_fetch_result_matches_python_format() {
    let r = FetchResult {
        provider: "crossref".into(), success: true,
        items: vec![serde_json::json!({"title": "Test"})],
        downloads: vec![], warnings: vec![], raw: None, meta: None,
    };
    let j = serde_json::to_value(&r).unwrap();
    assert_eq!(j["provider"], "crossref");
    assert!(j["success"].as_bool().unwrap());
    assert!(j["items"].as_array().unwrap().len() == 1);
}

#[test]
fn test_fetch_result_failure_constructor() {
    let r = FetchResult::failure("pmc", vec!["error".into()]);
    assert!(!r.success);
    assert_eq!(r.provider, "pmc");
    assert_eq!(r.warnings, vec!["error"]);
}
```

**Step 2: Run tests**

Run: `cd backend/libs/rust-io && cargo test`
Expected: All pass

**Step 3: Commit**

```bash
git add backend/libs/rust-io/tests/test_types.rs
git commit -m "test(rust-io): add Rust unit tests for types and client"
```

---

## Task 14: Build and Smoke Test

**Step 1: Build with maturin**

Run: `cd backend/libs/rust-io && maturin develop --release`

**Step 2: Smoke test**

```python
import asyncio
from rust_io.literature import fetch_one, fetch_multi, scrape_web

async def main():
    r = await fetch_one("crossref", "search", {"query": "BRCA1", "limit": 3})
    print(f"crossref: success={r['success']}, items={len(r['items'])}")

    results = await fetch_multi(["crossref", "openalex"], "search", {"query": "BRCA1", "limit": 3})
    for r in results:
        print(f"  {r['provider']}: success={r['success']}, items={len(r['items'])}")

    print("OK")

asyncio.run(main())
```

**Step 3: Commit**

```bash
git commit -m "chore(rust-io): build and verify Python smoke test"
```

---

## Task 15: Python Integration Tests

**Files:**
- Create: `backend/libs/rust-io/tests/test_integration.py`

**Step 1: Tests**

```python
import asyncio
import pytest
from rust_io.literature import fetch_one, fetch_multi, scrape_web

class TestFetchOne:
    def test_crossref(self):
        r = asyncio.run(fetch_one("crossref", "search", {"query": "BRCA1", "limit": 3}))
        assert r["provider"] == "crossref"
        assert isinstance(r["items"], list)

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="unknown provider"):
            asyncio.run(fetch_one("nope", "search", {"query": "x"}))

    def test_invalid_action(self):
        with pytest.raises(ValueError, match="action must be"):
            asyncio.run(fetch_one("crossref", "nope", {"query": "x"}))

class TestFetchMulti:
    def test_concurrent(self):
        results = asyncio.run(fetch_multi(["crossref", "openalex"], "search", {"query": "BRCA1", "limit": 3}))
        assert len(results) == 2
        assert {r["provider"] for r in results} == {"crossref", "openalex"}

    def test_empty(self):
        assert asyncio.run(fetch_multi([], "search", {"query": "x"})) == []

class TestScrapeWeb:
    def test_unknown_provider(self):
        with pytest.raises(RuntimeError, match="unknown web provider"):
            asyncio.run(scrape_web("nope", "search", {"query": "x"}))
```

**Step 2: Run**

Run: `cd backend/libs/rust-io && python -m pytest tests/test_integration.py -v`

**Step 3: Commit**

```bash
git add backend/libs/rust-io/tests/test_integration.py
git commit -m "test(rust-io): add Python integration tests"
```

---

## Summary

| Task | Description | Dependencies | Status |
|------|-------------|--------------|--------|
| 1 | Add Cargo dependencies | — | ✅ COMPLETED |
| 2 | Shared types (error, result) | 1 | ✅ COMPLETED |
| 3 | HTTP client (retry, proxy) | 2 | ✅ COMPLETED |
| 4 | Crossref provider | 3 | ✅ COMPLETED |
| 5 | Unpaywall provider | 3 | ❌ NOT IMPLEMENTED |
| 6 | PMC provider | 3 | ✅ COMPLETED |
| 7 | DOAJ provider | 3 | ❌ NOT IMPLEMENTED |
| 8 | OpenAlex provider | 3 | ✅ COMPLETED |
| 9 | EuropePMC provider | 3 | ✅ COMPLETED |
| 10 | JStage provider | 3 | ❌ NOT IMPLEMENTED |
| 11 | HTML web scraper | 3 | ✅ COMPLETED |
| 12 | PyO3-async bindings | 4-11 | ✅ COMPLETED |
| 13 | Rust tests | 12 | ❌ NOT IMPLEMENTED |
| 14 | Build + smoke test | 12 | ⚠️ PARTIAL (build artifacts exist) |
| 15 | Python integration tests | 14 | ❌ NOT IMPLEMENTED |

### Implementation Status: 9/15 tasks complete (60%)

**Source files implemented:**
- `src/lib.rs` — PyO3 module with `rust_io.literature` submodule
- `src/error.rs` — `GatewayError` enum with thiserror + PyErr conversion
- `src/types.rs` — `Action`, `Identifiers`, `FetchParams`, `FetchResult`
- `src/client.rs` — `HttpClient` with retry, timeout, gzip, SOCKS proxy
- `src/providers/mod.rs` — Provider module (4 providers: crossref, openalex, europepmc, pmc)
- `src/providers/crossref.rs` — Crossref search via `/works` API
- `src/providers/pmc.rs` — PMC search + PDF URL resolution
- `src/providers/openalex.rs` — OpenAlex search + download URLs
- `src/providers/europepmc.rs` — EuropePMC search + fulltext XML URLs
- `src/scraper.rs` — Static HTML scraper for pubscholar, cyberleninka, hans_publishers
- `src/py.rs` — PyO3 bindings for `fetch_one`, `fetch_multi`, `scrape_web`
- `Cargo.toml` — Dependencies (pyo3 0.28, pyo3-async-runtimes 0.28, reqwest 0.13, tokio, serde, scraper 0.26, thiserror 2, url, pythonize)
- `pyproject.toml` — Maturin build system config

**Missing provider implementations:**
- `src/providers/unpaywall.rs` — Unpaywall DOI lookup (Task 5)
- `src/providers/doaj.rs` — DOAJ article search (Task 7)
- `src/providers/jstage.rs` — JStage search + PDF candidates (Task 10)

**Missing test coverage:**
- `tests/test_types.rs` — Rust unit tests (Task 13)
- `tests/test_integration.py` — Python integration tests (Task 15)

**Notable deviations from plan:**
- Uses `pyo3-async-runtimes` 0.28 instead of `pyo3-async` 0.22
- Uses `reqwest` 0.13 instead of 0.12
- Uses `scraper` 0.26 instead of 0.22
- Scraper is `src/scraper.rs` (single file) instead of `src/scraper/mod.rs`
- No `async-trait` crate — providers use direct trait impls without `#[async_trait]`
