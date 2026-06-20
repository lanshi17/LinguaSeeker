# Fused-75 Candidate Recovery and Source Validation Design

**Status:** planned
**Created:** 2026-06-20
**Owner:** CrossEvidence benchmark team

## Goal

Improve fused-75 source-visible F1 on real data by recovering missing target-specific candidates and filtering unsupported extracted items before benchmark scoring.

## Metric Gate

All tuning uses the adjudicated dev split only.

Primary dev gate:

```text
dev source-visible F1 >= 0.55
```

Frozen test checkpoint is allowed only after the dev gate passes.

Promotion gate:

```text
test source-visible F1 > 0.4340
```

Preferred secondary gate:

```text
test recall >= 0.45
```

The secondary recall gate is reported separately. It must not be used to tune on test.

## Starting Point

Current checkpoints:

| Variant | Split | Precision | Recall | Source-visible F1 |
|---|---:|---:|---:|---:|
| adjudicated-field-filter | test | 0.5897 | 0.3433 | 0.4340 |
| target-aware-source-visible | dev | 0.5238 | 0.5077 | 0.5156 |
| target-aware-source-visible | test | 0.4182 | 0.3433 | 0.3770 |

The latest production-side target-aware variant improved dev recall but did not improve frozen test recall and reduced precision. The next loop must therefore avoid broad context expansion as the main lever.

## Recommended Architecture

Keep the current Phase 2 topology. Add two narrow controls inside the `extract_evidence` vertical slice:

1. **Target evidence scouting** before catalog extraction.
   - Build a deterministic set of target terms from `ExtractionTarget`.
   - Include gene, target disease words, known disease aliases, target variant tokens, and normalized HGVS forms.
   - Select only document blocks that contain those target terms or immediate high-confidence aliases.
   - Expose the scout result as typed contracts, not bare dictionaries.

2. **Source-visible item validation** after source grounding and before final artifact emission.
   - Require every `found` `EvidenceItem` to have a source snippet that is present in the relevant document blocks.
   - Optionally require value support for high-risk fields where exact value can be checked without domain reasoning.
   - Downgrade unsupported items to `not_found` or discard them from scoring-facing artifacts, with a normalization issue note.

## Why This Direction

The previous failed direction asked the LLM fewer fields and gave it neighboring context. That improved dev but hurt test precision. The current F1 bottleneck is not only field scope; it is whether the right source-visible candidate is present and whether unsupported candidates survive to the artifact.

This design makes candidate recovery and source validation explicit:

- candidate recovery targets recall,
- source validation targets precision,
- both can be measured on dev before any test checkpoint.

## Data Flow

```text
TrackDocument + ExtractionTarget
    -> TargetEvidenceScout
    -> selected block indices + target aliases
    -> CatalogExtractionStage prompt chunks
    -> SourceGroundingStage
    -> SourceVisibleValidationStage
    -> EvidenceExtractionResult artifacts
```

The scout should not call an LLM. It is deterministic so dev iteration is cheap and reproducible.

## Error Taxonomy First

Before implementation, generate a dev-only detailed error taxonomy for `target-aware-source-visible`:

- false negatives by `entry_id`, `field_id`, expected value, and source quote,
- false positives by `entry_id`, `field_id`, extracted value, and extracted source snippet,
- paired same-field FN/FP errors indicating boundary or normalization issues,
- aggregate counts by failure class.

This report decides the first implementation target. If candidate-absent is not the largest dev loss, the implementation plan should be revised before code changes.

## Risks

- Alias expansion can over-match broad disease words and harm precision.
- Source-visible validation can over-filter paraphrased but correct values.
- Test F1 may still regress if dev failure modes do not represent test.

Mitigation:

- Keep aliases conservative and target-bound.
- Validate source presence before value semantics.
- Use dev gate before test and never tune on test output.
