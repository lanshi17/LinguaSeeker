use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::providers::{
    CrossrefProvider, DoajProvider, EuropePmcProvider, JstageProvider, OpenAlexProvider,
    PmcProvider, UnpaywallProvider,
};
use crate::types::{Action, FetchParams, FetchResult};
use pyo3::prelude::*;
use pyo3::types::PyDict;

#[pyfunction]
#[pyo3(signature = (provider, action, params, timeout_ms=None, max_retries=None, proxy=None))]
pub fn fetch_one<'py>(
    py: Python<'py>,
    provider: String,
    action: &str,
    params: &Bound<'py, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = execute_provider(&client, &provider, &action, &params)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[pyfunction]
#[pyo3(signature = (providers, action, params, timeout_ms=None, max_retries=None, proxy=None))]
pub fn fetch_multi<'py>(
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

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let mut results = Vec::with_capacity(providers.len());
        for provider in providers {
            results.push(
                execute_provider(&client, &provider, &action, &params)
                    .await
                    .map_err(PyErr::from)?,
            );
        }
        Python::attach(|py| {
            pythonize::pythonize(py, &results)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[pyfunction]
#[pyo3(signature = (provider, action, params, timeout_ms=None, max_retries=None, proxy=None))]
pub fn scrape_web<'py>(
    py: Python<'py>,
    provider: String,
    action: &str,
    params: &Bound<'py, PyDict>,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let action = parse_action(action)?;
    let params = parse_params(params)?;
    let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::scraper::scrape_provider(&client, &provider, &action, &params)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
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

fn py_err(e: PyErr) -> GatewayError {
    GatewayError::Other(e.to_string())
}

fn parse_params(params: &Bound<'_, PyDict>) -> Result<FetchParams, GatewayError> {
    let query = params
        .get_item("query")
        .map_err(py_err)?
        .map(|v| v.extract::<String>())
        .transpose()
        .map_err(py_err)?;

    let limit = params
        .get_item("limit")
        .map_err(py_err)?
        .map(|v| v.extract::<u32>())
        .transpose()
        .map_err(py_err)?;

    let raw = params
        .get_item("raw")
        .map_err(py_err)?
        .map(|v| v.extract::<bool>())
        .transpose()
        .map_err(py_err)?;

    let selected_index = params
        .get_item("selected_index")
        .map_err(py_err)?
        .map(|v| v.extract::<u32>())
        .transpose()
        .map_err(py_err)?;

    let selected_title = params
        .get_item("selected_title")
        .map_err(py_err)?
        .map(|v| v.extract::<String>())
        .transpose()
        .map_err(py_err)?;

    let detail_link = params
        .get_item("detail_link")
        .map_err(py_err)?
        .map(|v| v.extract::<String>())
        .transpose()
        .map_err(py_err)?;

    let identifiers = params
        .get_item("identifiers")
        .map_err(py_err)?
        .map(|value| {
            let dict = value
                .cast::<PyDict>()
                .map_err(|e| GatewayError::Other(e.to_string()))?;
            let doi = dict
                .get_item("doi")
                .map_err(py_err)?
                .map(|v| v.extract::<String>())
                .transpose()
                .map_err(py_err)?;
            let pmid = dict
                .get_item("pmid")
                .map_err(py_err)?
                .map(|v| v.extract::<String>())
                .transpose()
                .map_err(py_err)?;
            let pmcid = dict
                .get_item("pmcid")
                .map_err(py_err)?
                .map(|v| v.extract::<String>())
                .transpose()
                .map_err(py_err)?;
            let issn = dict
                .get_item("issn")
                .map_err(py_err)?
                .map(|v| v.extract::<String>())
                .transpose()
                .map_err(py_err)?;
            Ok(crate::types::Identifiers {
                doi,
                pmid,
                pmcid,
                issn,
            })
        })
        .transpose()
        .map_err(py_err)?;

    Ok(FetchParams {
        query,
        identifiers,
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
    match (provider, action) {
        ("crossref", Action::Search) => CrossrefProvider::search(client, params).await,
        ("openalex", Action::Search) => OpenAlexProvider::search(client, params).await,
        ("europepmc", Action::Search) => EuropePmcProvider::search(client, params).await,
        ("pmc", Action::Search) => PmcProvider::search(client, params).await,
        ("doaj", Action::Search) => {
            let query = params.query.as_deref().unwrap_or_default();
            DoajProvider::search(client, query, params.limit).await
        }
        ("doaj", Action::Download) => DoajProvider::download_urls(client, params).await,
        ("jstage", Action::Search) => {
            let query = params.query.as_deref().unwrap_or_default();
            JstageProvider::search(client, query, params.limit).await
        }
        ("jstage", Action::Download) => JstageProvider::download_urls(client, params).await,
        ("unpaywall", Action::Search | Action::Download) => {
            UnpaywallProvider::search(client, params).await
        }
        ("crossref" | "openalex" | "europepmc" | "pmc", Action::Download) => {
            Err(GatewayError::Other(format!(
                "action {action:?} is not supported for provider {provider}"
            )))
        }
        _ => Err(GatewayError::Provider {
            provider: provider.to_string(),
            message: format!("unknown provider: {provider}"),
        }),
    }
}
