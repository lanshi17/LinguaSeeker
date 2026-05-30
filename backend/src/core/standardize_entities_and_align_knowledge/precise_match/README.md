# Precise Match Module

> Phase 3 submodule — deterministic, rule-based terminology matching using source-priority ranking and exact alias lookups.

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

```
PreciseTerminologyMatcher [core.py]
│
├─ match(candidate) → EntityMatch
│   ├─ repository.find_alias_candidates(entity_type, raw_text)
│   └─ _rank(entity_type, choices, candidate)
│       ├─ GENE     → HGNC only, alias-type priority
│       ├─ DISEASE   → OMIM first, then HPO/MONDO
│       ├─ PHENOTYPE → HPO only
│       └─ VARIANT  → ClinVar with gene-symbol context filter
│
└─ _apply_alias_type_priority(choices)
    └─ FILTER: keep only best priority level (primary > alias > previous_symbol > name > rsid)

Result classification:
  - 1 match  → STANDARDIZED (unique)
  - 2+ matches → AMBIGUOUS (needs downstream resolution)
  - 0 matches → UNMAPPED (passed to similarity matcher)
```

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

### Gene-symbol context filtering (Variant)

When matching variants against ClinVar, the matcher checks the candidate's metadata for a `gene_symbol` field. If present, it filters candidates to only those matching the same gene — reducing ambiguity from variants that share position but differ by gene context.

### Alias-type priority

Within a source database, candidates are ranked by alias type. Only candidates at the best (lowest-numbered) priority level are kept. This prevents a `previous_symbol` match from competing with a `primary` match.

## Usage Patterns

### Basic matching

```python
matcher = PreciseTerminologyMatcher(repo)
result = await matcher.match(candidate)
if result.status == MatchStatus.STANDARDIZED:
    print(f"Matched: {result.display_name} → {result.external_id}")
elif result.status == MatchStatus.AMBIGUOUS:
    print(f"Ambiguous: {len(result.terminology_candidates)} candidates")
```

### Integration with HybridTerminologyMatcher

The precise matcher is the first stage in the hybrid pipeline:

```
HybridTerminologyMatcher
├── PreciseTerminologyMatcher (this module)  ← first attempt
└── SimilarityTerminologyMatcher              ← fallback for UNMAPPED
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

- All lookups are database queries (SQLAlchemy async) — latency depends on index performance
- Gene-symbol filtering is O(n) in-memory after DB query
- Alias-type priority is O(n log n) sort

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `StandardizationRepository` | Alias candidate lookup |
| Parent contracts (`...contracts`) | EntityMatch, MatchStatus, StandardizationCandidate |

## Testing

```bash
uv run pytest tests/ -k "precise_match" -v
```
