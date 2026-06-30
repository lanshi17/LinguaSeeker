use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::providers::{
    ArxivProvider, BaseProvider, BioRxivProvider, CiniiProvider, CoreProvider, CrossrefProvider,
    DoajProvider, EuropePmcProvider, JstageProvider, MedRxivProvider, OpenAlexProvider,
    OpenAireProvider, PmcProvider, SciEloProvider, UnpaywallProvider,
};
use crate::types::{Action, FetchParams, FetchResult};
use futures::future::join_all;
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

/// Fan out a literature action to multiple providers concurrently.
///
/// All provider requests are launched in parallel via `join_all`.
/// Per-provider runtime failures (HTTP errors, timeouts) are captured
/// as `FetchResult::failure` objects rather than propagating exceptions,
/// so a single provider failure does not abort the entire batch.
///
/// **Note**: Unknown provider names also produce a `FetchResult::failure`
/// object. Callers should inspect `success` / `warnings` on each result
/// to distinguish "no results" from "provider not recognized".
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
        let tasks = providers.into_iter().map(|provider| {
            let client = client.clone();
            let action = action.clone();
            let params = params.clone();
            async move {
                match execute_provider(&client, &provider, &action, &params).await {
                    Ok(result) => result,
                    Err(err) => FetchResult::failure(&provider, vec![err.to_string()]),
                }
            }
        });
        let results = join_all(tasks).await;
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

#[pyfunction]
#[pyo3(signature = (html, css_selector))]
pub fn scrape_html<'py>(
    py: Python<'py>,
    html: &str,
    css_selector: &str,
) -> PyResult<Bound<'py, PyAny>> {
    let result = crate::scraper::scrape_html(html, css_selector)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
    pythonize::pythonize(py, &result).map_err(PyErr::from)
}

#[pyfunction]
#[pyo3(signature = (html, base_url))]
pub fn extract_pdf_links<'py>(
    py: Python<'py>,
    html: &str,
    base_url: &str,
) -> PyResult<Bound<'py, PyAny>> {
    let links = crate::scraper::extract_pdf_links(html, base_url);
    pythonize::pythonize(py, &links).map_err(PyErr::from)
}

/// Download a file from a URL. Returns Python dict {"bytes": <bytes>, "final_url": <str>, "status_code": <int>}.
#[pyfunction]
#[pyo3(signature = (url, timeout_ms=None, max_retries=None, proxy=None))]
pub fn download_file<'py>(
    py: Python<'py>,
    url: String,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let client = HttpClient::new(timeout_ms, max_retries, proxy.as_deref())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let (bytes, final_url, status_code) = client
            .get_bytes(&url)
            .await
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
        Python::attach(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("bytes", pyo3::types::PyBytes::new(py, &bytes))?;
            dict.set_item("final_url", final_url)?;
            dict.set_item("status_code", status_code)?;
            Ok(dict.into_any().unbind())
        })
    })
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
        ("doaj", Action::Search) => DoajProvider::search(client, params).await,
        ("doaj", Action::Download) => DoajProvider::download_urls(client, params).await,
        ("jstage", Action::Search) => JstageProvider::search(client, params).await,
        ("jstage", Action::Download) => JstageProvider::download_urls(client, params).await,
        ("scielo", Action::Search) => SciEloProvider::search(client, params).await,
        ("base", Action::Search) => BaseProvider::search(client, params).await,
        ("core", Action::Search) => CoreProvider::search(client, params).await,
        ("openaire", Action::Search) => OpenAireProvider::search(client, params).await,
        ("arxiv", Action::Search) => ArxivProvider::search(client, params).await,
        ("biorxiv", Action::Search) => BioRxivProvider::search(client, params).await,
        ("medrxiv", Action::Search) => MedRxivProvider::search(client, params).await,
        ("cinii", Action::Search) => CiniiProvider::search(client, params).await,
        ("unpaywall", Action::Search | Action::Download) => {
            UnpaywallProvider::search(client, params).await
        }
        ("crossref" | "openalex" | "europepmc" | "pmc" | "scielo" | "base" | "core" | "openaire" | "arxiv" | "biorxiv" | "medrxiv" | "cinii", Action::Download) => {
            Err(GatewayError::Other(format!(
                "action {action:?} is not supported for provider {provider}"
            )))
        }
        _ => Err(GatewayError::Provider {
            provider: provider.to_string(),
            message: format!("unknown provider: {provider}"),
        }),
    }

