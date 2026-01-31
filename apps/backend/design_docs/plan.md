# Implementation Plan: Intelligent Parsing Pipeline System

**Branch**: `001-intelligent-parsing-pipeline` | **Date**: 2026-01-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-intelligent-parsing-pipeline/spec.md`

## Summary

The Intelligent Parsing Pipeline System automates ACMG evidence extraction from biomedical literature PDFs. Researchers upload documents (or provide PMID/DOI), which are parsed via MinerU, processed through a multi-agent workflow (Layout → Translation → Evidence → Arbitration), and stored with cryptographic traceability. The system maintains a confidence threshold of 0.85, routing low-confidence extractions to human review. A three-screen interface synchronizes PDF, translation, and evidence views, enabling verification and editing. A Neo4j knowledge graph aggregates cross-document evidence for "evidence stacking" intelligence. All operations are asynchronous with comprehensive audit trails and real-time WebSocket progress updates.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI (async web framework with Pydantic v2 for DTOs), Celery (task queue), Redis 8+ (broker/backend), `transitions` library (state machine), MinerU (PDF parsing adapter), LLM Provider (Agent logic)
**Storage**: PostgreSQL 18+ (metadata, tasks, logs), MinIO (object storage for PDFs/JSON/MD/images), Neo4j 5+ (knowledge graph), Qdrant 1.16+ `gpu-nvidia` (vector embeddings for RAG)
**Testing**: pytest with pytest-asyncio (unit/integration), pytest-celery (async task testing), testcontainers-python (database integration tests)
**Target Platform**: Linux server (containerized deployment via Docker Compose or Kubernetes)
**Project Type**: Web application (backend FastAPI + frontend consumer not in scope but API designed for integration)
**Performance Goals**:
- Document processing: 5 min for <20 pages, 10 min for <50 pages
- WebSocket progress updates: every 30 seconds
- Task failure rate: <1%
- Confidence threshold: ≥0.85 for auto-acceptance
**Constraints**:
- File size limit: 100MB per PDF
- Audit log retention: 90 days minimum
- State machine determinism: SHA256 input hash caching
- Layer architecture: Presentation → Application → Domain → Infrastructure (no bypassing)
- File decomposition: 200 lines maximum per Python file
**Scale/Scope**:
- Expected concurrent users: 10-50 researchers
- Document corpus: 1000-10000 papers
- Neo4j graph: 10+ documents for meaningful evidence stacking
- Concurrent parsing tasks: 5-10 simultaneous

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Architectural Sovereignty & Modularity

- ✅ **Strict Layered Governance**: Design enforces Presentation → Application → Domain → Infrastructure
  - Controllers (Presentation) call Services (Application) call Domain logic call Repositories (Infrastructure)
  - No controller-to-repository direct access
  - DTOs defined at layer boundaries

- ✅ **Granular Decomposition**: 200-line file limit
  - Agent workflow split into: `agent_workflow.py` (state machine), `layout_agent.py`, `translation_agent.py`, `evidence_agent.py`, `arbitration_agent.py`
  - Services split by concern: `storage_orchestration_service.py`, `pdf_parse_service.py`, `data_processing_service.py`
  - Each controller handles single resource: `pdf_parse_controller.py`, `literature_graph_controller.py`

- ✅ **DTO Isolation**:
  - Presentation layer: `PDFUploadRequestDTO`, `EvidenceListResponseDTO`, `TaskStatusResponseDTO`
  - Application layer: domain models never exposed directly
  - Infrastructure layer: database entities (SQLAlchemy models) isolated from domain

### II. Domain Integrity & Precision

- ✅ **ACMG Compliance**: 0.85 confidence threshold enforced in `arbitration_agent.py`
  - Low-confidence items flagged in `evidence_items` table (`review_required` boolean)
  - Human-in-the-loop queue implementation via task status filtering

- ✅ **Traceability**: Source coordinates stored with every evidence item
  - `evidence_items.source_page` (integer), `evidence_items.bounding_box` (JSONB)
  - SHA256 hash linkage: `evidence_items.source_hash` references `documents.content_hash`

- ✅ **Agent Determinism**: `transitions` library state machine in `agent_workflow.py`
  - State transitions logged to `agent_logs` table
  - Input hash caching: `agent_cache` table with `input_hash` (SHA256) as primary key
  - Cache invalidation on prompt/model version change

### III. Resilience & Consistency

- ✅ **Transactional Orchestration**: `StorageOrchestrationService` manages multi-store writes
  - Order: MinIO write → PostgreSQL commit (rollback on failure via compensation)
  - Idempotency key: `task_id` UUID prevents duplicate operations

- ✅ **Asynchronous Reliability**: Celery task configuration
  - Retry strategy: `max_retries=3`, `retry_backoff=True` (2s, 4s, 8s)
  - Dead Letter Queue: `celery_dead_letter` queue for failed tasks
  - Task status queryable via `parsing_tasks` table

- ✅ **Auditability**: `agent_logs` table schema
  - Columns: `timestamp`, `task_id`, `agent_type`, `state_from`, `state_to`, `confidence_score`, `latency_ms`, `failure_reason`, `input_prompt`, `output_reasoning`
  - Retention: 90-day TTL via PostgreSQL partitioning + cron cleanup

### IV. Performance & UX

- ✅ **Real-Time Feedback**: WebSocket implementation
  - FastAPI WebSocket endpoint: `/ws/task/{task_id}/progress`
  - Celery task progress updates: `self.update_state(state='PROGRESS', meta={'percentage': 50, 'stage': 'Evidence Extraction'})`
  - Auto-reconnect: client-side exponential backoff

- ✅ **Graph-Based Aggregation**: Neo4j Cypher queries
  - Minimum 2-hop traversal: `MATCH (v:Variant)-[:MENTIONED_IN]->(d:Document)-[:HAS_EVIDENCE]->(e:Evidence) WHERE ... RETURN ...`
  - Evidence upgrade logic in `evidence_aggregation_service.py`

### Gate Status: **PASS** ✅

All constitution principles satisfied. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-intelligent-parsing-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions and best practices
├── data-model.md        # Phase 1: Entity schemas and relationships
├── quickstart.md        # Phase 1: Developer setup guide
├── contracts/           # Phase 1: API contracts
│   ├── openapi.yaml     # REST API specification
│   └── websocket.md     # WebSocket protocol documentation
└── checklists/
    └── requirements.md  # Specification quality checklist (already created)
```

