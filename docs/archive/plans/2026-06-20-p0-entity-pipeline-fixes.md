# P0 Entity Pipeline Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix three high-ROI gaps in the entity standardization pipeline: implement Phase 2 gene pre-normalization, expand OMIM alias import + cross-lingual disease mapping, and add HGVS variant normalization for ClinVar matching.

**Architecture:** All three fixes operate within the existing Phase 2/3 pipeline without changing its topology. (1) A lightweight synchronous gene-symbol resolver runs inside Phase 2's `value_normalization` node, normalizing gene aliases to HGNC-approved symbols before group_id construction. (2) The OMIM importer parses semicolon-separated alternative titles and included titles as additional aliases, and the cross-lingual disease map is replaced by a terminology-alias-driven lookup. (3) A pure-function HGVS normalizer produces canonical forms that are tried as additional lookup aliases during Phase 3 precise variant matching.

**Tech Stack:** Python 3.12, SQLAlchemy async, PostgreSQL, Pydantic, pytest, pytest-asyncio, Ruff (Google Python Style Guide, line-length 120).

---

## Context for the Implementer

### Project Conventions (from AGENTS.md)

- **Python tooling**: `uv` only — never `pip`. Run tests with `cd backend && uv run pytest`.
- **Linting**: `cd backend && uv run ruff check` — Google Python Style Guide, 120 char lines.
- **Testing**: `pytest` + `pytest-asyncio`. Tests mirror source structure under `backend/tests/`.
- **Progress**: Append to `progress.txt` after each task: `[date] [description] [status]`.
- **Lessons**: Append to `lesson.md` for any debugging insights.
- **Commits**: Conventional Commits in English. Stage only files you changed.
- **Architecture**: Vertical slices — `contracts.py` for types, `core.py` for pure logic, `providers.py` for I/O.
- **No bare dict returns**: Use `dataclass` for internal contracts, `BaseModel` for API boundaries.
- **Code style**: Match existing patterns exactly. Don't refactor code you didn't write.

### Current Pipeline State (from DB analysis)

| Entity | Standardized | Unmapped | Unmapped % |
|--------|-------------|----------|-----------|
| gene | 36 | 1 | 2.7% |
| disease | 22 | 28 | **54%** |
| phenotype | 128 | 422 | **76%** |
| variant | 3 | 20 | **77%** |

### Key File Locations

```
backend/src/core/
├── cross_lingual_process_and_extract_evidence/extract_evidence/
│   ├── contracts.py          # EvidenceItem, EvidenceChain, EvidenceExtractionState
│   ├── core.py               # EvidenceItemNormalizer, EvidenceChainBuilder, make_group_id
│   ├── workflow.py           # LangGraph 13-node graph (relevance_scan → ... → catalog_backfill)
│   └── stages/
│       ├── entity_resolution.py  # DEAD PLACEHOLDER — never called, references non-existent type
│       └── value_normalization.py  # NOT USED — normalization happens in workflow nodes
└── standardize_entities_and_align_knowledge/
    ├── contracts.py          # EntityType, StandardizationCandidate, EntityMatch, MatchStatus
    ├── normalizers.py        # normalize_gene_symbol, normalize_disease_lookup_text, normalize_variant_text
    ├── importers.py          # parse_omim_rows, parse_hgnc_rows, parse_clinvar_rows
    ├── precise_match/core.py # PreciseTerminologyMatcher
    └── repositories.py       # StandardizationRepository.find_alias_candidates

backend/src/dao/postgresql/
    └── models.py             # TerminologyEntry, TerminologyAlias, NormalizedEntity

backend/tests/core/standardize_entities_and_align_knowledge/
    ├── test_normalizers.py   # Tests for normalize_* functions
    ├── test_importers.py     # Tests for parse_* functions
    └── test_precise_match.py # Tests for PreciseTerminologyMatcher
```

### OMIM mimTitles.txt Format

```
# Prefix  MIM Number  Preferred Title; symbol  Alternative Title(s); symbol(s)  Included Title(s); symbols
*  100100  PRUNE BELLY SYNDROME; PBS  ABDOMINAL MUSCLES, ABSENCE OF...;; EAGLE-BARRETT SYNDROME; EGBRS  APLASIA CUTIS CONGENITA..., INCLUDED
```

- Column 3: Preferred title — semicolons separate the full name from the abbreviation symbol
- Column 4: Alternative titles — `;;` separates multiple alternatives, `;` separates title from symbol
- Column 5: Included titles — same format as column 4

Current importer only uses column 3 as a single alias. Fix: split all three columns into individual aliases.

### HGVS Variant Notation Patterns (from unmapped data)

```
p.(Glu292Val)     → 3-letter amino acid notation
p.Arg243*         → 1-letter with stop codon
p.His97Arg        → 1-letter notation
c.727C>T          → DNA-level notation
c.290A>G          → DNA-level notation
```

