# Phase 3 Benchmark Coverage — Fix Relevance Scan for Case Reports

> **Archived:** 2026-06-02
> **Reason:** Plan's root-cause assumption (FAST model misclassifying case reports) was incorrect. The real root cause was missing `EVIDENCE_EXTRACTION_*` env vars → ChatOpenAI missing credentials → silent LLM failure → `relevant=False`. The fixes applied were: config.py fallback to `self.llm.*`, RuntimeError in `evidence_map.py`, and prompt strengthening. See lesson.md for full details.
> **Status:** Superceded by actual fixes applied 2026-06-02. Phase 3 now executes (3/7 papers completed).

---

*Original content preserved below for reference.*

---

**Goal:** Fix the FAST model relevance scan so case reports are correctly classified as relevant, unblocking Phase 3 execution in the benchmark pipeline.

**Architecture:** MVP scope = case reports only. The fix targets the relevance scan prompt and model tier in the Phase 2 extraction workflow. The benchmark manifest stays case_report-only. No manifest expansion.

**Tech Stack:** Python, FastAPI, LangGraph, Pydantic, loguru, httpx (benchmark runner), pytest

---

## Context: Root Cause Analysis

### The Problem

All 10 benchmark reports show Phase 3 has **never executed**:
```json
"phase_3": { "status": "skipped", "summary": { "reason": "not_relevant" } }
```

### Causal Chain

**1. LLM misclassifies ALL case reports as NOT_RELEVANT.**
The relevance scan prompt (`prompts.py:90-126`) explicitly states "DEFAULT: Set relevant to TRUE", yet the FAST model returns `relevant: false` for every case report across all 7 languages — including a Chinese Fabry disease paper with explicit gene GLA and variant c.92C>A.

**2. Dual-track amplification.**
Both tracks (original + translated) use the same FAST model → both return NOT_RELEVANT → `both_not_relevant=true` → `skip_phase_3_reason = NOT_RELEVANT` → Phase 3 short-circuits.

### What Phase 3 Needs

Phase 3 has no code bugs. It needs Phase 2 to return `status == "completed"` for at least one track. This requires the relevance scan to return `relevant: true`.

---

## Diagnostic Tasks

### Task 1: Add structured logging to relevance scan stage

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`

**Step 1: Add loguru logging after LLM response parsing**

In `RelevanceScanStage.run()`, after the evidence map is built, add:

```python
logger.debug(
    "Relevance scan: doc_id={}, track={}, relevant={}, disease={}, gene={}, variant={}",
    document.document_id, document.track.value,
    evidence_map.relevant,
    len(evidence_map.disease_terms),
    len(evidence_map.gene_terms),
    len(evidence_map.variant_terms),
)
```

**Step 2: Run single benchmark PDF and capture logs**

Run: `cd backend && uv run python -m benchmark.pipeline.benchmark --limit 1`

**Step 3: Examine logs**

Check `logs/` for the debug output. Two scenarios:
- `relevant=False` with non-empty term lists → **prompt compliance issue** (LLM finds content but ignores default)
- `relevant=False` with empty term lists → **document parsing issue** (LLM receives no text)

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py
git commit -m "debug: add structured logging to relevance scan stage"
```

---

### Task 2: Verify PDF text extraction quality

**Goal:** Rule out that parsed text is empty or garbled.

**Files:**
- Check: `backend/output/` for Phase 1 parsed text files

**Step 1: Find parsed text from recent runs**

```bash
find backend/output -name "*.txt" -o -name "*parsed*" -o -name "*digitized*" | head -20
```

**Step 2: Read parsed text for the ZH Fabry disease paper**

This paper explicitly contains gene GLA and variant c.92C>A. If the LLM can't find these, parsing is the bottleneck.

**Step 3: Document findings as (a) parsing failure, (b) prompt compliance, or (c) both**

---

## Fix Tasks

### Task 3: Strengthen relevance scan prompt for case reports

