# Fix Translation Token Limit & MinerU Parsing

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix `MultiStageTranslator` so all pipeline stages handle documents exceeding qwen-mt-flash's 8192 token limit, and ensure MinerU parsing works end-to-end.

**Architecture:** Add segment-and-merge logic to `extract_terminology`, `plan_structure`, `polish`, and `review` stages in `MultiStageTranslator`, mirroring the existing `translate_segments` pattern. For MinerU, fix proxy configuration and ensure model-server VLM endpoint is available.

**Tech Stack:** Python, LangChain, OpenAI SDK, qwen-mt-flash, MinerU API

---
**Status:** completed
**Created:** 2026-05-15
**Completed:** 2026-05-15
**PR:** merged

## Problem Analysis

### Issue 1: Translation 8192 Token Limit

`MultiStageTranslator` has 6 stages. Only `translate_segments` (draft) segments text before sending to LLM. The other 5 stages send the full document, which fails when content exceeds 8192 tokens:

| Stage | Method | Segmented? | Error |
|-------|--------|------------|-------|
| terminology | `extract_terminology()` | No | `Range of input length should be [1, 8192]` |
| structure | `plan_structure()` | No | Same |
| draft | `translate_segments()` | Yes (8192 tokens) | Works |
| polish | `polish()` | No | Same |
| review | `review()` | No | Same |

**Root cause:** `get_terminology_prompt()`, `get_structure_prompt()`, `get_polish_prompt()`, `get_review_prompt()` embed the full document text without segmentation.

### Issue 2: MinerU Remote Network Failure

MinerU API calls fail with `error sending request for url (https://mineru.net/api/v4/...)`. Likely cause: missing HTTP proxy configuration for external API calls.

### Issue 3: MinerU Local 404

Model-server returns 404 for `/v1/chat/completions`. The VLM service is not loaded because `VLM_MODEL_ID` is not configured in model-server's environment.

---

## Task 1: Fix `extract_terminology` Segmentation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py:118-122`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py
"""Tests for MultiStageTranslator segmentation in all stages."""
import pytest
from unittest.mock import MagicMock, patch

from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import MultiStageTranslator
from src.core.cross_lingual_process_and_extract_evidence.contracts import FormattedDocument


@pytest.fixture
def large_document():
    """Create a document that exceeds 8192 tokens (~32000 chars of CJK)."""
    # CJK chars are ~1 token each, so 10000 chars ≈ 10000 tokens
    text = "这是一段测试文本。" * 1200  # ~10800 chars ≈ 10800 tokens
    return FormattedDocument(
        formatted_markdown=text,
        source_language="zh",
    )


@pytest.fixture
def mock_translator():
    """Create a translator with mocked LLM."""
    ctx = MagicMock()
    ctx.model = "test-model"
    ctx.api_key = "test-key"
    ctx.base_url = "http://test"
    ctx.temperature = 0.0

    with patch("src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator.ChatOpenAI"):
        translator = MultiStageTranslator(ctx=ctx)

    # Mock _invoke_with_retry to return simple responses
    translator._invoke_with_retry = MagicMock(side_effect=lambda prompt, stage: f"result_for_{stage}")
    return translator


def test_extract_terminology_handles_large_document(mock_translator, large_document):
    """extract_terminology should not fail on documents exceeding 8192 tokens."""
    result = mock_translator.extract_terminology(large_document)
    assert result is not None
    assert "result_for_terminology" in result