ClinVar stores variants as `NM_000059.4(BRCA2):c.5946del` (with transcript prefix) and `p.R227X` (1-letter protein). The gap: extracted variants like `p.(Glu292Val)` (3-letter) don't match ClinVar's `p.E292V` (1-letter), and `c.727C>T` doesn't match ClinVar's `NM_000021.4(ABCG5):c.727C>T` (with transcript prefix).

---

## Task 1: Implement HGVS Variant Normalizer

**Rationale:** This is a pure function with no external dependencies — easiest to test in isolation. It converts between HGVS notation variants so that extracted variants can match ClinVar aliases.

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/hgvs_normalizer.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py`

### Step 1: Write failing tests

```python
# backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py
"""Tests for HGVS variant notation normalization."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import (
    normalize_hgvs_for_lookup,
    expand_hgvs_aliases,
)


def test_three_letter_protein_to_one_letter() -> None:
    """p.(Glu292Val) produces p.E292V as an additional alias."""
    aliases = expand_hgvs_aliases("p.(Glu292Val)")
    assert "p.E292V" in aliases


def test_one_letter_protein_passes_through() -> None:
    """p.Arg243* is already canonical and included in aliases."""
    aliases = expand_hgvs_aliases("p.Arg243*")
    assert "p.Arg243*" in aliases


def test_dna_notation_strips_transcript_prefix() -> None:
    """NM_000059.4(BRCA2):c.5946del produces c.5946del as an alias."""
    aliases = expand_hgvs_aliases("NM_000059.4(BRCA2):c.5946del")
    assert "c.5946del" in aliases


def test_bare_dna_notation_passes_through() -> None:
    """c.727C>T is included as-is in aliases."""
    aliases = expand_hgvs_aliases("c.727C>T")
    assert "c.727C>T" in aliases


def test_three_letter_with_parentheses() -> None:
    """p.His97Arg (no parens) produces p.H97R as an additional alias."""
    aliases = expand_hgvs_aliases("p.His97Arg")
    assert "p.H97R" in aliases


def test_stop_codon_three_letter_to_one_letter() -> None:
    """p.Trp159Ter produces p.W159* as an additional alias."""
    aliases = expand_hgvs_aliases("p.Trp159Ter")
    assert "p.W159*" in aliases


def test_normalize_strips_whitespace_and_applies_nfkc() -> None:
    """normalize_hgvs_for_lookup collapses whitespace and NFKC-folds."""
    assert normalize_hgvs_for_lookup("  p. Arg243*  ") == "p.Arg243*"


def test_empty_input_returns_empty() -> None:
    """Empty input produces empty aliases."""
    assert expand_hgvs_aliases("") == []
    assert normalize_hgvs_for_lookup("") == ""


def test_non_hgvs_input_passes_through() -> None:
    """Non-HGVS text like 'BRCA1' produces only the normalized original."""
    aliases = expand_hgvs_aliases("BRCA1")
    assert aliases == ["BRCA1"]


def test_list_input_is_joined() -> None:
    """List-like input ['p.S242R','p.S346I'] is split and each expanded."""
    aliases = expand_hgvs_aliases("['p.S242R','p.S346I']")
    assert "p.S242R" in aliases
    assert "p.S346I" in aliases
```

### Step 2: Run tests to verify they fail

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.standardize_entities_and_align_knowledge.hgvs_normalizer'`

### Step 3: Implement the HGVS normalizer

```python
# backend/src/core/standardize_entities_and_align_knowledge/hgvs_normalizer.py
"""HGVS variant notation normalization for improved ClinVar alias matching."""
from __future__ import annotations

import re
import unicodedata

from src.core.standardize_entities_and_align_knowledge.importers import AA3_TO_1

_SPACE_RE = re.compile(r"\s+")

# p.(Glu292Val) or p.Glu292Val or p.(Glu292Val)/E292V
# Group 1: prefix "p." or "p.("
# Group 2: 3-letter ref amino acid
# Group 3: position number
# Group 4: 3-letter alt amino acid or "Ter"
# Group 5: optional closing ")"
_PROTEIN_3LETTER_RE = re.compile(
    r"p\.?\(?([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter)\)?",
)

# NM_000059.4(BRCA2):c.5946del  →  captures the c.XXX part after the colon
_TRANSCRIPT_PREFIX_RE = re.compile(
    r"^(?:NM|NR|XM|XR|NG)_[\d.]+(?:\([^)]+\))?:",
)

# ['p.S242R','p.S346I']  →  split into individual values
_LIST_RE = re.compile(r"^\[([^\]]+)\]$")

_LIST_SPLIT_RE = re.compile(r"['\"]([^'\"]+)['\"]")


def normalize_hgvs_for_lookup(value: str) -> str:
    """Normalize a single HGVS string: NFKC + whitespace removal."""
    text = unicodedata.normalize("NFKC", value or "")
    return _SPACE_RE.sub("", text.strip())


def _three_to_one_protein(match: re.Match[str]) -> str | None:
    """Convert a 3-letter protein match to 1-letter notation like p.E292V."""
    ref = AA3_TO_1.get(match.group(1))
    pos = match.group(2)
    alt_raw = match.group(3)
    alt = "*" if alt_raw == "Ter" else AA3_TO_1.get(alt_raw)
    if ref is None or alt is None:
        return None
    return f"p.{ref}{pos}{alt}"


def expand_hgvs_aliases(raw_text: str) -> list[str]:
    """Produce all normalized alias forms of an HGVS variant string.

    For a 3-letter protein notation like ``p.(Glu292Val)``, produces both the
    original normalized form and the 1-letter form ``p.E292V``.

    For a transcript-prefixed DNA notation like ``NM_000059.4(BRCA2):c.5946del``,
    produces both the original and the stripped ``c.5946del``.

    For list-like input ``['p.S242R','p.S346I']``, splits and expands each element.

    Returns:
        List of unique normalized alias strings, ordered with the original first.
    """
    text = raw_text or ""
    if not text.strip():
        return []

    # Handle list-like input: ['p.S242R','p.S346I']
    list_match = _LIST_RE.match(text.strip())
    if list_match:
        inner = list_match.group(1)
        items = _LIST_SPLIT_RE.findall(inner)
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            for alias in expand_hgvs_aliases(item):
                normalized = normalize_hgvs_for_lookup(alias)
                if normalized and normalized not in seen:
                    result.append(normalized)
                    seen.add(normalized)
        return result

    normalized = normalize_hgvs_for_lookup(text)
    aliases: list[str] = []
    seen: set[str] = set()

    def _add(alias: str) -> None:
        if alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)

    # Start with the normalized original
    _add(normalized)

    # Try 3-letter → 1-letter protein conversion
    for match in _PROTEIN_3LETTER_RE.finditer(normalized):
        one_letter = _three_to_one_protein(match)
        if one_letter:
            _add(one_letter)

    # Strip transcript prefix: NM_000059.4(BRCA2):c.5946del → c.5946del
    stripped = _TRANSCRIPT_PREFIX_RE.sub("", normalized)
    if stripped != normalized:
        _add(stripped)

    return aliases
```

### Step 4: Run tests to verify they pass

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py -v`
Expected: 10 PASS

### Step 5: Lint

Run: `cd backend && uv run ruff check src/core/standardize_entities_and_align_knowledge/hgvs_normalizer.py`
Expected: Clean

### Step 6: Commit

```bash
cd backend
git add src/core/standardize_entities_and_align_knowledge/hgvs_normalizer.py \
  tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py
git commit -m "feat: add HGVS variant notation normalizer for ClinVar matching

Pure-function module that converts between HGVS notation variants:
- 3-letter to 1-letter protein (p.(Glu292Val) → p.E292V)
- Strip transcript prefix (NM_000059.4(BRCA2):c.5946del → c.5946del)
- Split list-like input (['p.S242R','p.S346I'] → individual aliases)"
```

---

## Task 2: Integrate HGVS Normalizer into Precise Variant Matching

**Rationale:** The current `PreciseTerminologyMatcher.match()` does a single alias lookup with `find_alias_candidates`. For variants, we need to try multiple normalized forms (1-letter protein, stripped transcript prefix) as additional lookup keys.

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/precise_match/core.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_precise_match.py`

### Step 1: Write failing test for multi-alias variant lookup

Add to `backend/tests/core/standardize_entities_and_align_knowledge/test_precise_match.py`:

```python
@pytest.mark.asyncio
async def test_precise_matcher_tries_hgvs_aliases_for_variant() -> None:
    """Variant matching tries 1-letter protein alias when 3-letter fails."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="p.(Glu292Val)",
        chain_id="chain-1",
        track="original",
    )
    # ClinVar has the 1-letter form p.E292V but not the 3-letter form
    terminology = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:12345",
        display_name="p.E292V",
        normalized_alias="p.E292V",
        alias_type="name",
    )

    class FakeRepoWithEmptyFirstLookup:
        """Returns empty for first lookup, terminology for second."""
        def __init__(self):
            self._call_count = 0

        async def find_alias_candidates(self, entity_type, raw_text):
            self._call_count += 1
            if self._call_count == 1:
                return ()  # 3-letter form not found
            return (terminology,)  # 1-letter form found

    match = await PreciseTerminologyMatcher(FakeRepoWithEmptyFirstLookup()).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "ClinVarVariation:12345"


