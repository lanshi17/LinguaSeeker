# ClinGen Batch Regression Extraction Quality Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-06-10
**Completed:** —
**PR:** —

**Goal:** Improve ClinGen layer-3 batch regression reliability by normalizing harmless text differences, reducing missing gene extraction, and tightening relationship/precision behavior.

**Architecture:** Keep the evaluator as benchmark-only infrastructure and keep extraction behavior inside the Phase 2 vertical slice. Deterministic comparison normalization belongs in `benchmark/layer3/evaluate.py`; LLM behavior guidance belongs in `extract_evidence/prompts.py`; post-LLM safeguards belong in current normalizer classes rather than the orchestrator.

**Tech Stack:** Python 3.12, `uv`, pytest, FastAPI backend modules, Pydantic contracts, loguru benchmark logging.

---

## Success Criteria

- `Charcot-Marie-Tooth` and `Charcot–Marie–Tooth` match in layer-3 evaluation without changing reported extracted strings.
- `AARS2-related` / `AARS2-mutation related` disease text no longer causes `A.gene_symbol` to be omitted when prompt/normalizer changes are applied in a fresh extraction.
- `A.gene_disease_relationship` prompt and deterministic value normalization preserve `causative` for established disease-gene phrasing and avoid upgrading preliminary association language.
- Precision accounting exposes over-extraction risk in benchmark output, not only false negatives.
- The quick preprocessed regression for `clingen_000 clingen_001 clingen_002` runs through `uv` and produces a report with at least the previous F1 baseline.

## Scope

In scope:
- Benchmark comparison normalization for punctuation and whitespace only.
- Extraction prompt constraints for `A.gene_symbol`, `B.disease_diagnosis`, and `A.gene_disease_relationship`.
- Deterministic postprocessing for safe gene-symbol cleanup and relationship synonym normalization.
- Focused unit tests and one benchmark regression command.

Out of scope:
- Rebuilding all preprocessed cache artifacts.
- Changing ClinGen expected JSON values.
- Adding new LLM providers or changing model configuration.
- Broad ontology matching changes beyond existing MONDO fallback.

## Context To Read Before Editing

- `benchmark/layer3/evaluate.py`
- `benchmark/layer3/README.md`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py`
- Prior-art prompt guidance: `backend/.old_version/src/domain/agent/prompts.py`, section `CRITICAL FIELD 1: Gene Symbol`

## Task 1: Normalize Benchmark Text Comparison

**Files:**
- Modify: `benchmark/layer3/evaluate.py`
- Create: `backend/tests/benchmark/layer3/test_evaluate_matching.py`

**Step 1: Write the failing tests**

Create `backend/tests/benchmark/layer3/test_evaluate_matching.py`:

```python
"""Tests for ClinGen layer-3 value matching."""
from __future__ import annotations

from benchmark.layer3.evaluate import fuzzy_match_value


def test_fuzzy_match_value_treats_dash_variants_as_equivalent() -> None:
    assert fuzzy_match_value(
        "Charcot-Marie-Tooth disease axonal type 2N",
        "Charcot–Marie–Tooth disease axonal type 2N",
    )


def test_fuzzy_match_value_normalizes_curly_quotes_and_spacing() -> None:
    assert fuzzy_match_value("AARS2-related disease", "AARS2‑related  disease")
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_evaluate_matching.py -v
```

Expected: at least `test_fuzzy_match_value_treats_dash_variants_as_equivalent` fails before implementation.

**Step 3: Write minimal implementation**

In `benchmark/layer3/evaluate.py`, add near the comparison section:

```python
_PUNCT_TRANSLATION = str.maketrans({
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
    "−": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
})


def normalize_comparison_text(value: str) -> str:
    """Normalize harmless typography differences for benchmark matching."""
    normalized = value.translate(_PUNCT_TRANSLATION)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
```

Update `fuzzy_match_value`:

```python
    exp_norm = normalize_comparison_text(expected)
    ext_norm = normalize_comparison_text(extracted)
    exp_lower = exp_norm.lower()
    ext_lower = ext_norm.lower()
```

Update gene exact check:

```python
    if exp_norm == ext_norm:
        return True
```

Keep `FieldMatch.extracted_value` unchanged so reports still show raw extracted output.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_evaluate_matching.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add benchmark/layer3/evaluate.py backend/tests/benchmark/layer3/test_evaluate_matching.py
git commit -m "test: cover clingen benchmark text normalization"
```

## Task 2: Add Gene Extraction Prompt Constraints

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Write the failing test**

Append to `test_prompts.py`:

```python
def test_catalog_prompt_requires_gene_symbol_from_disease_prefix() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="AARS2-mutation related mitochondrial disease",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "A.gene_symbol" in prompt
    assert "AARS2-related" in prompt
    assert "must extract the gene symbol independently" in prompt
    assert "must not leave A.gene_symbol as not_found" in prompt
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_requires_gene_symbol_from_disease_prefix -v
```

Expected: FAIL because the exact prompt guidance is absent.

