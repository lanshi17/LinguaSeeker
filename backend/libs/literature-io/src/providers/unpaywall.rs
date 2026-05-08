use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct UnpaywallProvider;

impl UnpaywallProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let Some(doi) = params
            .identifiers
            .as_ref()
            .and_then(|identifiers| identifiers.doi.as_deref())
        else {
            return Ok(FetchResult::failure(
                "unpaywall",
                vec!["unpaywall_requires_doi".into()],
            ));
        };

        let Ok(email) = std::env::var("UNPAYWALL_EMAIL") else {
            return Ok(FetchResult::failure(
                "unpaywall",
                vec!["unpaywall_requires_email".into()],
            ));
        };
        let url = format!("https://api.unpaywall.org/v2/{}", urlencoding::encode(doi));
        let params = serde_json::json!({ "email": email });
        let json = client.get_json(&url, &params).await?;

        let pdf_url = json
            .get("best_oa_location")
            .and_then(|location| location.get("url_for_pdf"))
            .and_then(|value| value.as_str())
            .or_else(|| {
                json.get("best_oa_location")
                    .and_then(|location| location.get("url"))
                    .and_then(|value| value.as_str())
            });

        let downloads = pdf_url
            .map(|url| vec![serde_json::json!({ "pdf_url": url })])
            .unwrap_or_default();
        let warnings = if pdf_url.is_some() {
            vec![]
        } else {
            vec!["no_oa_location".into()]
        };

        Ok(FetchResult {
            provider: "unpaywall".into(),
            success: true,
            items: vec![json.clone()],
            downloads,
            warnings,
            raw: Some(json),
            meta: None,
        })
    }
}