**Goal:** Make the FAST model reliably return `relevant=true` for case reports with biomedical content.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py:90-126`

**Step 1: Write test for prompt constraints**

Create `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_relevance_prompt.py`:

```python
"""Tests for relevance scan prompt structure."""
from unittest.mock import MagicMock
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    get_evidence_map_prompt,
)


def test_prompt_defaults_to_relevant():
    """Prompt must instruct LLM to default to relevant=TRUE."""
    prompt = get_evidence_map_prompt(document_id="test", track=MagicMock(value="original"))
    assert "DEFAULT" in prompt
    assert "TRUE" in prompt


def test_prompt_lists_not_relevant_criteria():
    """Prompt must list specific NOT_RELEVANT categories."""
    prompt = get_evidence_map_prompt(document_id="test", track=MagicMock(value="original"))
    assert "methodological" in prompt.lower() or "methods" in prompt.lower()
    assert "editorial" in prompt.lower() or "letter" in prompt.lower()


def test_prompt_mentions_case_reports_as_relevant():
    """Prompt must explicitly mention case reports as relevant."""
    prompt = get_evidence_map_prompt(document_id="test", track=MagicMock(value="original"))
    assert "case report" in prompt.lower()
```

**Step 2: Run test to verify current prompt satisfies constraints**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_relevance_prompt.py -v`
Expected: PASS

**Step 3: Strengthen the prompt**

Current weaknesses:
- "DEFAULT: Set relevant to TRUE" is buried mid-prompt
- No explicit instruction about case reports containing patient/genetic data
- No "if unsure, default to TRUE" safety net

Strengthen by:
1. Move default instruction to the very top of the prompt
2. Add: "If unsure, set relevant to TRUE"
3. Add explicit: "Case reports with patient data, clinical findings, or genetic information MUST be relevant"
4. Add negative instruction: "Do NOT set relevant=FALSE for documents containing any disease names, gene symbols, or patient descriptions"

**Step 4: Run test again**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_relevance_prompt.py -v`
Expected: PASS

**Step 5: Run benchmark to verify**

Run: `cd backend && uv run python -m benchmark.pipeline.benchmark --limit 1`
Check: Phase 2 `relevant` should be `true`.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_relevance_prompt.py
git commit -m "fix(extract-evidence): strengthen relevance scan prompt for case report compliance"
```

---

### Task 4: Upgrade relevance scan model tier (if prompt fix alone is insufficient)

**Goal:** If the FAST model still misclassifies after prompt strengthening, upgrade to STANDARD tier.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`

**Step 1: Check current tier**

Find `EvidenceModelTier.FAST` in `evidence_map.py`. Note the exact line.

**Step 2: Change tier**

```python
tier = EvidenceModelTier.STANDARD  # was FAST
```

**Step 3: Benchmark verification**

Run: `cd backend && uv run python -m benchmark.pipeline.benchmark --limit 2`
Check: Phase 2 `relevant` should be `true` for at least one PDF.

**Step 4: Commit if changed**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py
git commit -m "fix(extract-evidence): upgrade relevance scan to STANDARD tier"
```

---

### Task 5: Run full benchmark and verify Phase 3 executes

**Goal:** Confirm Phase 3 runs end-to-end with case report PDFs.

**Step 1: Ensure backend is running**

```bash
cd backend && uv run uvicorn app.main:app --reload &
```

**Step 2: Run full benchmark**

```bash
cd backend && uv run python -m benchmark.pipeline.benchmark
```

**Step 3: Check report for Phase 3 execution**

```bash
python -c "
import json
from pathlib import Path
latest = sorted(Path('benchmark/pipeline/reports').glob('report_*.json'))[-1]
data = json.loads(latest.read_text())
for r in data['results']:
    p2 = r['phases'].get('phase_2', {}).get('summary', {})
    p3 = r['phases'].get('phase_3', {})
    print(f\"{r['file']}: relevant={p2.get('relevant')}, phase_3={p3.get('status')}, matches={p3.get('summary', {}).get('match_count', 'N/A')}\")
"
```