def test_plan_structure_handles_large_document(mock_translator, large_document):
    """plan_structure should not fail on documents exceeding 8192 tokens."""
    result = mock_translator.plan_structure(large_document)
    assert result is not None
    assert "result_for_structure" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py -v`
Expected: FAIL with `Range of input length should be [1, 8192]` or similar

**Step 3: Implement segmentation for `extract_terminology`**

Modify `extract_terminology` to segment the document, extract terminology from each segment, then merge:

```python
def extract_terminology(self, formatted: FormattedDocument) -> str:
    logger.info("Stage: terminology")
    text = formatted.formatted_markdown
    overhead = estimate_tokens(get_terminology_prompt(""))
    segments = segment_text(text, max_tokens=8192, prompt_overhead_tokens=overhead)

    if len(segments) <= 1:
        return self._invoke_with_retry(
            get_terminology_prompt(text), "terminology",
        )

    all_terms: list[str] = []
    for idx, segment in enumerate(segments, start=1):
        prompt = get_terminology_prompt(segment)
        terms = self._invoke_with_retry(prompt, f"terminology/{idx}")
        all_terms.append(terms)
        logger.info("Terminology segment {}/{} done", idx, len(segments))

    # Merge: deduplicate by keeping unique source:target pairs
    merged = "\n".join(all_terms)
    seen: set[str] = set()
    unique_lines: list[str] = []
    for line in merged.splitlines():
        key = line.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique_lines.append(line.strip())
    return "\n".join(unique_lines)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_extract_terminology_handles_large_document -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git add backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py
git commit -m "fix: segment extract_terminology to handle documents exceeding 8192 tokens"
```

---

## Task 2: Fix `plan_structure` Segmentation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py:124-128`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py`

**Step 1: Add test for `plan_structure`**

```python
def test_plan_structure_segments_and_merges(mock_translator, large_document):
    """plan_structure should segment, process, and merge results."""
    # Track how many times _invoke_with_retry is called
    call_count = [0]
    original_side_effect = mock_translator._invoke_with_retry.side_effect

    def counting_side_effect(prompt, stage):
        call_count[0] += 1
        return original_side_effect(prompt, stage)

    mock_translator._invoke_with_retry.side_effect = counting_side_effect
    result = mock_translator.plan_structure(large_document)

    # Should be called multiple times (once per segment)
    assert call_count[0] > 1
    assert result is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_plan_structure_segments_and_merges -v`
Expected: FAIL (called only once, not segmented)

**Step 3: Implement segmentation for `plan_structure`**

```python
def plan_structure(self, formatted: FormattedDocument) -> str:
    logger.info("Stage: structure")
    text = formatted.formatted_markdown
    overhead = estimate_tokens(get_structure_prompt(""))
    segments = segment_text(text, max_tokens=8192, prompt_overhead_tokens=overhead)

    if len(segments) <= 1:
        return self._invoke_with_retry(
            get_structure_prompt(text), "structure",
        )

    plans: list[str] = []
    for idx, segment in enumerate(segments, start=1):
        prompt = get_structure_prompt(segment)
        plan = self._invoke_with_retry(prompt, f"structure/{idx}")
        plans.append(plan)
        logger.info("Structure segment {}/{} done", idx, len(segments))

    # Merge: concatenate structure plans
    merged = "\n\n".join(plans)

    # Final consolidation pass if merged result is still within limits
    if estimate_tokens(merged) < 6000:
        consolidation_prompt = (
            "CONSOLIDATE_STRUCTURE\n"
            "Merge the following structure plans into one coherent plan:\n\n"
            f"{merged}"
        )
        return self._invoke_with_retry(consolidation_prompt, "structure/consolidate")

    return merged
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_plan_structure_segments_and_merges -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "fix: segment plan_structure to handle documents exceeding 8192 tokens"
```

---

## Task 3: Fix `polish` Segmentation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py:146-150`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py`

**Step 1: Add test for `polish`**

```python
def test_polish_handles_large_draft(mock_translator):
    """polish should segment large drafts before sending to LLM."""
    large_draft = "This is a translated sentence. " * 2000  # ~60000 chars
    terminology = "gene: 基因\nprotein: 蛋白质"

    call_count = [0]
    original_side_effect = mock_translator._invoke_with_retry.side_effect

    def counting_side_effect(prompt, stage):
        call_count[0] += 1
        return original_side_effect(prompt, stage)

    mock_translator._invoke_with_retry.side_effect = counting_side_effect
    result = mock_translator.polish(large_draft, terminology)

    assert call_count[0] > 1
    assert result is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_polish_handles_large_draft -v`
Expected: FAIL

**Step 3: Implement segmentation for `polish`**

```python
def polish(self, draft: str, terminology: str) -> str:
    logger.info("Stage: polish")
    if not draft:
        return ""

    overhead = estimate_tokens(get_polish_prompt("", terminology))
    segments = segment_text(draft, max_tokens=8192, prompt_overhead_tokens=overhead)

    if len(segments) <= 1:
        return self._invoke_with_retry(get_polish_prompt(draft, terminology), "polish") or draft

    polished_parts: list[str] = []
    for idx, segment in enumerate(segments, start=1):
        prompt = get_polish_prompt(segment, terminology)
        polished = self._invoke_with_retry(prompt, f"polish/{idx}")
        polished_parts.append(polished or segment)
        logger.info("Polish segment {}/{} done", idx, len(segments))

    return "\n\n".join(polished_parts)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_polish_handles_large_draft -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "fix: segment polish to handle documents exceeding 8192 tokens"
