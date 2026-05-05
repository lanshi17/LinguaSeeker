use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::providers::{CrossrefProvider, EuropePmcProvider, OpenAlexProvider, PmcProvider};
use crate::types::{Action, FetchParams, FetchResult};
use pyo3::prelude::*;
use pyo3::types::PyDict;

#[pyfunction]
#[pyo3(signature = (provider, action, params, timeout_ms=None, max_retries=None, proxy=None))]
pub fn fetch_one(
    py: Python<'_>,
    provider: String,
    action: &str,
    params: &Bound<'_, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'_, PyAny>> {
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = execute_provider(&client, &provider, &action, &params).await?;
        Python::attach(|py| pythonize::pythonize(py, &result).map(|obj| obj.unbind()))
    })
}

#[pyfunction]
#[pyo3(signature = (providers, action, params, timeout_ms=None, max_retries=None, proxy=None))]
pub fn fetch_multi(
    py: Python<'_>,
    providers: Vec<String>,
    action: &str,
    params: &Bound<'_, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'_, PyAny>> {
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let mut results = Vec::with_capacity(providers.len());
        for provider in providers {
            results.push(execute_provider(&client, &provider, &action, &params).await?);
        }
        Python::attach(|py| pythonize::pythonize(py, &results).map(|obj| obj.unbind()))
    })
}

#[pyfunction]
#[pyo3(signature = (provider, action, params, timeout_ms=None, max_retries=None, proxy=None))]
pub fn scrape_web(
    py: Python<'_>,
    provider: String,
    action: &str,
    params: &Bound<'_, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'_, PyAny>> {
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::scraper::scrape_provider(&client, &provider, &action, &params).await?;
        Python::attach(|py| pythonize::pythonize(py, &result).map(|obj| obj.unbind()))
    })
}

fn parse_action(action: &str) -> Result<Action, GatewayError> {
    match action.to_lowercase().as_str() {
        "search" => Ok(Action::Search),
        "download" => Ok(Action::Download),
        _ => Err(GatewayError::Other(format!(
            "action must be 'search' or 'download', got '{action}'"
        ))),
    }
}

fn parse_params(params: &Bound<'_, PyDict>) -> Result<FetchParams, GatewayError> {
    let query = params
        .get_item("query")?
        .map(|v| v.extract::<String>())
        .transpose()?;

    let limit = params
        .get_item("limit")?
        .map(|v| v.extract::<u32>())
        .transpose()?;

    let raw = params
        .get_item("raw")?
        .map(|v| v.extract::<bool>())
        .transpose()?;

    let selected_index = params
        .get_item("selected_index")?
        .map(|v| v.extract::<u32>())
        .transpose()?;

    let selected_title = params
        .get_item("selected_title")?
        .map(|v| v.extract::<String>())
        .transpose()?;

    let detail_link = params
        .get_item("detail_link")?
        .map(|v| v.extract::<String>())
        .transpose()?;

    Ok(FetchParams {
        query,
        identifiers: None,
        limit,
        raw,
        selected_index,
        selected_title,
        detail_link,
    })
}

async fn execute_provider(
    client: &HttpClient,
    provider: &str,
    action: &Action,
    params: &FetchParams,
) -> Result<FetchResult, GatewayError> {
    if !matches!(action, Action::Search) {
        return Err(GatewayError::Other(format!(
            "action {action:?} is not supported for provider {provider}"
        )));
    }

    let query = params.query.as_deref().unwrap_or_default();
    match provider {
        "crossref" => CrossrefProvider::search(client, query, params.limit).await,
        "openalex" => OpenAlexProvider::search(client, query, params.limit).await,
        "europepmc" => EuropePmcProvider::search(client, query, params.limit).await,
        "pmc" => PmcProvider::search(client, query, params.limit).await,
        _ => Err(GatewayError::Provider {
            provider: provider.to_string(),
            message: format!("unknown provider: {provider}"),
        }),
    }
}
