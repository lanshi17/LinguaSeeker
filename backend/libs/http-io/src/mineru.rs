use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{MinerUBatchSubmitRequest, MinerUCreateTaskRequest};
use serde_json::Value;

const MINERU_BASE_URL: &str = "https://mineru.net/api/v4";

fn auth_header(token: &str) -> String {
    format!("Bearer {token}")
}

/// Create a single document parsing task.
/// POST /extract/task
pub async fn create_task(
    client: &HttpClient,
    token: &str,
    request: &MinerUCreateTaskRequest,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract/task");
    let body = build_create_task_body(request);
    post_json_with_auth(client, &url, token, &body).await
}

/// Get single task result.
/// GET /extract/task/{task_id}
pub async fn get_result(
    client: &HttpClient,
    token: &str,
    task_id: &str,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract/task/{task_id}");
    get_with_auth(client, &url, token).await
}

/// Submit batch URL-based parsing tasks.
/// POST /extract/task/batch
pub async fn batch_submit(
    client: &HttpClient,
    token: &str,
    request: &MinerUBatchSubmitRequest,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract/task/batch");
    let body = build_batch_submit_body(request);
    post_json_with_auth(client, &url, token, &body).await
}

/// Get batch results.
/// GET /extract-results/batch/{batch_id}
pub async fn batch_result(
    client: &HttpClient,
    token: &str,
    batch_id: &str,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract-results/batch/{batch_id}");
    get_with_auth(client, &url, token).await
}

fn build_create_task_body(request: &MinerUCreateTaskRequest) -> Value {
    let mut body = serde_json::json!({ "url": request.url });
    if let Some(ref v) = request.model_version {
        body["model_version"] = Value::String(v.clone());
    }
    if let Some(v) = request.is_ocr {
        body["is_ocr"] = Value::Bool(v);
    }
    if let Some(v) = request.enable_formula {
        body["enable_formula"] = Value::Bool(v);
    }
    if let Some(v) = request.enable_table {
        body["enable_table"] = Value::Bool(v);
    }
    if let Some(ref v) = request.language {
        body["language"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.data_id {
        body["data_id"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.page_ranges {
        body["page_ranges"] = Value::String(v.clone());
    }
    if let Some(v) = request.no_cache {
        body["no_cache"] = Value::Bool(v);
    }
    if let Some(v) = request.cache_tolerance {
        body["cache_tolerance"] = Value::from(v);
    }
    body
}

fn build_batch_submit_body(request: &MinerUBatchSubmitRequest) -> Value {
    let files: Vec<Value> = request
        .files
        .iter()
        .map(|f| {
            let mut entry = serde_json::json!({ "url": f.url });
            if let Some(ref v) = f.data_id {
                entry["data_id"] = Value::String(v.clone());
            }
            if let Some(v) = f.is_ocr {
                entry["is_ocr"] = Value::Bool(v);
            }
            if let Some(ref v) = f.page_ranges {
                entry["page_ranges"] = Value::String(v.clone());
            }
            entry
        })
        .collect();

    let mut body = serde_json::json!({ "files": files });
    if let Some(ref v) = request.model_version {
        body["model_version"] = Value::String(v.clone());
    }
    if let Some(v) = request.enable_formula {
        body["enable_formula"] = Value::Bool(v);
    }
    if let Some(v) = request.enable_table {
        body["enable_table"] = Value::Bool(v);
    }
    if let Some(ref v) = request.language {
        body["language"] = Value::String(v.clone());
    }
    if let Some(v) = request.no_cache {
        body["no_cache"] = Value::Bool(v);
    }
    if let Some(v) = request.cache_tolerance {
        body["cache_tolerance"] = Value::from(v);
    }
    body
}

async fn post_json_with_auth(
    client: &HttpClient,
    url: &str,
    token: &str,
    body: &Value,
) -> Result<Value, GatewayError> {
    client.post_json(url, body, Some(&auth_header(token))).await
}

async fn get_with_auth(
    client: &HttpClient,
    url: &str,
    token: &str,
) -> Result<Value, GatewayError> {
    client.get_json_with_auth(url, Some(&auth_header(token))).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::MinerUBatchFileEntry;

    #[test]
    fn test_build_create_task_body_defaults() {
        let req = MinerUCreateTaskRequest {
            url: "https://example.com/test.pdf".into(),
            model_version: None,
            is_ocr: None,
            enable_formula: None,
            enable_table: None,
            language: None,
            data_id: None,
            page_ranges: None,
            no_cache: None,
            cache_tolerance: None,
        };
        let body = build_create_task_body(&req);
        assert_eq!(body["url"], "https://example.com/test.pdf");
        assert!(body.get("model_version").is_none());
        assert!(body.get("is_ocr").is_none());
    }

    #[test]
    fn test_build_create_task_body_full() {
        let req = MinerUCreateTaskRequest {
            url: "https://example.com/test.pdf".into(),
            model_version: Some("vlm".into()),
            is_ocr: Some(true),
            enable_formula: Some(true),
            enable_table: Some(false),
            language: Some("en".into()),
            data_id: Some("abc-123".into()),
            page_ranges: Some("1-10".into()),
            no_cache: Some(true),
            cache_tolerance: Some(600),
        };
        let body = build_create_task_body(&req);
        assert_eq!(body["model_version"], "vlm");
        assert_eq!(body["is_ocr"], true);
        assert_eq!(body["enable_formula"], true);
        assert_eq!(body["enable_table"], false);
        assert_eq!(body["language"], "en");
        assert_eq!(body["data_id"], "abc-123");
        assert_eq!(body["page_ranges"], "1-10");
        assert_eq!(body["no_cache"], true);
        assert_eq!(body["cache_tolerance"], 600);
    }

    #[test]
    fn test_build_batch_submit_body() {
        let req = MinerUBatchSubmitRequest {
            files: vec![
                MinerUBatchFileEntry {
                    url: "https://example.com/a.pdf".into(),
                    data_id: Some("a".into()),
                    is_ocr: None,
                    page_ranges: None,
                },
                MinerUBatchFileEntry {
                    url: "https://example.com/b.pdf".into(),
                    data_id: None,
                    is_ocr: Some(true),
                    page_ranges: Some("1-5".into()),
                },
            ],
            model_version: Some("pipeline".into()),
            enable_formula: None,
            enable_table: None,
            language: None,
            no_cache: None,
            cache_tolerance: None,
        };
        let body = build_batch_submit_body(&req);
        let files = body["files"].as_array().unwrap();
        assert_eq!(files.len(), 2);
        assert_eq!(files[0]["url"], "https://example.com/a.pdf");
        assert_eq!(files[0]["data_id"], "a");
        assert_eq!(files[1]["is_ocr"], true);
        assert_eq!(files[1]["page_ranges"], "1-5");
        assert_eq!(body["model_version"], "pipeline");
    }

    #[test]
    fn test_create_task_body_html_model() {
        let req = MinerUCreateTaskRequest {
            url: "https://example.com/page.html".into(),
            model_version: Some("MinerU-HTML".into()),
            is_ocr: None,
            enable_formula: None,
            enable_table: None,
            language: None,
            data_id: None,
            page_ranges: None,
            no_cache: None,
            cache_tolerance: None,
        };
        let body = build_create_task_body(&req);
        assert_eq!(body["model_version"], "MinerU-HTML");
    }
}
