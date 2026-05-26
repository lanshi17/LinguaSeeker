# Standardize Entities: Audit Output & Match Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix Phase 3 entity standardization so that (a) output is auditable without DB access, (b) core biomedical entities (disease synonyms, variant nomenclature, compound phenotypes) are correctly matched, and (c) summary metadata is truthful.

**Architecture:** Changes stay inside the existing `standardize_entities_and_align_knowledge/` vertical slice. Extend contracts to carry full match detail through to output, fix adapter phenotype splitting, add cross-lingual normalization for disease names, and write a `matches.json` output file. The orchestrator and repository layers get minimal surgical edits.

**Tech Stack:** Python 3.12, dataclasses, loguru, pytest, uv, Ruff

---

**Status:** completed
**Created:** 2026-05-26
**Completed:** 2026-05-26
**PR:** —

## Context

The Phase 3 standardization module has five confirmed issues from a real-case run on "法布雷病1例":

1. **Output not auditable**: `result.json` only has counts + UUID list. `summary.json` repeats the same. No per-entity raw_text, entity_type, status, external_id, display_name, or rationale. Auditing requires DB queries.
2. **Core entities unmapped**: 法布雷病, p.R227X, Chinese compound phenotypes ("水肿、蛋白尿、心律失常..."), and several English phenotypes (Gastrointestinal symptoms, Myocardial hypertrophy, etc.) all fall to unmapped.
3. **Chinese disease synonyms not merged**: "Fabry disease" maps to OMIM:301500 via precise match, but "法布雷病" stays unmapped — they should resolve to the same disease entity.
4. **Phenotype splitting inconsistent**: Chinese `B.clinical_phenotypes` is a 顿号-separated string ("水肿、蛋白尿、心律失常..."), English is comma-separated. The adapter's `_extract_field_values` only handles `list` types, returning the entire compound string as one candidate.
5. **summary.json misleading**: Shows `imported_terminology=false` while simultaneously listing terminology sources/versions, making it unclear whether this was a full or partial run.

### DB Audit Results

- **Standardized**: GLA→HGNC:4296, Fabry disease→OMIM:301500, Edema→HP:0000969, Proteinuria→HP:0000093, Arrhythmia→HP:0011675
- **Unmapped**: 法布雷病, p.R227X, Chinese compound phenotype, Gastrointestinal symptoms, Myocardial hypertrophy, Cardiac valve lesions, Hearing loss, English compound phenotype
- **Most unmapped rationale**: `semantic matching unavailable: SemanticMatchServiceError`

## Task 1: Extend StandardizationResult to carry full match list

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/contracts.py:119-128`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py`

**Step 1: Write the failing test**

```python
# In test_contracts.py, add:
def test_standardization_result_carries_matches() -> None:
    """StandardizationResult includes the full match tuple for audit output."""
    candidate = StandardizationCandidate(
        candidate_id="c1", entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT, raw_text="BRCA1",
        chain_id="chain-1", track="original",
    )
    match = EntityMatch(
        candidate=candidate, status=MatchStatus.STANDARDIZED,
        external_id="HGNC:1100", display_name="BRCA1",
        rationale="unique HGNC primary match",
    )
    result = StandardizationResult(
        document_id="doc-1", match_count=1,
        standardized_count=1, ambiguous_count=0, unmapped_count=0,
        normalized_entity_ids=("e1",),
        matches=(match,),
    )
    assert len(result.matches) == 1
    assert result.matches[0].candidate.raw_text == "BRCA1"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py::test_standardization_result_carries_matches -v`
Expected: FAIL — `StandardizationResult` has no `matches` field.

**Step 3: Add matches field to StandardizationResult**

```python
# contracts.py — add to StandardizationResult:
    matches: tuple[EntityMatch, ...] = ()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py::test_standardization_result_carries_matches -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/contracts.py backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py
git commit -m "feat: add matches field to StandardizationResult for audit output"
```