@pytest.mark.asyncio
async def test_precise_matcher_tries_stripped_transcript_for_variant() -> None:
    """Variant matching strips transcript prefix when full form fails."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="NM_000059.4(BRCA2):c.5946del",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:67890",
        display_name="c.5946del",
        normalized_alias="c.5946del",
        alias_type="name",
    )

    class FakeRepo:
        def __init__(self):
            self._call_count = 0

        async def find_alias_candidates(self, entity_type, raw_text):
            self._call_count += 1
            if self._call_count == 1:
                return ()
            return (terminology,)

    match = await PreciseTerminologyMatcher(FakeRepo()).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "ClinVarVariation:67890"
```

### Step 2: Run tests to verify they fail

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_precise_match.py::test_precise_matcher_tries_hgvs_aliases_for_variant tests/core/standardize_entities_and_align_knowledge/test_precise_match.py::test_precise_matcher_tries_stripped_transcript_for_variant -v`
Expected: FAIL — the matcher only does one lookup, returns UNMAPPED

### Step 3: Implement multi-alias variant lookup

In `backend/src/core/standardize_entities_and_align_knowledge/precise_match/core.py`, modify the `match` method to try HGVS alias expansion for VARIANT candidates:

```python
# Add import at top of file:
from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import expand_hgvs_aliases

# Replace the match method (lines 30-63) with:

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Match one candidate to zero, one, or many deterministic terminology entries."""
        # For variants, try multiple normalized HGVS alias forms
        if candidate.entity_type == EntityType.VARIANT:
            return await self._match_variant(candidate)

        choices = await self._repository.find_alias_candidates(candidate.entity_type, candidate.raw_text)
        ranked = self._rank(candidate.entity_type, choices, candidate)

        if len(ranked) == 1:
            selected = ranked[0]
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id=selected.external_id,
                display_name=selected.display_name,
                terminology_candidates=(selected,),
                rationale=f"unique {selected.source_db} {selected.alias_type} match",
                match_method=MatchMethod.PRECISE,
            )
        if len(ranked) > 1:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(ranked),
                rationale="multiple deterministic terminology candidates",
                match_method=MatchMethod.PRECISE,
            )
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale="no deterministic terminology candidate",
            match_method=MatchMethod.PRECISE,
        )

    async def _match_variant(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Try multiple HGVS alias forms for variant matching."""
        aliases = expand_hgvs_aliases(candidate.raw_text)
        all_choices: list[TerminologyCandidate] = []
        seen_entry_ids: set[str] = set()

        for alias in aliases:
            choices = await self._repository.find_alias_candidates(candidate.entity_type, alias)
            for choice in choices:
                if choice.entry_id not in seen_entry_ids:
                    all_choices.append(choice)
                    seen_entry_ids.add(choice.entry_id)

        ranked = self._rank(EntityType.VARIANT, tuple(all_choices), candidate)
        return self._build_match_result(candidate, ranked)

    @staticmethod
    def _build_match_result(
        candidate: StandardizationCandidate,
        ranked: tuple[TerminologyCandidate, ...],
    ) -> EntityMatch:
        """Construct an EntityMatch from ranked candidates."""
        if len(ranked) == 1:
            selected = ranked[0]
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id=selected.external_id,
                display_name=selected.display_name,
                terminology_candidates=(selected,),
                rationale=f"unique {selected.source_db} {selected.alias_type} match",
                match_method=MatchMethod.PRECISE,
            )
        if len(ranked) > 1:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(ranked),
                rationale="multiple deterministic terminology candidates",
                match_method=MatchMethod.PRECISE,
            )
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale="no deterministic terminology candidate",
            match_method=MatchMethod.PRECISE,
        )
```

Also add `from typing import TYPE_CHECKING` at the top if not already present (for type hints — actually `TerminologyCandidate` is already imported from contracts, so no new typing import needed).

### Step 4: Run all precise match tests

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_precise_match.py -v`
Expected: All PASS (existing test + 2 new tests)

### Step 5: Run full standardization test suite

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/ -x -q`
Expected: All PASS

### Step 6: Lint

Run: `cd backend && uv run ruff check src/core/standardize_entities_and_align_knowledge/precise_match/core.py`
Expected: Clean

### Step 7: Commit

```bash
cd backend
git add src/core/standardize_entities_and_align_knowledge/precise_match/core.py \
  tests/core/standardize_entities_and_align_knowledge/test_precise_match.py
git commit -m "feat: integrate HGVS normalizer into precise variant matching

Variant candidates now try multiple normalized alias forms:
- 3-letter protein (p.(Glu292Val)) falls back to 1-letter (p.E292V)
- Transcript-prefixed (NM_000059.4:c.5946del) falls back to bare (c.5946del)

Deduplicates by entry_id across alias attempts."
```

---

## Task 3: Expand OMIM Alias Import

**Rationale:** The current `parse_omim_rows` only imports the full "Preferred Title" as a single alias. OMIM's mimTitles.txt has 3 columns of titles, each with semicolon-separated symbols and alternative names. Parsing all of them as aliases will significantly increase disease match rates.

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/importers.py` — `parse_omim_rows` function (lines 192-231)
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py` — `test_parse_omim_rows_builds_disease_entries`

### Step 1: Write failing test for expanded OMIM aliases

Replace the existing `test_parse_omim_rows_builds_disease_entries` in `backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py`:

```python
def test_parse_omim_rows_builds_disease_entries(tmp_path: Path) -> None:
    """OMIM title rows create OMIM-prefixed disease entries with all title aliases."""
    root = tmp_path / "omim"
    root.mkdir()
    (root / "mimTitles.txt").write_text(
        "# Prefix\tMIM Number\tPreferred Title; symbol\tAlternative Title(s); symbol(s)\tIncluded Title(s); symbols\n"
        "*\t100100\tPRUNE BELLY SYNDROME; PBS\tABDOMINAL MUSCLES, ABSENCE OF, WITH URINARY TRACT ABNORMALITY;; EAGLE-BARRETT SYNDROME; EGBRS\tAPLASIA CUTIS CONGENITA, INCLUDED\n",
        encoding="utf-8",
    )

    batch = parse_omim_rows(root, version="omim_test")

    assert batch.entries[0].external_id == "OMIM:100100"
    assert batch.entries[0].display_name == "PRUNE BELLY SYNDROME; PBS"

    # All aliases should be present
    alias_texts = {alias.alias_text for alias in batch.aliases}
    assert "PRUNE BELLY SYNDROME; PBS" in alias_texts
    assert "PRUNE BELLY SYNDROME" in alias_texts  # preferred title without symbol
    assert "PBS" in alias_texts  # preferred symbol
    assert "ABDOMINAL MUSCLES, ABSENCE OF, WITH URINARY TRACT ABNORMALITY" in alias_texts
    assert "EAGLE-BARRETT SYNDROME" in alias_texts
    assert "EGBRS" in alias_texts
    assert "APLASIA CUTIS CONGENITA" in alias_texts
```

### Step 2: Run test to verify it fails

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_importers.py::test_parse_omim_rows_builds_disease_entries -v`
Expected: FAIL — new aliases not produced by current parser

### Step 3: Implement expanded OMIM alias parsing

In `backend/src/core/standardize_entities_and_align_knowledge/importers.py`, replace the `parse_omim_rows` function (lines 192-231):

```python
def _split_omim_titles(field: str) -> list[str]:
    """Split an OMIM title field into individual title/symbol aliases.

    OMIM fields use ``;;`` to separate multiple alternative titles and ``;``
    to separate a title from its abbreviation symbol.  ``INCLUDED`` suffixes
    on individual titles are stripped.

    Examples:
        "PRUNE BELLY SYNDROME; PBS" → ["PRUNE BELLY SYNDROME; PBS", "PRUNE BELLY SYNDROME", "PBS"]
        "ALT TITLE 1;; ALT TITLE 2; SYM2" → ["ALT TITLE 1", "ALT TITLE 2", "SYM2"]
        "SOME TITLE, INCLUDED" → ["SOME TITLE"]
    """
    raw_titles = [t.strip() for t in field.split(";;") if t.strip()]
    aliases: list[str] = []
    for title in raw_titles:
        # Split title from symbol on "; "
        parts = [p.strip() for p in title.split(";") if p.strip()]
        if not parts:
            continue
        # Full combined title (e.g. "PRUNE BELLY SYNDROME; PBS")
        if len(parts) > 1:
            aliases.append(title)
        # Individual parts
        for part in parts:
            # Strip ", INCLUDED" suffix
            cleaned = re.sub(r",\s*INCLUDED\s*$", "", part).strip()
            if cleaned:
                aliases.append(cleaned)
    return aliases


def parse_omim_rows(root: Path, version: str) -> ImportBatch:
    """Parse OMIM title rows into disease entries and aliases.

    Imports all three title columns from mimTitles.txt:
    - Preferred Title (column 3): full title + individual symbol
    - Alternative Titles (column 4): each alternative + its symbol
    - Included Titles (column 5): each included title
    """
    path = root / "mimTitles.txt"
    if not path.exists():
        return ImportBatch()

    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []

    for row in _iter_tsv_rows(path, header_prefix="Prefix\tMIM Number"):
        mim_number = (row.get("MIM Number") or "").strip()
        preferred_title = (row.get("Preferred Title; symbol") or "").strip()
        if not mim_number or not preferred_title:
            continue

        external_id = f"OMIM:{mim_number}"

        # Collect all aliases from all three title columns
        all_alias_texts: list[str] = []
        all_alias_texts.extend(_split_omim_titles(preferred_title))

        alt_titles = (row.get("Alternative Title(s); symbol(s)") or "").strip()
        if alt_titles:
            all_alias_texts.extend(_split_omim_titles(alt_titles))

        included_titles = (row.get("Included Title(s); symbols") or "").strip()
        if included_titles:
            all_alias_texts.extend(_split_omim_titles(included_titles))

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_aliases: list[str] = []
        for alias_text in all_alias_texts:
            normalized = normalize_lookup_text(alias_text)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_aliases.append(alias_text)

        entries.append(
            ImportEntry(
                entity_type=EntityType.DISEASE,
                source_db="OMIM",
                external_id=external_id,
                display_name=preferred_title,
                normalized_name=normalize_lookup_text(preferred_title),
                aliases=tuple(unique_aliases),
                raw_payload={"mim_number": mim_number},
                version=version,
            ),
        )

        for alias_text in unique_aliases:
            aliases.append(
                ImportAlias(
                    external_id=external_id,
                    entity_type=EntityType.DISEASE,
                    source_db="OMIM",
                    alias_text=alias_text,
                    normalized_alias=normalize_lookup_text(alias_text),
                    alias_type="name",
                ),
            )

    return ImportBatch(entries=tuple(entries), aliases=tuple(aliases))
```

### Step 4: Run test to verify it passes

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_importers.py::test_parse_omim_rows_builds_disease_entries -v`
Expected: PASS

### Step 5: Run all importer tests

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_importers.py -v`
Expected: All PASS

### Step 6: Lint

Run: `cd backend && uv run ruff check src/core/standardize_entities_and_align_knowledge/importers.py`
Expected: Clean

### Step 7: Commit

```bash
cd backend
git add src/core/standardize_entities_and_align_knowledge/importers.py \
  tests/core/standardize_entities_and_align_knowledge/test_importers.py
git commit -m "feat: expand OMIM alias import to parse all title columns

parse_omim_rows now imports aliases from all three mimTitles.txt columns:
- Preferred Title (with symbol split)
- Alternative Titles (;; separated, with symbol split)
- Included Titles (with INCLUDED suffix stripped)

Previously only the full preferred title was imported as a single alias.
This should significantly reduce the 54% disease unmapped rate."
```

---

## Task 4: Implement Gene Symbol Pre-Normalization in Phase 2

**Rationale:** The `entity_resolution.py` placeholder is dead code — never called, references a non-existent type `ExtractedEvidence`. Instead of wiring it into the workflow graph (which would add a new node and state field), we add gene normalization to the existing `value_normalization` node. This is the simplest integration point because it already transforms `EvidenceItem` values.

The approach: when an `EvidenceItem` has `field_id == "A.gene_symbol"`, normalize its value using the same rules as `normalize_gene_symbol` (uppercase, NFKC, strip whitespace). This ensures gene symbols are canonical before `make_group_id` runs in the `group_assignment` node.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py` — the `AcmgEvidenceValueNormalizer` class
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalization.py` (check if exists, create if not)

### Step 1: Check existing normalization tests

Run: `find backend/tests/core/cross_lingual_process_and_extract_evidence -name "test_normal*" -o -name "test_value*" 2>/dev/null`

If `test_normalization.py` exists, read it. If not, create it.

### Step 2: Write failing test for gene symbol normalization

Create or add to `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalization.py`:

```python
"""Tests for evidence value normalization including gene symbol canonicalization."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import (
    AcmgEvidenceValueNormalizer,
)


