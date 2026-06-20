# Ingest & Digitize Data (Phase 1)

> Phase 1 of the LinguaSeeker pipeline: acquire documents (local upload or online literature search) and parse them into structured markdown via MinerU. Provides a unified facade that routes to the appropriate acquisition source and a parsing service that handles both local and remote MinerU backends.

## Quick Start

```python
from src.core.ingest_and_digitize_data.document_acquisition import (
    DocumentAcquisitionService,
    DocumentAcquisitionRequest,
    AcquisitionSource,
)

service = DocumentAcquisitionService()

# Local upload with dedup
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.LOCAL,
    filename="paper.pdf",
    content=pdf_bytes,
    deduplicate=True,
))

# Online search
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="search",
    query="BRCA1 variant classification",
    limit=10,
))
```

## Architecture

```
ingest_and_digitize_data/
├── document_acquisition/    # Unified acquisition facade
│   ├── service.py           # DocumentAcquisitionService.acquire()
│   ├── contracts.py         # Request/Response models
│   ├── local_upload/        # File upload with SHA-256 dedup
│   └── online_acquisition/  # Multi-provider search + download
│       ├── workflow.py       # Fallback chain orchestration
│       ├── gateway.py        # Rust net_io bridge
│       ├── search_service.py # Multilingual provider routing
│       └── web/              # JS-rendered site scrapers
│
└── parse_document/          # Document parsing via MinerU
    ├── service.py           # ParseDocumentService
    ├── orchestrator.py      # Remote/local parser selection
    ├── common/              # Shared parsing utilities
    ├── local/               # MinerU local VLM parsing
    └── remote/              # MinerU cloud API parsing
```

**Data flow:**

```
User input (file bytes or search query)
  │
  ▼
DocumentAcquisitionService.acquire()
  ├── LOCAL  → local_upload/ → SHA-256 dedup → disk write
  └── ONLINE → online_acquisition/ → provider chain → PDF download
  │
  ▼
ParseDocumentService.parse_local_files_and_save()
  ├── remote → MinerURemoteParser (cloud API)
  └── local  → MinerULocalParser (model server :8001)
  │
  ▼
Output: {md_path, metadata_path, images_dir}
```

## Sub-module Reference

- **[document_acquisition/](./document_acquisition/README.md)** — Unified acquisition facade, multi-provider search, download fallback chains, web scrapers
- **[parse_document/](./parse_document/README.md)** — MinerU document parsing (local VLM + remote API), output normalization

## Testing

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/ -v
```