## Task 2: Wire StandardizationService to populate matches in result

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/core.py:40-47`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_core.py`

**Step 1: Write the failing test**

```python
# In test_core.py, add:
@pytest.mark.asyncio
async def test_standardization_service_result_includes_matches() -> None:
    """Service result carries the full matches tuple for downstream audit output."""
    candidate = StandardizationCandidate(
        candidate_id="c1", entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT, raw_text="BRCA1",
        chain_id="chain-1", track="original",
    )
    input_data = StandardizationInput(
        document_id="doc-1", source_document_id="source-1",
        processing_run_id="run-1", candidates=(candidate,), evidence_items=(),
    )
    repo = FakeRepository()
    result = await StandardizationService(FakeMatcher(), repo).run(input_data)
    assert len(result.matches) == 1
    assert result.matches[0].candidate.raw_text == "BRCA1"
    assert result.matches[0].status == MatchStatus.STANDARDIZED
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_core.py::test_standardization_service_result_includes_matches -v`
Expected: FAIL — `result.matches` is empty tuple (default).

**Step 3: Wire matches into the result**

```python
# core.py — in StandardizationService.run(), change the return statement:
        return StandardizationResult(
            document_id=input_data.document_id,
            match_count=len(matches),
            standardized_count=sum(match.status == MatchStatus.STANDARDIZED for match in matches),
            ambiguous_count=sum(match.status == MatchStatus.AMBIGUOUS for match in matches),
            unmapped_count=sum(match.status == MatchStatus.UNMAPPED for match in matches),
            normalized_entity_ids=entity_ids,
            matches=matches,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_core.py::test_standardization_service_result_includes_matches -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/core.py backend/tests/core/standardize_entities_and_align_knowledge/test_core.py
git commit -m "feat: wire matches tuple into StandardizationResult from service"
```

## Task 3: Add per-entity detail to result.json and write matches.json

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/api.py` (the script that writes output — find where result.json/summary.json are generated)
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_api.py`

First, find where result.json is written:

```bash
grep -rn "result.json\|summary.json" backend/src/core/standardize_entities_and_align_knowledge/
grep -rn "result.json\|summary.json" backend/src/ --include="*.py" | grep -i standardiz
```

The output script is likely in `backend/src/core/standardize_entities_and_align_knowledge/api.py` or a separate CLI/script. Read it to understand the current output generation.

**Step 1: Write the failing test**

```python
# In test_api.py, add a test for the output serialization:
def test_matches_json_serialization() -> None:
    """EntityMatch list serializes to auditable matches.json format."""
    candidate = StandardizationCandidate(
        candidate_id="c1", entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT, raw_text="GLA",
        chain_id="chain-1", track="original",
    )
    match = EntityMatch(
        candidate=candidate, status=MatchStatus.STANDARDIZED,
        external_id="HGNC:4296", display_name="GLA",
        rationale="unique HGNC primary match",
        match_method=MatchMethod.PRECISE,
    )
    # Test the serialization helper (to be written)
    from src.core.standardize_entities_and_align_knowledge.api import serialize_matches
    entries = serialize_matches((match,))
    assert len(entries) == 1
    entry = entries[0]
    assert entry["raw_text"] == "GLA"
    assert entry["entity_type"] == "gene"
    assert entry["status"] == "standardized"
    assert entry["external_id"] == "HGNC:4296"
    assert entry["display_name"] == "GLA"
    assert entry["rationale"] == "unique HGNC primary match"
    assert entry["match_method"] == "precise"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_api.py::test_matches_json_serialization -v`
Expected: FAIL — `serialize_matches` does not exist.

**Step 3: Implement serialize_matches and update output generation**

Add to `api.py` (or the output-writing module):

