# ACMG Evidence Normalization Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-09
**Completed:** 2026-06-09
**PR:** merged (fd8229a3)

**Goal:** Fix critical ACMG evidence extraction errors around HGVS fields, semantic age/evidence interpretation, duplicate facts, enum/value normalization, and HPO-ready phenotype mapping.

**Architecture:** Keep the existing Orchestrated Vertical Slice Architecture. Phase 2 stays responsible for extracting and validating typed evidence items; Phase 3 stays responsible for entity resolution and normalized IDs. Add small deterministic post-processing components inside existing feature slices instead of rewriting the pipeline or embedding business rules in the orchestrator.

**Tech Stack:** Python 3.12, Pydantic, pytest, Ruff, existing LangGraph workflow, existing Phase 2 extraction contracts, existing Phase 3 standardization contracts.

---

## Scope and Success Criteria

This plan addresses five review findings:

1. Coordinates such as `chr6_44270253` must not be accepted as HGVS genomic variants, reference sequences, or legacy names.
2. Variant-critical fields must require true HGVS-like molecular content where applicable, not prose-only splice descriptions.
3. Age of onset, computational prediction, functional evidence, prediction-tool names, de novo status, consanguinity, obligate carriers, and similar values must be normalized deterministically after LLM extraction.
4. Repeated facts across chunks/tracks must be merged into one canonical item per `(group_id, field_id, normalized_value)` with confidence/source preservation.
5. Phenotype text must be projected toward HPO IDs when Phase 3 has a terminology match, while preserving unmapped text for review.

Non-goals:

- Do not implement a full ACMG scoring engine.
- Do not call external annotation APIs for allele frequencies or HGVS conversion.
- Do not guess missing nucleotide changes from coordinates alone.
- Do not replace existing LLM prompts with a new extraction architecture.

Before implementation, search `.old_version/` for reusable parsing or graph-sync logic:

```bash
cd backend
rg -n "hgvs|variant_hgvs|phenotype|HPO|de novo|consanguinity|obligate|prediction|in silico|age_of_onset" .old_version/src .old_version/tests
```

Expected: reusable ideas may exist in `.old_version/src/domain/graph/sync.py`, but code must be adapted to current contracts and must not introduce stable bare-dict returns.

---

### Task 1: Add Typed Normalization Contracts

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py`

**Step 1: Write the failing test**

Add to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceNormalizationIssue,
    EvidenceNormalizationIssueType,
    EvidenceNormalizationSeverity,
)


def test_evidence_normalization_issue_contract() -> None:
    issue = EvidenceNormalizationIssue(
        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
        severity=EvidenceNormalizationSeverity.ERROR,
        field_id="A.variant_hgvs_g",
        message="Coordinate-only value is not valid HGVS.",
        original_value="chr6_44270253",
    )

    assert issue.issue_type == EvidenceNormalizationIssueType.INVALID_HGVS
    assert issue.severity == EvidenceNormalizationSeverity.ERROR
    assert issue.field_id == "A.variant_hgvs_g"


def test_extraction_result_and_state_carry_normalization_issues() -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        EvidenceExtractionResult,
        EvidenceExtractionState,
        EvidenceExtractionStatus,
        Track,
        TrackDocument,
    )

    result = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc",
        track=Track.ORIGINAL,
        normalization_issues=[issue],
    )
    state = EvidenceExtractionState(
        document=TrackDocument(
            document_id="doc",
            track=Track.ORIGINAL,
            formatted_text="",
            page_spans=[],
        ),
        normalization_issues=[issue],
    )

    assert result.normalization_issues == [issue]
    assert state.normalization_issues == [issue]
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py::test_evidence_normalization_issue_contract -v
```

Expected: FAIL with import error for the new contract classes.

**Step 3: Add minimal contracts**

Add to `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`:

```python
class EvidenceNormalizationIssueType(str, Enum):
    INVALID_HGVS = "invalid_hgvs"
    MISSING_VARIANT_DETAIL = "missing_variant_detail"
    SEMANTIC_CONFLICT = "semantic_conflict"
    GENERIC_PREDICTION_TOOL = "generic_prediction_tool"
    VALUE_NORMALIZED = "value_normalized"
    DUPLICATE_MERGED = "duplicate_merged"


class EvidenceNormalizationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvidenceNormalizationIssue(BaseModel):
    issue_type: EvidenceNormalizationIssueType
    severity: EvidenceNormalizationSeverity = EvidenceNormalizationSeverity.WARNING
    field_id: str
    message: str
    original_value: str | int | float | bool | list[str] | None = None
    normalized_value: str | int | float | bool | list[str] | None = None
```

Add `normalization_issues: list[EvidenceNormalizationIssue] = Field(default_factory=list)` to both contracts:

- `EvidenceExtractionResult`
- `EvidenceExtractionState`

Do not add it to only one of the two; the workflow writes to state and the service copies state into the result.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py::test_evidence_normalization_issue_contract -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py
git commit -m "feat: add evidence normalization issue contracts"
```

---

### Task 2: Reject Coordinate-Only Values in HGVS and Reference Fields

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py`

**Step 1: Write the failing tests**

Create `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py`:

```python
"""Tests for ACMG-oriented evidence value normalization."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import (
    AcmgEvidenceValueNormalizer,
)


def _item(field_id: str, value: object) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
    )


def test_coordinate_only_value_is_rejected_for_hgvs_g() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_g", "chr6_44270253")])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].field_id == "A.variant_hgvs_g"
    assert issues[0].issue_type.value == "invalid_hgvs"


def test_reference_sequence_does_not_accept_coordinate_only_value() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.reference_sequence", "chr6_44270253")])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].field_id == "A.reference_sequence"


def test_valid_hgvs_g_is_preserved() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_g", "NC_000006.12:g.44270253G>A")])

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == "NC_000006.12:g.44270253G>A"
    assert issues == []


def test_valid_hgvs_g_indel_dup_forms_are_preserved() -> None:
    values = [
        "NC_000006.12:g.44270253del",
        "NC_000006.12:g.44270253_44270254insA",
        "NC_000006.12:g.44270253dup",
        "NC_000006.12:g.44270253_44270260inv",
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize([
        _item("A.variant_hgvs_g", value) for value in values
    ])

    assert [item.value for item in items] == values
    assert issues == []


def test_lowercase_hgvs_g_is_rejected() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([
        _item("A.variant_hgvs_g", "nc_000006.12:g.44270253g>a"),
    ])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "invalid_hgvs"


def test_rejected_item_clears_stale_assigned_codes() -> None:
    item = _item("A.variant_hgvs_g", "chr6_44270253").model_copy(update={
        "assigned_acmg_codes": ["PS1"],
        "assigned_clingen_modules": ["variant_evidence"],
    })

    items, _ = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].assigned_acmg_codes == []
    assert items[0].assigned_clingen_modules == []
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py -v
```

Expected: FAIL because `normalization.py` does not exist.

**Step 3: Implement minimal normalizer**

Create `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`:

```python
"""Deterministic ACMG evidence value normalization."""
from __future__ import annotations

import re

from .contracts import (
    EvidenceItem,
    EvidenceNormalizationIssue,
    EvidenceNormalizationIssueType,
    EvidenceNormalizationSeverity,
    EvidenceStatus,
)

_COORDINATE_ONLY_RE = re.compile(r"^(?:chr)?[0-9XYM]+[_:][0-9]+$", re.IGNORECASE)
_HGVS_G_RE = re.compile(
    r"^[A-Z]{1,3}_[0-9]+(?:\.[0-9]+)?:g\."
    r"(?:"
    r"[0-9]+[ACGT]>[ACGT]|"
    r"[0-9]+(?:_[0-9]+)?del(?:[ACGT]+)?|"
    r"[0-9]+(?:_[0-9]+)?ins[ACGT]+|"
    r"[0-9]+(?:_[0-9]+)?dup(?:[ACGT]+)?|"
    r"[0-9]+_[0-9]+inv"
    r")$"
)


class AcmgEvidenceValueNormalizer:
    """Normalize extracted values before catalog backfill and quality gates."""

    _HGVS_OR_REFERENCE_FIELDS = {
        "A.variant_hgvs_g",
        "A.reference_sequence",
        "A.variant_legacy_name",
    }

    def normalize(self, items: list[EvidenceItem]) -> tuple[list[EvidenceItem], list[EvidenceNormalizationIssue]]:
        normalized: list[EvidenceItem] = []
        issues: list[EvidenceNormalizationIssue] = []
        for item in items:
            replacement, item_issues = self._normalize_one(item)
            normalized.append(replacement)
            issues.extend(item_issues)
        return normalized, issues

    def _normalize_one(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if item.status != EvidenceStatus.FOUND or item.value is None:
            return item, []
        value_text = str(item.value).strip()
        if item.field_id in self._HGVS_OR_REFERENCE_FIELDS and _COORDINATE_ONLY_RE.fullmatch(value_text):
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Coordinate-only value is not valid for this HGVS/reference field.",
                        original_value=item.value,
                    )
                ],
            )
        if item.field_id == "A.variant_hgvs_g" and value_text and not _HGVS_G_RE.fullmatch(value_text):
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="HGVS genomic variant must include reference sequence, g. coordinate, and base change.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _reject_item(self, item: EvidenceItem) -> EvidenceItem:
        return item.model_copy(update={
            "status": EvidenceStatus.NOT_FOUND,
            "value": None,
            "confidence": 0.0,
            "assigned_acmg_codes": [],
            "assigned_clingen_modules": [],
        })
```

**Step 4: Wire normalizer into the existing workflow**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`, keep `FieldValueNormalizer` for catalog enum rules but delegate ACMG-specific validation to `AcmgEvidenceValueNormalizer` later in Task 7. Do not wire yet if that would break existing tests; Task 7 wires the graph once all normalizers are complete.

**Step 5: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py
git commit -m "fix: reject coordinate-only HGVS evidence values"
```

---

