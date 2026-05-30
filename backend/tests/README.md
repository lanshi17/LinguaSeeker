# Tests

> Test suite for the ACMG Lingua backend. Uses `pytest` with `pytest-asyncio` for async test support. Tests mirror the `backend/src/` source structure.

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
├── agents/                                  # Orchestrator tests
├── api/                                     # API route tests
├── core/
│   ├── cross_lingual_process_and_extract_evidence/  # Phase 2 tests
│   │   ├── extract_evidence/                        # Evidence extraction
│   │   └── (translation tests at this level)
│   ├── ingest_and_digitize_data/                    # Phase 1 tests
│   │   ├── document_acquisition/                    # Acquisition facade
│   │   ├── literature_acquisition/                  # Provider tests
│   │   └── parse_document/                          # Parser tests
│   ├── standardize_entities_and_align_knowledge/    # Phase 3 tests
│   └── visualize_evidence_with_expert_in_loop/      # Phase 4 tests
├── dao/
│   ├── postgresql/                          # ORM, connection, repo tests
│   └── redis/                               # Cache repo tests
├── utils/                                   # Utility tests
├── scripts/                                 # Script smoke tests
├── services/                                # Model server tests (placeholder)
├── integration/                             # Full integration tests (placeholder)
├── online_acquisition/                      # Legacy online acquisition tests
├── phase4/                                  # Phase 4 additional tests
└── output/                                  # Test output artifacts
```

## Test Strategy

### Unit Tests

Most tests are unit tests with mocked external dependencies:
- LLM calls are mocked via `unittest.mock` — no real API calls
- Database tests use in-memory SQLite or test fixtures
- Rust native extension tests mock `rust_io` when unavailable

### Integration Tests

Integration tests require live external services (PostgreSQL, Redis, LLM endpoints):
- Marked with `@pytest.mark.integration` or `@pytest.mark.e2e`
- Skipped by default in CI
- Run manually: `uv run pytest -m integration -v`

### E2E Tests

End-to-end tests exercise the full pipeline with real services:
- Located in `core/*/test_e2e_*.py`
- Require configured `.env.local` with all service endpoints
- Run manually: `uv run pytest -m e2e -v`

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
| API routes | Good | Request validation, error responses |
| Phase 1 (acquisition) | Good | Facade, local upload, gateway, normalizers |
| Phase 2 (translation) | Good | Translator, formatter, validator, prompts |
| Phase 3 (standardization) | Good | Matching, alignment |
| Phase 4 (review/feedback) | Good | Feedback, chat, audit, source linking |
| DAO | Good | Models, connection, repos, migrations |
| Rust integration | Partial | Tests mock `rust_io`; no GPU/hardware tests |
| Model server | Partial | Domain + API tests; no real GPU inference |
| Web scrapers | Partial | Dispatcher tested; individual scrapers need live sites |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `unittest.mock` | Mocking (stdlib) |
