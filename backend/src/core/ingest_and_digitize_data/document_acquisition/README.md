# Document Acquisition Module

Unified interface for acquiring documents from different sources.

## Overview

The document acquisition module provides a single entry point for:
- **Local Upload**: Upload files from local filesystem
- **Online Acquisition**: Search/download literature from online providers

## Usage

### Basic Usage

```python
from src.core.ingest_and_digitize_data.document_acquisition import (
    DocumentAcquisitionService,
    DocumentAcquisitionRequest,
    AcquisitionSource,
)

service = DocumentAcquisitionService()

# Local upload
request = DocumentAcquisitionRequest(
    source=AcquisitionSource.LOCAL,
    filename="report.pdf",
    content=open("report.pdf", "rb").read(),
    deduplicate=True,
)
result = service.acquire(request)

# Online search
request = DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="search",
    query="ACMG variant classification",
    use_cache=True,
)
result = service.acquire(request)
```

### Advanced Usage

```python
# Online download with specific provider
request = DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="download",
    query="10.1234/test.paper",
    api_provider="unpaywall",
    download_path="./downloads",
    max_retries=3,
    timeout=60,
)
result = service.acquire(request)
```

## API Reference

### DocumentAcquisitionService

#### `acquire(request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult`

Acquire a document from the specified source.

**Parameters:**
- `request`: The acquisition request.

**Returns:**
- `DocumentAcquisitionResult`: The acquisition result.

### DocumentAcquisitionRequest

**Parameters:**
- `source`: The acquisition source (LOCAL or ONLINE).
- `filename`: The filename for local upload.
- `content`: The file content for local upload.
- `deduplicate`: Whether to deduplicate files (default: False).
- `action`: The action for online acquisition (search or download).
- `query`: The search query for online acquisition.
- `use_cache`: Whether to use cache (default: True).
- `max_retries`: The maximum number of retries (default: 3).
- `timeout`: The timeout in seconds (default: 60).

### DocumentAcquisitionResult

**Fields:**
- `success`: Whether the acquisition was successful.
- `source`: The acquisition source.
- `warnings`: A list of warnings.
- `error`: The error message (if any).
- `stored_file`: The stored file (for local upload).
- `deduplicated`: Whether the file was deduplicated.
- `items`: The search results (for online search).
- `downloads`: The download results (for online download).
- `route`: The route information (for online acquisition).
- `cached`: Whether the result was cached.
- `elapsed_time`: The elapsed time in seconds.
- `retries`: The number of retries performed.