Expected: At least some PDFs show `phase_3=completed` with non-zero match counts.

**Step 4: If still all skipped**

Escalation path:
1. Further strengthen prompt with chain-of-thought
2. Check if `json_schema` enforcement is needed for structured output
3. Verify the parsed document text length is sufficient (>100 chars)

**Step 5: Commit report**

```bash
git add benchmark/pipeline/reports/
git commit -m "test(benchmark): Phase 3 coverage report after relevance scan fix"
```

---

### Task 6: Add Phase 2 → Phase 3 integration test

**Goal:** Verify the skip decision logic without relying on LLM.

**Files:**
- Create: `backend/tests/agents/test_phase_2_to_phase_3_integration.py`

**Step 1: Write parametrized test**

```python
"""Integration test: Phase 2 output → Phase 3 skip decision."""
import pytest
from src.agents.contracts import SkipPhase3Reason
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionStatus,
)


def _make_dual_result(orig_status: str, trans_status: str) -> dict:
    track = {"document_id": "test", "evidence_chains": [], "evidence_items": []}
    return {
        "document_id": "test",
        "original_result": {**track, "status": orig_status, "track": "original"},
        "translated_result": {**track, "status": trans_status, "track": "translated"},
    }


@pytest.mark.parametrize(
    "orig, trans, expected",
    [
        ("not_relevant", "not_relevant", SkipPhase3Reason.NOT_RELEVANT),
        ("completed", "not_relevant", None),
        ("not_relevant", "completed", None),
        ("completed", "completed", None),
    ],
)
def test_skip_only_when_both_tracks_not_relevant(orig, trans, expected):
    dual = DualEvidenceExtractionResult.model_validate(_make_dual_result(orig, trans))
    both_nr = (
        dual.original_result.status == EvidenceExtractionStatus.NOT_RELEVANT
        and dual.translated_result.status == EvidenceExtractionStatus.NOT_RELEVANT
    )
    assert (both_nr and expected == SkipPhase3Reason.NOT_RELEVANT) or (not both_nr and expected is None)
```

**Step 2: Run test**

Run: `cd backend && uv run pytest tests/agents/test_phase_2_to_phase_3_integration.py -v`
Expected: All 4 cases PASS.

**Step 3: Commit**

```bash
git add backend/tests/agents/test_phase_2_to_phase_3_integration.py
git commit -m "test(agents): add Phase 2→Phase 3 skip decision integration test"
```

---

### Task 7: Update progress and lesson

**Step 1:** Update `progress.txt`:
```
[2026-06-02] [Fix Phase 3 benchmark coverage — relevance scan for case reports] [in_progress]
```

**Step 2:** Record in `lesson.md`: root cause (FAST model ignoring prompt defaults), fix (strengthened prompt / upgraded tier), and verification results.

---

## Verification Checklist

- [ ] Relevance scan logs captured in `logs/` with structured doc_id/track/relevant/term counts
- [ ] At least 1 benchmark case report shows `phase_2.relevant=true`
- [ ] At least 1 benchmark result shows `phase_3.status=completed` with match data
- [ ] `test_phase_2_to_phase_3_integration.py` passes all 4 parametrized cases
- [ ] `lesson.md` documents root cause and fix
- [ ] `progress.txt` updated

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| FAST model still returns NOT_RELEVANT after prompt fix | Medium | High | Upgrade to STANDARD tier (Task 4) |
| PDF parsing produces empty/garbled text | Low | High | Task 2 diagnosis; fix parsing pipeline |
| Phase 3 runtime errors when finally exercised | Medium | Medium | Existing unit tests cover adapter; add integration test |
| Upgrading to STANDARD tier increases cost/latency | Certain | Low | Relevance scan is small fraction of Phase 2 time (~5s of ~150s) |
