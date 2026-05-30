# MinIO DAO

> MinIO / S3-compatible object storage data access layer. **Currently a placeholder** — not yet implemented. Planned for binary artifact storage (PDFs, images, parsed outputs).

## Status

This sub-package contains only `__init__.py`. No repository or connection code has been implemented yet.

## Planned Purpose

When implemented, this module will provide:
- Async MinIO client wrapper using `minio` Python SDK
- Upload/download for pipeline artifacts (PDFs, images, parsed markdown)
- Bucket lifecycle management
- SHA-256 content-addressed storage for deduplication

## Configuration

MinIO connection settings are defined in `src.core.config`:

| Env Var | Default | Description |
|---------|---------|-------------|
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO server address |
| `MINIO_ACCESS_KEY` | `""` | Access key |
| `MINIO_SECRET_KEY` | `""` | Secret key |
| `MINIO_BUCKET_NAME` | `acmg-bucket` | Default bucket |
| `MINIO_SECURE` | `false` | Use HTTPS |

Access via `from src.core.config import get_config; cfg = get_config().minio`.

## Current Workaround

File I/O currently uses `rust_io.files` (S3 backend) or direct filesystem access. See `src.utils.rust_io` for the native extension bridge.
