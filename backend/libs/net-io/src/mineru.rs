use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{
    MinerUBatchSubmitRequest, MinerUBatchUploadUrlRequest, MinerUCreateTaskRequest,
    MinerULocalFileEntry, MinerUUploadUrlRequest,
};
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

/// Get a pre-signed local file upload URL.
/// POST /file-urls/batch
pub async fn create_upload_url(
    client: &HttpClient,
    token: &str,
    request: &MinerUUploadUrlRequest,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/file-urls/batch");
    let body = build_upload_url_body(request);
    post_json_with_auth(client, &url, token, &body).await
}

/// Get pre-signed upload URLs for local files. Uploaded files are auto-submitted by MinerU.
/// POST /file-urls/batch
pub async fn create_batch_upload_urls(
    client: &HttpClient,
    token: &str,
    request: &MinerUBatchUploadUrlRequest,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/file-urls/batch");
    let body = build_batch_upload_url_body(request);
    post_json_with_auth(client, &url, token, &body).await
}

/// Create upload URLs and upload local files. MinerU auto-submits parsing after upload.
pub async fn upload_local_files(
    client: &HttpClient,
    token: &str,
    request: &MinerUBatchUploadUrlRequest,
    file_paths: &[String],
) -> Result<Value, GatewayError> {
    let response = create_batch_upload_urls(client, token, request).await?;
    let urls = response
        .get("data")
        .and_then(|data| data.get("file_urls"))
        .and_then(|value| value.as_array())
        .ok_or_else(|| {
            GatewayError::Other("MinerU upload URL response missing data.file_urls".into())
        })?;

    if urls.len() != file_paths.len() {
        return Err(GatewayError::Other(format!(
            "MinerU returned {} upload URLs for {} local files",
            urls.len(),
            file_paths.len()
        )));
    }

    for (url, file_path) in urls.iter().zip(file_paths) {
        let upload_url = url
            .as_str()
            .ok_or_else(|| GatewayError::Other("MinerU upload URL is not a string".into()))?;
        upload_local_file(client, upload_url, file_path, None).await?;
    }

    Ok(response)
}

