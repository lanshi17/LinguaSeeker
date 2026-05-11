# Code Review: MinerU VLM + vllm Migration — Pass 2

**Branch:** `feat/mineru-vlm-vllm-migration`  
**Commit:** `f65b837a`  
**Plan:** `docs/planned/2026-05-11-mineru-vlm-vllm-migration.md`  
**Reviewer:** Staff Engineer  
**Date:** 2026-05-11

---

## Summary

The implementation successfully unifies Embedding, Rerank, and VLM inference under vllm, adds MinerU VLM document extraction via `/v1/chat/completions`, and includes 16 passing tests. The core migration is mechanically correct. However, several architectural and type-safety issues need attention before merge.

**Decision: 🔄 Request Changes** — 3 blocking, 5 important, 4 nits.

---

## 🔴 Blocking

### B1. `LLMService` is misnamed — it's a VLM/MinerU service, not an LLM service

**File:** `backend/services/model-server/app/domain/llm.py:18`

The class is named `LLMService` but it's exclusively a MinerU VLM document extraction service. The plan (Task 7) says "保留 LLMService 名称以保持向后兼容" but there is no backward compatibility to maintain — this is a greenfield design. The name is misleading because:

- The class docstring says "MinerU2.5-Pro VLM"
- The `infer()` method only accepts `Image.Image`, not text chat
- It wraps `MinerUClient`, not an LLM chat engine

A future developer searching for the actual LLM service (Task 10 placeholder) will be confused.

**Fix:** Rename to `VLMService` or `MinerUService`. Update `main.py` imports and bind calls accordingly.

### B2. `chat.py` endpoint is orphaned at `/v1/chat/completions_legacy` with no documentation

**File:** `backend/services/model-server/app/api/chat.py:48`

The original chat endpoint was moved from `/v1/chat/completions` to `/v1/chat/completions_legacy` and wire to the same `LLMService`. This leaves a zombie endpoint that:

- Is always registered even when `VLM_MODEL_ID` is empty (returns 503)
- Duplicates `vlm.py`'s functionality with a different message format (string-based image detection vs. multimodal content array)
- Has no documentation explaining its purpose or deprecation timeline

**Fix:** Either (a) remove `chat.py` entirely since all its functionality is subsumed by `vlm.py`, or (b) add a deprecation warning and document the migration path. If keeping it, move it under `vlm.py` to avoid confusion.

### B3. `vlm.router` is always included even when `_llm_svc is None`

**File:** `backend/services/model-server/main.py:65`

```python
app.include_router(vlm.router)  # Always registered
```

When `VLM_MODEL_ID` is empty, `_llm_svc = None`, but the route is still registered — it just returns 503 on every request. This pollutes the API surface and the OpenAPI docs.

**Fix:** Make the include conditional:

```python
if _llm_svc:
    app.include_router(vlm.router)
    app.include_router(chat.router)
```

---

## 🟡 Important

### I1. `LLMService.infer()` returns bare `dict[str, Any]` — violates AGENTS.md Rule 22

**File:** `backend/services/model-server/app/domain/llm.py:47`

```python
def infer(self, image: Image.Image, **kwargs: Any) -> dict[str, Any]:
```

Per Rule 22, internal data contracts must use dataclasses or TypedDict, not bare dict. The return value has a well-defined structure (`id`, `full_markdown`, `pages`, `metadata`) that should be typed.

**Fix:** Define `@dataclass class VLMInferResult:` with the four fields, or use a TypedDict.

### I2. `VLMExtractRequest.messages: list[dict]` — untyped dict in a Pydantic schema

**File:** `backend/services/model-server/app/models/schemas.py:250`

```python
messages: list[dict]  # OpenAI multimodal message format
```

This is an API contract — it should be a typed model. While the OpenAI multimodal format is complex, at minimum define the union type for `content` (string vs. list of `ContentPart`).

**Fix:** Add minimal typed models:

```python
class VLMImageUrl(BaseModel):
    url: str

class VLMContentPart(BaseModel):
    type: str  # "text" | "image_url"
    text: str | None = None
    image_url: VLMImageUrl | None = None

class VLMMessage(BaseModel):
    role: str
    content: str | list[VLMContentPart]  # OpenAI multimodal format

class VLMExtractRequest(BaseModel):
    model: str = ""
    messages: list[VLMMessage]
```

### I3. `_build_pages` passes raw dicts to typed Pydantic fields — silent coercion

**File:** `backend/services/model-server/app/api/vlm.py:67-76`

```python
pages.append(VLMPageContent(
    page_number=page_number,
    markdown=page.get("markdown", ""),
    figures=page.get("figures", []),  # Pydantic coerces these
    tables=page.get("tables", []),    # Pydantic coerces these
))
```

Pydantic will silently coerce raw dicts into `VLMFigurePosition`/`VLMTableStructure`, but if the upstream data has an unexpected shape, the error surfaces as a 500 at serialization time rather than with a clear message about what went wrong. Better to validate explicitly.

