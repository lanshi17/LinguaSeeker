# Plan A — Drop 4 Free-Text `_notes` Fields

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`.

**Status:** ready
**Created:** 2026-06-16
**Supersedes part of:** `docs/archive/2026-06-16-sparse-evidence-output-superseded.md` (Tasks 7–8)

**Goal:** Remove the 4 catalog fields that are pure free-text and never used by any ACMG / ClinGen scoring code: `B.case_notes`, `E.computational_evidence_notes`, `H.contradiction_notes`, `I.gene_level_experimental_notes`. Catalog goes from 138 → 134 fields.

**Why this is a real LLM-token win (unlike sparse filtering):** these fields appear inside the catalog block injected into every catalog-extraction prompt, so the LLM is currently asked to fill them on **both** input (the field row inside the catalog table) and output (the `EvidenceItem` for each one). Deleting them shrinks both ends of the prompt without touching extraction quality, because they have zero downstream consumers.

**Architecture:** Single-file catalog edit in `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py`, plus the two test fixtures in `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py` that reference `B.case_notes`. No production behavior depends on these field IDs.

**Tech Stack:** Python, Pydantic v2, pytest.

---

## Audit Evidence

Confirmed via repo-wide grep on 2026-06-16 (literal `\.` matches via `grep -F`):

| Field ID | Production refs | Test refs | Downstream consumers |
|---|---|---|---|
| `B.case_notes` | `catalog.py:62` | `test_stages.py:474, 507` | none |
| `E.computational_evidence_notes` | `catalog.py:103` | none | none |
| `H.contradiction_notes` | `catalog.py:148` | none | none |
| `I.gene_level_experimental_notes` | `catalog.py:168` | none | none |

The two `test_stages.py` references are inside `test_special_evidence_stage_keeps_non_g_case_control_when_document_text_is_traceable`. Both can be retargeted onto an existing scoring field — the test asserts source-grounding behavior, not the specific catalog field used.

`acmg_codes=()` and `clingen_modules` for these specs:

| Field | acmg_codes | clingen_modules |
|---|---|---|
| `B.case_notes` | `()` | `("phenotype_consistency",)` |
| `E.computational_evidence_notes` | `("PP3", "BP4")` | `("computational",)` |
| `H.contradiction_notes` | `("BP5", "BS4")` | `("contradiction",)` |
| `I.gene_level_experimental_notes` | `()` | `("function",)` |

The `acmg_codes` on `E.computational_evidence_notes` and `H.contradiction_notes` are spurious — they tag a free-text "notes" field with codes that are already covered by structured fields (`E.deleterious_prediction_summary`, `E.benign_prediction_summary`, `E.prediction_conflict` for PP3/BP4; `H.misdiagnosis_or_reclassification`, `H.alternative_causative_gene`, `H.other_pathogenic_variant`, `H.non_segregation` for BP5/BS4). Removing them does not orphan any code.

---

## Task 1 — Delete 4 catalog entries

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py`

**Step 1: Apply the edit**

Remove these 4 lines (line numbers from the current snapshot; resolve fresh tag before editing):

- Line 62: `EvidenceFieldSpec("B.case_notes", "B", ...)`
- Line 103: `EvidenceFieldSpec("E.computational_evidence_notes", "E", ...)`
- Line 148: `EvidenceFieldSpec("H.contradiction_notes", "H", ...)`
- Line 168: `EvidenceFieldSpec("I.gene_level_experimental_notes", "I", ...)`

Update the comment on line 188 from `# Split 138 fields into 2 balanced groups` to `# Split 134 fields into 2 balanced groups`. Also update the docstring on `stages/catalog_extraction.py:3-5` from `the 138-field catalog` to `the 134-field catalog` (and `~63 and ~75 fields` → `~62 and ~72 fields`).

**Step 2: Verify counts via Python**

```bash
cd backend && uv run python -c "
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import EVIDENCE_FIELD_SPECS, CATALOG_GROUPS
from collections import Counter
print('total:', len(EVIDENCE_FIELD_SPECS))
print('by category:', Counter(s.category_id for s in EVIDENCE_FIELD_SPECS))
print('high_signal:', len(CATALOG_GROUPS['high_signal']))
print('supporting:', len(CATALOG_GROUPS['supporting']))
"
```