### Task 3: Normalize Core ACMG Field Values

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py`

**Step 1: Add failing tests**

Append:

```python
def test_de_novo_status_is_normalized_to_enum_value() -> None:
    inputs = [
        _item("C.de_novo_status", "not de novo"),
        _item("C.de_novo_status", False),
        _item("C.de_novo_status", 0),
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == ["not_de_novo", "not_de_novo", "not_de_novo"]
    assert [issue.issue_type.value for issue in issues] == [
        "value_normalized",
        "value_normalized",
        "value_normalized",
    ]


def test_consanguinity_preserves_detail_and_normalizes_status() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize([
        _item("B.consanguinity", "first-degree maternal cousins"),
    ])

    assert items[0].value == "present:first-degree maternal cousins"


def test_consanguinity_unknown_is_not_marked_present() -> None:
    inputs = [
        _item("B.consanguinity", "unknown"),
        _item("B.consanguinity", "N/A"),
        _item("B.consanguinity", "not applicable"),
    ]

    items, _ = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == ["unknown", "unknown", "unknown"]


def test_obligate_carriers_numeric_and_parent_text_normalize_to_count() -> None:
    inputs = [_item("C.obligate_carriers", "parents"), _item("C.obligate_carriers", True)]

    items, _ = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == [2, 2]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py -v
```

Expected: FAIL on the new normalization expectations.

**Step 3: Implement field mappings**

Add private methods to `AcmgEvidenceValueNormalizer`:

```python
    def _normalize_one(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        # keep existing HGVS logic first
        ...
        if item.field_id == "C.de_novo_status":
            return self._normalize_de_novo(item)
        if item.field_id == "B.consanguinity":
            return self._normalize_consanguinity(item)
        if item.field_id == "C.obligate_carriers":
            return self._normalize_obligate_carriers(item)
        return item, []

    def _with_value_issue(self, item: EvidenceItem, normalized_value: object) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        return (
            item.model_copy(update={"value": normalized_value}),
            [
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.VALUE_NORMALIZED,
                    severity=EvidenceNormalizationSeverity.INFO,
                    field_id=item.field_id,
                    message="Field value normalized to ACMG-ready representation.",
                    original_value=item.value,
                    normalized_value=normalized_value,
                )
            ],
        )

    def _normalize_de_novo(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip().lower()
        if item.value is False or text in {"0", "false", "not de novo", "not_de_novo", "inherited"}:
            return self._with_value_issue(item, "not_de_novo")
        if item.value is True or text in {"1", "true", "de novo", "denovo"}:
            return self._with_value_issue(item, "de_novo")
        if text in {"unknown", "not reported", "not_reported"}:
            return self._with_value_issue(item, "unknown")
        return item, []

    def _normalize_consanguinity(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip()
        lower = text.lower()
        if lower in {"present", "consanguineous", "true"}:
            return self._with_value_issue(item, "present")
        if lower in {"absent", "non-consanguineous", "false"}:
            return self._with_value_issue(item, "absent")
        if lower in {"unknown", "not reported", "not_reported", "not applicable", "n/a", "na"}:
            return self._with_value_issue(item, "unknown")
        if text:
            return self._with_value_issue(item, f"present:{text}")
        return item, []

    def _normalize_obligate_carriers(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if item.value is True:
            return self._with_value_issue(item, 2)
        if item.value is False:
            return self._with_value_issue(item, 0)
        if isinstance(item.value, int):
            return item, []
        text = str(item.value).strip().lower()
        if text in {"parents", "both parents"}:
            return self._with_value_issue(item, 2)
        if text.isdigit():
            return self._with_value_issue(item, int(text))
        return item, []
```

Use `object` internally only as parameter type; do not use bare dict return values.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py
git commit -m "fix: normalize ACMG segregation field values"
```

---

### Task 4: Guard Age of Onset Against Milestone Misclassification

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Add failing value-normalization test**

Append:

```python
def test_age_of_onset_rejects_developmental_milestone_text() -> None:
    item = _item("B.age_of_onset", "started sitting with support at the age of 15 months")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "semantic_conflict"


def test_age_of_onset_does_not_reject_non_milestone_support_text() -> None:
    item = _item("B.age_of_onset", "required respiratory support from age 2")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == "required respiratory support from age 2"
    assert issues == []
```

**Step 2: Add failing prompt test**

Add to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import EVIDENCE_FIELD_SPECS
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import get_catalog_extraction_prompt


def test_catalog_prompt_distinguishes_age_of_onset_from_milestones() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="started sitting with support at the age of 15 months; referred at 17 months",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "Do NOT use developmental milestones as B.age_of_onset" in prompt
    assert "referral, diagnosis, first symptoms, or presentation age" in prompt
```

**Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py::test_age_of_onset_rejects_developmental_milestone_text \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_distinguishes_age_of_onset_from_milestones \
  -v
```

Expected: FAIL.

**Step 4: Implement deterministic guard**

In `AcmgEvidenceValueNormalizer._normalize_one`, add:

```python
        if item.field_id == "B.age_of_onset":
            return self._normalize_age_of_onset(item)
```

Add:

```python
    def _normalize_age_of_onset(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip()
        lower = text.lower()
        milestone_patterns = (
            r"\bstarted sitting\b",
            r"\bsitting with support\b",
            r"\bstarted walking\b",
            r"\bdelayed walking\b",
            r"\bstarted speaking\b",
            r"\bdevelopmental milestone\b",
        )
        onset_terms = ("onset", "presented", "presentation", "diagnosed", "referred", "symptom")
        if any(re.search(pattern, lower) for pattern in milestone_patterns) and not any(term in lower for term in onset_terms):
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.SEMANTIC_CONFLICT,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Developmental milestone age must not be used as age of onset.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []
```

**Step 5: Update prompt**

In `get_catalog_extraction_prompt`, add a new rule after the disease diagnosis rules:

```text
20. For B.age_of_onset, extract referral, diagnosis, first symptoms, or presentation age. Do NOT use developmental milestones as B.age_of_onset, for example sitting, walking, or speaking ages unless the sentence explicitly states symptom onset.
```

**Step 6: Run tests**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py::test_age_of_onset_rejects_developmental_milestone_text \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_distinguishes_age_of_onset_from_milestones \
  -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
git commit -m "fix: prevent milestone ages from onset extraction"
```

---

### Task 5: Separate Computational Prediction From Functional Evidence

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Add failing tests**

Append:

```python
def test_in_silico_functional_phrase_is_not_functional_evidence() -> None:
    item = _item("F.functional_result", "functional analysis predicted by in silico tools")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "semantic_conflict"


def test_generic_prediction_tool_name_is_rejected() -> None:
    item = _item("E.prediction_tools_list", "in silico tools")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "generic_prediction_tool"


def test_empty_prediction_tools_list_is_not_generic_tool_evidence() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([
        _item("E.prediction_tools_list", []),
    ])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues == []


def test_mixed_prediction_tools_filters_generic_entry_with_audit_issue() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([
        _item("E.prediction_tools_list", ["CADD", "in silico tools"]),
    ])

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == ["CADD"]
    assert [issue.issue_type.value for issue in issues] == [
        "value_normalized",
        "generic_prediction_tool",
    ]
```

Add to `test_prompts.py`:

```python
def test_catalog_prompt_requires_named_prediction_tools() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="functional analysis by in silico tools",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "Computational predictions support PP3/BP4 only" in prompt
    assert "Do not treat in silico predictions as F.functional_result" in prompt
    assert "E.prediction_tools_list requires named tools" in prompt
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_requires_named_prediction_tools \
  -v
```

Expected: FAIL.

**Step 3: Implement deterministic guards**

In `AcmgEvidenceValueNormalizer._normalize_one`, add:

```python
        if item.field_id.startswith("F."):
            return self._reject_in_silico_functional(item)
        if item.field_id == "E.prediction_tools_list":
            return self._normalize_prediction_tools(item)
```

Add:

```python
    def _reject_in_silico_functional(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value or "").strip().lower()
        if "in silico" in text or "computational" in text:
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.SEMANTIC_CONFLICT,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Computational prediction must not be treated as functional evidence.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _normalize_prediction_tools(self, item: EvidenceItem) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        generic_values = {"in silico tools", "bioinformatics tools", "prediction tools", "computational tools"}
        if isinstance(item.value, list):
            values = [str(value).strip() for value in item.value if str(value).strip()]
            if not values:
                return self._reject_item(item), []
            named = [value for value in values if value.lower() not in generic_values]
            if named:
                replacement, issues = self._with_value_issue(item, named)
                if len(named) != len(values):
                    issues.append(
                        EvidenceNormalizationIssue(
                            issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                            severity=EvidenceNormalizationSeverity.WARNING,
                            field_id=item.field_id,
                            message="Generic prediction-tool phrase removed from named tool list.",
                            original_value=item.value,
                            normalized_value=named,
                        )
                    )
                return replacement, issues
        else:
            text = str(item.value).strip()
            if text.lower() not in generic_values:
                return item, []
        return (
            self._reject_item(item),
            [
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                    severity=EvidenceNormalizationSeverity.WARNING,
                    field_id=item.field_id,
                    message="Prediction tool evidence requires named algorithms.",
                    original_value=item.value,
                )
            ],
        )
```

**Step 4: Update prompt rules**

Add:

```text
21. Computational predictions support PP3/BP4 only. Do not treat in silico predictions as F.functional_result, F.assay_type, or other functional evidence fields unless there is a real wet-lab, cell, animal, or patient-derived assay.
22. E.prediction_tools_list requires named tools such as SpliceAI, CADD, REVEL, PolyPhen-2, SIFT, MutationTaster, or MaxEntScan. Generic phrases like "in silico tools" are insufficient and must be not_found.
```

**Step 5: Run tests**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_requires_named_prediction_tools \
  -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
git commit -m "fix: separate computational and functional evidence"
```

---

### Task 6: Merge Duplicate Evidence Items by Normalized Fact Key

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py`

**Step 1: Add failing test**

Append:

```python
def test_duplicate_facts_merge_by_group_field_and_value() -> None:
    duplicate_items = [
        _item("A.gene_symbol", "AARS2").model_copy(update={"group_id": "gene=AARS2|variant=__missing__", "confidence": 0.80}),
        _item("A.gene_symbol", " AARS2 ").model_copy(update={"group_id": "gene=AARS2|variant=__missing__", "confidence": 0.95}),
        _item("B.age_current_or_last_followup", "10 years").model_copy(update={"group_id": "gene=AARS2|variant=__missing__"}),
        _item("B.age_current_or_last_followup", "10 years").model_copy(update={"group_id": "gene=AARS2|variant=__missing__"}),
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize(duplicate_items)

    assert [(item.field_id, item.value) for item in items] == [
        ("A.gene_symbol", "AARS2"),
        ("B.age_current_or_last_followup", "10 years"),
    ]
    assert items[0].confidence == 0.95
    assert [issue.issue_type.value for issue in issues].count("duplicate_merged") == 2


def test_duplicate_merge_preserves_available_raw_source() -> None:
    source = SourceLocation(
        context_type="text",
        context_ref="case paragraph",
        text_snippet="AARS2",
        block_index=4,
    )
    duplicate_items = [
        _item("A.gene_symbol", "AARS2").model_copy(update={
            "group_id": "gene=AARS2|variant=__missing__",
            "confidence": 0.80,
            "raw_source": source,
        }),
        _item("A.gene_symbol", "AARS2").model_copy(update={
            "group_id": "gene=AARS2|variant=__missing__",
            "confidence": 0.95,
            "raw_source": None,
        }),
    ]

    items, _ = AcmgEvidenceValueNormalizer().normalize(duplicate_items)

    assert items[0].confidence == 0.95
    assert items[0].raw_source == source


def test_duplicate_merge_keeps_distinct_source_blocks() -> None:
    source_1 = SourceLocation(context_type="text", context_ref="case", text_snippet="AARS2", block_index=1)
    source_2 = SourceLocation(context_type="table", context_ref="Table 1", text_snippet="AARS2", block_index=7)

    items, issues = AcmgEvidenceValueNormalizer().normalize([
        _item("A.gene_symbol", "AARS2").model_copy(update={"raw_source": source_1}),
        _item("A.gene_symbol", "AARS2").model_copy(update={"raw_source": source_2}),
    ])

    assert len(items) == 2
    assert issues == []


def test_normalized_value_key_preserves_falsey_values() -> None:
    normalizer = AcmgEvidenceValueNormalizer()

    assert normalizer._normalized_value_key(0) != normalizer._normalized_value_key(None)
    assert normalizer._normalized_value_key(False) != normalizer._normalized_value_key(None)
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py::test_duplicate_facts_merge_by_group_field_and_value -v
```

Expected: FAIL because duplicates are preserved.

**Step 3: Implement merge after per-item normalization**

In `AcmgEvidenceValueNormalizer.normalize`, normalize each item first, then merge:

```python
        merged, merge_issues = self._merge_duplicates(normalized)
        issues.extend(merge_issues)
        return merged, issues
```

Add:

```python
    def _merge_duplicates(self, items: list[EvidenceItem]) -> tuple[list[EvidenceItem], list[EvidenceNormalizationIssue]]:
        by_key: dict[tuple[str, str, str, str], EvidenceItem] = {}
        order: list[tuple[str, str, str, str]] = []
        issues: list[EvidenceNormalizationIssue] = []
        for item in items:
            base_key = (item.group_id, item.field_id, self._normalized_value_key(item.value))
            key = self._dedupe_key(base_key, item, by_key)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = item
                order.append(key)
                continue
            if item.confidence > existing.confidence:
                by_key[key] = self._merge_source(item, existing)
            elif existing.raw_source is None and item.raw_source is not None:
                by_key[key] = existing.model_copy(update={"raw_source": item.raw_source})
            issues.append(
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.DUPLICATE_MERGED,
                    severity=EvidenceNormalizationSeverity.INFO,
                    field_id=item.field_id,
                    message="Duplicate evidence item merged by normalized fact key.",
                    original_value=item.value,
                    normalized_value=by_key[key].value,
                )
            )
        return [by_key[key] for key in order], issues

    def _dedupe_key(
        self,
        base_key: tuple[str, str, str],
        item: EvidenceItem,
        by_key: dict[tuple[str, str, str, str], EvidenceItem],
    ) -> tuple[str, str, str, str]:
        source_signature = self._source_signature(item)
        exact_key = (*base_key, source_signature)
        if exact_key in by_key:
            return exact_key
        if source_signature == "source:none":
            for existing_key in by_key:
                if existing_key[:3] == base_key:
                    return existing_key
            return exact_key
        none_key = (*base_key, "source:none")
        if none_key in by_key:
            return none_key
        return exact_key

    def _normalized_value_key(self, value: object) -> str:
        if isinstance(value, list):
            return "list:" + "|".join(sorted(str(entry).strip().lower() for entry in value))
        if value is None:
            return "none:"
        normalized_text = re.sub(r"\s+", " ", str(value).strip().lower())
        return f"{type(value).__name__}:{normalized_text}"

    def _source_signature(self, item: EvidenceItem) -> str:
        source = item.raw_source or item.source
        if source is None:
            return "source:none"
        return f"source:{source.block_index}:{source.context_type}:{source.context_ref}:{source.text_snippet}"

    def _merge_source(self, winner: EvidenceItem, loser: EvidenceItem) -> EvidenceItem:
        if winner.raw_source is None and loser.raw_source is not None:
            return winner.model_copy(update={"raw_source": loser.raw_source})
        if winner.source is None and loser.source is not None:
            return winner.model_copy(update={"source": loser.source})
        return winner
```

If Ruff flags `dict[...]` return annotations, this code is okay because no function returns a bare dict. It only uses a local mapping.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py
git commit -m "fix: merge duplicate extracted evidence facts"
```

---

### Task 7: Wire Normalization Into Phase 2 Workflow

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`

**Step 1: Add failing workflow test**

Add to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionState,
    EvidenceItem,
    EvidenceStatus,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import (
    AcmgEvidenceValueNormalizer,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import EvidenceExtractionWorkflow


def test_workflow_normalization_node_rejects_coordinate_only_hgvs() -> None:
    workflow = EvidenceExtractionWorkflow.__new__(EvidenceExtractionWorkflow)
    workflow._value_normalizer = AcmgEvidenceValueNormalizer()
    state = EvidenceExtractionState(
        document=TrackDocument(
            document_id="doc",
            track=Track.ORIGINAL,
            formatted_text="chr6_44270253",
            page_spans=[],
        ),
        evidence_items=[
            EvidenceItem(
                field_id="A.variant_hgvs_g",
                category="A",
                field_name="HGVS genomic variant",
                status=EvidenceStatus.FOUND,
                value="chr6_44270253",
                confidence=0.9,
            )
        ],
    )

    result = workflow._node_value_normalization(state)

    assert result.evidence_items[0].status == EvidenceStatus.NOT_FOUND
    assert result.normalization_issues[0].field_id == "A.variant_hgvs_g"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py::test_workflow_normalization_node_rejects_coordinate_only_hgvs -v
```

Expected: FAIL because `_node_value_normalization` does not exist.

**Step 3: Add normalization node**

In `workflow.py`, import:

```python
from .normalization import AcmgEvidenceValueNormalizer
```

In `__init__`, add:

```python
        self._value_normalizer = AcmgEvidenceValueNormalizer()
```

Add:

```python
    def _node_value_normalization(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        value_normalizer = getattr(self, "_value_normalizer", AcmgEvidenceValueNormalizer())
        items, issues = value_normalizer.normalize(state.evidence_items)
        state.evidence_items = items
        state.normalization_issues = [*state.normalization_issues, *issues]
        return state
```

Wire graph edges by replacing the existing direct `group_assignment -> source_grounding` edge. Do not leave both paths in place.

```python
graph.add_node("value_normalization", self._node_value_normalization)
graph.add_edge("catalog_extraction", "special_evidence")
graph.add_edge("special_evidence", "group_assignment")
graph.add_edge("group_assignment", "value_normalization")
graph.add_edge("value_normalization", "source_grounding")
```

Apply the same node and edge replacement to `_build_async_graph`: add `value_normalization`, add `group_assignment -> value_normalization`, add `value_normalization -> source_grounding`, and remove the old `group_assignment -> source_grounding` edge in both sync and async graph builders.

**Step 4: Propagate issues through service result**

In `api.py`, when returning `EvidenceExtractionResult`, include:

```python
normalization_issues=state.normalization_issues,
```

**Step 5: Run workflow tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py
git commit -m "feat: add ACMG evidence normalization stage"
```

---

### Task 8: Add ACMG-Ready Projection Contracts in Phase 3

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/contracts.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py`

**Step 1: Write failing tests**

Add:

```python
from src.core.standardize_entities_and_align_knowledge.contracts import (
    AcmgReadyEvidenceItem,
    AcmgReadyEvidenceSet,
)


def test_acmg_ready_contracts_capture_hpo_ids_and_normalized_values() -> None:
    item = AcmgReadyEvidenceItem(
        field_id="B.clinical_phenotypes",
        normalized_key="clinical_phenotypes",
        normalized_value=["HP:0001263", "HP:0001252"],
        raw_values=("global developmental delay", "hypotonia"),
        source_field_ids=("B.clinical_phenotypes",),
    )
    evidence_set = AcmgReadyEvidenceSet(document_id="doc-1", items=(item,))

    assert evidence_set.items[0].normalized_value == ["HP:0001263", "HP:0001252"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py::test_acmg_ready_contracts_capture_hpo_ids_and_normalized_values -v
```

Expected: FAIL with import error.

**Step 3: Add dataclass contracts**

Add to `contracts.py`:

```python
@dataclass(frozen=True)
class AcmgReadyEvidenceItem:
    """Normalized evidence fact suitable for rules-based ACMG consumers."""

    field_id: str
    normalized_key: str
    normalized_value: str | int | float | bool | list[str] | None
    raw_values: tuple[str, ...] = ()
    source_field_ids: tuple[str, ...] = ()
    confidence: float = 0.0


@dataclass(frozen=True)
class AcmgReadyEvidenceSet:
    """Document-level normalized evidence projection for ACMG scoring consumers."""

    document_id: str
    items: tuple[AcmgReadyEvidenceItem, ...] = ()
```

Add `acmg_ready: AcmgReadyEvidenceSet | None = None` to `StandardizationResult`.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/contracts.py backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py
git commit -m "feat: add ACMG-ready evidence projection contracts"
```

---

### Task 9: Project Phenotypes to HPO IDs When Standardized

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/acmg_projection.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/core.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_acmg_projection.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_core.py`

**Step 1: Write failing projection test**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_acmg_projection.py`:

```python
"""Tests for ACMG-ready normalized evidence projection."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.standardize_entities_and_align_knowledge.acmg_projection import AcmgReadyProjector
from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
    StandardizationInput,
)


def test_projector_maps_clinical_phenotypes_to_hpo_ids() -> None:
    item = EvidenceItem(
        field_id="B.clinical_phenotypes",
        category="B",
        field_name="Key clinical phenotypes",
        status=EvidenceStatus.FOUND,
        value="global developmental delay, hypotonia",
        confidence=0.9,
        group_id="gene=AARS2|variant=__missing__",
    )
    candidate = StandardizationCandidate(
        candidate_id="gene=AARS2|variant=__missing__:phenotype:0",
        entity_type=EntityType.PHENOTYPE,
        role=BindingRole.CONTEXT,
        raw_text="global developmental delay",
        chain_id="gene=AARS2|variant=__missing__",
        track="original",
        field_id="B.clinical_phenotypes",
    )
    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.STANDARDIZED,
        external_id="HP:0001263",
        display_name="Global developmental delay",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(item,),
    )

    result = AcmgReadyProjector().project(input_data, (match,))

    assert result.document_id == "doc-1"
    assert result.items[0].field_id == "B.clinical_phenotypes"
    assert result.items[0].normalized_key == "hpo_terms"
    assert result.items[0].normalized_value == ["HP:0001263"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_acmg_projection.py -v
```

Expected: FAIL because `acmg_projection.py` does not exist.

**Step 3: Implement projector**

Create `backend/src/core/standardize_entities_and_align_knowledge/acmg_projection.py`:

```python
"""Project standardized entities into ACMG-ready evidence facts."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.standardize_entities_and_align_knowledge.contracts import (
    AcmgReadyEvidenceItem,
    AcmgReadyEvidenceSet,
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationInput,
)


class AcmgReadyProjector:
    """Build compact key-value evidence for downstream rules-based ACMG consumers."""

    def project(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> AcmgReadyEvidenceSet:
        items: list[AcmgReadyEvidenceItem] = []
        hpo_ids = self._hpo_ids(matches)
        phenotype_raw_values = self._raw_values(input_data.evidence_items, {"B.hpo_terms", "B.clinical_phenotypes"})
        if hpo_ids:
            items.append(
                AcmgReadyEvidenceItem(
                    field_id="B.clinical_phenotypes",
                    normalized_key="hpo_terms",
                    normalized_value=hpo_ids,
                    raw_values=phenotype_raw_values,
                    source_field_ids=("B.hpo_terms", "B.clinical_phenotypes"),
                    confidence=self._max_confidence(input_data.evidence_items, {"B.hpo_terms", "B.clinical_phenotypes"}),
                )
            )
        return AcmgReadyEvidenceSet(document_id=input_data.document_id, items=tuple(items))

    def _hpo_ids(self, matches: tuple[EntityMatch, ...]) -> list[str]:
        ids = []
        for match in matches:
            if (
                match.candidate.entity_type == EntityType.PHENOTYPE
                and match.status == MatchStatus.STANDARDIZED
                and match.external_id
                and match.external_id.startswith("HP:")
                and match.external_id not in ids
            ):
                ids.append(match.external_id)
        return ids

    def _raw_values(self, evidence_items: tuple[object, ...], field_ids: set[str]) -> tuple[str, ...]:
        values: list[str] = []
        for item in evidence_items:
            if not isinstance(item, EvidenceItem) or item.status != EvidenceStatus.FOUND or item.field_id not in field_ids:
                continue
            if isinstance(item.value, list):
                values.extend(str(value) for value in item.value)
            elif item.value is not None:
                values.append(str(item.value))
        return tuple(values)

    def _max_confidence(self, evidence_items: tuple[object, ...], field_ids: set[str]) -> float:
        confidences = [
            item.confidence
            for item in evidence_items
            if isinstance(item, EvidenceItem) and item.status == EvidenceStatus.FOUND and item.field_id in field_ids
        ]
        return max(confidences, default=0.0)
```

**Step 4: Wire into StandardizationService**

In `core.py`, import `AcmgReadyProjector`, instantiate in `__init__`, and include projection in `StandardizationResult`:

```python
from src.core.standardize_entities_and_align_knowledge.acmg_projection import AcmgReadyProjector

class StandardizationService:
    def __init__(self, matcher: TerminologyMatcher, repository: StandardizationRepository):
        self._matcher = matcher
        self._repository = repository
        self._acmg_projector = AcmgReadyProjector()
```

Before return:

```python
        acmg_ready = self._acmg_projector.project(input_data, matches)
```

Return:

```python
            acmg_ready=acmg_ready,
```

**Step 5: Add service test**

Append to `backend/tests/core/standardize_entities_and_align_knowledge/test_core.py`:

```python
@pytest.mark.asyncio
async def test_standardization_service_returns_acmg_ready_projection() -> None:
    candidate = StandardizationCandidate(
        candidate_id="phenotype-1",
        entity_type=EntityType.PHENOTYPE,
        role=BindingRole.CONTEXT,
        raw_text="hypotonia",
        chain_id="chain-1",
        track="original",
        field_id="B.clinical_phenotypes",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )

    class HpoMatcher:
        async def match(self, candidate):
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id="HP:0001252",
                display_name="Hypotonia",
            )

    result = await StandardizationService(HpoMatcher(), FakeRepository()).run(input_data)

    assert result.acmg_ready is not None
    assert result.acmg_ready.items[0].normalized_value == ["HP:0001252"]
```

**Step 6: Run tests**

Run:

```bash
cd backend
uv run pytest \
  tests/core/standardize_entities_and_align_knowledge/test_acmg_projection.py \
  tests/core/standardize_entities_and_align_knowledge/test_core.py \
  -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/acmg_projection.py backend/src/core/standardize_entities_and_align_knowledge/core.py backend/tests/core/standardize_entities_and_align_knowledge/test_acmg_projection.py backend/tests/core/standardize_entities_and_align_knowledge/test_core.py
git commit -m "feat: project standardized evidence to ACMG-ready facts"
```

---

### Task 10: Add Regression Fixture for the AARS2 Review Case

**Files:**
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_aars2_regression.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`

**Step 1: Write focused regression test**

Create:

```python
"""Regression tests for AARS2 extraction review findings."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import (
    AcmgEvidenceValueNormalizer,
)


def _found(field_id: str, value: object, confidence: float = 0.9) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=confidence,
        group_id="gene=AARS2|variant=__missing__",
    )


def test_aars2_review_errors_are_normalized_or_rejected() -> None:
    items = [
        _found("A.gene_symbol", "AARS2", 0.8),
        _found("A.gene_symbol", "AARS2", 0.9),
        _found("A.variant_hgvs_g", "chr6_44270253"),
        _found("A.reference_sequence", "chr6_44270253"),
        _found("A.variant_legacy_name", "chr6_44270253"),
        _found("A.splice_or_synonymous_effect", "flanking the splice site acceptor sequence of exon 18"),
        _found("B.age_of_onset", "started sitting with support at the age of 15 months"),
        _found("B.age_current_or_last_followup", "10 years"),
        _found("B.age_current_or_last_followup", "10 years"),
        _found("F.functional_result", "functional analysis by in silico tools"),
        _found("E.prediction_tools_list", "in silico tools"),
        _found("C.de_novo_status", "not de novo"),
        _found("B.consanguinity", "first-degree maternal cousins"),
        _found("C.obligate_carriers", "parents"),
    ]

    normalized, issues = AcmgEvidenceValueNormalizer().normalize(items)
    by_field = {item.field_id: item for item in normalized}

    assert by_field["A.gene_symbol"].confidence == 0.9
    assert by_field["A.variant_hgvs_g"].status == EvidenceStatus.NOT_FOUND
    assert by_field["A.reference_sequence"].status == EvidenceStatus.NOT_FOUND
    assert by_field["A.variant_legacy_name"].status == EvidenceStatus.NOT_FOUND
    assert by_field["B.age_of_onset"].status == EvidenceStatus.NOT_FOUND
    assert by_field["F.functional_result"].status == EvidenceStatus.NOT_FOUND
    assert by_field["E.prediction_tools_list"].status == EvidenceStatus.NOT_FOUND
    assert by_field["C.de_novo_status"].value == "not_de_novo"
    assert by_field["B.consanguinity"].value == "present:first-degree maternal cousins"
    assert by_field["C.obligate_carriers"].value == 2
    assert len([item for item in normalized if item.field_id == "B.age_current_or_last_followup"]) == 1
    assert len(issues) >= 8
```

**Step 2: Run test**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_aars2_regression.py -v
```

Expected: PASS if prior tasks are complete; otherwise fix only the minimal normalizer logic needed.

**Step 3: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_aars2_regression.py backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py
git commit -m "test: add AARS2 evidence normalization regression coverage"
```

---

### Task 11: Update Developer Documentation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/README.md`
- Modify: `progress.txt`

**Step 1: Update Phase 2 README**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md`, add a short section:

```markdown
## ACMG Value Normalization

`normalization.py` runs after group assignment and before source grounding. It rejects coordinate-only HGVS/reference values, normalizes segregation and family values, blocks developmental milestone ages from `B.age_of_onset`, keeps computational prediction evidence out of functional evidence fields, and merges duplicate facts by `(group_id, field_id, normalized_value)`.

Normalization emits `EvidenceNormalizationIssue` records so UI and review workflows can show exactly which extracted values were rejected or rewritten.
```

**Step 2: Update Phase 3 README**

In `backend/src/core/standardize_entities_and_align_knowledge/README.md`, add:

```markdown
## ACMG-Ready Projection

`acmg_projection.py` converts standardized entity matches into compact rules-engine facts. Phenotype matches with `HP:` identifiers are exposed as `hpo_terms`, while unmapped phenotype text remains available in the original evidence items for human review.
```

**Step 3: Record project progress**

Append to root `progress.txt`:

```text
[2026-06-09] ACMG evidence normalization and HPO projection fixes planned [completed]
```

**Step 4: Run doc-related checks**

Run:

```bash
cd backend
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence src/core/standardize_entities_and_align_knowledge tests/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/standardize_entities_and_align_knowledge
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md backend/src/core/standardize_entities_and_align_knowledge/README.md progress.txt
git commit -m "docs: document ACMG evidence normalization flow"
```

---

### Task 12: Final Verification and Review Package

**Files:**
- Modify: `lesson.md` only if debugging or failed iterations occurred during execution

**Step 1: Run focused backend tests**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_value_normalization.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_aars2_regression.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow_async.py \
  tests/core/standardize_entities_and_align_knowledge/test_acmg_projection.py \
  tests/core/standardize_entities_and_align_knowledge/test_core.py \
  -v
```

Expected: PASS.

**Step 2: Run wider module tests**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence \
  tests/core/standardize_entities_and_align_knowledge \
  -v
```

Expected: PASS.

**Step 3: Run lint**

Run:

```bash
cd backend
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence src/core/standardize_entities_and_align_knowledge tests/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/standardize_entities_and_align_knowledge
```

Expected: PASS.

**Step 4: Request code review**

Use @requesting-code-review before merge. Review focus:

- No coordinate-only values survive in HGVS/reference fields.
- Prompt rules and deterministic normalization agree.
- No stable function return type uses bare `dict`.
- Duplicate merge does not collapse distinct variant groups.
- HPO projection only emits standardized `HP:` IDs and preserves raw text.

**Step 5: Final commit if documentation/lesson updates remain**

```bash
git status --short
git add lesson.md progress.txt
git commit -m "docs: record ACMG normalization verification notes"
```

Only run this commit if those files changed during implementation.