**Fix:** Add a `_parse_figure(raw: dict) -> VLMFigurePosition` and `_parse_table(raw: dict) -> VLMTableStructure` with try/except that logs malformed data before re-raising. Or use Pydantic's `model_validate` with `strict=True` and catch `ValidationError`.

### I4. `_extract_images_from_messages` silently takes only `images[0]`, discards the rest

**File:** `backend/services/model-server/app/api/vlm.py:79`

```python
result = _service.infer(image=images[0])
```

Multi-page documents may send multiple images but only the first is used. This is a data loss bug for the multi-page extraction use case the architecture was designed for.

**Fix:** Either (a) iterate over all images and aggregate results, or (b) validate at the request level that exactly one image is provided (raise 400 for multi-image), and document the limitation. Option (b) is simpler and matches the current `LLMService` interface.

### I5. No error handling in `LLMService.infer()` — MinerUClient failures propagate as unhandled 500s

**File:** `backend/services/model-server/app/domain/llm.py:54-70`

```python
result = self._client.two_step_extract(image)
```

`MinerUClient.two_step_extract()` can fail for many reasons (CUDA OOM, invalid image format, model not loaded, logits processor mismatch). None of these are caught. This results in FastAPI returning a raw 500 with traceback in production.

**Fix:** Wrap in try/except and convert known exceptions to `HTTPException` (in the route layer) or a domain-level `VLMInferenceError`. Log the full traceback server-side.

---

## 🟢 Nits

### N1. Hardcoded `hf_home` path

**File:** `backend/services/model-server/app/config.py:26`

```python
hf_home: str = "/home/[redacted-user]/.cache/huggingface/hub"
```

This hardcodes a user-specific path. Should be configurable via `HF_HOME` env var with a reasonable default that uses `$HOME` or `os.path.expanduser`.

### N2. `MinerULogitsProcessor` passed as class, not instance

**File:** `backend/services/model-server/app/domain/llm.py:38`

```python
logits_processors=[MinerULogitsProcessor],
```

The vllm API expects logits processor **instances**, not classes. Depending on vllm version, this may or may not work. Check the mineru_vl_utils documentation — typically you need `MinerULogitsProcessor()`.

### N3. `_build_pages` parameter type is `list[dict]`

**File:** `backend/services/model-server/app/api/vlm.py:54`

```python
def _build_pages(pages_data: list[dict]) -> list[VLMPageContent]:
```

Use `list[dict[str, Any]]` at minimum, or better a TypedDict for the page dict shape.

### N4. Tests don't verify the test helper sets `PYTHONPATH` — discovered via trial

**File:** `backend/services/model-server/tests/*`

All tests import `from app.models import ...` which requires `PYTHONPATH=.` (cwd = `services/model-server/`). The `pyproject.toml` doesn't configure this. Add a `conftest.py` that does `sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))` or a `[tool.pytest.ini_options]` pythonpath setting.

---

## 📚 What's Good

- **All 16 tests pass** with proper mocking — good TDD discipline
- **Base class refactor** cleanly removes `_require_cuda` / `torch` dependency — the `gpu_memory_utilization` parameter is well-designed
- **Binding pattern** (`bind()` + module-level `_service`) is consistent across all API routes — easy to follow
- **README update** correctly documents the new endpoints and removes stale examples
- **Config fields** follow existing conventions and use `pydantic-settings` properly
- **OpenAI-compatible API shape** for `/v1/chat/completions` is well-implemented with proper base64 image decoding

---

## Test Coverage Gaps

| Area | Status | Notes |
|------|--------|-------|
| Embedding normalize=True | Partially covered | Tests verify shape but not normalized values |
| Rerank with multiple documents | Not covered | Only tests single document |
| VLM 503 when service None | Covered | `test_vlm_not_available` |
| VLM 400 when no image | Covered | `test_vlm_extract_text_only_returns_400` |
| VLM with multi-image messages | Not covered | Would expose I4 |
| VLM MinerUClient error handling | Not covered | Would expose I5 |
| chat.py legacy endpoint | Not covered | No tests exist for `/v1/chat/completions_legacy` |
| `_build_pages` with malformed page data | Not covered | Would expose I3 |
| `vllm_gpu_memory_utilization` bounds validation | Not covered | No test for values outside [0.0, 1.0] |

---

## Checklist

- [ ] B1: Rename `LLMService` → `VLMService` or plan a future LLM service separately
- [ ] B2: Resolve `chat.py` vs `vlm.py` endpoint duplication
- [ ] B3: Conditionally include `vlm.router` and `chat.router`
- [ ] I1: Replace `dict[str, Any]` return type on `infer()`
- [ ] I2: Type `VLMExtractRequest.messages` with proper Pydantic models
- [ ] I3: Add explicit validation in `_build_pages`
- [ ] I4: Enforce single-image or handle multi-image in `/v1/chat/completions`
- [ ] I5: Add error handling around `MinerUClient.two_step_extract()`
- [ ] N1: Make `hf_home` configurable via env var
- [ ] N2: Verify `MinerULogitsProcessor` usage (class vs. instance)
- [ ] N3: Add conftest.py with `sys.path` setup for tests
- [ ] Add tests for: multi-document rerank, VLM error handling, `_build_pages` edge cases