```

---

## Task 4: Fix `review` Segmentation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py:152-156`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py`

**Step 1: Add test for `review`**

```python
def test_review_handles_large_documents(mock_translator):
    """review should segment large source+translated pairs."""
    large_source = "这是源文档。" * 2000
    large_translated = "This is translated. " * 2000

    call_count = [0]
    original_side_effect = mock_translator._invoke_with_retry.side_effect

    def counting_side_effect(prompt, stage):
        call_count[0] += 1
        return original_side_effect(prompt, stage)

    mock_translator._invoke_with_retry.side_effect = counting_side_effect
    result = mock_translator.review(large_source, large_translated)

    assert call_count[0] > 1
    assert result is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_review_handles_large_documents -v`
Expected: FAIL

**Step 3: Implement segmentation for `review`**

```python
def review(self, source: str, translated: str) -> str:
    logger.info("Stage: review")
    if not translated:
        return ""

    # Review needs both source and translated, so budget is split
    overhead = estimate_tokens(get_review_prompt("", ""))
    max_per_part = (8192 - overhead) // 2

    source_segments = segment_text(source, max_tokens=max_per_part)
    translated_segments = segment_text(translated, max_tokens=max_per_part)

    # If either needs segmentation, review segment-by-segment
    if len(source_segments) <= 1 and len(translated_segments) <= 1:
        return self._invoke_with_retry(
            get_review_prompt(source, translated), "review",
        )

    # Align segments (use zip, review shorter set)
    max_pairs = max(len(source_segments), len(translated_segments))
    reviews: list[str] = []
    for idx in range(max_pairs):
        src = source_segments[idx] if idx < len(source_segments) else ""
        tgt = translated_segments[idx] if idx < len(translated_segments) else ""
        if not src or not tgt:
            continue
        prompt = get_review_prompt(src, tgt)
        review = self._invoke_with_retry(prompt, f"review/{idx + 1}")
        reviews.append(review)
        logger.info("Review segment {}/{} done", idx + 1, max_pairs)

    return "\n\n".join(reviews)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_review_handles_large_documents -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "fix: segment review to handle documents exceeding 8192 tokens"
```

---

## Task 5: Integration Test — Full Pipeline with Large Document

**Files:**
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py`

**Step 1: Write integration test**

```python
def test_run_pipeline_with_large_document(mock_translator, large_document):
    """Full pipeline should complete without token limit errors."""
    # Mock all stages to return simple results
    mock_translator._invoke_with_retry = MagicMock(
        side_effect=lambda prompt, stage: f"result_for_{stage}"
    )

    # Should not raise
    terminology_map, structure_plan, draft, translated, segments, warnings = (
        mock_translator.run_pipeline(large_document)
    )

    assert terminology_map is not None
    assert translated is not None
```

