# Precise Match Module

> Phase 3 submodule -- deterministic, rule-based terminology matching using source-priority ranking and exact alias lookups.

## Quick Start

```python
from src.core.standardize_entities_and_align_knowledge.precise_match import (
    PreciseTerminologyMatcher,
)
from src.core.standardize_entities_and_align_knowledge.repositories import (
    StandardizationRepository,
)

matcher = PreciseTerminologyMatcher(repository)
result = await matcher.match(candidate)
print(f"Status: {result.status.value}, Method: {result.match_method.value}")
```

## Architecture

```text
PreciseTerminologyMatcher [core.py]
|
+-- match(candidate) -> EntityMatch
|   +-- (non-variant) repository.find_alias_candidates(entity_type, raw_text)
|   +-- (variant) expand_hgvs_aliases() + repository lookups per alias, merged by entry_id
|   +-- _rank(entity_type, choices, candidate)
|       +-- GENE     -> HGNC only, alias-type priority
|       +-- DISEASE  -> OMIM first, then HPO/MONDO
|       +-- PHENOTYPE -> HPO only
|       +-- VARIANT  -> ClinVar with gene-symbol context filter
|
+-- _apply_alias_type_priority(choices)
    +-- FILTER: keep only best priority level (primary > alias > previous_symbol > name > rsid)

Result classification:
  1 match  -> STANDARDIZED (unique)
  2+ matches -> AMBIGUOUS (needs downstream resolution)
  0 matches -> UNMAPPED (passed to similarity matcher)
```

## Module Layout

- `__init__.py`: exports `PreciseTerminologyMatcher`
- `core.py`: all matching rules, ranking logic, and gene-symbol context filtering

## Public API

### `PreciseTerminologyMatcher`

```python
class PreciseTerminologyMatcher:
    def __init__(self, repository: StandardizationRepository)
    async def match(self, candidate: StandardizationCandidate) -> EntityMatch
```

Single entry point. Returns `EntityMatch` with status `STANDARDIZED`, `AMBIGUOUS`, or `UNMAPPED`.

### Alias Type Priority

| Priority | Alias Type | Description |
|----------|------------|-------------|
| 0 (best) | `primary` | Current approved symbol |
| 1 | `alias` | Alternative symbol |
| 2 | `previous_symbol` | Historical symbol |
| 3 | `name` | Full gene name |
| 4 (worst) | `rsid` | dbSNP reference ID |

### Entity-Specific Ranking

| Entity Type | Primary Source | Fallback |
|-------------|---------------|----------|
| `GENE` | HGNC | None (strict) |
| `DISEASE` | OMIM | HPO, MONDO |
| `PHENOTYPE` | HPO | None (strict) |
| `VARIANT` | ClinVar | Gene-symbol context filter |

## Internal Design

### Variant matching with HGVS expansion

For VARIANT candidates, the matcher calls `expand_hgvs_aliases()` from `hgvs_normalizer.py` to produce all equivalent HGVS notation forms before looking up aliases. This handles:

- Three-letter to one-letter amino acid code conversion (e.g., `p.Arg243Ter` to `p.R243*`)
- RefSeq transcript prefix stripping (e.g., `NM_000059.4(BRCA2):c.123A>T` to `c.123A>T`)
- List literal expansion (e.g., `['p.S242R','p.S346I']`)
- Stop codon normalization (`X` to `*` in one-letter notation)

Each alias form is looked up in the repository and results are merged by `entry_id` to avoid double-counting ClinVar entries reachable via multiple alias forms.

### Gene-symbol context filtering (Variant)

When matching variants against ClinVar, the matcher checks the candidate's metadata for a `gene_symbol` field. The decision tree (D3):

1. `choices` empty -> return `()` (UNMAPPED).
2. `candidate is None` -> return a single deterministic winner via `_pick_deterministic_winner()`.
3. Normalize the candidate gene and each choice's ClinVar `gene_symbol` with `normalize_gene_symbol()`. Partition choices into `same_gene`.
4. When `same_gene` is non-empty, keep the best alias-type tier within it and return a single deterministic winner (`entry_id` ascending).
5. When `same_gene` is empty:
   - `len(choices) == 1` -> return `choices` (single unambiguous HGVS match is a strong identity signal).
   - `len(choices) > 1` -> return `()` (UNMAPPED). Multiple cross-gene matches are genuine ambiguity.

### Alias-type priority

Within a source database, candidates are ranked by alias type. Only candidates at the best (lowest-numbered) priority level are kept. This prevents a `previous_symbol` match from competing with a `primary` match.

## Usage Patterns

### Basic matching

```python
matcher = PreciseTerminologyMatcher(repo)
result = await matcher.match(candidate)
if result.status == MatchStatus.STANDARDIZED:
    print(f"Matched: {result.display_name} -> {result.external_id}")
elif result.status == MatchStatus.AMBIGUOUS:
    print(f"Ambiguous: {len(result.terminology_candidates)} candidates")
```

### Integration with HybridTerminologyMatcher

The precise matcher is the first stage in the hybrid pipeline:

```text
HybridTerminologyMatcher
+-- PreciseTerminologyMatcher (this module)   <- first attempt
+-- CrossLingualDiseaseResolver               <- disease-only fallback
+-- SimilarityTerminologyMatcher               <- semantic fallback for UNMAPPED
```

## Extension Guide

### Adding a new entity type

1. Add a branch in `_rank()` with source-priority rules:

```python
if entity_type == EntityType.MY_TYPE:
    return self._apply_alias_type_priority(
        tuple(c for c in choices if c.source_db == "MYDB")
    )
```

### Adding a new source database

1. Add the source-database name to the appropriate entity-type branch in `_rank()`
2. Ensure the terminology data is imported via the import pipeline (`importers.py`)
3. The repository's `find_alias_candidates()` will automatically query it

## Performance Notes

- All lookups are database queries (SQLAlchemy async) -- latency depends on index performance
- Gene-symbol filtering is O(n) in-memory after DB query
- Alias-type priority is O(n log n) sort
- Variant matching with HGVS expansion performs multiple DB lookups per candidate (one per alias form), merged by `entry_id`

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `StandardizationRepository` | Alias candidate lookup |
| `hgvs_normalizer.expand_hgvs_aliases` | HGVS alias expansion for variant matching |
| `normalizers.normalize_gene_symbol` | Gene symbol normalization for context filtering |
| Parent contracts (`...contracts`) | EntityMatch, MatchStatus, StandardizationCandidate |

## Testing

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/ -k "precise_match" -v
```
