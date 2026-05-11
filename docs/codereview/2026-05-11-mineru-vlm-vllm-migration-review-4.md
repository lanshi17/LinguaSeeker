# Code Review: MinerU VLM + vllm Migration — Pass 4

**Branch:** `feat/mineru-vlm-vllm-migration`  
**Commit:** `014ddd35` (fix: apply pass-3 review)  
**Plan:** `docs/planned/2026-05-11-mineru-vlm-vllm-migration.md`  
**Reviewer:** Staff Engineer  
**Date:** 2026-05-11

---

## Pass-3 Resolution Summary

| Issue | Status | Notes |
|-------|--------|-------|
| I1: `VLMInferResult.pages: list[dict]` | ✅ Fixed | `MinerUPageDict` TypedDict added; `metadata` field annotated with rationale |
| I2: `VLMExtractResponse.choices: list[dict]` | ✅ Fixed | Comment: "OpenAI-compatible passthrough — choice object shape not yet finalized" |
| I3: `_extract_images_from_messages(messages: list)` | ✅ Fixed | Now `list[VLMMessage]` |
| I4: Dead `hasattr`/`get` fallback branches | ✅ Fixed | Direct attribute access (`msg.content`, `part.type`, `part.image_url.url`) |
| N1: Broad `Exception` → `ValidationError` | ✅ Fixed | `_parse_figure`/`_parse_table` now catch `ValidationError` specifically |
| N2: `VLMInferenceError` → 502 | ✅ Fixed | Separate catch: `VLMInferenceError` → 502, `Exception` → 500 |
| N3: Orphaned `Chat*` schemas | ✅ Fixed | Comment: "placeholder for future local LLM — Task 10. These schemas are reserved…" |

All 7 pass-3 issues resolved. 18 tests passing. Ruff lint clean.

---

## Decision: ✅ Approve

No remaining issues. The branch is clean, well-typed, properly tested, and all prior review feedback has been addressed end-to-end across 3 rounds.

---

## Final State Summary

### Files changed (cumulative)
```
app/config.py              +3  (vlm_model_id, vlm_image_analysis, vllm_gpu_memory_utilization)
app/domain/base.py         +1  (gpu_memory_utilization param, removed _require_cuda)
app/domain/embedding.py    ~   (migrated to vllm task="embed")
app/domain/rerank.py       ~   (migrated to vllm task="score")
app/domain/vlm.py          NEW (VLMService + MinerUClient + VLMInferResult dataclass)
app/api/vlm.py             NEW (/v1/chat/completions multimodal endpoint)
app/api/chat.py            DEL (functionality subsumed by vlm.py)
app/models/schemas.py      +70 (VLMMessage, VLMContentPart, VLMImageUrl, VLMExtractRequest/Response, etc.)
app/models/__init__.py     +6  (VLM exports)
app/enums/model_type.py    +1  (VLM enum value)
main.py                    ~   (VLMService wiring, conditional router)
config.py                  ~   (hf_home via os.path.expanduser)
tests/conftest.py          NEW (sys.path setup)
tests/test_config.py       +18 (VLM config tests)
tests/test_embedding_vllm.py +32
tests/test_rerank_vllm.py  +20
tests/test_vlm_schemas.py  +51
tests/test_vlm_service.py  +55 (init, load, infer, error handling)
tests/test_vlm_api.py      +75 (text-only 400, image 200, multi-image 400, 503)
tests/test_main_wiring.py  +4
pyproject.toml             +2  (vllm>=0.10.1, mineru_vl_utils)
```

### Architecture verification
- [x] Embedding → vllm `task="embed"` + `model.embed()`
- [x] Rerank → vllm `task="score"` + `model.score()`
- [x] VLM → vllm LLM + `MinerUClient(backend="vllm-engine")`
- [x] Each service holds independent vllm.LLM instance
- [x] `VLLM_GPU_MEMORY_UTILIZATION` shared across all services
- [x] `/v1/chat/completions` accepts OpenAI multimodal format (text + base64 image)
- [x] Returns structured `VLMExtractResponse` with pages, figures, tables
- [x] VLM router conditionally registered (only when `VLM_MODEL_ID` is set)
- [x] Multi-image requests → 400
- [x] Upstream MinerU failures → 502 via `VLMInferenceError`
- [x] Internal failures → 500
- [x] Figure/table validation → 502 via `model_validate`
- [x] Health check includes VLM status
- [x] Type-safe schemas (Pydantic models for messages, TypedDict for internal page data)
- [x] Config via env vars with sensible defaults

### Test coverage
- [x] Config defaults and env var loading
- [x] Embedding service init + infer (mocked vllm)
- [x] Rerank service infer (mocked vllm)
- [x] VLM service init, load, infer, error handling
- [x] VLM API: text-only → 400, image → 200, multi-image → 400, no-service → 503
- [x] VLM schemas: text-only and multimodal request, page content, response
- [x] Main wiring importability
