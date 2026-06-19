# Tests

> Test suite for the CrossEvidence backend. Uses `pytest` with `pytest-asyncio` for async test support. Tests mirror the `backend/src/` source structure.

## Quick Start

```bash
cd backend

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/agents/test_orchestrator.py -v

# Run a single test function
uv run pytest tests/agents/test_orchestrator.py::test_full_pipeline -v

# Run tests by marker
uv run pytest -m "not e2e" -v  # Skip end-to-end tests
```

## Directory Map

```
tests/
├── conftest.py                              # Shared fixtures
├── agents/                                  # Orchestrator, runner, adapters, state persistence
│   ├── test_orchestrator.py                 # PipelineOrchestrator graph construction and routing
│   ├── test_runner.py                       # PipelineRunner lifecycle
│   ├── test_concurrency.py                  # PipelineSemaphore, RetryablePhaseExecutor
│   ├── test_contracts.py                    # Agent contract validation
│   ├── test_state_persistence*.py           # State persistence layer tests
│   ├── test_state_transition_guard.py       # Transition guard logic
│   ├── test_phase_1_adapter.py              # Phase 1 adapter
│   ├── test_phase_1_pre_parsed_handoff.py   # Pre-parsed markdown handoff
│   ├── test_phase_2_adapter.py              # Phase 2 adapter
│   ├── test_phase2_retry.py                 # Phase 2 retry logic
│   ├── test_phase_3_adapter.py              # Phase 3 adapter
│   └── test_phase_4_factory.py              # Phase 4 factory
├── api/                                     # API route and middleware tests
│   ├── conftest.py                          # Test client and mock fixtures
│   ├── test_auth.py                         # API key authentication
│   ├── test_body_size_limit.py              # Body size middleware
│   ├── test_rate_limiting.py                # Rate limiter behavior
│   ├── test_pipeline_api.py                 # Pipeline CRUD endpoints
│   ├── test_pipeline_auth.py                # Pipeline auth enforcement
│   ├── test_pipeline_path_traversal.py      # Upload path traversal prevention
│   ├── test_pipeline_upload_limit.py        # Upload size limit enforcement
│   ├── test_evidence_api.py                 # Evidence search and detail endpoints
│   ├── test_chat_api.py                     # Chat session and message endpoints
│   ├── test_delta_audit_api.py              # Delta audit endpoints
│   ├── test_source_link_api.py              # Source link endpoints
│   ├── test_literature_profile_api.py       # Literature profile endpoints
│   ├── test_deps_session.py                 # DB session dependency
│   ├── test_error_handlers.py               # Global error handler
│   ├── test_error_response_type.py          # Error response structure
│   ├── test_health_endpoint.py              # Health check endpoint
│   ├── test_response_models.py              # Response model validation
│   └── test_wiring_config.py                # Wiring configuration
├── core/                                    # Business logic tests
│   ├── cross_lingual_process_and_extract_evidence/   # Phase 2
│   │   ├── extract_evidence/                           # Evidence extraction
│   │   │   ├── stages/                                 # Pipeline stages
│   │   │   ├── reconcile/                              # Reconciliation
│   │   │   ├── verify/                                 # Verification
│   │   │   ├── test_catalog.py                         # Catalog extraction
│   │   │   ├── test_chain_builder.py                   # Chain builder
│   │   │   ├── test_chunking.py                        # Text chunking
│   │   │   ├── test_contracts.py                       # Contract validation
│   │   │   ├── test_group_assignment.py                # Group assignment
│   │   │   ├── test_normalizer.py                      # Value normalization
│   │   │   ├── test_prompts.py                         # Prompt templates
│   │   │   ├── test_providers.py                       # LLM providers
│   │   │   ├── test_quality_validation.py              # Quality checks
│   │   │   ├── test_role_routing.py                    # Role routing
│   │   │   ├── test_source_grounding.py                # Source grounding
│   │   │   ├── test_target_guard.py                    # Target guard
│   │   │   ├── test_workflow.py                        # Workflow orchestration
│   │   │   └── test_e2e_*.py                           # E2E extraction tests
│   │   ├── test_translator.py                          # Translation service
│   │   ├── test_segmenter.py                           # Text segmentation
│   │   ├── test_language_detector.py                   # Language detection
│   │   ├── test_router.py                              # Translation router
│   │   ├── test_formatter.py                           # Output formatting
│   │   ├── test_validator.py                           # Translation validation
│   │   ├── test_drift_tracking.py                      # Drift tracking
│   │   └── test_e2e_*.py                               # E2E translation tests
│   ├── ingest_and_digitize_data/                      # Phase 1
│   │   ├── document_acquisition/                       # Acquisition service
│   │   │   ├── local_upload/                           # Local file upload
│   │   │   └── online_acquisition/                     # Online search/download
│   │   └── parse_document/                             # Document parsing
│   │       ├── test_mineru_parser.py                   # MinerU remote parser
│   │       ├── test_mineru_local_parser.py             # MinerU local parser
│   │       ├── test_orchestrator.py                    # Parse orchestrator
│   │       └── test_e2e_*.py                           # E2E parsing tests
│   ├── standardize_entities_and_align_knowledge/       # Phase 3
│   │   ├── context_pack/                               # Context pack
│   │   ├── test_matchers.py                            # Entity matching
│   │   ├── test_normalizers.py                         # Entity normalization
│   │   ├── test_importers.py                           # Terminology importers
│   │   ├── test_similarity_*.py                        # Similarity search
│   │   └── test_literature_profile_refresh.py          # Profile refresh
│   ├── visualize_evidence_with_expert_in_loop/         # Phase 4
│   │   ├── test_feedback_service.py                    # Feedback service
│   │   ├── test_chat_service.py                        # Chat service
│   │   ├── test_chat_ai.py                             # Chat AI integration
│   │   ├── test_chat_sse.py                            # SSE streaming
│   │   ├── test_delta_audit.py                         # Delta audit
│   │   ├── test_source_linker.py                       # Source linker
│   │   ├── test_search_service.py                      # Search service
│   │   └── test_contracts*.py                          # Contract validation
│   ├── test_config.py                                  # Config loading
│   ├── test_config_loader.py                           # Layered config loader
│   └── test_grounding.py                               # Grounding utilities
├── dao/
│   ├── postgresql/                          # ORM, connection, repo tests
│   │   ├── test_models.py                   # Model validation
│   │   ├── test_connection.py               # Engine and session lifecycle
│   │   ├── test_literature_profile_repo.py  # Literature profile repo
│   │   ├── test_search_index_repo.py        # Search index repo
│   │   ├── test_alembic_migration.py        # Migration integrity
│   │   ├── test_pgvector_migration.py       # pgvector migration
│   │   └── test_type_contract_compliance.py # Type contract compliance
│   └── redis/
│       ├── test_connection.py               # Redis connection
│       └── test_cache_repo.py               # Cache repository
├── benchmark/                               # Evaluation and benchmark tests
│   └── layer3/                              # Layer 3 benchmark suite
│       ├── clinvar_fused/                   # ClinVar fused evaluation
│       ├── test_evaluate_matching.py        # Matching evaluation
│       ├── test_baseline_runner.py          # Baseline runner
│       ├── test_diagnose_*.py               # Diagnostic tests
│       ├── test_reconcile_*.py              # Reconciliation evaluation
│       └── test_prompt_model_sweep_*.py     # Prompt/model sweep
├── integration/                             # Full integration tests
│   ├── test_app_startup.py                  # App startup sequence
│   └── test_literature_profile_e2e.py       # Literature profile E2E
├── online_acquisition/                      # Online acquisition E2E tests
│   ├── test_e2e_multilingual.py             # Multilingual acquisition
│   ├── test_e2e_providers.py                # Provider E2E
│   ├── test_e2e_workflow.py                 # Workflow E2E
│   ├── test_parallel_search.py              # Parallel search
│   ├── test_ranking.py                      # Result ranking
│   └── test_provider_health.py              # Provider health checks
├── scripts/                                 # Script smoke tests
│   ├── test_e2e_extract_evidence.py         # Extract evidence script
│   └── test_e2e_standardize_entities.py     # Standardize entities script
├── unit/                                    # Standalone unit tests
│   ├── test_batch_parse_downloads.py        # Batch parse downloads
│   ├── test_query_translator.py             # Query translation
│   └── test_relevance_gate_parsed.py        # Relevance gate
└── utils/                                   # Utility tests
    ├── test_exceptions.py                   # Exception hierarchy
    ├── test_health.py                       # Health check utilities
    ├── test_logger.py                       # Logger setup
    ├── test_middleware.py                    # Request monitoring middleware
    ├── test_observability.py                # Observability utilities
    └── test_text.py                         # Text utilities
```