// ── MinerU API functions ──────────────────────────────────────────────

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (url, token, model_version=None, is_ocr=None, enable_formula=None, enable_table=None, language=None, data_id=None, page_ranges=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None))]
pub fn mineru_create_task<'py>(
    py: Python<'py>,
    url: String,
    token: String,
    model_version: Option<String>,
    is_ocr: Option<bool>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    data_id: Option<String>,
    page_ranges: Option<String>,
    no_cache: Option<bool>,
    cache_tolerance: Option<u32>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    // MinerU API: use no-proxy client unless explicitly provided
    let client = match proxy {
        Some(ref p) => HttpClient::new(timeout_ms, None, Some(p))?,
        None => HttpClient::new_no_proxy(timeout_ms, None)?,
    };
    let request = crate::types::MinerUCreateTaskRequest {
        url,
        model_version,
        is_ocr,
        enable_formula,
        enable_table,
        language,
        data_id,
        page_ranges,
        no_cache,
        cache_tolerance,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::create_task(&client, &token, &request)
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
#[pyo3(signature = (task_id, token, timeout_ms=None, proxy=None))]
pub fn mineru_get_result<'py>(
    py: Python<'py>,
    task_id: String,
    token: String,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    // MinerU API: use no-proxy client unless explicitly provided
    let client = match proxy {
        Some(ref p) => HttpClient::new(timeout_ms, None, Some(p))?,
        None => HttpClient::new_no_proxy(timeout_ms, None)?,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::get_result(&client, &token, &task_id)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (files, token, model_version=None, enable_formula=None, enable_table=None, language=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None))]
pub fn mineru_batch_submit<'py>(
    py: Python<'py>,
    files: Vec<Bound<'py, PyDict>>,
    token: String,
    model_version: Option<String>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    no_cache: Option<bool>,
    cache_tolerance: Option<u32>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    // MinerU API: use no-proxy client unless explicitly provided
    let client = match proxy {
        Some(ref p) => HttpClient::new(timeout_ms, None, Some(p))?,
        None => HttpClient::new_no_proxy(timeout_ms, None)?,
    };

    let mut entries = Vec::with_capacity(files.len());
    for file_dict in &files {
        let url = file_dict
            .get_item("url")
            .map_err(py_err)?
            .ok_or_else(|| GatewayError::Other("file entry missing 'url'".into()))
            .and_then(|v| {
                v.extract::<String>()
                    .map_err(|e| GatewayError::Other(e.to_string()))
            })?;
        let data_id = file_dict
            .get_item("data_id")
            .map_err(py_err)?
            .map(|v| v.extract::<String>())
            .transpose()
            .map_err(py_err)?;
        let is_ocr = file_dict
            .get_item("is_ocr")
            .map_err(py_err)?
            .map(|v| v.extract::<bool>())
            .transpose()
            .map_err(py_err)?;
        let page_ranges = file_dict
            .get_item("page_ranges")
            .map_err(py_err)?
            .map(|v| v.extract::<String>())
            .transpose()
            .map_err(py_err)?;
        entries.push(crate::types::MinerUBatchFileEntry {
            url,
            data_id,
            is_ocr,
            page_ranges,
        });
    }

    let request = crate::types::MinerUBatchSubmitRequest {
        files: entries,
        model_version,
        enable_formula,
        enable_table,
        language,
        no_cache,
        cache_tolerance,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::batch_submit(&client, &token, &request)
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
#[pyo3(signature = (batch_id, token, timeout_ms=None, proxy=None))]
pub fn mineru_batch_result<'py>(
    py: Python<'py>,
    batch_id: String,
    token: String,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    // MinerU API: use no-proxy client unless explicitly provided
    let client = match proxy {
        Some(ref p) => HttpClient::new(timeout_ms, None, Some(p))?,
        None => HttpClient::new_no_proxy(timeout_ms, None)?,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::batch_result(&client, &token, &batch_id)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (filename, token, content_type=None, model_version=None, is_ocr=None, enable_formula=None, enable_table=None, language=None, data_id=None, page_ranges=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None))]
