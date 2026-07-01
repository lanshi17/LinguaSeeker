# Semantic Word Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-07-01
**Completed:** 2026-07-01
**PR:** N/A

**Goal:** Add semantic word/phrase span-pair alignment between original-language blocks and English translations, with deterministic fallback and frontend linked hover/click behavior.

**Architecture:** Extend `TranslationAlignmentChunk` with nested `TranslationSpanPair` records. Generate span pairs per translated chunk through a bounded JSON alignment provider, validate offsets before persistence, fallback to deterministic token alignment, then consume span pairs in traceback and bilingual readers.

**Tech Stack:** FastAPI backend, Pydantic contracts, pytest, Vite + React + TypeScript + Antd frontend, Vitest/Testing Library, existing LLM JSON invocation utilities.

**Progress:** Tasks 1-9 completed on 2026-07-01.

---

### Task 1: Add Typed Alignment Contracts `[completed]`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py`

**Step 1: Write the failing contract tests**

Create tests for:

- `TranslationSpanPair` serializes with `method="semantic_llm"`.
- `TranslationAlignmentChunk.model_validate()` accepts old payloads without `span_pairs`.
- Invalid method values fail validation.

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py -v
```

Expected: fails because `TranslationSpanPair` does not exist.

**Step 2: Implement contracts**

Add `TranslationSpanPair` as a Pydantic `BaseModel` and add:

```python
span_pairs: list[TranslationSpanPair] = Field(default_factory=list)
```

to `TranslationAlignmentChunk`.

**Step 3: Verify**

Run the same pytest command. Expected: pass.

### Task 2: Build Span Pair Validation and Fallback `[completed]`

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/alignment.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py`

**Step 1: Write failing tests**

Cover:

- Valid copied text pairs are converted to full-document offsets.
- Pairs whose copied text is not found are dropped.
- Overlapping non-duplicate pairs are dropped.
- Chinese/English fallback emits non-empty monotonic pairs for Rett-like text.

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py -v
```

Expected: fails because `alignment.py` does not exist.

**Step 2: Implement minimal validation helpers**

Implement:

- `RawAlignmentPair` dataclass or Pydantic model for provider output.
- `validate_span_pairs(chunk, raw_pairs) -> list[TranslationSpanPair]`.
- `build_fallback_span_pairs(chunk) -> list[TranslationSpanPair]`.

Use full-document offsets from the chunk and locate copied text inside `chunk.original_text` / `chunk.english_text`.

**Step 3: Verify**

Run the same pytest command. Expected: pass.

### Task 3: Generate Semantic Alignment Per Chunk `[completed]`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/alignment.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py`

**Step 1: Write failing async tests**

Use monkeypatch to fake JSON LLM output and assert:

- semantic JSON pairs become `method="semantic_llm"`;
- invalid JSON falls back to `method="deterministic_token"`;
- provider failure does not raise for the whole translation.

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py -v
```

Expected: fails because no generator is wired.

**Step 2: Implement generator**

Add an async helper such as:

```python
async def generate_chunk_span_pairs(json_llm, chunk, source_language, stage) -> list[TranslationSpanPair]:
    ...
```

It should:

- skip very short chunks and use fallback;
- call `invoke_json_with_retry`;
- parse `{"pairs": [...]}`;
- validate pairs;
- fallback when semantic output is unusable.

**Step 3: Wire into translation result construction**

Keep the call after block/segment translations are known and before persistence builds alignment chunks. Prefer storing raw per-segment pair lists on `TranslationSegment` or generating inside `_build_translation_alignment()` through a prepared helper output. Avoid new global state.

**Step 4: Verify**

Run translation alignment tests. Expected: pass.

### Task 4: Persist Span Pairs in Translation Alignment `[completed]`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/persistence.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_persistence.py` or new focused alignment test

**Step 1: Write failing persistence test**

Build a `TranslationResult` with one segment and known span pairs. Assert `_build_translation_alignment()` returns one chunk whose nested pairs have full-document offsets and survive `model_dump()`.

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py -v
```

Expected: fails because `_build_translation_alignment()` does not include pairs.

**Step 2: Implement persistence mapping**

Ensure the chunk keeps `span_pairs` and that offsets are full-document offsets. If pairs are stored block-local before this point, convert them here.

**Step 3: Verify**

Run focused tests. Expected: pass.

### Task 5: Use Span Pairs for Narrow Traceback `[completed]`

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/translation_traceback.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_translation_traceback.py`

