use std::time::Duration;

use crate::error::GatewayError;
use reqwest::Client;

const DEFAULT_TIMEOUT_MS: u64 = 30_000;
const DEFAULT_MAX_RETRIES: u32 = 2;
const BACKOFF_BASE_MS: u64 = 1000;

fn retry_backoff(attempt: u32) -> Duration {
    let shift = attempt.saturating_sub(1).min(20);
    Duration::from_millis(BACKOFF_BASE_MS * (1u64 << shift))
}

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

    /// Create a client that explicitly ignores system proxy settings.
    pub fn new_no_proxy(
        timeout_ms: Option<u64>,
        max_retries: Option<u32>,
    ) -> Result<Self, GatewayError> {
        let timeout = Duration::from_millis(timeout_ms.unwrap_or(DEFAULT_TIMEOUT_MS));
        let builder = Client::builder()
            .timeout(timeout)
            .user_agent("acmg-lingua-io/0.1.0")
            .gzip(true)
            .redirect(reqwest::redirect::Policy::limited(10))
            .no_proxy();

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

            tokio::time::sleep(retry_backoff(attempt)).await;
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

    /// POST JSON with optional Authorization header.
    pub async fn post_json(
        &self,
        url: &str,
        body: &serde_json::Value,
        auth_header: Option<&str>,
    ) -> Result<serde_json::Value, GatewayError> {
        let mut request = self
            .inner
            .post(url)
            .header("Content-Type", "application/json")
            .header("Accept", "*/*");

        if let Some(auth) = auth_header {
            request = request.header("Authorization", auth);
        }

        let response = request.json(body).send().await?;
        let json = response.error_for_status()?.json().await?;
        Ok(json)
    }

    /// PUT bytes with an optional Content-Type header, returning an empty JSON object.
    pub async fn put_bytes(
        &self,
        url: &str,
        bytes: Vec<u8>,
        content_type: Option<&str>,
    ) -> Result<serde_json::Value, GatewayError> {
        let mut request = self.inner.put(url).body(bytes);

        if let Some(value) = content_type {
            request = request.header("Content-Type", value);
        }

        request.send().await?.error_for_status()?;
        Ok(serde_json::json!({}))
    }

    /// GET with optional Authorization header, returning JSON.
    pub async fn get_json_with_auth(
        &self,
        url: &str,
        auth_header: Option<&str>,
    ) -> Result<serde_json::Value, GatewayError> {
        let mut request = self.inner.get(url);

        if let Some(auth) = auth_header {
            request = request.header("Authorization", auth);
        }

        let response = request.send().await?;
        let json = response.error_for_status()?.json().await?;
        Ok(json)
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn retry_backoff_caps_large_attempt_numbers() {
        assert_eq!(retry_backoff(1), Duration::from_millis(BACKOFF_BASE_MS));
        assert_eq!(
            retry_backoff(21),
            Duration::from_millis(BACKOFF_BASE_MS * (1u64 << 20))
        );
        assert_eq!(
            retry_backoff(32),
            Duration::from_millis(BACKOFF_BASE_MS * (1u64 << 20))
        );
    }

    #[test]
    fn build_url_percent_encodes_query_values_once() {
        let client = HttpClient::new(None, None, None).unwrap();
        let doi = "10.1002/(SICI)1097-0258(19980815)17:15<1661::AID-SIM889>3.0.CO;2-2";
        let url = client
            .build_url(
                "https://api.openalex.org/works",
                &serde_json::json!({ "filter": format!("doi:{doi}") }),
            )
            .unwrap();
        let query = url.query().unwrap();

        assert!(query.contains("filter=doi%3A10.1002%2F%28SICI%29"));
        assert!(query.contains("%3C1661%3A%3AAID-SIM889%3E"));
        assert!(!query.contains("%25"));
    }
}