def _make_gene_item(value: str | list[str]) -> EvidenceItem:
    """Build a minimal A.gene_symbol evidence item."""
    return EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.95,
        source=SourceLocation(context_type="text", context_ref="test", text_snippet="test"),
    )


def test_gene_symbol_lowercased_is_uppercased() -> None:
    """Gene symbol 'brca1' is normalized to 'BRCA1'."""
    normalizer = AcmgEvidenceValueNormalizer()
    items, _ = normalizer.normalize([_make_gene_item("brca1")])
    assert items[0].value == "BRCA1"


def test_gene_symbol_with_whitespace_is_trimmed() -> None:
    """Gene symbol '  BRCA1  ' is normalized to 'BRCA1'."""
    normalizer = AcmgEvidenceValueNormalizer()
    items, _ = normalizer.normalize([_make_gene_item("  BRCA1  ")])
    assert items[0].value == "BRCA1"


def test_gene_symbol_fullwidth_is_nfkc_normalized() -> None:
    """Full-width gene symbol 'ｂｒｃａ２' is normalized to 'BRCA2'."""
    normalizer = AcmgEvidenceValueNormalizer()
    items, _ = normalizer.normalize([_make_gene_item("ｂｒｃａ２")])
    assert items[0].value == "BRCA2"


def test_gene_symbol_list_values_are_uppercased() -> None:
    """List gene symbols are each uppercased."""
    normalizer = AcmgEvidenceValueNormalizer()
    items, _ = normalizer.normalize([_make_gene_item(["brca1", "tp53"])])
    assert items[0].value == ["BRCA1", "TP53"]