```python
def serialize_matches(matches: tuple[EntityMatch, ...]) -> list[dict[str, Any]]:
    """Serialize EntityMatch tuple into auditable JSON-serializable dicts."""
    entries = []
    for match in matches:
        entry = {
            "candidate_id": match.candidate.candidate_id,
            "raw_text": match.candidate.raw_text,
            "entity_type": match.candidate.entity_type.value,
            "chain_id": match.candidate.chain_id,
            "track": match.candidate.track,
            "field_id": match.candidate.field_id,
            "status": match.status.value,
            "external_id": match.external_id,
            "display_name": match.display_name,
            "rationale": match.rationale,
            "match_method": match.match_method.value,
            "similarity_score": match.similarity_score,
        }
        if match.terminology_candidates:
            entry["terminology_candidates"] = [
                {
                    "external_id": tc.external_id,
                    "display_name": tc.display_name,
                    "source_db": tc.source_db,
                    "alias_type": tc.alias_type,
                }
                for tc in match.terminology_candidates
            ]
        entries.append(entry)
    return entries
```

Then in the output-writing code, write `matches.json` using `serialize_matches(result.matches)`, and add `matches` key to `result.json` as well.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_api.py::test_matches_json_serialization -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/api.py backend/tests/core/standardize_entities_and_align_knowledge/test_api.py
git commit -m "feat: add matches.json with per-entity audit detail to standardization output"
```

## Task 4: Fix phenotype string splitting for Chinese and English compound values

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/adapters.py:153-161`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py`

**Problem:** `_extract_field_values` handles `list` values but not compound strings. Chinese phenotypes use 顿号 "、" separator, English use ", ".

**Step 1: Write the failing tests**

```python
# In test_adapters.py, add:
def test_dual_result_adapter_splits_chinese_compound_phenotypes() -> None:
    """The adapter splits 顿号-separated Chinese phenotype strings into individual candidates."""
    result = DualEvidenceExtractionResult(
        document_id="doc-cn",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-cn",
            track=Track.ORIGINAL,
            evidence_items=[
                EvidenceItem(
                    field_id="B.clinical_phenotypes",
                    category="B",
                    field_name="Key clinical phenotypes",
                    status=EvidenceStatus.FOUND,
                    value="水肿、蛋白尿、心律失常",
                    confidence=0.9,
                    group_id="gene=GLA|variant=__missing__",
                ),
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-cn",
            track=Track.TRANSLATED,
        ),
    )
    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result, source_document_id="s1", processing_run_id="r1",
    )
    phenotype_texts = [c.raw_text for c in output.candidates if c.entity_type == EntityType.PHENOTYPE]
    assert phenotype_texts == ["水肿", "蛋白尿", "心律失常"]


def test_dual_result_adapter_splits_english_comma_phenotypes() -> None:
    """The adapter splits comma-separated English phenotype strings into individual candidates."""
    result = DualEvidenceExtractionResult(
        document_id="doc-en",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-en",
            track=Track.ORIGINAL,
            evidence_items=[
                EvidenceItem(
                    field_id="B.clinical_phenotypes",
                    category="B",
                    field_name="Key clinical phenotypes",
                    status=EvidenceStatus.FOUND,
                    value="edema, proteinuria, arrhythmia",
                    confidence=0.9,
                    group_id="gene=GLA|variant=__missing__",
                ),
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-en",
            track=Track.TRANSLATED,
        ),
    )
    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result, source_document_id="s1", processing_run_id="r1",
    )
    phenotype_texts = [c.raw_text for c in output.candidates if c.entity_type == EntityType.PHENOTYPE]
    assert phenotype_texts == ["edema", "proteinuria", "arrhythmia"]
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_adapters.py::test_dual_result_adapter_splits_chinese_compound_phenotypes tests/core/standardize_entities_and_align_knowledge/test_adapters.py::test_dual_result_adapter_splits_english_comma_phenotypes -v`
Expected: FAIL — returns the full compound string as one candidate.

**Step 3: Fix _extract_field_values to split compound strings**

```python
# adapters.py — replace _extract_field_values:
import re

