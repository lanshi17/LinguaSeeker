# Backend Code Review Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address 8 findings from the 2026-05-30 backend code review — fix sync I/O blocking, complete content injection path, remove dead code, fix pytest collection, generate initial Alembic migration, unify LLM provider routing, and improve chat intent detection.

**Architecture:** All changes are surgical fixes to existing modules. No new abstractions. Each task is independent and can be executed in any order.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, pytest, aiofiles, Alembic

---

## Task 1: Fix Sync File I/O in Phase 2 Adapter

**Files:**
- Modify: `backend/src/agents/phase_2_adapter.py:89-91`
- Test: `backend/tests/agents/test_phase_2_adapter.py`

**Problem:** `open()` blocks the event loop when reading `metadata_path` and writing `extraction_result_path`.

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_phase2_adapter_reads_metadata_async(tmp_path, monkeypatch):
    """Phase 2 adapter uses aiofiles to read/write, not sync open()."""
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"pages": [], "content_blocks": []}))
    state = build_mock_state(metadata_path=str(metadata))
    adapter = Phase2Adapter(mock_translation, mock_extraction)

    # Patch aiofiles.open to verify it's called (not sync open)
    import aiofiles
    original_open = aiofiles.open
    call_log = []
    def spy_open(*a, **kw):
        call_log.append(a)
        return original_open(*a, **kw)
    monkeypatch.setattr(aiofiles, "open", spy_open)

    result = await asyncio.wait_for(adapter.run(state), timeout=5.0)
    assert result.phase_2_output is not None
    assert len(call_log) >= 1, "Expected aiofiles.open to be called"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/agents/test_phase_2_adapter.py::test_phase2_adapter_reads_metadata_async -v`
Expected: FAIL or timeout

**Step 3: Implement aiofiles usage**

```python
# In phase_2_adapter.py, replace:
#   with open(metadata_path, "r") as f:
#       parse_data = json.load(f)
# With:
import aiofiles
async with aiofiles.open(metadata_path, "r") as f:
    content = await f.read()
    parse_data = json.loads(content)

# Replace:
#   with open(extraction_result_path, "w") as f:
#       json.dump(dual_result.model_dump(mode="json"), f)
# With:
async with aiofiles.open(extraction_result_path, "w") as f:
    await f.write(json.dumps(dual_result.model_dump(mode="json")))
```

**Step 4: Add aiofiles to dependencies**

```bash
cd backend && uv add aiofiles
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/agents/test_phase_2_adapter.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/agents/phase_2_adapter.py backend/tests/agents/test_phase_2_adapter.py backend/pyproject.toml backend/uv.lock
git commit -m "fix(agents): use aiofiles for async file I/O in Phase 2 adapter"
```

---

## Task 2: Complete Content Injection Path (Base64 → Phase 1)

**Files:**
- Modify: `backend/src/api/v1/pipeline.py:189-193`
- Modify: `backend/src/agents/phase_1_adapter.py:78-85`
- Modify: `backend/src/agents/contracts.py` (add content_bytes field)
- Test: `backend/tests/api/test_pipeline_api.py`

**Problem:** `content_bytes` is decoded but never injected into state or stored for Phase 1 to consume.

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_pipeline_run_injects_content_to_state(async_client):
    """POST /api/v1/pipeline/run injects base64 content into state."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.start = MagicMock()
        mock_runner.is_running_for_source = MagicMock(return_value=False)
        mock_get_runner.return_value = mock_runner

        await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "filename": "test.pdf",
                "content_base64": "dGVzdA==",  # "test"
                "mode": "full",
            },
        )

        # Verify start() was called with state containing upload_file_path
        call_args = mock_runner.start.call_args
        initial_state = call_args[0][0]
        assert initial_state.upload_file_path is not None
        assert initial_state.upload_file_path.endswith("test.pdf")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_pipeline_api.py::test_pipeline_run_injects_content_to_state -v`
Expected: FAIL (upload_file_path not in state)

**Step 3: Add upload_file_path to PipelineGraphState**

```python
# In contracts.py, add to PipelineGraphState:
upload_file_path: str | None = None  # Temp file path for uploaded content (base64 decoded)
```

**Step 4: Write content to temp file in pipeline.py**