Expected:
- total = 134
- A=18, B=21, C=18, D=9, E=7, F=17, G=12, H=9, I=17, J=6
- high_signal = 61 (A18 + B21 + D9 + E7 + J6)
- supporting = 73 (C18 + F17 + G12 + H9 + I17)

**Step 3: No commit yet — Task 2 fixes the broken catalog test, then commit together.**

---

## Task 2 — Update `test_catalog.py` category counts

**Files:**
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py`

**Step 1: Update the expected dict in `test_catalog_has_expected_category_counts`**

```python
assert counts == {
    "A": 18,
    "B": 21,  # was 22
    "C": 18,
    "D": 9,
    "E": 7,   # was 8
    "F": 17,
    "G": 12,
    "H": 9,   # was 10
    "I": 17,  # was 18
    "J": 6,
}
```

**Step 2: Run the catalog test**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py -v
```

Expected: 3 PASS.

---

## Task 3 — Retarget `test_stages.py` fixtures off `B.case_notes`

**Files:**
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

The test `test_special_evidence_stage_keeps_non_g_case_control_when_document_text_is_traceable` (lines 468–530) cares about source-grounding traceability, not the specific catalog field. Retarget both `B.case_notes` references onto `B.clinical_phenotypes` (an existing kept field with the same category and a similarly free-form `value`). The text snippet `"Fabry disease"` already matches a phenotype context, so no other changes are needed.

**Step 1: Apply two edits**

- Line 474: `"evidence_field_ids": ["B.disease_diagnosis", "B.case_notes"]` → `"evidence_field_ids": ["B.disease_diagnosis", "B.clinical_phenotypes"]`
- Line 507: `field_id="B.case_notes"` → `field_id="B.clinical_phenotypes"`
- Line 509: `field_name="Case notes"` → `field_name="Key clinical phenotypes"`
- Line 511: `value="retrospective analysis mentioned"` → `value="Fabry disease"` (matches the snippet, satisfies non-empty value)

**Step 2: Run the affected test**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py::test_special_evidence_stage_keeps_non_g_case_control_when_document_text_is_traceable -v
```

Expected: PASS.

---

## Task 4 — Full extraction-module test sweep

**Files:** none modified.

**Step 1: Run the extraction module's complete pytest tree**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v --tb=short
```

Expected: all PASS. If any test fails referencing one of the 4 deleted field IDs, retarget it onto a sibling (mirroring Task 3) — do **not** re-add the deleted field.

**Step 2: Negative grep — confirm no live code references survive**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua && \
  for fid in 'B.case_notes' 'E.computational_evidence_notes' 'H.contradiction_notes' 'I.gene_level_experimental_notes'; do
    echo "=== $fid ==="
    grep -rn -F "$fid" --include="*.py" backend/ benchmark/ scripts/ 2>/dev/null
  done
```

Expected: every block prints only the `===` header (zero matches). If a benchmark fixture references one, decide case-by-case: prefer retargeting to a kept field; deletion is acceptable when the fixture is not load-bearing.

---

## Task 5 — End-to-end smoke verification on real extraction output

**Files:** none modified.

**Goal:** prove the deleted fields no longer appear in `evidence_items` for at least one already-cached document under `backend/output/extract_evidence/`. This is the only acceptance check that goes beyond unit tests.

**Step 1: Pick a cached fixture document**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua && \
  uv run --project backend python -c "
from pathlib import Path
import json
# pick the most recent result.json
samples = sorted(Path('backend/output/extract_evidence').rglob('result.json'),
                 key=lambda p: p.stat().st_mtime, reverse=True)
print(samples[0])
" >&1 | tail -1
```

Note the path; call it `\$RESULT_JSON`.

**Step 2: Re-run extraction over that document's source**

The cached document has its own input under the same parent directory. Use `backend/scripts/e2e_extract_evidence.py` with the cached inputs:

```bash
cd backend && uv run python scripts/e2e_extract_evidence.py --help | head -30
```

Identify the right CLI shape from `--help`, then re-run extraction targeting the same source the cached `result.json` was built from. Save the new result to a new path so the cache stays available for diffing.