def test_non_gene_fields_are_not_uppercased() -> None:
    """Non-gene fields like disease names are not uppercased."""
    item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.FOUND,
        value="Charcot-Marie-Tooth disease",
        confidence=0.9,
        source=SourceLocation(context_type="text", context_ref="test", text_snippet="test"),
    )
    normalizer = AcmgEvidenceValueNormalizer()
    items, _ = normalizer.normalize([item])
    # Disease name should not be uppercased
    assert items[0].value == "Charcot-Marie-Tooth disease"
```

### Step 3: Run test to verify it fails

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalization.py -v`
Expected: FAIL — gene symbol normalization not implemented

### Step 4: Read the current normalizer implementation

Read `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py` to understand the existing `normalize` method structure.

### Step 5: Implement gene symbol normalization

Add gene symbol normalization to the `AcmgEvidenceValueNormalizer.normalize()` method. The exact insertion point depends on the existing code structure — add a check for `field_id == "A.gene_symbol"` or `field_id == "A.gene_aliases"` that applies `value.strip().upper()` (with NFKC normalization) to string values, or maps it over list values.

The implementation should use `unicodedata.normalize("NFKC", value).strip().upper()` for string values, and apply it element-wise for list values.

### Step 6: Run tests to verify they pass

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalization.py -v`
Expected: 5 PASS

### Step 7: Run broader extraction tests

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -x -q`
Expected: All PASS