```python
# In start_pipeline_run(), replace TODO:
content_bytes = None
if request.content_base64:
    content_bytes = base64.b64decode(request.content_base64)

upload_file_path = None
if content_bytes and request.filename:
    temp_dir = Path("data/pipeline/uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    upload_file_path = str(temp_dir / f"{processing_run_id}_{request.filename}")
    async with aiofiles.open(upload_file_path, "wb") as f:
        await f.write(content_bytes)

initial_state = PipelineGraphState(
    ...,
    upload_file_path=upload_file_path,
)
```

**Step 4a: Add cleanup after pipeline completes**

```python
# In start_pipeline_run(), after runner.start() or in a finally block:
if upload_file_path:
    try:
        Path(upload_file_path).unlink(missing_ok=True)
    except OSError:
        pass  # best-effort cleanup
```

> **Why cleanup?** Temp files accumulate on repeated runs. The file is only needed during pipeline execution.

**Step 5: Update Phase1Adapter to use upload_file_path**

```python
# In phase_1_adapter.py, replace:
#   filename=None,  # Populated from API request params
#   content=None,
# With:
request = DocumentAcquisitionRequest(
    source=AcquisitionSource(state.source_type.value),
    filename=Path(state.upload_file_path).name if state.upload_file_path else None,
    content=state.upload_file_path,  # file path for gateway to read
    upload_dir=None,
)
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/api/test_pipeline_api.py tests/agents/test_phase_1_adapter.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/src/agents/contracts.py backend/src/api/v1/pipeline.py backend/src/agents/phase_1_adapter.py backend/tests/
git commit -m "feat(pipeline): inject base64 content to Phase 1 via temp file"
```

---

## Task 3: Remove Dead Code (VectorRepository)

**Files:**
- Delete: `backend/src/dao/postgresql/vector_repo.py`
- Modify: `backend/src/dao/postgresql/__init__.py` (remove exports)
- Delete: `backend/tests/dao/postgresql/test_vector_repo.py`

**Problem:** `VectorRepository` uses outdated schema (`source_text`, `model_version`) and is not called by active code.

**Step 1: Verify no active callers**

```bash
cd backend && rg -l "VectorRepository" src/ --type py
# Expected: only src/dao/postgresql/__init__.py
# Also check tests/ and old_version/:
rg -l "VectorRepository" . --type py
```

**Step 2: Remove vector_repo.py**

```bash
rm backend/src/dao/postgresql/vector_repo.py
rm backend/tests/dao/postgresql/test_vector_repo.py
```

**Step 3: Update __init__.py**

```python
# Remove from TYPE_CHECKING block:
from src.dao.postgresql.vector_repo import VectorRepository

# Remove from __all__:
"VectorRepository",

# Remove from _LAZY_IMPORTS:
"VectorRepository": "src.dao.postgresql.vector_repo",
```

**Step 4: Run tests to verify no breakage**

Run: `uv run pytest tests/dao/ -v`
Expected: PASS (no test_vector_repo.py collected)

**Step 5: Commit**

```bash
git add backend/src/dao/postgresql/ backend/tests/dao/postgresql/
git commit -m "refactor(dao): remove dead VectorRepository (replaced by similarity_match/repositories.py)"
```

---

## Task 4: Fix pytest Collection Conflict

**Files:**
- Rename: `backend/services/model-server/tests/test_config.py` → `test_model_server_config.py`

**Problem:** `backend/tests/core/test_config.py` and `backend/services/model-server/tests/test_config.py` have the same module name, causing pytest collection to fail.

**Step 1: Rename the file**

```bash
cd backend/services/model-server/tests
mv test_config.py test_model_server_config.py
```

**Step 2: Run repo-wide pytest collection**

```bash
cd backend && uv run pytest --collect-only -q 2>&1 | head -20
# Expected: no ImportError or collection errors
```

**Step 3: Commit**

```bash
git add backend/services/model-server/tests/
git commit -m "fix(tests): rename test_config.py to avoid pytest collection conflict"
```

---

## Task 5: Generate Initial Alembic Migration

**Files:**
- Create: `backend/alembic/versions/001_initial_schema.py`

**Problem:** `alembic/versions/` is empty; database schema lacks versioned migration history.

**Step 1: Autogenerate migration from ORM models**

```bash
cd backend
uv run alembic revision --autogenerate -m "initial_schema"
```

**Step 2: Review generated migration**

