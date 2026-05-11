# Code Review: MinerU VLM + vllm Migration — Pass 3

**Branch:** `feat/mineru-vlm-vllm-migration`  
**Commit:** `91dfe184` (fix: apply pass-2 code review)  
**Plan:** `docs/planned/2026-05-11-mineru-vlm-vllm-migration.md`  
**Reviewer:** Staff Engineer  
**Date:** 2026-05-11

---

## Pass-2 Resolution Summary

| Issue | Status | Notes |
|-------|--------|-------|
| B1: `LLMService` misnamed | ✅ Fixed | Renamed to `VLMService` in `app/domain/vlm.py` |
| B2: `chat.py` zombie endpoint | ✅ Fixed | `chat.py` deleted entirely |
| B3: `vlm.router` always included | ✅ Fixed | `if _vlm_svc:` guard added in `main.py` |
| I1: Bare `dict` return | ✅ Fixed | `VLMInferResult` dataclass added |
| I2: `messages: list[dict]` | ✅ Fixed | `VLMMessage`, `VLMContentPart`, `VLMImageUrl` typed models |
| I3: Raw dict → typed coercion | ✅ Fixed | `_parse_figure`/`_parse_table` with `model_validate` |
| I4: Only `images[0]` used | ✅ Fixed | Multi-image → 400 error |
| I5: No error handling | ✅ Fixed | `VLMInferenceError` + try/except in `vlm.py` domain |
| N1: Hardcoded `hf_home` | ✅ Fixed | Now `os.path.expanduser("~/.cache/huggingface/hub")` |
| N2: `MinerULogitsProcessor` class | ✅ Confirmed | Comment added: "vllm accepts logits processor classes" |
| N3: `conftest.py` needed | ✅ Fixed | `sys.path` setup in `tests/conftest.py` |
| Test gaps (error handling, multi-image) | ✅ Fixed | 2 new tests: `test_vlm_multi_image_returns_400`, `test_vlm_service_infer_error_handling` |

All 12 pass-2 issues resolved. 18 tests passing.

---

## Decision: 💬 Comment — minor suggestions only, no blockers

The pass-2 issues are all correctly addressed. The remaining items are polish-level.

---

## 🟡 Important

### I1. `VLMInferResult.pages: list[dict]` and `metadata: dict` — bare dicts inside the dataclass

**File:** `backend/services/model-server/app/domain/vlm.py:17-23`

```python
@dataclass
class VLMInferResult:
    id: str
    full_markdown: str
    pages: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=lambda: {"total_pages": 1})
```

The outer return type is now properly typed (dataclass instead of bare dict), but the inner fields `pages` and `metadata` are still bare dicts. Since these come from `MinerUClient.two_step_extract()` which returns opaque upstream data, this is defensible — but a TypedDict for the page dict shape would make downstream consumers safer.

**Suggested fix:** Define `class MinerUPageDict(TypedDict, total=False): page_number: int; markdown: str; figures: list[dict]; tables: list[dict]` and use it for `pages`. Document that `metadata` is opaque upstream data (`# noqa: dict-return`).

### I2. `VLMExtractResponse.choices: list[dict]` — still bare dict

**File:** `backend/services/model-server/app/models/schemas.py`

```python
choices: list[dict] = Field(default_factory=list)
```

The plan describes this as an OpenAI-compatible field. If it's intentionally a passthrough for future OpenAI-compatible choice objects, add a `# noqa: dict-return` comment explaining why. Otherwise, define a proper `VLMChoice` model.

### I3. `_extract_images_from_messages` input type is unannotated `list`

**File:** `backend/services/model-server/app/api/vlm.py:33`

```python
def _extract_images_from_messages(messages: list) -> list[Image.Image]:
```

Since `VLMExtractRequest.messages` is now `list[VLMMessage]`, the parameter should be `list[VLMMessage]`.

### I4. `_extract_images_from_messages` uses defensive `hasattr`/`get` pattern on Pydantic models