**Step 2: Run test**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py::test_run_pipeline_with_large_document -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py
git commit -m "test: add integration test for full pipeline with large documents"
```

---

## Task 6: Fix MinerU Proxy Configuration

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py` (add proxy support)
- Or: Configure proxy in environment

**Step 1: Check if proxy is needed**

```bash
curl -v --connect-timeout 5 https://mineru.net/api/v4 2>&1 | grep -i "connect\|proxy\|error"
```

**Step 2: If proxy needed, add proxy to MinerU API calls**

The `MinerUParser` uses `rust_io.net` for API calls. Check if it supports proxy:

```bash
grep -r "proxy" backend/libs/net-io/src/ | head -10
```

**Step 3: Configure proxy in `.env.local` if needed**

```bash
# Add to .env.local if proxy is required
HTTP_PROXY="http://127.0.0.1:7890"
HTTPS_PROXY="http://127.0.0.1:7890"
```

**Step 4: Test MinerU remote connectivity**

```bash
cd backend && uv run python -c "
import asyncio
from src.core.config import get_config
from src.core.ingest_and_digitize_data.parse_document.mineru_parser import MinerUParser

async def test():
    cfg = get_config()
    parser = MinerUParser(api_token=cfg.mineru.api_token)
    # Test with a small PDF
    result = await parser.parse_local_files(
        file_paths=['downloads/ja/52_26.pdf'],
        model_version='vlm',
    )
    print(f'Success: {len(result.results)} results')

asyncio.run(test())
"
```

**Step 5: Commit**

```bash
git commit -m "fix: configure proxy for MinerU API access"
```

---

## Task 7: Fix Model-Server VLM Endpoint

**Files:**
- Modify: `backend/services/model-server/.env.local` or startup config

**Step 1: Check if VLM model is available locally**

```bash
ls ~/.cache/huggingface/hub/models--opendatalab--MinerU2.5-Pro-2604-1.2B 2>/dev/null
```

**Step 2: Configure model-server to load VLM**

Add to `backend/services/model-server/.env.local`:

```bash
VLM_MODEL_ID="opendatalab/MinerU2.5-Pro-2604-1.2B"
```

**Step 3: Restart model-server**

```bash
# Kill existing
pkill -f "model-server"

# Start with VLM
cd backend/services/model-server
uv run python main.py &
```

**Step 4: Test VLM endpoint**

```bash
curl -s http://localhost:8001/v1/chat/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"model":"opendatalab/MinerU2.5-Pro-2604-1.2B","messages":[{"role":"user","content":"test"}]}'
```

**Step 5: Commit**

```bash
git commit -m "fix: enable VLM model in model-server configuration"
```

---

## Task 8: End-to-End Test

**Files:**
- Script: `scripts/parse_and_translate.py`

**Step 1: Clear previous output**

```bash
rm -rf backend/output/*
```

**Step 2: Run the full pipeline**

```bash
cd backend && uv run python ../scripts/parse_and_translate.py 2>&1
```

**Step 3: Verify output structure**

```bash
find backend/output -type f | sort
```

Expected output per PDF:
```
output/<language>/<doc_id>/output.md          # MinerU parsed
output/<language>/<doc_id>/metadata.json      # Parse metadata
output/<language>/<doc_id>/images/            # Extracted images
output/<language>/<doc_id>/original.md        # Formatted source
output/<language>/<doc_id>/translated.md      # English translation
```

**Step 4: Verify translation quality**

```bash
# Check a translated file
head -50 output/zh/法布雷病1例/translated.md
```

**Step 5: Commit**

```bash
git add scripts/parse_and_translate.py
git commit -m "feat: end-to-end parse and translate pipeline"
```

---

## Verification Checklist

- [ ] All unit tests pass: `uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py -v`
- [ ] MinerU remote parsing works (or local fallback works)
- [ ] Translation completes without 8192 token errors
- [ ] Output contains `original.md` (formatted source language)
- [ ] Output contains `translated.md` (English translation)
- [ ] Output contains `images/` directory with extracted images
- [ ] All 9 PDFs processed successfully