```bash
ls backend/alembic/versions/
cat backend/alembic/versions/*_initial_schema.py | head -100
```

Verify tables: `source_documents`, `processing_runs`, `run_evidence_items`, `canonical_evidence_items`, `normalized_entities`, `terminology_entries`, `terminology_aliases`, `terminology_relationships`, `terminology_embeddings`, `review_audit_events`, `chat_sessions`, `chat_messages`, `pipeline_run_states`, `users`, `entity_merge_events`, `source_document_identifiers`, `frontend_search_index`.

**Step 3: Apply migration to test database**

```bash
cd backend
# Use DB name from alembic.ini / env vars, not hardcoded
uv run alembic upgrade head
```

> **Note:** Ensure `alembic.ini` and `alembic/env.py` read `sqlalchemy.url` from env vars (`DATABASE_URL` or `POSTGRES_*`), not hardcoded values. If not configured yet, wire it before running.

**Step 4: Verify migration (upgrade + downgrade)**

```bash
# Verify upgrade
uv run alembic upgrade head
uv run alembic current

# Verify downgrade path exists
uv run alembic downgrade -1
uv run alembic upgrade head  # re-apply

# Run migration tests if they exist
uv run pytest tests/dao/postgresql/test_alembic_migration.py -v 2>/dev/null || echo "No migration tests yet"
```

**Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): add initial Alembic migration for full schema"
```

---

## Task 6: Fix ReasoningConfig Timeout Field

**Files:**
- Modify: `backend/src/core/config.py:71-77` (add timeout field)
- Modify: `backend/src/core/config.py` (_build_nested validator)
- Test: `backend/tests/core/test_config.py`

**Problem:** `ReasoningLLMProvider` reads `cfg.reasoning_llm_timeout` which is a flat field, but `ReasoningConfig` doesn't have a `timeout` field. The provider should read from nested config.

**Step 1: Write the failing test**

```python
def test_reasoning_config_has_timeout():
    """ReasoningConfig includes timeout field."""
    cfg = Settings(reasoning_llm_timeout=120, _env_file=None)
    assert cfg.reasoning.timeout == 120
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_config.py::test_reasoning_config_has_timeout -v`
Expected: FAIL (AttributeError: timeout)

**Step 3: Add timeout to ReasoningConfig**

```python
class ReasoningConfig(BaseModel):
    """Expert reasoning agent (stronger reasoning model)."""

    api_key: str = ""
    model: str = ""
    reasoning_effort: str = "high"
    base_url: str = ""
    timeout: int = 60  # Add this
```

**Step 4: Update _build_nested validator**

```python
# In _build_nested(), update ReasoningConfig construction:
self.reasoning = ReasoningConfig(
    api_key=reasoning_api_key,
    model=reasoning_model,
    reasoning_effort=reasoning_effort,
    base_url=reasoning_base_url,
    timeout=self.reasoning_llm_timeout or 60,  # Add this
)
```

**Step 5: Update ReasoningLLMProvider to use nested config**

```python
# In providers.py, replace:
#   self._timeout = cfg.reasoning_llm_timeout or 60
# With:
self._timeout = cfg.reasoning.timeout
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/core/test_config.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/src/core/config.py backend/src/core/visualize_evidence_with_expert_in_loop/providers.py backend/tests/core/test_config.py
git commit -m "fix(config): add timeout field to ReasoningConfig"
```

---

## Task 7: Unify LLM Provider Routing Through Model Server

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/providers.py`
- Test: `backend/tests/phase4/test_providers.py`

**Problem:** `ReasoningLLMProvider` calls LLM API directly (`cfg.reasoning.base_url`) instead of routing through model-server's OpenAI-compatible interface.

> **Dependency:** `cfg.model_server_url` already exists in `config.py:320` (default `http://localhost:8001`). This change makes model-server a hard runtime dependency for Phase 4. Document this in the commit message.