**Step 1: Write failing traceback test**

Create a chunk with:

- whole original chunk: long Chinese paragraph;
- whole English chunk: long English paragraph;
- span pair for `c.194delC` / `c.194delC`;
- source location in English offsets that falls inside the English pair.

Assert mapped raw source points only to the original pair span, not the whole paragraph.

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_translation_traceback.py -v
```

Expected: fails because traceback returns the whole chunk.

**Step 2: Implement pair selection**

Add helper:

```python
def _select_alignment_pair(chunk, source) -> TranslationSpanPair | None:
    ...
```

Use pair offsets when the English source range intersects or is contained by a pair. Fall back to current whole-chunk mapping if no pair matches.

**Step 3: Verify**

Run traceback tests. Expected: pass.

### Task 6: Expose Span Pairs Through API and Frontend Types `[completed]`

**Files:**
- Modify: backend API schemas that serialize evidence detail translation alignment, if they do not already pass through `model_dump()`.
- Modify: `frontend/src/features/evidence-search/types/evidenceSearch.ts`
- Test: relevant backend API tests and frontend type-check.

**Step 1: Write type-level/frontend fixture test**

Add `span_pairs` to an evidence detail fixture and assert TypeScript accepts it.

Run:

```bash
cd frontend
bun run type-check
```

Expected: fails before type update.

**Step 2: Update types**

Add:

```ts
export interface TranslationSpanPair { ... }
span_pairs?: TranslationSpanPair[];
```

to the translation alignment type.

**Step 3: Verify**

Run `bun run type-check`. Expected: pass.

### Task 7: Add Linked Reader Interaction `[completed]`

**Files:**
- Modify: `frontend/src/features/evidence-search/components/BilingualCompareView.tsx`
- Modify: `frontend/src/features/evidence-db/components/BilingualEvidenceView.tsx`
- Modify: shared document reader/highlight utilities as needed.
- Test: frontend tests under `frontend/tests/`.

**Step 1: Write failing interaction tests**

Use a detail fixture with one original paragraph, one English paragraph, and two span pairs. Assert:

- hovering original pair adds a linked highlight in English paragraph;
- hovering English pair adds a linked highlight in original paragraph;
- clicking pins the pair;
- no `span_pairs` preserves current rendering.

Run:

```bash
cd frontend
bun run test -- Bilingual
```

Expected: fails before UI wiring.

**Step 2: Implement span index builder**

Build a shared utility that converts full-document alignment pairs into reader paragraph offsets. Keep it separate from evidence-value highlighting so evidence colors remain primary.

**Step 3: Implement hover/click state**

Add linked span state at bilingual view level and pass it into both readers. Use existing highlight rendering where possible; add a secondary alignment highlight style only when needed.

**Step 4: Verify**

Run focused frontend tests and `bun run type-check`.

### Task 8: Integration Verification `[completed]`

**Files:**
- Existing backend/frontend files only.

**Step 1: Run backend checks**

```bash
cd backend
uv run ruff check
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translation_alignment.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_translation_traceback.py \
  tests/core/cross_lingual_process_and_extract_evidence/test_validator.py \
  tests/core/cross_lingual_process_and_extract_evidence/test_translator.py \
  tests/core/cross_lingual_process_and_extract_evidence/test_round2_fixes.py \
  tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py
```

Expected: all pass.

**Step 2: Run frontend checks**

```bash
cd frontend
bun run type-check
bun run test
```

Expected: all pass, unless pre-existing unrelated frontend changes fail; document any such failures with exact output.

**Step 3: Manual smoke**

Run the app stack, open a bilingual evidence detail with span pairs, and verify hover/click links both panes. Use Playwright if the frontend test environment supports it.

### Task 9: Documentation and Progress `[completed]`

**Files:**
- Modify: `progress.txt`
- Modify: `lesson.md` only if debugging or failed iterations occurred.
- Modify: module README only if this becomes a completed backend module feature.

**Step 1: Update progress**

Append:

```text
[2026-07-01] [backend/frontend] Implemented semantic word-level original-English span alignment with deterministic fallback and bilingual reader linked hover/click. [completed]
```

**Step 2: Organize docs**

Run doc organization after docs change, keeping this plan in `docs/active/` while implementation is in progress and archiving it only after completion.

**Step 3: Final verification**

Re-run the commands from Task 8 before claiming completion.
