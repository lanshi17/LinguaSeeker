# MinIO DAO

> MinIO / S3-compatible object storage data access layer. **Currently a placeholder** -- not yet implemented. Planned for binary artifact storage (PDFs, images, parsed outputs).

## Status

This sub-package contains only `__init__.py`. No repository, connection, or configuration code has been implemented yet. No MinIO configuration exists in `src.core.config`.

## Planned Purpose

When implemented, this module will provide:

- Async MinIO client wrapper using `minio` Python SDK
- Upload/download for pipeline artifacts (PDFs, images, parsed markdown)
- Bucket lifecycle management
- SHA-256 content-addressed storage for deduplication

## Current Workaround

File I/O currently uses `files_io` (the `rust_io.files` PyO3 extension) for local and S3-compatible file operations, or direct filesystem access. See `src.utils.rust_io` for the native extension bridge.