> **Mock impact:** Existing tests that mock `httpx.AsyncClient.post` against `cfg.reasoning.base_url` will need URL updates to point at model-server.

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_reasoning_provider_uses_model_server():
    """ReasoningLLMProvider routes through model-server /v1/chat/completions."""
    provider = ReasoningLLMProvider()
    # Verify base_url points to model-server, not external API
    assert "localhost:8001" in provider._base_url or "model-server" in provider._base_url
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase4/test_providers.py::test_reasoning_provider_uses_model_server -v`
Expected: FAIL

**Step 3: Update provider to use model-server**

```python
class ReasoningLLMProvider:
    """Wrapper for REASONING_LLM_MODEL via model-server.

    Routes all requests through model-server's OpenAI-compatible
    /v1/chat/completions endpoint for unified monitoring and rate limiting.
    Requires model-server to be running (hard dependency).
    """

    def __init__(self) -> None:
        cfg = get_config()
        self._api_key = "not-needed"  # model-server doesn't require auth
        self._model = cfg.reasoning.model
        self._base_url = cfg.model_server_url  # config.py:320, default "http://localhost:8001"
        self._timeout = cfg.reasoning.timeout
```

**Step 4: Verify model-server supports /v1/chat/completions**

Check `backend/services/model-server/app/api/chat.py` exists and routes `/v1/chat/completions`.

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/phase4/test_providers.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/providers.py backend/tests/phase4/
git commit -m "refactor(providers): route ReasoningLLMProvider through model-server (hard dependency)"
```

---

## Task 8: Improve Chat Intent Detection

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py:187-195`
- Test: `backend/tests/phase4/test_chat_service.py`

**Problem:** Regex-based intent detection misclassifies complex questions like "What should I change?" — the `change` pattern fires before the `?` pattern.

> **Design decision:** Questions take priority over corrections. A message like "Please change X to Y?" will be classified as `question` (has `?`). This is intentional — ambiguous cases default to the less destructive intent. Document this in the method's docstring.

**Step 1: Write the failing test**

```python
def test_detect_intent_question_with_change_keyword():
    """Questions containing 'change' are classified as questions, not corrections."""
    service = ChatService(mock_session)
    assert service._detect_intent("What should I change?") == "question"
    assert service._detect_intent("How do I change this?") == "question"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase4/test_chat_service.py::test_detect_intent_question_with_change_keyword -v`
Expected: FAIL (returns "correction")

**Step 3: Reorder pattern matching**

```python
def _detect_intent(self, message: str) -> str:
    """Detect user intent: question, correction, or note.

    Priority: question > correction > note.
    Ambiguous messages (e.g. "change X to Y?") default to question
    as the less destructive intent.
    """
    msg_lower = message.lower()

    # Check question patterns FIRST (higher priority)
    question_patterns = [
        r"\?",
        r"\bwhat\b",
        r"\bwhy\b",
        r"\bhow\b",
        r"\bwhich\b",
        r"\b什么\b",
        r"\b为什么\b",
        r"\b如何\b",
    ]
    if any(re.search(p, msg_lower) for p in question_patterns):
        return "question"

    # Only check correction patterns if not a question
    correction_patterns = [
        r"\bchange\b.*\bto\b",
        r"\bupdate\b.*\bto\b",
        r"\bcorrect\b.*\bto\b",
        r"\b修改\b.*\b为\b",
        r"\b改为\b",
    ]
    if any(re.search(p, msg_lower) for p in correction_patterns):
        return "correction"

    return "note"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/phase4/test_chat_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py backend/tests/phase4/test_chat_service.py
git commit -m "fix(chat): prioritize question detection over correction patterns"
```

---

## Execution Order

Tasks are independent. Recommended order by priority:

1. **Task 1** (sync I/O) — performance fix, easy win
2. **Task 6** (ReasoningConfig timeout) — bug fix, affects correctness
3. **Task 4** (pytest collection) — CI blocker
4. **Task 2** (content injection) — feature completion
5. **Task 3** (dead code) — cleanup
6. **Task 8** (intent detection) — UX improvement
7. **Task 7** (LLM routing) — architectural improvement
8. **Task 5** (Alembic migration) — infrastructure, requires DB setup

---

## Verification Checklist

After completing all tasks:

- [ ] `uv run pytest` passes (888+ tests)
- [ ] `uv run ruff check` clean
- [ ] `uv run alembic upgrade head` + `alembic downgrade -1` succeeds on test DB
- [ ] Manual test: POST /api/v1/pipeline/run with base64 content creates temp file, file cleaned up after run
- [ ] Manual test: Phase 2 adapter reads metadata without blocking
- [ ] Manual test: Chat "What should I change?" detected as question
- [ ] Manual test: ReasoningLLMProvider routes through model-server (check model-server logs)
