use super::{FileMetadata, FileOps};
use crate::error::FileError;
use aws_credential_types::provider::SharedCredentialsProvider;
use aws_sdk_s3::Client;
use aws_sdk_s3::config::{Credentials, Region};
use aws_sdk_s3::error::SdkError;
use std::collections::HashMap;
use std::io::Read;
use std::sync::OnceLock;
use tokio::runtime::Runtime;

/// Shared tokio runtime for sync FileOps methods that bridge into async AWS calls.
static S3_RT: OnceLock<Runtime> = OnceLock::new();

fn get_runtime() -> &'static Runtime {
    S3_RT.get_or_init(|| Runtime::new().expect("failed to create tokio runtime for S3"))
}

#[derive(Clone)]
pub struct S3Backend {
    client: Client,
}

fn parse_s3_path(path: &str) -> Result<(&str, &str), FileError> {
    let stripped = path
        .strip_prefix("s3://")
        .ok_or_else(|| FileError::Path(format!("not an S3 path: {path}")))?;
    let slash = stripped
        .find('/')
        .ok_or_else(|| FileError::Path(format!("S3 path missing key: {path}")))?;
    Ok((&stripped[..slash], &stripped[slash + 1..]))
}

impl S3Backend {
    pub fn new(
        access_key: &str,
        secret_key: &str,
        endpoint: Option<&str>,
        region: Option<&str>,
    ) -> Result<Self, FileError> {
        let credentials = Credentials::new(access_key, secret_key, None, None, "files-io");
        let mut config_builder = aws_config::SdkConfig::builder()
            .credentials_provider(SharedCredentialsProvider::new(credentials))
            .region(Region::new(region.unwrap_or("us-east-1").to_string()));
        if let Some(ep) = endpoint {
            config_builder = config_builder.endpoint_url(ep);
        }
        let config = config_builder.build();
        let client = Client::new(&config);
        Ok(Self { client })
    }

    fn rt(&self) -> &'static Runtime {
        get_runtime()
    }
}

/// Check if an S3 error is a 404 (not found).
fn is_not_found(err: &SdkError<aws_sdk_s3::operation::head_object::HeadObjectError>) -> bool {
    match err {
        SdkError::ServiceError(e) => {
            matches!(
                e.err(),
                aws_sdk_s3::operation::head_object::HeadObjectError::NotFound(_)
            )
        }
        _ => false,
    }
}