**Step 3: Write minimal prompt update**

In `get_catalog_extraction_prompt()`, insert after rule 16:

```text
17. For A.gene_symbol, exhaustively extract a standalone HGNC-style gene symbol from titles, abstracts, variant descriptions, tables, and disease modifiers. If the gene appears as a disease-name prefix such as "AARS2-related disease", "AARS2-mutation related mitochondrial disease", or "AARS1-associated Charcot-Marie-Tooth disease", you must extract the gene symbol independently into A.gene_symbol and must not leave A.gene_symbol as not_found.
```

Renumber the existing relationship rule and following rules.

**Step 4: Run prompt tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
git commit -m "fix: clarify gene symbol extraction prompt"
```

## Task 3: Normalize Gene Symbols Safely After Extraction

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py`

**Step 1: Write failing tests**

Append to `test_normalizer.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import FieldValueNormalizer


def test_field_value_normalizer_extracts_gene_from_related_phrase() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="AARS2-mutation related mitochondrial disease",
        confidence=0.74,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "AARS2"


def test_field_value_normalizer_preserves_plain_gene_symbol() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="ABCA3",
        confidence=0.95,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "ABCA3"
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py::test_field_value_normalizer_extracts_gene_from_related_phrase -v
```

Expected: FAIL because gene phrase cleanup is not implemented.

**Step 3: Write minimal implementation**

In `FieldValueNormalizer`, add:

```python
    _GENE_SYMBOL_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")
    _GENE_PREFIX_HINTS = ("-related", "-mutation", "-associated", " related", " mutation", " associated")
```

Update `normalize_items()` before enum handling:

```python
            if item.field_id == "A.gene_symbol" and item.value is not None:
                normalized.append(cls._normalize_gene_symbol(item))
                continue
```

Add:

```python
    @classmethod
    def _normalize_gene_symbol(cls, item: EvidenceItem) -> EvidenceItem:
        raw = str(item.value).strip()
        if cls._GENE_SYMBOL_RE.fullmatch(raw):
            return item.model_copy(update={"value": raw.upper()})
        lowered = raw.lower()
        if not any(hint in lowered for hint in cls._GENE_PREFIX_HINTS):
            return item
        match = cls._GENE_SYMBOL_RE.search(raw)
        if match is None:
            return item
        return item.model_copy(update={"value": match.group(0).upper()})
```

This is intentionally conservative: it only extracts a token when the value contains relationship-prefix hints.

**Step 4: Run normalizer tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py
git commit -m "fix: normalize extracted gene symbol phrases"
```

## Task 4: Tighten Relationship Prompt And Synonym Normalization

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py`

**Step 1: Write failing prompt test**

Append:

```python
def test_catalog_prompt_relationship_distinguishes_established_from_preliminary() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="AARS1 causes Charcot-Marie-Tooth disease",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS1 case",
    )

    assert "known disease gene" in prompt
    assert "established causal relationship" in prompt
    assert "Do not choose associated merely because the sentence contains associated" in prompt
```

**Step 2: Write failing normalizer tests**

Append to `test_normalizer.py`:

```python
def test_field_value_normalizer_maps_known_disease_gene_to_causative() -> None:
    item = EvidenceItem(
        field_id="A.gene_disease_relationship",
        category="A",
        field_name="Reported gene-disease relationship",
        status=EvidenceStatus.FOUND,
        value="known disease gene",
        confidence=0.9,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "causative"


def test_field_value_normalizer_keeps_preliminary_association_as_associated() -> None:
    item = EvidenceItem(
        field_id="A.gene_disease_relationship",
        category="A",
        field_name="Reported gene-disease relationship",
        status=EvidenceStatus.FOUND,
        value="preliminary association only",
        confidence=0.8,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "associated"
```

**Step 3: Run tests to verify failure**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_relationship_distinguishes_established_from_preliminary \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py::test_field_value_normalizer_maps_known_disease_gene_to_causative \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py::test_field_value_normalizer_keeps_preliminary_association_as_associated \
  -v
```

Expected: FAIL on missing prompt text and missing `known disease gene` mapping.

**Step 4: Update prompt and normalizer**

In `prompts.py`, strengthen the relationship rule:

```text
Decision guidance: Use "causative" when the document supports an established causal relationship: known disease gene, pathogenic variants causing the disease, ACMG pathogenic/likely pathogenic variants in affected cases, ClinGen Definitive/Strong/Moderate curation, or replicated genetic/functional evidence. Do not choose associated merely because the sentence contains associated; choose "associated" only when the gene-disease link itself is explicitly preliminary, correlative, risk-modifying, or not established as causal.
```

In `FieldValueNormalizer._normalize_enum()`, update `keyword_map`:

```python
            "causative": (
                "cause", "causative", "causal", "pathogenic",
                "responsible", "known disease gene", "disease gene",
            ),
            "associated": (
                "preliminary association", "associated", "association",
                "linked", "related",
            ),