### Source Code (repository root)

```text
apps/backend/
├── src/
│   ├── presentation/                    # Layer 1: HTTP/WebSocket endpoints
│   │   ├── controllers/
│   │   │   ├── pdf_parse_controller.py      # Upload, status, retry endpoints
│   │   │   ├── evidence_controller.py       # Evidence CRUD and review
│   │   │   ├── literature_graph_controller.py  # Graph query endpoints
│   │   │   └── task_controller.py           # Task management dashboard
│   │   ├── dtos/
│   │   │   ├── request/
│   │   │   │   ├── pdf_upload_request.py
│   │   │   │   ├── pmid_fetch_request.py
│   │   │   │   └── evidence_edit_request.py
│   │   │   └── response/
│   │   │       ├── evidence_list_response.py
│   │   │       ├── task_status_response.py
│   │   │       └── graph_viz_response.py
│   │   └── websocket/
│   │       └── progress_handler.py          # WebSocket connection manager
│   │
│   ├── application/                     # Layer 2: Business logic orchestration
│   │   ├── services/
│   │   │   ├── storage_orchestration_service.py  # Multi-store consistency
│   │   │   ├── pdf_parse_service.py              # High-level workflow
│   │   │   ├── data_processing_service.py        # File routing
│   │   │   ├── evidence_aggregation_service.py   # Graph-based intelligence
│   │   │   └── task_management_service.py        # Queue prioritization
│   │   └── use_cases/
│   │       ├── upload_document_use_case.py
│   │       ├── process_document_use_case.py
│   │       └── aggregate_evidence_use_case.py
│   │
│   ├── domain/                          # Layer 3: Core business logic
│   │   ├── agents/
│   │   │   ├── agent_workflow.py             # State machine definition
│   │   │   ├── layout_agent.py               # Markdown sanitization
│   │   │   ├── translation_agent.py          # Bilingual alignment
│   │   │   ├── evidence_agent.py             # ACMG extraction
│   │   │   └── arbitration_agent.py          # Confidence scoring
│   │   ├── models/
│   │   │   ├── document.py                   # Domain entity
│   │   │   ├── evidence_item.py              # Domain entity
│   │   │   ├── variant.py                    # Domain entity
│   │   │   └── parsing_task.py               # Domain entity
│   │   ├── value_objects/
│   │   │   ├── confidence_score.py
│   │   │   ├── source_coordinates.py
│   │   │   └── acmg_code.py
│   │   └── interfaces/
│   │       ├── document_repository.py        # Abstract interface
│   │       ├── graph_repository.py           # Abstract interface
│   │       └── storage_client.py             # Abstract interface
│   │
│   └── infrastructure/                  # Layer 4: External integrations
│       ├── repositories/
│       │   ├── postgres/
│       │   │   ├── document_repository_impl.py
│       │   │   ├── task_repository_impl.py
│       │   │   └── audit_log_repository_impl.py
│       │   ├── neo4j/
│       │   │   └── graph_repository_impl.py
│       │   └── qdrant/
│       │       └── vector_repository_impl.py
│       ├── storage/
│       │   └── minio_storage_client.py       # S3 protocol wrapper
│       ├── adapters/
│       │   ├── mineru_adapter.py             # PDF parsing integration
│       │   └── llm_adapter.py                # LLM provider integration
│       ├── database/
│       │   ├── postgres_models.py            # SQLAlchemy entities
│       │   └── migrations/                   # Alembic migrations
│       └── tasks/
│           └── celery_tasks.py               # Async task definitions
│
├── tests/
│   ├── unit/
│   │   ├── domain/                           # Pure domain logic tests
│   │   ├── services/                         # Service layer tests
│   │   └── agents/                           # Agent workflow tests
│   ├── integration/
│   │   ├── test_pdf_parsing_pipeline.py      # End-to-end workflow
│   │   ├── test_storage_orchestration.py     # Multi-store consistency
│   │   └── test_graph_aggregation.py         # Neo4j integration
│   └── contract/
│       └── test_api_contracts.py             # OpenAPI compliance
│
├── config/
│   ├── app_config.py                         # Application settings
│   ├── database_config.py                    # Database connections
│   └── celery_config.py                      # Task queue configuration
│
├── migrations/                               # Alembic database migrations
├── docker-compose.yml                        # Local development stack
├── requirements.txt                          # Python dependencies
└── README.md                                 # Project documentation
```

**Structure Decision**: Web application backend following strict 4-layer architecture (Presentation → Application → Domain → Infrastructure). The directory structure enforces layer isolation by nesting depth and naming conventions. Each layer has clear responsibilities with no cross-layer violations.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations detected. All constitution gates passed.*
