# Evidence Extraction Output E2E Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real-LLM end-to-end test that runs `extract_evidence` over parsed `backend/output/**/original.md` and `translated.md` document tracks.

**Architecture:** Keep the extractor implementation unchanged unless the test exposes a concrete failure. Add a small test helper that discovers complete output pairs, builds typed `TrackDocument` inputs with full-document page spans, validates fixture quality before model calls, and runs the public `EvidenceExtractionService` against real `EVIDENCE_EXTRACTION_*` settings.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, Pydantic v2, LangGraph, LangChain OpenAI-compatible structured output, uv.

---

**Status:** planned
**Created:** 2026-05-16
**Completed:** -
**PR:** -

## Scope

In scope:

- Use real files under `backend/output/**/original.md` and `backend/output/**/translated.md`.
- Run the public facade at `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`.
- Use the real LLM provider, not mocks.
- Assert stable contract-level invariants and selected biomedical terms, not exact LLM wording.
- Write JSON result artifacts to `backend/tests/output/evidence_extraction_e2e/`.
- Keep the test skipped unless real LLM config and valid fixture pairs are available.

Out of scope:

- Fixing translation quality defects in `backend/output/**/translated.md`.
- Comparing original and translated extraction parity.
- Database persistence.
- FastAPI route coverage.
- Scoring or clinical interpretation.

## Current Repository Findings

- Complete output pairs currently exist under:
  - `backend/output/en/10.3389_fimmu.2025.1655475/`
  - `backend/output/ja/32_2015-0041/`
  - `backend/output/ja/33_2017-0026/`
  - `backend/output/ja/52_26/`
- `backend/output/ru/elibrary_53981733_40074746/` only has `metadata.json`, so it is not a complete extraction fixture.
- `backend/output/ja/33_2017-0026/translated.md` is about 355 KB and contains prompt leakage such as `# Critical Rules`; the test must detect this as an invalid translated fixture before sending it to the LLM.
- Existing real-LLM smoke test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_integration_real_llm.py`.
- Existing extractor package: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/`.

## Success Criteria

- `uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_discover_output_pairs -q` passes without LLM credentials.
- `uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_output_fixture_audit -q` passes without LLM credentials and reports invalid fixtures before model calls.
- With `EVIDENCE_EXTRACTION_*` configured, the real smoke test runs on a small allowlisted set and writes output JSON artifacts.
- The real smoke test verifies both `Track.ORIGINAL` and `Track.TRANSLATED` on at least one valid output pair.
- The test does not use bare `dict` return annotations in backend code.
- `uv run ruff check tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py` passes.

## Implementation Tasks

### Task 1: Add Output Pair Discovery Tests

**Files:**

- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py`
- No production files.

**Step 1: Write the failing discovery test**

Create the file with this initial content:

```python
"""Real-LLM E2E tests for evidence extraction over backend/output fixtures."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_BACKEND_DIR = Path(__file__).resolve().parents[5]
_OUTPUT_DIR = _BACKEND_DIR / "output"


@dataclass(frozen=True)
class OutputPair:
    """A complete original/translated output pair from parse-and-translate."""

    doc_id: str
    language: str
    base_dir: Path
    original_path: Path
    translated_path: Path


def discover_output_pairs(output_dir: Path = _OUTPUT_DIR) -> list[OutputPair]:
    """Return complete output fixture pairs sorted by language and document ID."""
    pairs: list[OutputPair] = []
    if not output_dir.exists():
        return pairs

    for original_path in sorted(output_dir.glob("*/*/original.md")):
        translated_path = original_path.with_name("translated.md")
        if not translated_path.exists():
            continue
        base_dir = original_path.parent
        pairs.append(
            OutputPair(
                doc_id=base_dir.name,
                language=base_dir.parent.name,
                base_dir=base_dir,
                original_path=original_path,
                translated_path=translated_path,
            )
        )
    return pairs


def test_discover_output_pairs():
    pairs = discover_output_pairs()

    pair_ids = {(pair.language, pair.doc_id) for pair in pairs}
    assert ("en", "10.3389_fimmu.2025.1655475") in pair_ids
    assert ("ja", "32_2015-0041") in pair_ids
    assert all(pair.original_path.exists() for pair in pairs)
    assert all(pair.translated_path.exists() for pair in pairs)
```

**Step 2: Run the test**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_discover_output_pairs -q
```

Expected: PASS if `backend/output/**/original.md` and `translated.md` fixtures are present. If it fails with no pairs, stop and confirm the fixture location.

**Step 3: Commit**

Do not commit yet if the user only asked for a plan. During implementation, commit with:

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py
git commit -m "test: discover evidence extraction output fixtures"
```

### Task 2: Add Fixture Audit Before Real LLM Calls

**Files:**

- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py`

**Step 1: Add audit contracts and tests**

Append these imports and helpers near the top of the file:

```python
from typing import Literal

from pydantic import BaseModel


class FixtureAuditIssue(BaseModel):
    """A preflight fixture issue that should be fixed before expensive LLM calls."""

    severity: Literal["warning", "error"]
    doc_id: str
    language: str
    track_name: str
    message: str


class FixtureAuditReport(BaseModel):
    """Preflight audit result for all output pairs."""

    valid_pair_ids: list[str]
    issues: list[FixtureAuditIssue]
```

Add these constants and helper functions:

```python
_MAX_E2E_CHARS = 80_000
_PROMPT_LEAK_MARKERS = (
    "# Critical Rules",
    "TERMINOLOGY MAP:",
    "Output ONLY the translated markdown",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def audit_output_pairs(pairs: list[OutputPair]) -> FixtureAuditReport:
    valid_pair_ids: list[str] = []
    issues: list[FixtureAuditIssue] = []

    for pair in pairs:
        pair_has_error = False
        for track_name, path in (
            ("original", pair.original_path),
            ("translated", pair.translated_path),
        ):
            text = _read_text(path)
            if not text.strip():
                pair_has_error = True
                issues.append(FixtureAuditIssue(
                    severity="error",
                    doc_id=pair.doc_id,
                    language=pair.language,
                    track_name=track_name,
                    message="file is empty",
                ))
            if len(text) > _MAX_E2E_CHARS:
                pair_has_error = True
                issues.append(FixtureAuditIssue(
                    severity="error",
                    doc_id=pair.doc_id,
                    language=pair.language,
                    track_name=track_name,
                    message=f"file has {len(text)} chars, limit is {_MAX_E2E_CHARS}",
                ))
            for marker in _PROMPT_LEAK_MARKERS:
                if marker in text:
                    pair_has_error = True
                    issues.append(FixtureAuditIssue(
                        severity="error",
                        doc_id=pair.doc_id,
                        language=pair.language,
                        track_name=track_name,
                        message=f"contains prompt leakage marker: {marker}",
                    ))

        if not pair_has_error:
            valid_pair_ids.append(f"{pair.language}/{pair.doc_id}")

    return FixtureAuditReport(valid_pair_ids=valid_pair_ids, issues=issues)
```

Add this test:

```python
def test_output_fixture_audit():
    pairs = discover_output_pairs()
    report = audit_output_pairs(pairs)

    assert "en/10.3389_fimmu.2025.1655475" in report.valid_pair_ids
    assert "ja/32_2015-0041" in report.valid_pair_ids
    assert any(
        issue.doc_id == "33_2017-0026"
        and issue.track_name == "translated"
        and issue.severity == "error"
        for issue in report.issues
    )
```

**Step 2: Run the audit test**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_output_fixture_audit -q
```

Expected: PASS. The test should prove that valid pairs are available and the known bad translated fixture is rejected before LLM calls.

**Step 3: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py
git commit -m "test: audit evidence extraction output fixtures"
```

### Task 3: Build TrackDocument Inputs From Output Files

**Files:**

- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py`

**Step 1: Add imports**

Add:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    PageSpan,
    Track,
    TrackDocument,
)
```

**Step 2: Add the document builder**

Add:

```python
def build_track_document(pair: OutputPair, track: Track) -> TrackDocument:
    """Build a single-span TrackDocument from an output markdown file."""
    path = pair.original_path if track == Track.ORIGINAL else pair.translated_path
    text = _read_text(path)
    return TrackDocument(
        document_id=f"{pair.language}/{pair.doc_id}",
        track=track,
        formatted_text=text,
        page_spans=[
            PageSpan(
                span_id=f"{track.value}-full-text",
                page=1,
                start_offset=0,
                end_offset=len(text),
            )
        ],
        metadata={
            "source_path": str(path.relative_to(_BACKEND_DIR)),
            "language": pair.language,
        },
    )
```

**Step 3: Add builder test**

Add:

```python
def test_build_track_document_uses_full_text_span():
    pair = next(
        pair
        for pair in discover_output_pairs()
        if pair.language == "ja" and pair.doc_id == "32_2015-0041"
    )

    document = build_track_document(pair, Track.TRANSLATED)

    assert document.document_id == "ja/32_2015-0041"
    assert document.track == Track.TRANSLATED
    assert document.page_spans == [
        PageSpan(
            span_id="translated-full-text",
            page=1,
            start_offset=0,
            end_offset=len(document.formatted_text),
        )
    ]
    assert "DSG2" in document.formatted_text
```

**Step 4: Run the builder test**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_build_track_document_uses_full_text_span -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py
git commit -m "test: build evidence extraction track documents"
```

### Task 4: Add Real LLM E2E Smoke Test

**Files:**

- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py`

**Step 1: Add imports**

Add:

```python
import json
import os

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
    EvidenceExtractionService,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
)
```

Extend the existing contracts import instead of creating duplicate imports.

**Step 2: Add env guards and output path**

Add:

```python
_REQUIRED_ENV = (
    "EVIDENCE_EXTRACTION_API_KEY",
    "EVIDENCE_EXTRACTION_BASE_URL",
    "EVIDENCE_EXTRACTION_FAST_MODEL",
    "EVIDENCE_EXTRACTION_STANDARD_MODEL",
    "EVIDENCE_EXTRACTION_STRONG_MODEL",
)
_E2E_RESULT_DIR = _BACKEND_DIR / "tests" / "output" / "evidence_extraction_e2e"
_REAL_LLM_SKIP_REASON = "Evidence extraction real LLM env vars are not configured"
```

Add:

```python
def _has_real_llm_config() -> bool:
    return all(os.environ.get(name) for name in _REQUIRED_ENV)
```

**Step 3: Add assertion helpers**

Add:

```python
def _assert_result_contract(result: EvidenceExtractionResult) -> None:
    assert result.status in (
        EvidenceExtractionStatus.COMPLETED,
        EvidenceExtractionStatus.NOT_RELEVANT,
    )
    assert result.document_id
    assert result.track in (Track.ORIGINAL, Track.TRANSLATED)
    if result.status == EvidenceExtractionStatus.NOT_RELEVANT:
        return

    assert result.evidence_map is not None
    assert result.quality_report is not None
    assert result.quality_report.found_count + result.quality_report.not_found_count > 0
    assert all(0.0 <= item.confidence <= 1.0 for item in result.evidence_items)
    for item in result.evidence_items:
        if item.source is None:
            continue
        snippet = item.source.text_snippet
        assert snippet
        assert snippet in item.source.text_snippet
        assert item.source.start_offset <= item.source.end_offset


def _assert_expected_terms(result: EvidenceExtractionResult, expected_terms: set[str]) -> None:
    haystack = " ".join(
        [
            " ".join(result.evidence_map.gene_terms if result.evidence_map else []),
            " ".join(result.evidence_map.variant_terms if result.evidence_map else []),
            " ".join(str(item.value) for item in result.evidence_items if item.value is not None),
            " ".join(item.notes for item in result.evidence_items),
        ]
    )
    assert any(term in haystack for term in expected_terms)


def _write_result_artifact(result: EvidenceExtractionResult) -> None:
    _E2E_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_name = result.document_id.replace("/", "__") + f"__{result.track.value}.json"
    artifact_path = _E2E_RESULT_DIR / artifact_name
    artifact_path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

**Step 4: Add the real LLM test**

Add:

```python
@pytest.mark.integration
@pytest.mark.skipif(not _has_real_llm_config(), reason=_REAL_LLM_SKIP_REASON)
@pytest.mark.asyncio
async def test_evidence_extraction_over_output_pair_with_real_llm():
    from src.core.config import get_config

    pairs = discover_output_pairs()
    audit = audit_output_pairs(pairs)
    valid_pairs = {
        f"{pair.language}/{pair.doc_id}": pair
        for pair in pairs
        if f"{pair.language}/{pair.doc_id}" in audit.valid_pair_ids
    }
    pair = valid_pairs["ja/32_2015-0041"]

    service = EvidenceExtractionService(cfg=get_config())
    expected_terms = {"DSG2", "TMEM43", "c.1481", "c.601"}

    for track in (Track.ORIGINAL, Track.TRANSLATED):
        document = build_track_document(pair, track)
        result = await service.run(document)

        _assert_result_contract(result)
        if result.status == EvidenceExtractionStatus.COMPLETED:
            _assert_expected_terms(result, expected_terms)
        _write_result_artifact(result)
```

**Step 5: Run without real LLM config**

Run:

```bash
cd backend
env -u EVIDENCE_EXTRACTION_API_KEY \
  -u EVIDENCE_EXTRACTION_BASE_URL \
  -u EVIDENCE_EXTRACTION_FAST_MODEL \
  -u EVIDENCE_EXTRACTION_STANDARD_MODEL \
  -u EVIDENCE_EXTRACTION_STRONG_MODEL \
  uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_evidence_extraction_over_output_pair_with_real_llm -q
```

Expected: SKIPPED with `Evidence extraction real LLM env vars are not configured`.

**Step 6: Run with real LLM config**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_evidence_extraction_over_output_pair_with_real_llm -m integration -vv -s
```

Expected: PASS or a concrete extractor/provider failure. If this fails because the real LLM returns a schema error or no expected terms, keep the failing artifact/output and continue to Task 5.

**Step 7: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py
git commit -m "test: add evidence extraction output e2e smoke"
```

### Task 5: Fix Only Concrete Failures Exposed By The Real E2E Test

**Files:**

- Modify only if required:
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py`
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
  - `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Test:
  - `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py`
  - The narrow unit test matching the changed production file.

**Step 1: Classify the failure**

Use this checklist:

- Schema validation or structured-output error: inspect `providers.py` and stage output schemas.
- Token/context overflow: inspect `prompts.py` and consider a narrow text-window strategy for E2E fixtures.
- Source grounding marks all found items invalid: inspect `core.py` and the model's snippet/offset behavior.
- Result is `NOT_RELEVANT` for a clearly relevant medical genetics case: inspect `prompts.py` evidence-map instructions.
- Expected terms missing but evidence exists: adjust the E2E assertion helper, not production code.

**Step 2: Write a failing unit test for the concrete behavior**

Example for prompt context overflow prevention:

```python
def test_e2e_fixture_audit_rejects_oversized_translated_prompt_leak():
    pair = next(
        pair
        for pair in discover_output_pairs()
        if pair.language == "ja" and pair.doc_id == "33_2017-0026"
    )

    report = audit_output_pairs([pair])

    assert any(
        issue.track_name == "translated"
        and "Critical Rules" in issue.message
        for issue in report.issues
    )
```

Example for source grounding tolerance:

```python
def test_output_e2e_sources_are_substrings_when_offsets_are_repaired():
    # Add this only after a real failure proves it is needed.
    ...
```

**Step 3: Implement the smallest fix**

Do not refactor unrelated extractor code. Do not repair `backend/output/**` fixtures inside this task unless the user explicitly asks.

**Step 4: Re-run the narrow tests**

Run the exact failing test plus the related unit test:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py -q
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py -q
```

Expected: PASS for the non-LLM tests, and PASS/SKIP for real-LLM tests depending on env.

**Step 5: Commit**

Use the matching Conventional Commit type:

```bash
git add <changed-files>
git commit -m "fix: stabilize evidence extraction output e2e"
```

### Task 6: Final Verification And Documentation Updates

**Files:**

- Modify: `progress.txt`
- Modify if implementation changed docs: `docs/README.md`
- No `lesson.md` change unless debugging/iteration found a real root cause.

**Step 1: Run lint on the new test**

Run:

```bash
cd backend
uv run ruff check tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py
```

Expected: PASS.

**Step 2: Run fast extractor tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -q
```

Expected: PASS with real-LLM tests skipped if env vars are missing.

**Step 3: Run real E2E test when credentials are available**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_output_e2e_real_llm.py::test_evidence_extraction_over_output_pair_with_real_llm -m integration -vv -s
```

Expected: PASS. If credentials are not available, report SKIPPED and do not claim real E2E success.

**Step 4: Inspect generated artifacts**

Run:

```bash
cd backend
find tests/output/evidence_extraction_e2e -maxdepth 1 -type f -name '*.json' -print
```

Expected after real E2E run: at least:

```text
tests/output/evidence_extraction_e2e/ja__32_2015-0041__original.json
tests/output/evidence_extraction_e2e/ja__32_2015-0041__translated.json
```

**Step 5: Update progress**

Append:

```text
[2026-05-16] Evidence extraction output E2E real-LLM test over backend/output original+translated tracks [done]
```

If only the plan is written, append:

```text
[2026-05-16] Planned evidence extraction output E2E real-LLM test over backend/output original+translated tracks [planned]
```

**Step 6: Commit final verification/docs**

```bash
git add progress.txt docs/README.md
git commit -m "docs: record evidence extraction output e2e progress"
```

## Notes For Executor

- Use `@verification-before-completion` before any completion claim.
- Use `@systematic-debugging` before changing production code for any failing E2E behavior.
- Use `@git-auto-commit` for commits.
- Preserve existing dirty worktree changes that are unrelated to this plan.
- Do not modify or delete files under `backend/output/**` unless the user explicitly requests fixture cleanup.
- The real E2E test intentionally costs LLM calls. Keep its default scope to one valid pair (`ja/32_2015-0041`) and both tracks.
- The known invalid translated fixture `ja/33_2017-0026/translated.md` should be audited, not sent to the LLM.