```

Keep exact enum match first.

**Step 5: Run focused tests**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py \
  -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py
git commit -m "fix: tighten gene disease relationship extraction"
```

## Task 5: Add Over-Extraction Visibility To Benchmark Metrics

**Files:**
- Modify: `benchmark/layer3/evaluate.py`
- Modify: `backend/tests/benchmark/layer3/test_evaluate_matching.py`

**Step 1: Write failing test**

Append:

```python
from benchmark.layer3.evaluate import compare_evidence


def test_compare_evidence_counts_extra_found_candidate_as_over_extraction() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    extracted = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.6},
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].matched
    assert matches[0].match_type == "exact"
    assert matches[0].extra_found_values == ["BRCA1"]
```

**Step 2: Run test to verify failure**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_evaluate_matching.py::test_compare_evidence_counts_extra_found_candidate_as_over_extraction -v
```

Expected: FAIL because `FieldMatch.extra_found_values` does not exist.

**Step 3: Implement minimal metric field**

In `FieldMatch`, add:

```python
    extra_found_values: list[str] = field(default_factory=list)
```

In `compare_evidence()`, after choosing `best_match`, compute extras:

```python
        if best_match:
            extra_values = []
            for cand in candidates:
                value = str(cand.get("value", ""))
                if value != best_match.extracted_value and not fuzzy_match_value(expected_value, value):
                    extra_values.append(value)
            matches.append(best_match.__class__(
                **{**best_match.__dict__, "extra_found_values": extra_values}
            ))
```

Prefer `dataclasses.replace(best_match, extra_found_values=extra_values)` if `replace` is imported from `dataclasses`.

Update aggregate precision:

```python
    over_extracted = sum(len(f.extra_found_values) for m in all_metrics for f in m.field_matches)
    fp = (
        sum(1 for m in all_metrics for f in m.field_matches if f.match_type == "wrong_value")
        + over_extracted
    )
```

Add `"over_extractions": over_extracted` to report `overall`.

Update per-entry field serialization:

```python
                     "match_type": f.match_type,
                     "extra_found_values": f.extra_found_values}
```

**Step 4: Run benchmark tests**

Run:

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_evaluate_matching.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add benchmark/layer3/evaluate.py backend/tests/benchmark/layer3/test_evaluate_matching.py
git commit -m "feat: expose benchmark over extraction metrics"
```

## Task 6: Run Focused Verification And Batch Regression

**Files:**
- Modify: `progress.txt`
- Modify if docs changed during execution: `docs/README.md`

**Step 1: Run focused backend tests**

Run:

```bash
cd backend
uv run pytest \
  tests/benchmark/layer3/test_evaluate_matching.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalizer.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py \
  -v
```

Expected: PASS.

**Step 2: Run quick preprocessed ClinGen regression**

Run:

```bash
cd backend
uv run python -m benchmark.layer3.evaluate --entries clingen_000 clingen_001 clingen_002
```

Expected:
- Logs show `pipeline_status` as `preprocessed` for all three entries if preprocessed cache is present.
- `Charcot–Marie–Tooth` no longer fails only because of dash encoding.
- Report JSON appears under `benchmark/layer3/reports/eval_*.json`.

**Step 3: Inspect latest report**

Run:

```bash
cd backend
uv run python - <<'PY'
from pathlib import Path
import json

report = max(Path("../benchmark/layer3/reports").glob("eval_*.json"), key=lambda p: p.stat().st_mtime)
data = json.loads(report.read_text(encoding="utf-8"))
print(report)
print(data["aggregates"]["overall"])
for entry in data["per_entry"]:
    print(entry["entry_id"], entry["pipeline_status"], entry["field_matches"])
PY
```

Expected:
- Overall F1 is not lower than the baseline report being fixed.
- Any remaining `AARS2` miss is attributable to stale preprocessed cache, not comparator punctuation.

**Step 4: Update progress**

Append to root `progress.txt`:

```text
[2026-06-10] ClinGen batch regression extraction quality fixes implemented and verified [completed]
```

**Step 5: Use doc organization if docs changed**

If implementation adds or moves documentation, use `skill:doc-organize` and update `docs/README.md`.

**Step 6: Commit verification/docs update**

```bash
git add progress.txt docs/README.md
git commit -m "docs: record clingen regression quality work"
```

## Task 7: Request Code Review

**Files:**
- Create: `docs/codereview/2026-06-10-clingen-batch-regression-extraction-quality.md`

**Step 1: Use review skill**

Use `skill:requesting-code-review`.

**Step 2: Ask reviewer to focus on**

- Whether benchmark normalization hides meaningful biomedical differences.
- Whether gene-symbol phrase cleanup is conservative enough.
- Whether relationship synonym mapping can accidentally upgrade weak evidence.
- Whether over-extraction precision accounting double-counts expected duplicates.

**Step 3: Commit review request**

```bash
git add docs/codereview/2026-06-10-clingen-batch-regression-extraction-quality.md
git commit -m "docs: request review for clingen regression fixes"
```