**Step 3: Confirm the deleted fields are absent from the new run**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua && \
  uv run --project backend python -c "
import json, sys
from pathlib import Path
new = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
deleted = {'B.case_notes', 'E.computational_evidence_notes', 'H.contradiction_notes', 'I.gene_level_experimental_notes'}
for track in ('original_result', 'translated_result'):
    items = new.get(track, {}).get('evidence_items', [])
    seen = {it.get('field_id') for it in items}
    leaked = seen & deleted
    print(track, 'items:', len(items), 'leaked deleted fields:', leaked)
    assert not leaked, f'deleted field leaked into {track}: {leaked}'
print('OK')
" "<path-to-new-result.json>"
```

Expected: `OK`. If the LLM still emits `B.case_notes` (it might, since the model has memorized old prompts), the catalog deletion is sufficient — the field is no longer in the catalog text injected into the prompt, so the LLM has no canonical reason to fabricate it. If it leaks anyway, that is signal that prompt-side reinforcement is needed in a follow-up — not a blocker for this plan.

**Step 4: Spot-check item count drop**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua && \
  uv run --project backend python -c "
import json, sys
from pathlib import Path
old = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
new = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
for track in ('original_result', 'translated_result'):
    o = len(old.get(track, {}).get('evidence_items', []))
    n = len(new.get(track, {}).get('evidence_items', []))
    print(f'{track}: {o} -> {n} (delta {n - o:+d})')
" "<old-result.json>" "<new-result.json>"
```

Expected: each populated track drops by exactly 4 (138 → 134). A drop of 0 means the LLM is still echoing the deleted fields and a prompt-side follow-up is needed; record that finding in `lesson.md` and proceed — Task 6 still applies because the catalog-side change is correct and downstream consumers need updating regardless.

---

## Task 6 — Single commit covering catalog + tests

**Files:** none modified beyond previous tasks.

**Step 1: Stage and commit**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua && git add \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  && git commit -m "refactor(catalog): drop 4 free-text _notes fields (138→134)

These four fields had no downstream consumers and produced unstructured
free-text the scoring pipeline never read:

- B.case_notes
- E.computational_evidence_notes
- H.contradiction_notes
- I.gene_level_experimental_notes

They were duplicating ACMG signal already covered by structured siblings
(E.{deleterious,benign,conflict}_prediction_summary, H.misdiagnosis_or_*,
H.non_segregation). Catalog group counts updated to 61/73 (was 63/75).
Test fixtures retargeted onto B.clinical_phenotypes."
```

**Step 2: Update progress.txt**

Append:

```
[2026-06-16] [Drop 4 free-text _notes catalog fields; 138->134] [DONE]
```

**Step 3: Archive this plan**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua && \
  mv docs/plans/2026-06-16-plan-a-drop-notes-fields.md docs/archive/
```

---

## Summary

**Total tasks:** 6
**Estimated time:** 20–30 minutes
**Risk:** very low — these fields have zero non-test consumers and the two test references are easily retargeted.

**What this plan does NOT do** (and earlier `2026-06-16-sparse-evidence-output.md` falsely promised):

- Does **not** reduce LLM API output tokens for the *other 134* fields. The LLM still returns one `EvidenceItem` per kept field, each with `status=found|not_found`. To shrink LLM output for fields that remain, you must change `prompts.py:202` to instruct the model to omit absent fields and remove all "for each catalog field" wording — that is a separate, higher-risk change deferred to **Plan C** (sparse-emission prompt) once recall regression has been measured against the existing benchmark sets.

**What this plan DOES win:**

- Per-call prompt input shrinks by 4 catalog rows.
- Per-call LLM output shrinks by 4 `EvidenceItem` JSON objects (~2 % of catalog output).
- 4 fewer fields for the source-grounding stage to reconcile.
- Eliminates 4 fields whose `acmg_codes` were redundant with structured siblings, reducing scoring ambiguity.

**Follow-ups (not in this plan):**

- **Plan B** — drop `not_found` items from the *serialized* result.json (memory-only filter). Pure cosmetic / disk-size win; doesn't touch LLM cost.
- **Plan C** — change `prompts.py` to request sparse emission. Real LLM-cost win, but needs a recall-regression benchmark before merge.