### Step 8: Lint

Run: `cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
Expected: Clean

### Step 9: Commit

```bash
cd backend
git add src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_normalization.py
git commit -m "feat: normalize gene symbols in Phase 2 value normalization

A.gene_symbol and A.gene_aliases values are now NFKC-normalized,
whitespace-stripped, and uppercased during the value_normalization
node, ensuring canonical gene symbols before group_id construction."
```

---

## Task 5: Remove Dead entity_resolution.py Placeholder

**Rationale:** The `entity_resolution.py` file is dead code — never imported, references a non-existent `ExtractedEvidence` type. Clean cutover means removing it.

**Files:**
- Delete: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/entity_resolution.py`

### Step 1: Verify no imports exist

Run: `cd backend && grep -r "entity_resolution" src/ tests/ --include="*.py" | grep -v "stages/entity_resolution.py"`
Expected: No output (no imports)

### Step 2: Delete the file

Run: `rm backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/entity_resolution.py`

### Step 3: Run all tests to verify nothing breaks

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -x -q`
Expected: All PASS

### Step 4: Lint

Run: `cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/`
Expected: Clean

### Step 5: Commit

```bash
cd backend
git add -A src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/
git commit -m "refactor: remove dead entity_resolution.py placeholder

The EntityResolver class was never imported or called, and referenced
a non-existent ExtractedEvidence type. Gene normalization is now
handled in the value_normalization node instead."
```

---

## Task 6: Re-import Terminology with Expanded OMIM Aliases

**Rationale:** The code changes in Tasks 1-4 need to be applied to the existing database. The terminology import script needs to be re-run to pick up the expanded OMIM aliases. The gene normalization (Task 4) and HGVS normalizer (Tasks 1-2) apply at query time, so they don't need data backfill.

**Files:**
- Run: `scripts/import_terminology.py` (existing script, no modifications)

### Step 1: Check current terminology import script

Run: `cd backend && uv run python scripts/import_terminology.py --help`
Review the available options.

### Step 2: Re-import OMIM with expanded aliases

Run the import script with the OMIM source only (to avoid re-importing all sources unnecessarily):

```bash
cd backend
uv run python scripts/import_terminology.py --sources omim --version omim_expanded_20260620
```

Expected: OMIM entries re-imported with expanded aliases. The `on_conflict_do_update` logic in the repository will update existing entries with the new aliases.

### Step 3: Verify alias count increased

Run SQL to check:
```sql
SELECT alias_type, COUNT(*) FROM lingua.terminology_aliases WHERE entity_type = 'disease' GROUP BY alias_type;
```

Expected: The `name` alias count should be significantly higher than the previous 29,378.

### Step 4: Commit (no code changes — just data update)

No commit needed — this is a data migration, not a code change. But record in progress.txt:

```
[2026-06-20] [Re-imported OMIM terminology with expanded aliases] [completed]
```

---

## Task 7: Write Integration Test for Variant Matching with HGVS Normalization

**Rationale:** Verify end-to-end that the HGVS normalizer + precise matcher integration works with realistic data.

**Files:**
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_integration.py`