impl FileOps for S3Backend {
    fn read_all(&self, path: &str) -> Result<Vec<u8>, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let resp = self
            .rt()
            .block_on(self.client.get_object().bucket(bucket).key(key).send())
            .map_err(|e| FileError::S3(e.to_string()))?;
        let bytes = self
            .rt()
            .block_on(resp.body.collect())
            .map_err(|e| FileError::S3(e.to_string()))?;
        Ok(bytes.to_vec())
    }

    fn read_chunk(&self, path: &str, offset: u64, size: u64) -> Result<Vec<u8>, FileError> {
        if size == 0 {
            return Ok(Vec::new());
        }
        let (bucket, key) = parse_s3_path(path)?;
        let end = offset
            .checked_add(size - 1)
            .ok_or_else(|| FileError::Path("read_chunk range overflow".into()))?;
        let range = format!("bytes={offset}-{end}");
        let resp = self
            .rt()
            .block_on(
                self.client
                    .get_object()
                    .bucket(bucket)
                    .key(key)
                    .range(range)
                    .send(),
            )
            .map_err(|e| FileError::S3(e.to_string()))?;
        let bytes = self
            .rt()
            .block_on(resp.body.collect())
            .map_err(|e| FileError::S3(e.to_string()))?;
        Ok(bytes.to_vec())
    }

    fn write(&self, path: &str, data: &[u8], _create_parents: bool) -> Result<(), FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let body = aws_sdk_s3::primitives::ByteStream::from(data.to_vec());
        self.rt()
            .block_on(
                self.client
                    .put_object()
                    .bucket(bucket)
                    .key(key)
                    .body(body)
                    .send(),
            )
            .map_err(|e| FileError::S3(e.to_string()))?;
        Ok(())
    }

    fn write_stream(
        &self,
        path: &str,
        reader: &mut dyn Read,
        _create_parents: bool,
    ) -> Result<(), FileError> {
        let mut data = Vec::new();
        reader.read_to_end(&mut data)?;
        self.write(path, &data, false)
    }

    fn exists(&self, path: &str) -> Result<bool, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let result = self
            .rt()
            .block_on(self.client.head_object().bucket(bucket).key(key).send());
        match result {
            Ok(_) => Ok(true),
            Err(e) => {
                if is_not_found(&e) {
                    return Ok(false);
                }
                Err(FileError::S3(e.to_string()))
            }
        }
    }

    fn metadata(&self, path: &str) -> Result<FileMetadata, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let resp = self
            .rt()
            .block_on(self.client.head_object().bucket(bucket).key(key).send())
            .map_err(|e| FileError::S3(e.to_string()))?;
        let size = resp.content_length().unwrap_or(0) as u64;
        let mtime = resp.last_modified().map(|t| t.secs() as f64).unwrap_or(0.0);
        let mut extra = HashMap::new();
        if let Some(etag) = resp.e_tag() {
            extra.insert("etag".to_string(), etag.to_string());
        }
        if let Some(ct) = resp.content_type() {
            extra.insert("content_type".to_string(), ct.to_string());
        }
        if let Some(storage) = resp.storage_class().map(|s| s.as_str()) {
            extra.insert("storage_class".to_string(), storage.to_string());
        }
        Ok(FileMetadata {
            size,
            mtime,
            is_file: true,
            is_dir: false,
            is_symlink: false,
            permissions: String::new(),
            extra,
        })
    }

    fn rename(&self, src: &str, dst: &str) -> Result<(), FileError> {
        self.copy(src, dst)?;
        if let Err(e) = self.remove(src) {
            // Attempt to clean up the copied destination on failure.
            let _ = self.remove(dst);
            return Err(e);
        }
        Ok(())
    }

    fn copy(&self, src: &str, dst: &str) -> Result<(), FileError> {
        let (src_bucket, src_key) = parse_s3_path(src)?;
        let (dst_bucket, dst_key) = parse_s3_path(dst)?;
        let copy_source = format!("{src_bucket}/{src_key}");
        self.rt()
            .block_on(
                self.client
                    .copy_object()
                    .bucket(dst_bucket)
                    .key(dst_key)
                    .copy_source(&copy_source)
                    .send(),
            )
            .map_err(|e| FileError::S3(e.to_string()))?;
        Ok(())
    }

    fn remove(&self, path: &str) -> Result<(), FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        self.rt()
            .block_on(self.client.delete_object().bucket(bucket).key(key).send())
            .map_err(|e| FileError::S3(e.to_string()))?;
        Ok(())
    }

    fn remove_dir_all(&self, path: &str) -> Result<(), FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let prefix = if key.ends_with('/') {
            key.to_string()
        } else {
            format!("{key}/")
        };
        let mut continuation_token: Option<String> = None;

        loop {
            let mut req = self.client.list_objects_v2().bucket(bucket).prefix(&prefix);
            if let Some(token) = &continuation_token {
                req = req.continuation_token(token);
            }
            let resp = self
                .rt()
                .block_on(req.send())
                .map_err(|e| FileError::S3(e.to_string()))?;

            for obj in resp.contents() {
                if let Some(k) = obj.key() {
                    self.rt()
                        .block_on(self.client.delete_object().bucket(bucket).key(k).send())
                        .map_err(|e| FileError::S3(e.to_string()))?;
                }
            }

            if resp.is_truncated().unwrap_or(false) {
                continuation_token = resp.next_continuation_token().map(|s| s.to_string());
            } else {
                break;
            }
        }
        Ok(())
    }

    fn list_dir(&self, path: &str) -> Result<Vec<String>, FileError> {
        let (bucket, key) = parse_s3_path(path)?;
        let prefix = if key.ends_with('/') {
            key.to_string()
        } else {
            format!("{key}/")
        };
        let mut entries = Vec::new();
        let mut continuation_token: Option<String> = None;

        loop {
            let mut req = self
                .client
                .list_objects_v2()
                .bucket(bucket)
                .prefix(&prefix)
                .delimiter("/");
            if let Some(token) = &continuation_token {
                req = req.continuation_token(token);
            }
            let resp = self
                .rt()
                .block_on(req.send())
                .map_err(|e| FileError::S3(e.to_string()))?;

            for cp in resp.common_prefixes() {
                if let Some(p) = cp.prefix() {
                    let name = p.strip_prefix(&prefix).unwrap_or(p);
                    entries.push(name.to_string());
                }
            }
            for obj in resp.contents() {
                if let Some(k) = obj.key() {
                    let name = k.strip_prefix(&prefix).unwrap_or(k);
                    if !name.is_empty() {
                        entries.push(name.to_string());
                    }
                }
            }

            if resp.is_truncated().unwrap_or(false) {
                continuation_token = resp.next_continuation_token().map(|s| s.to_string());
            } else {
                break;
            }
        }
        Ok(entries)
    }

    fn ensure_dir(&self, _path: &str) -> Result<(), FileError> {
        Ok(())
    }
}