**File:** `backend/services/model-server/app/api/vlm.py:36-49`

```python
content = msg.content if hasattr(msg, "content") else msg.get("content", "")
part_type = part.type if hasattr(part, "type") else part.get("type")
```

Since messages are now always `VLMMessage` (Pydantic models via `VLMExtractRequest` validation), these fallback branches will never execute. This creates dead code that a future maintainer might wonder about. The code works correctly — the dead branches are harmless — but direct attribute access (`msg.content`, `part.type`, `part.image_url.url`) would be clearer and remove the `list` annotation ambiguity.

**Suggested fix:** Replace with direct attribute access since the Pydantic models guarantee the shape.

---

## 🟢 Nits

### N1. `_parse_figure` / `_parse_table` catch bare `Exception`

**File:** `backend/services/model-server/app/api/vlm.py:59, 68`

```python
except Exception as exc:
```

Catching `Exception` broadly is acceptable here since the intent is "any validation failure → 502", but consider catching `ValidationError` specifically so genuine bugs (e.g. `AttributeError`, `TypeError`) still surface as 500s rather than being silently converted to 502s.

### N2. `chat_completions` function catches bare `Exception` and converts to 500

**File:** `backend/services/model-server/app/api/vlm.py:96-99`

```python
try:
    result = _service.infer(image=images[0])
except Exception as exc:
    logger.error("VLM inference failed: {exc}", exc=exc)
    raise HTTPException(status_code=500, detail=f"VLM inference failed: {exc}") from exc
```

This catches `VLMInferenceError` (domain-level) but also any other unexpected exception. That's reasonable for a top-level route handler, but if `_service.infer` raises `VLMInferenceError`, consider using a 502 (Bad Gateway — upstream failure) instead of 500. The domain-level error was meant to separate "our bug" (500) from "upstream failure" (502). Currently both map to 500.

### N3. `ChatMessage` / `ChatRequest` / `ChatResponse` remain in schemas but no API consumes them

**File:** `backend/services/model-server/app/models/schemas.py:77-107`

With `chat.py` deleted, these schemas (`ChatMessage`, `ChatRequest`, `ChatChoice`, `ChatUsage`, `ChatResponse`) are orphaned. They serve as documentation for a future LLM chat endpoint. That's fine — leave them — but consider adding a comment noting they're placeholders for a future Task 10 LLM service, to prevent someone from deleting them as dead code.

---

## 📚 What's Good

- **All 12 pass-2 issues resolved** — clean closures on every blocking and important item
- **18 tests passing** with 2 new tests covering previously uncovered edge cases (multi-image rejection, error handling)
- **`VLMInferResult` dataclass** is a clean replacement for bare dict returns — idiomatic Python
- **`VLMMessage`/`VLMContentPart`/`VLMImageUrl`** typed models are well-designed — they mirror the OpenAI multimodal format cleanly
- **`_parse_figure`/`_parse_table`** with `model_validate` + explicit 502 errors is the right approach for upstream data validation
- **`conftest.py`** with `sys.path` setup removes the `PYTHONPATH=.` manual step — tests now run from any cwd
- **`chat.py` deletion** is the right call — no deprecated zombie endpoints
- **Conditional router registration** in `main.py` keeps the OpenAPI surface clean
- **`VLMInferenceError`** domain exception separates upstream failures from internal bugs

---

## Checklist

- [ ] I1: Consider TypedDict for `VLMInferResult.pages` shape
- [ ] I2: Type or annotate `VLMExtractResponse.choices: list[dict]`
- [ ] I3: Annotate `_extract_images_from_messages(messages: list[VLMMessage])`
- [ ] I4: Simplify `_extract_images_from_messages` to direct attribute access (remove dead `hasattr`/`get` branches)
- [ ] N1: Narrow `_parse_figure`/`_parse_table` exception catch to `ValidationError`
- [ ] N2: Map `VLMInferenceError` to 502 in route handler
- [ ] N3: Add placeholder comment on orphaned `Chat*` schemas