/// Upload local file bytes to a pre-signed URL.
pub async fn upload_local_file(
    client: &HttpClient,
    upload_url: &str,
    file_path: &str,
    content_type: Option<&str>,
) -> Result<Value, GatewayError> {
    let bytes = std::fs::read(file_path)?;
    client.put_bytes(upload_url, bytes, content_type).await
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

fn build_upload_url_body(request: &MinerUUploadUrlRequest) -> Value {
    let file = build_upload_file_entry(request);
    let mut body = serde_json::json!({ "files": [file] });
    apply_common_task_options(&mut body, request);
    body
}

fn build_batch_upload_url_body(request: &MinerUBatchUploadUrlRequest) -> Value {
    let files: Vec<Value> = request.files.iter().map(build_local_file_entry).collect();
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
    if let Some(ref v) = request.callback {
        body["callback"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.seed {
        body["seed"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.extra_formats {
        body["extra_formats"] = serde_json::json!(v);
    }
    body
}

fn build_local_file_entry(file: &MinerULocalFileEntry) -> Value {
    let mut entry = serde_json::json!({ "name": file.name });
    if let Some(ref v) = file.data_id {
        entry["data_id"] = Value::String(v.clone());
    }
    if let Some(v) = file.is_ocr {
        entry["is_ocr"] = Value::Bool(v);
    }
    if let Some(ref v) = file.page_ranges {
        entry["page_ranges"] = Value::String(v.clone());
    }
    entry
}

fn build_upload_file_entry(request: &MinerUUploadUrlRequest) -> Value {
    let mut file = serde_json::json!({ "name": request.filename });
    if let Some(ref v) = request.content_type {
        file["content_type"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.data_id {
        file["data_id"] = Value::String(v.clone());
    }
    if let Some(v) = request.is_ocr {
        file["is_ocr"] = Value::Bool(v);
    }
    if let Some(ref v) = request.page_ranges {
        file["page_ranges"] = Value::String(v.clone());
    }
    file
}

fn apply_common_task_options(body: &mut Value, request: &MinerUUploadUrlRequest) {
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

async fn get_with_auth(client: &HttpClient, url: &str, token: &str) -> Result<Value, GatewayError> {
    client
        .get_json_with_auth(url, Some(&auth_header(token)))
        .await
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
    fn test_build_upload_url_body() {
        let req = MinerUUploadUrlRequest {
            filename: "paper.pdf".into(),
            content_type: Some("application/pdf".into()),
            model_version: Some("vlm".into()),
            is_ocr: Some(true),
            enable_formula: Some(true),
            enable_table: Some(false),
            language: Some("en".into()),
            data_id: Some("paper-1".into()),
            page_ranges: Some("1-3".into()),
            no_cache: Some(true),
            cache_tolerance: Some(600),
        };
        let body = build_upload_url_body(&req);
        let files = body["files"].as_array().unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0]["name"], "paper.pdf");
        assert_eq!(files[0]["content_type"], "application/pdf");
        assert_eq!(files[0]["data_id"], "paper-1");
        assert_eq!(files[0]["is_ocr"], true);
        assert_eq!(files[0]["page_ranges"], "1-3");
        assert_eq!(body["model_version"], "vlm");
        assert_eq!(body["enable_formula"], true);
        assert_eq!(body["enable_table"], false);
        assert_eq!(body["language"], "en");
        assert_eq!(body["no_cache"], true);
        assert_eq!(body["cache_tolerance"], 600);
    }

    #[test]
    fn test_build_batch_upload_url_body() {
        let req = MinerUBatchUploadUrlRequest {
            files: vec![
                MinerULocalFileEntry {
                    name: "paper.pdf".into(),
                    data_id: Some("paper-1".into()),
                    is_ocr: None,
                    page_ranges: None,
                },
                MinerULocalFileEntry {
                    name: "table.xlsx".into(),
                    data_id: None,
                    is_ocr: Some(true),
                    page_ranges: Some("1-2".into()),
                },
            ],
            model_version: Some("vlm".into()),
            enable_formula: Some(true),
            enable_table: Some(false),
            language: Some("en".into()),
            callback: Some("https://example.com/callback".into()),
            seed: Some("seed_1".into()),
            extra_formats: Some(vec!["docx".into(), "html".into()]),
        };
        let body = build_batch_upload_url_body(&req);
        let files = body["files"].as_array().unwrap();
        assert_eq!(files.len(), 2);
        assert_eq!(files[0]["name"], "paper.pdf");
        assert_eq!(files[0]["data_id"], "paper-1");
        assert!(files[0].get("is_ocr").is_none());
        assert_eq!(files[1]["name"], "table.xlsx");
        assert_eq!(files[1]["is_ocr"], true);
        assert_eq!(files[1]["page_ranges"], "1-2");
        assert_eq!(body["model_version"], "vlm");
        assert_eq!(body["enable_formula"], true);
        assert_eq!(body["enable_table"], false);
        assert_eq!(body["language"], "en");
        assert_eq!(body["callback"], "https://example.com/callback");
        assert_eq!(body["seed"], "seed_1");
        assert_eq!(body["extra_formats"], serde_json::json!(["docx", "html"]));
    }

    #[test]
    fn test_build_batch_upload_url_body_omits_unset_options() {
        let req = MinerUBatchUploadUrlRequest {
            files: vec![MinerULocalFileEntry {
                name: "demo.html".into(),
                data_id: None,
                is_ocr: None,
                page_ranges: None,
            }],
            model_version: Some("MinerU-HTML".into()),
            enable_formula: None,
            enable_table: None,
            language: None,
            callback: None,
            seed: None,
            extra_formats: None,
        };
        let body = build_batch_upload_url_body(&req);
        assert_eq!(body["files"][0]["name"], "demo.html");
        assert_eq!(body["model_version"], "MinerU-HTML");
        assert!(body.get("enable_formula").is_none());
        assert!(body.get("callback").is_none());
        assert!(body.get("extra_formats").is_none());
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
