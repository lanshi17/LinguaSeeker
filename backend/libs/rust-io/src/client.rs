use std::time::Duration;

use crate::error::GatewayError;
use reqwest::Client;

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
        query: &serde_json::Value,
    ) -> Result<serde_json::Value, GatewayError> {
        let url = self.build_url(url, query)?;
        let mut response = self.inner.get(url.clone()).send().await?;

        for attempt in 1..=self.max_retries {
            if response.status().is_success() {
                break;
            }

            if attempt == self.max_retries {
                break;
            }

            let backoff = Duration::from_millis(BACKOFF_BASE_MS * (1 << (attempt - 1)));
            tokio::time::sleep(backoff).await;
            response = self.inner.get(url.clone()).send().await?;
        }

        let json = response.error_for_status()?.json().await?;
        Ok(json)
    }

    pub async fn get_text(&self, url: &str) -> Result<String, GatewayError> {
        let text = self
            .inner
            .get(url)
            .send()
            .await?
            .error_for_status()?
            .text()
            .await?;
        Ok(text)
    }

    fn build_url(&self, base: &str, query: &serde_json::Value) -> Result<url::Url, GatewayError> {
        let mut url = url::Url::parse(base)?;
        if let Some(obj) = query.as_object() {
            for (key, value) in obj {
                if let Some(s) = value.as_str() {
                    url.query_pairs_mut().append_pair(key, s);
                } else if let Some(j) = value.as_i64() {
                    url.query_pairs_mut().append_pair(key, &j.to_string());
                } else if let Some(j) = value.as_u64() {
                    url.query_pairs_mut().append_pair(key, &j.to_string());
                }
            }
        }
        Ok(url)
    }
}

impl Default for HttpClient {
    fn default() -> Self {
        Self::new(None, None, None).unwrap()
    }
}
