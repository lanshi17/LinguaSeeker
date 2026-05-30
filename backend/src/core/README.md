# Core

> Vertical feature slices for the ACMG Lingua backend. Each sub-package owns a complete business loop for one pipeline phase — from orchestrator-facing API through pure business logic to LLM/DB/external service providers.

## Package Map

```
src/core/
├── config.py                                    # Singleton Settings (pydantic-settings)
├── ingest_and_digitize_data/                    # Phase 1: document acquisition + parsing
├── cross_lingual_process_and_extract_evidence/  # Phase 2: translation + evidence extraction
├── standardize_entities_and_align_knowledge/    # Phase 3: entity standardization
└── visualize_evidence_with_expert_in_loop/      # Phase 4: expert review + feedback
```

## Architecture

Each feature slice follows the vertical slice pattern:

```
core/<feature>/
├── api.py           # Orchestrator-facing entry point (service class)
├── core.py          # Pure business logic (no I/O)
├── providers.py     # LLM/DB/external service wrappers
├── contracts.py     # Typed data contracts (Pydantic BaseModel / dataclass)
└── README.md        # Developer guide
```

**Design rules:**
- Orchestrator adapters call `api.py` only — never import `core.py` or `providers.py` directly.
- `core.py` is pure: no network, no filesystem, no LLM calls. Testable with mocks.
- `providers.py` wraps all external I/O. Retries and error handling live here.
- `contracts.py` defines the typed boundary between slices. No bare `dict` returns.

## Quick Start

```python
from src.core.config import get_config

cfg = get_config()

# Access nested config domains
cfg.llm.api_key                 # LLM credentials
cfg.postgresql.host             # DB host
cfg.evidence_extraction.model   # Evidence extraction model
```

## Phase Overview

| Phase | Package | Entry Point | Description |
|-------|---------|-------------|-------------|
| 1 | `ingest_and_digitize_data/` | `DocumentAcquisitionService`, `ParseDocumentService` | Acquire PDFs (local upload or online search), parse via MinerU |
| 2 | `cross_lingual_process_and_extract_evidence/` | `TranslationService`, `EvidenceExtractionService` | Translate non-English docs, extract dual-track evidence |
| 3 | `standardize_entities_and_align_knowledge/` | `EntityStandardizationService` | Standardize entities against terminology DBs (HGNC, HPO, OMIM) |
| 4 | `visualize_evidence_with_expert_in_loop/` | `FeedbackService`, `ChatService`, `SourceLinker` | Expert review, feedback, conversational Q&A, audit trail |

## Configuration

All config is loaded from `.env.local` / `.env` via `src.core.config.Settings`. Nested domain models (`cfg.llm`, `cfg.postgresql`, etc.) are built from flat env vars by a `model_validator`.

| Env Prefix | Domain Model | Description |
|------------|-------------|-------------|
| `FAST_LLM_*` / `LLM_*` | `cfg.llm` | Default LLM (OpenAI-compatible) |
| `REASONING_LLM_*` | `cfg.reasoning` | High-accuracy reasoning model |
| `MULTIMODAL_LLM_*` | `cfg.multimodal_llm` | Vision/multimodal model |
| `EVIDENCE_EXTRACTION_*` | `cfg.evidence_extraction` | Evidence extraction models (fast/standard/strong) |
| `EMBEDDING_*` | `cfg.embedding` | Embedding model |
| `RERANK_*` | `cfg.rerank` | Rerank model |
| `POSTGRES_*` | `cfg.postgresql` | PostgreSQL connection |
| `REDIS_*` | `cfg.redis` | Redis connection |
| `NEO4J_*` | `cfg.neo4j` | Neo4j connection |
| `MINIO_*` | `cfg.minio` | MinIO object storage |
| `MINERU_*` | `cfg.mineru` | MinerU document parsing service |

## Testing

```bash
cd backend
uv run pytest tests/core/ -v
```

Each feature slice has its own test directory under `backend/tests/core/<feature>/`.