### Step 1: Write integration test

```python
# backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_integration.py
"""Integration tests for HGVS variant matching with realistic data."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import expand_hgvs_aliases
from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    PreciseTerminologyMatcher,
)


class FakeRepository:
    """Repository that matches against a pre-built alias-to-candidate map."""

    def __init__(self, alias_map: dict[str, tuple[TerminologyCandidate, ...]]):
        self._alias_map = alias_map

    async def find_alias_candidates(self, entity_type, raw_text):
        from src.core.standardize_entities_and_align_knowledge.normalizers import normalize_variant_text
        normalized = normalize_variant_text(raw_text)
        return self._alias_map.get(normalized, ())


@pytest.mark.asyncio
async def test_three_letter_protein_matches_clinvar_one_letter() -> None:
    """A 3-letter protein variant from a paper matches ClinVar's 1-letter form."""
    clinvar_candidate = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:12345",
        display_name="p.E292V",
        normalized_alias="p.E292V",
        alias_type="name",
    )

    repo = FakeRepository({
        "p.E292V": (clinvar_candidate,),
    })

    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="p.(Glu292Val)",
        chain_id="chain-1",
        track="original",
    )

    match = await PreciseTerminologyMatcher(repo).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "ClinVarVariation:12345"
    assert match.match_method == MatchMethod.PRECISE


@pytest.mark.asyncio
async def test_bare_dna_notation_matches_clinvar_bare_form() -> None:
    """A bare c.727C>T from a paper matches ClinVar's bare c.727C>T alias."""
    clinvar_candidate = TerminologyCandidate(
        entry_id="entry-2",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:67890",
        display_name="c.727C>T",
        normalized_alias="c.727C>T",
        alias_type="name",
    )

    repo = FakeRepository({
        "c.727C>T": (clinvar_candidate,),
    })

    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="c.727C>T",
        chain_id="chain-1",
        track="original",
    )

    match = await PreciseTerminologyMatcher(repo).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "ClinVarVariation:67890"


def test_expand_hgvs_aliases_covers_all_unmapped_patterns() -> None:
    """All unmapped variant patterns from the DB produce useful aliases."""
    test_cases = [
        ("p.(Glu292Val)", "p.E292V"),
        ("p.Arg243*", "p.R243*"),  # already 1-letter, passes through
        ("p.His97Arg", "p.H97R"),
        ("c.727C>T", "c.727C>T"),  # bare DNA, passes through
        ("p.Trp159Ter", "p.W159*"),
    ]

    for raw, expected_alias in test_cases:
        aliases = expand_hgvs_aliases(raw)
        assert expected_alias in aliases, f"Expected {expected_alias} in aliases for {raw}, got {aliases}"
```

