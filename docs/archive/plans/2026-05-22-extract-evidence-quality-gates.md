# Extract Evidence Quality Gates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-05-22
**Completed:** 2026-05-22
**PR:** TBD

**Goal:** Make evidence extraction outputs safe for downstream ACMG scoring by normalizing field coverage, separating OCR/source gaps from true absence, validating sources, and exposing explicit score/review gates.

**Architecture:** Keep the orchestrated vertical slice shape. The workflow remains the orchestrator; deterministic post-processing and validation live in `extract_evidence/core.py`; LLM-facing stages only gather candidate facts. Scoring readiness is derived from typed contracts and quality gates, not inferred from `quality_report.passed` alone.

**Tech Stack:** Python 3.12, Pydantic contracts, pytest, Ruff, existing LangGraph workflow.

---

## Adopted Review Suggestions

The following suggestions are in scope for this fix:

- Module 1: split `ocr_gap` status, annotate external-database completion needs, consume image blocks.
- Module 2: improve `diagnosis_sufficiency`, add biochemical marker baseline handling, mark allele frequency as `ocr_gap` when source is image/OCR-lost, add non-scorable `treatment_response` support.
- Module 3: structure `inference_basis`, distinguish source `block_type`, split quality report counts.
- Module 4 items 11, 12, 14: OCR precheck, image block extraction rules, human review trigger conditions.

Boundary decisions:

- External database completion is represented as metadata/status in this module. Actual database lookup belongs in a later annotation provider.
- Image extraction consumes upstream `image`, `caption`, and `table` blocks. This module does not implement OCR/VLM recognition from raw pixels.
- `treatment_response` is auxiliary clinical context and must not make ACMG scoring pass by itself.

---

## Success Criteria

- Original and translated tracks emit the same catalog-shaped field set.
- `source_invalid`, `ocr_gap`, and `not_found` are counted separately.
- Invalid, ambiguous, OCR-gap, or missing required fields cannot pass the scoring gate.
- `special_evidence` cannot reference invalid or missing evidence fields.
- `evidence_chains` are generated only from grounded identity fields.
- Fabry output can produce a draft identity chain but remains non-scorable until missing external/required evidence is supplied.
- Human review is triggered for OCR gaps, image-derived required fields, source ambiguity, missing identity fields, or score-blocking quality issues.

---

### Task 1: Add Status and Source Metadata Contracts

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py`

**Step 1: Write failing tests**

Add tests for:

- `EvidenceStatus.OCR_GAP`
- `SourceLocation.block_type`
- `EvidenceItem.inference_basis`
- `QualityReport` separate counts and score gate fields
- human review trigger fields

**Step 2: Run red test**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py -q
```

Expected: failures for missing enum/fields.

**Step 3: Implement minimal contract changes**

Add:

- `EvidenceStatus.OCR_GAP = "ocr_gap"`
- `BlockType` or literal field covering `text`, `table`, `figure`, `image`, `caption`, `supplementary`
- `SourceLocation.block_type`
- `EvidenceItem.inference_basis: list[str]`
- `EvidenceItem.requires_external_completion: bool`
- `EvidenceItem.external_completion_note: str`
- `QualityReport.invalid_source_count`, `ocr_gap_count`, `ambiguous_source_count`, `score_gate_passed`, `human_review_required`, `human_review_reasons`

**Step 4: Run green test**

Run the same pytest command and verify it passes.

---

### Task 2: Normalize Catalog Output

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write failing tests**

Test that sparse LLM output is expanded to every `EVIDENCE_FIELD_SPECS` field and that invalid/non-found fields have no ACMG or ClinGen assignments.

**Step 2: Run red tests**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -q
```

**Step 3: Implement `EvidenceItemNormalizer`**

Rules:

- Fill missing catalog fields with `not_found`.
- Preserve the best candidate per field.
- Convert model-produced `source_invalid` with value/source back to `found` before grounding.
- Clear scoring assignments from `not_found`, `source_invalid`, and `ocr_gap`.
- Mark `D.allele_frequency` as `requires_external_completion=True` when not present in the document.

**Step 4: Run green tests**

Run the same pytest command.

---

### Task 3: Split OCR Gap and Source Grounding Semantics

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py`

**Step 1: Write failing tests**

Cover:

- source snippet missing from text but block/image hints indicate evidence may be in a figure/table image -> `ocr_gap`
- ordinary snippet missing -> `source_invalid`
- repeated snippet -> `ambiguous` count

**Step 2: Run red test**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py -q
```

**Step 3: Implement grounding split**

Use document metadata and source `block_type/context_type` to distinguish OCR gaps from invalid hallucinated sources.

**Step 4: Run green test**

Run the same pytest command.

---

### Task 4: Add Conservative Score and Review Gates

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/quality_validation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py`

**Step 1: Write failing tests**

Cover:

- required field `source_invalid` -> `scorable=False`
- required field `ocr_gap` -> `human_review_required=True`
- empty `evidence_chains` -> `score_gate_passed=False`
- `passed=True` can coexist with `score_gate_passed=False`

**Step 2: Run red test**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py -q
```

**Step 3: Implement gates**

Add explicit gate computation. Keep `passed` as structural consumption safety; use `score_gate_passed` for scoring.

**Step 4: Run green test**

Run the same pytest command.

---

### Task 5: Build Minimal Evidence Chains

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`

**Step 1: Write failing tests**

Test that valid `A.gene_symbol`, `B.disease_diagnosis`, and one valid variant field produce a draft chain.

**Step 2: Run red test**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py -q
```

**Step 3: Implement `EvidenceChainBuilder`**

Build chains only from `found` fields with non-null sources and non-ambiguous/non-invalid/non-OCR-gap status.

**Step 4: Run green test**

Run the same pytest command.

---

### Task 6: Validate Special Evidence

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write failing tests**

Cover:

- record with `start_offset=end_offset=0` is rejected unless snippet exactly starts at 0
- `case_control` cannot map to `B.*`
- records with `[REDACTED]` statistical counts are rejected as case-control evidence
- records cannot reference invalid/not-found/ocr-gap field IDs

**Step 2: Run red tests**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -q
```

**Step 3: Implement `SpecialEvidenceValidator`**

Filter records deterministically after LLM generation and before quality validation.

**Step 4: Run green tests**

Run the same pytest command.

---

### Task 7: Extend Prompts Conservatively

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Write failing prompt tests**

Assert prompts include:

- do not infer external database values
- mark unavailable image/table evidence as OCR gap
- separate baseline biochemical markers from treatment response
- diagnosis sufficiency requires explicit genetic/clinical diagnostic statement

**Step 2: Run red tests**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -q
```

**Step 3: Update prompts**

Keep prompts short and rule-oriented. Deterministic validators remain authoritative.

**Step 4: Run green tests**

Run the same pytest command.

---

### Task 8: Update Script Summary and Output Reviewability

**Files:**
- Modify: `backend/scripts/e2e_extract_evidence.py`
- Test: `backend/tests/scripts/test_e2e_extract_evidence.py`

**Step 1: Write failing tests**

Assert summary includes split counts and score gate fields.

**Step 2: Run red tests**

```bash
cd backend
uv run pytest tests/scripts/test_e2e_extract_evidence.py -q
```

**Step 3: Update summary serialization**

Include:

- `found_count`
- `not_found_count`
- `source_invalid_count`
- `ocr_gap_count`
- `ambiguous_source_count`
- `human_review_required`
- `score_gate_passed`

**Step 4: Run green tests**

Run the same pytest command.

---

### Task 9: Documentation and Verification

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md`
- Modify: `docs/README.md`
- Modify: `progress.txt`
- Test: relevant test suite

**Step 1: Update module guide**

Regenerate the extract evidence README to describe:

- statuses
- quality gates
- OCR/image handling
- external completion semantics
- human review triggers

**Step 2: Organize docs**

Use `skill:doc-organize` because `docs/` changed.

**Step 3: Run verification**

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/scripts/test_e2e_extract_evidence.py
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence scripts/e2e_extract_evidence.py tests/scripts/test_e2e_extract_evidence.py
```

Note: the worktree baseline currently lacks ignored `backend/output/cross_lingual/zh/法布雷病1例` fixture files, so the real-output Fabry fixture test must either be supplied from the main workspace or skipped unless the fixture exists.

**Step 4: Record progress**

Append:

```text
[2026-05-22] [extract-evidence-quality-gates] [done] Added output normalization, OCR/source gap split, quality score gates, special evidence validation, evidence chain building, and review triggers.
```