_PHENOTYPE_SPLIT_RE = re.compile(r"[、,;；]")

    def _extract_field_values(self, item: EvidenceItem) -> list[str]:
        """Flatten supported evidence item value shapes into text candidates."""
        value: Any = item.value
        if isinstance(value, list):
            return [str(entry).strip() for entry in value if str(entry).strip()]
        if value is None:
            return []
        text = str(value).strip()
        if not text:
            return []
        if item.field_id in PHENOTYPE_FIELD_IDS and _PHENOTYPE_SPLIT_RE.search(text):
            return [part.strip() for part in _PHENOTYPE_SPLIT_RE.split(text) if part.strip()]
        return [text]
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_adapters.py -v`
Expected: ALL PASS (including existing tests)

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/adapters.py backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py
git commit -m "fix: split compound phenotype strings by 顿号 and comma delimiters"
```

## Task 5: Add cross-lingual disease normalization for Chinese synonym mapping

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/normalizers.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_normalizers.py`

**Problem:** "法布雷病" normalizes to "法布雷病" (casefold), which has no alias in the terminology DB. "Fabry disease" normalizes to "fabry disease" and matches OMIM:301500. The normalizer needs to map common Chinese disease name patterns to their English equivalents for lookup.

**Approach:** Add a lightweight Chinese-to-English disease name lookup table for known synonyms used in the medical genetics domain. This is a pragmatic first step — a full cross-lingual mapping would use the terminology alias table itself (which should already contain Chinese aliases if imported from OMIM/HPO with Chinese synonyms). Check first if the terminology DB has Chinese aliases:

```bash
# Check if terminology aliases include Chinese text
cd backend && uv run python -c "
import asyncio
from src.dao.connection import build_async_engine, async_session_factory, get_async_session
from src.core.config import get_config
from sqlalchemy import text
cfg = get_config()
engine = build_async_engine(cfg)
async def check():
    sf = async_session_factory(engine)
    async with get_async_session(sf) as session:
        r = await session.execute(text(\"SELECT alias_text, normalized_alias, entity_type FROM terminology_aliases WHERE alias_text ~ '[\\\\u4e00-\\\\u9fff]' LIMIT 10\"))
        for row in r:
            print(row)
asyncio.run(check())
"
```

If Chinese aliases exist in DB, the fix is simpler — just ensure `normalize_lookup_text` preserves Chinese characters (it already does via NFKC). The real issue may be that the terminology import didn't include Chinese synonyms.

**Step 1: Write the failing test**

```python
# In test_normalizers.py, add:
def test_normalize_lookup_text_preserves_chinese() -> None:
    """Chinese characters pass through normalization unchanged for alias lookup."""
    assert normalize_lookup_text("法布雷病") == "法布雷病"


def test_normalize_variant_text_strips_p_dot_prefix() -> None:
    """Protein variant notation like p.R227X is normalized for lookup."""
    # This tests that the normalizer handles common variant text formats
    result = normalize_variant_text("p.R227X")
    assert result == "p.R227X"
```

**Step 2: Investigate whether terminology DB has Chinese aliases**

Run the DB check above. If Chinese aliases are missing, the fix is in the import pipeline (adding Chinese OMIM/HPO synonyms). If they exist, the issue is elsewhere in the lookup chain.

**Step 3: Based on investigation, implement the fix**

If Chinese aliases are missing from DB:
- Add Chinese disease name aliases to the terminology import (OMIM already has Chinese names in some entries)
- Or add a cross-lingual alias expansion step in the normalizer

If Chinese aliases exist but lookup fails:
- Debug the `find_alias_candidates` query to see why "法布雷病" doesn't match

For p.R227X:
- Check if ClinVar has this variant. If not, the variant needs to go through similarity matching, which currently fails with `SemanticMatchServiceError`.

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_normalizers.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/normalizers.py backend/tests/core/standardize_entities_and_align_knowledge/test_normalizers.py
git commit -m "fix: ensure Chinese disease names pass through normalization for alias lookup"
```

## Task 6: Fix summary.json to reflect actual terminology import state

**Files:**
- Modify: The output-writing code in `api.py` (wherever summary.json is generated)
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_api.py`

**Problem:** `summary.json` shows `imported_terminology=false` but also lists `terminology_sources` and `terminology_version`, which is misleading.

**Step 1: Write the failing test**

```python
# In test_api.py, add:
def test_summary_includes_terminology_health_status() -> None:
    """Summary output includes DB terminology count and embedding availability."""
    # This test will verify the summary serialization includes health fields
    from src.core.standardize_entities_and_align_knowledge.api import build_summary_metadata
    summary = build_summary_metadata(
        imported_terminology=False,
        terminology_sources=["hgnc", "omim"],
        terminology_version="2026-05-26",
        terminology_entry_count=0,
        embedding_available=False,
    )
    assert summary["imported_terminology"] is False
    assert summary["terminology_entry_count"] == 0
    assert summary["embedding_available"] is False
    # The sources/version should still be present but clearly marked as not imported
    assert summary["terminology_sources"] == ["hgnc", "omim"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_api.py::test_summary_includes_terminology_health_status -v`
Expected: FAIL — `build_summary_metadata` does not exist.

**Step 3: Implement build_summary_metadata and update summary output**

```python
def build_summary_metadata(
    *,
    imported_terminology: bool,
    terminology_sources: list[str],
    terminology_version: str,
    terminology_entry_count: int = 0,
    embedding_available: bool = False,
) -> dict[str, Any]:
    """Build truthful summary metadata with terminology health indicators."""
    return {
        "imported_terminology": imported_terminology,
        "terminology_sources": terminology_sources,
        "terminology_version": terminology_version,
        "terminology_entry_count": terminology_entry_count,
        "embedding_available": embedding_available,
    }
```

Update the summary.json generation to query `terminology_entry_count` from DB (a simple COUNT query on `terminology_entries`) and check embedding availability.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_api.py::test_summary_includes_terminology_health_status -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/api.py backend/tests/core/standardize_entities_and_align_knowledge/test_api.py
git commit -m "fix: add terminology health indicators to summary.json output"
```

## Task 7: Run full test suite and verify end-to-end

**Files:**
- All modified files

**Step 1: Run the full Phase 3 test suite**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/ -v`
Expected: ALL PASS

**Step 2: Run Ruff lint check**

Run: `cd backend && uv run ruff check src/core/standardize_entities_and_align_knowledge/ tests/core/standardize_entities_and_align_knowledge/`
Expected: No errors

**Step 3: Run the real-case standardization on 法布雷病1例 and verify output**

Run the standardization script against the existing upstream_result.json and verify:
- `matches.json` exists with 13 per-entity entries
- Each entry has raw_text, entity_type, status, external_id, display_name, rationale
- Chinese phenotypes are split into individual candidates
- result.json includes matches array
- summary.json includes terminology_entry_count and embedding_available

**Step 4: Commit any fixes from end-to-end verification**

```bash
git add -A
git commit -m "test: verify end-to-end standardization output with audit detail"
```

## Verification Checklist

After all tasks:

- [ ] `matches.json` written with per-entity raw_text, entity_type, status, external_id, display_name, rationale, match_method
- [ ] Chinese compound phenotypes ("水肿、蛋白尿、心律失常") split into individual candidates
- [ ] English compound phenotypes ("edema, proteinuria, arrhythmia") split into individual candidates
- [ ] Chinese disease "法布雷病" maps to same entity as "Fabry disease" (OMIM:301500)
- [ ] p.R227X either matches ClinVar or has clear similarity-match rationale
- [ ] summary.json includes `terminology_entry_count` and `embedding_available` fields
- [ ] All existing tests still pass
- [ ] Ruff lint clean