### Step 2: Run tests

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_hgvs_integration.py -v`
Expected: 3 PASS

### Step 3: Lint

Run: `cd backend && uv run ruff check tests/core/standardize_entities_and_align_knowledge/test_hgvs_integration.py`
Expected: Clean

### Step 4: Commit

```bash
cd backend
git add tests/core/standardize_entities_and_align_knowledge/test_hgvs_integration.py
git commit -m "test: add integration tests for HGVS variant matching

Tests verify that 3-letter protein notation from papers matches
ClinVar's 1-letter form, and that bare DNA notation matches correctly."
```

---

## Task 8: Run Full Test Suite and Update Progress

### Step 1: Run all backend tests

Run: `cd backend && uv run pytest tests/ -x -q --ignore=tests/dao/postgresql/test_alembic_migration.py`
Expected: All PASS (excluding pre-existing alembic test failure)

### Step 2: Run lint on all changed files

Run: `cd backend && uv run ruff check src/core/standardize_entities_and_align_knowledge/ src/core/cross_lingual_process_and_extract_evidence/extract_evidence/normalization.py`
Expected: Clean

### Step 3: Update progress.txt

Append to `progress.txt`:
```
[2026-06-20] [P0 entity pipeline fixes — HGVS normalizer + OMIM alias expansion + gene normalization] [completed]
```

### Step 4: Commit

```bash
git add progress.txt
git commit -m "chore: update progress.txt for P0 entity pipeline fixes"
```

---

## Summary of Changes

| Task | What | Files | Impact |
|------|------|-------|--------|
| 1 | HGVS variant normalizer | `hgvs_normalizer.py` (new) | 3-letter→1-letter protein, transcript prefix stripping |
| 2 | Integrate HGVS into precise match | `precise_match/core.py` | Variant match tries multiple alias forms |
| 3 | Expand OMIM alias import | `importers.py` | Parse all 3 title columns + semicolons |
| 4 | Gene symbol pre-normalization | `normalization.py` | Uppercase + NFKC gene values in Phase 2 |
| 5 | Remove dead placeholder | `entity_resolution.py` (deleted) | Clean cutover |
| 6 | Re-import OMIM terminology | Data migration | Updated DB aliases |
| 7 | Integration tests | `test_hgvs_integration.py` (new) | End-to-end verification |
| 8 | Full test + progress | `progress.txt` | Verification |

**Expected impact on unmapped rates:**
- Disease: 54% → ~30% (OMIM alias expansion)
- Variant: 77% → ~50% (HGVS normalization, novel variants still unmapped)
- Gene: 2.7% → ~1% (gene pre-normalization)
- Phenotype: 76% → ~76% (not addressed in this plan — requires HPO cross-reference expansion)
