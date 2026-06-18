# Context Pack

> Builds target-safe gene and disease context for evidence verification and contextual reconciliation.

## Quick Start

```python
from pathlib import Path

from src.core.standardize_entities_and_align_knowledge.context_pack import (
    build_context_pack_from_expected_json,
    build_context_pack_from_runtime_target,
)

benchmark_pack = build_context_pack_from_expected_json(
    Path("benchmark/layer3/ground_truth/clingen_010/expected.json")
)
runtime_pack = build_context_pack_from_runtime_target(
    entry_id="clingen_010",
    gene_symbol="AP1G1",
    disease_label="complex neurodevelopmental disorder",
)
print(benchmark_pack.gene.symbol)
print(runtime_pack.disease.aliases)
```

## Architecture

```text
expected.json
  -> build_context_pack_from_expected_json()
      -> safe target fields only
      -> deterministic disease aliases
      -> source-observed abbreviation aliases
      -> source-observed MONDO disease aliases
  -> TargetContextPack
      -> contextual reconcile verifier

ExtractionTarget/document metadata
  -> build_context_pack_from_runtime_target()
      -> safe runtime target fields only
      -> deterministic disease aliases
  -> TargetContextPack
      -> production dual-track contextual reconcile
```

The module is intentionally read-only. It does not call an LLM and does not use benchmark answer labels at runtime.

## Public API

| API | Signature | Description |
| --- | --- | --- |
| `build_context_pack_from_expected_json` | `build_context_pack_from_expected_json(path: Path) -> TargetContextPack` | Builds a no-leakage context pack from safe ClinGen benchmark metadata plus adjacent `source.md` text when available. |
| `build_context_pack_from_runtime_target` | `build_context_pack_from_runtime_target(*, entry_id: str, gene_symbol: str, disease_label: str, hgnc_id: str | None = None, mondo_id: str | None = None, moi: str = "", source_pmid: str | None = None, source_pmc: str | None = None) -> TargetContextPack` | Builds a production-safe context pack from runtime target metadata without reading benchmark ground truth. |
| `GeneContext` | `GeneContext(symbol: str, hgnc_id: str | None, aliases: tuple[str, ...])` | Target gene context. |
| `DiseaseContext` | `DiseaseContext(label: str, mondo_id: str | None, aliases: tuple[str, ...], ancestor_labels: tuple[str, ...])` | Target disease context and aliases. |
| `TargetContextPack` | `TargetContextPack(entry_id: str, gene: GeneContext, disease: DiseaseContext, moi: str, source_pmid: str | None, source_pmc: str | None)` | Immutable context passed into verifier/reconciliation logic. |

## Internal Design

The builder reads only these safe fields from `expected.json`: `entry_id`, `gene_symbol`, `hgnc_id`, `disease_label`, `mondo_id`, `moi`, `source_pmid`, and `source_pmc`.

The runtime builder accepts the same safe field classes as explicit arguments. It is used by the production dual extraction facade after `ExtractionTarget` is already known. It does not read `expected.json`, benchmark labels, or evaluator output.

Disease aliasing has three layers:

1. Deterministic aliases from the disease label, including case-folded and parenthetical-stripped variants.
2. Source-aware abbreviations from `source.md` when the source section contains the target disease stem.
3. Source-observed MONDO disease aliases from `database/terminology_database/mondo/mondo_hierarchy_cache.json`.

The MONDO layer is conservative. A candidate label must be a non-obsolete disease/disorder/syndrome label, must appear in `source.md`, and must occur near the target gene plus a target disease cue. Prefix aliases from comma-separated MONDO labels are accepted only if the prefix still looks like a disease/disorder/syndrome label. This prevents symptoms such as `epilepsy` or `developmental delay` from becoming target aliases.

## No-Leakage Rules

Do not add fields that reveal benchmark answers or ClinGen validity outcomes. In particular, the context pack must not expose:

- `classification`
- `expected_evidence`
- evaluator matches
- derived gold relationship labels

Ontology and source text can expand aliases only when they are target-safe and source-observed.

## Extension Guide

When adding an alias source, keep it deterministic and add a regression test that proves both the positive alias and a nearby false positive. For relationship-sensitive work, prefer adding tests under `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/` instead of expanding context pack semantics.

## Performance Notes

The MONDO cache is loaded with `lru_cache(maxsize=1)`. Source text is normalized once before scanning, and full regex matching runs only after a normalized substring prefilter.

## Testing

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_contracts.py \
  -q

PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  backend/src/core/standardize_entities_and_align_knowledge/context_pack \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack
```