pub fn mineru_create_upload_url<'py>(
    py: Python<'py>,
    filename: String,
    token: String,
    content_type: Option<String>,
    model_version: Option<String>,
    is_ocr: Option<bool>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    data_id: Option<String>,
    page_ranges: Option<String>,
    no_cache: Option<bool>,
    cache_tolerance: Option<u32>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;
    let request = crate::types::MinerUUploadUrlRequest {
        filename,
        content_type,
        model_version,
        is_ocr,
        enable_formula,
        enable_table,
        language,
        data_id,
        page_ranges,
        no_cache,
        cache_tolerance,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::create_upload_url(&client, &token, &request)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (files, token, model_version=None, enable_formula=None, enable_table=None, language=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None))]
pub fn mineru_create_batch_upload_urls<'py>(
    py: Python<'py>,
    files: Vec<Bound<'py, PyDict>>,
    token: String,
    model_version: Option<String>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    callback: Option<String>,
    seed: Option<String>,
    extra_formats: Option<Vec<String>>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;

    let mut entries = Vec::with_capacity(files.len());
    for file_dict in &files {
        let name = file_dict
            .get_item("name")
            .map_err(py_err)?
            .ok_or_else(|| GatewayError::Other("file entry missing 'name'".into()))
            .and_then(|v| {
                v.extract::<String>()
                    .map_err(|e| GatewayError::Other(e.to_string()))
            })?;
        let data_id = file_dict
            .get_item("data_id")
            .map_err(py_err)?
            .map(|v| v.extract::<String>())
            .transpose()
            .map_err(py_err)?;
        let is_ocr = file_dict
            .get_item("is_ocr")
            .map_err(py_err)?
            .map(|v| v.extract::<bool>())
            .transpose()
            .map_err(py_err)?;
        let page_ranges = file_dict
            .get_item("page_ranges")
            .map_err(py_err)?
            .map(|v| v.extract::<String>())
            .transpose()
            .map_err(py_err)?;
        entries.push(crate::types::MinerULocalFileEntry {
            name,
            data_id,
            is_ocr,
            page_ranges,
        });
    }

    let request = crate::types::MinerUBatchUploadUrlRequest {
        files: entries,
        model_version,
        enable_formula,
        enable_table,
        language,
        callback,
        seed,
        extra_formats,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::create_batch_upload_urls(&client, &token, &request)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (file_paths, token, model_version=None, enable_formula=None, enable_table=None, language=None, data_ids=None, is_ocr=None, page_ranges=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None))]
pub fn mineru_upload_local_files<'py>(
    py: Python<'py>,
    file_paths: Vec<String>,
    token: String,
    model_version: Option<String>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    data_ids: Option<Vec<String>>,
    is_ocr: Option<bool>,
    page_ranges: Option<String>,
    callback: Option<String>,
    seed: Option<String>,
    extra_formats: Option<Vec<String>>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;
    if let Some(ref ids) = data_ids
        && ids.len() != file_paths.len()
    {
        return Err(PyErr::from(GatewayError::Other(format!(
            "data_ids length {} does not match file_paths length {}",
            ids.len(),
            file_paths.len()
        ))));
    }

    let entries = file_paths
        .iter()
        .enumerate()
        .map(|(idx, path)| {
            let name = std::path::Path::new(path)
                .file_name()
                .and_then(|value| value.to_str())
                .ok_or_else(|| {
                    GatewayError::Other(format!("local file path has no valid filename: {path}"))
                })?
                .to_owned();
            let data_id = data_ids.as_ref().map(|ids| ids[idx].clone());
            Ok(crate::types::MinerULocalFileEntry {
                name,
                data_id,
                is_ocr,
                page_ranges: page_ranges.clone(),
            })
        })
        .collect::<Result<Vec<_>, GatewayError>>()?;

    let request = crate::types::MinerUBatchUploadUrlRequest {
        files: entries,
        model_version,
        enable_formula,
        enable_table,
        language,
        callback,
        seed,
        extra_formats,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::upload_local_files(&client, &token, &request, &file_paths)
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
#[pyo3(signature = (upload_url, file_path, content_type=None, timeout_ms=None, proxy=None))]
pub fn mineru_upload_local_file<'py>(
    py: Python<'py>,
    upload_url: String,
    file_path: String,
    content_type: Option<String>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        crate::mineru::upload_local_file(&client, &upload_url, &file_path, content_type.as_deref())
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &serde_json::json!({"ok": true}))
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}