## Test Strategy

### Unit Tests

Most tests are unit tests with mocked external dependencies:
- LLM calls are mocked via `unittest.mock` -- no real API calls
- Database tests use in-memory SQLite or test fixtures
- Rust native extension tests mock `rust_io` when unavailable

### Integration Tests

Integration tests require live external services (PostgreSQL, Redis, LLM endpoints):
- Marked with `@pytest.mark.integration` or `@pytest.mark.e2e`
- Skipped by default in CI
- Run manually: `uv run pytest -m integration -v`

### E2E Tests

End-to-end tests exercise the full pipeline with real services:
- Located in `core/*/test_e2e_*.py` and `online_acquisition/test_e2e_*.py`
- Require configured `.env.local` with all service endpoints
- Run manually: `uv run pytest -m e2e -v`

### Benchmark Tests

Benchmark and evaluation tests in `benchmark/layer3/`:
- Evaluate extraction quality, reconciliation accuracy, and prompt/model baselines
- Generate report tables and diagnostic artifacts
- Require populated database and test datasets

## Writing Tests

### Fixtures

Shared fixtures are in `conftest.py` at each directory level. Key fixtures:

```python
# Example: mock config fixture
@pytest.fixture
def mock_config(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8001")
    ...
```

### Async Tests

Use `pytest.mark.asyncio` for async test functions:

```python
import pytest

@pytest.mark.asyncio
async def test_translation_service():
    service = TranslationService(cfg=mock_config)
    result = await service.run(pages=[...])
    assert result.source_language == "zh"
```

### Naming Convention

- Test files: `test_<module>.py`
- Test functions: `test_<behavior>`
- Test classes: `Test<ClassName>` (optional, for grouping)

## Coverage Gaps

| Area | Status | Notes |
|------|--------|-------|
| Agent orchestrator | Good | Unit tests for graph construction, routing, state persistence |
| API routes | Good | Request validation, error responses, auth, rate limiting |
| Phase 1 (acquisition) | Good | Facade, local upload, gateway, normalizers, parsers |
| Phase 2 (extraction) | Good | Catalog, chunking, prompts, providers, reconciliation, workflow |
| Phase 2 (translation) | Good | Translator, formatter, validator, prompts, drift tracking |
| Phase 3 (standardization) | Good | Matching, alignment, similarity, importers, context pack |
| Phase 4 (review/feedback) | Good | Feedback, chat, audit, source linking, search |
| DAO | Good | Models, connection, repos, migrations, type compliance |
| Benchmark | Good | Layer 3 evaluation suite for extraction quality and baselines |
| Rust integration | Partial | Tests mock `rust_io`; no GPU/hardware tests |
| Web scrapers | Partial | Dispatcher tested; individual scrapers need live sites |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `unittest.mock` | Mocking (stdlib) |
