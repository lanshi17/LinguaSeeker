# reconcile

> Deterministic cross-track reconciliation for source-grounded evidence extraction. It merges original and translated `EvidenceExtractionResult` objects, selects accepted evidence with auditable scores, and emits alignment records for traceability and cross-lingual analysis.

## Quick Start

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.api import (
    CrossTrackReconcileService,
)

service = CrossTrackReconcileService()
reconciled = service.run(original_result, translated_result)
print(reconciled.result.evidence_items)
print(reconciled.alignment_records)
```

## Architecture

```
original EvidenceExtractionResult ┐
                                  ├─ reconcile_results() ─→ ReconcileOutput
translated EvidenceExtractionResult┘
                                      │
                                      ├─ _build_candidates()
                                      ├─ _decide_fields()
                                      ├─ _deduplicate_chains()
                                      ├─ build_alignment_records()
                                      └─ EvidenceExtractionResult(track=RECONCILED)
```

The slice is split into three layers:

- `core.py` handles deterministic candidate building, scoring, and field decisions.
- `alignment.py` turns dual-track outputs into `EvidenceAlignmentRecord` entries.
- `api.py` exposes the public service wrapper used by callers and tests.
- `features.py` exposes a pure, typed feature vector for offline learned-arbitrator analysis.

## Public API

### `CrossTrackReconcileService`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, params: ReconcileParams = ReconcileParams()) -> None` | Stores reconcile tuning constants. |
| `run` | `(self, original: EvidenceExtractionResult, translated: EvidenceExtractionResult) -> EvidenceExtractionResult` | Reconciles both tracks and returns the merged extraction result. |

### `reconcile_results`

| Signature | Description |
|-----------|-------------|
| `(original: EvidenceExtractionResult, translated: EvidenceExtractionResult, params: ReconcileParams = ReconcileParams()) -> ReconcileOutput` | Deterministically reconciles the two tracks and returns the merged result plus field decisions. |

### `reconcile_with_context`

| Signature | Description |
|-----------|-------------|
| `(original: EvidenceExtractionResult, translated: EvidenceExtractionResult, context: TargetContextPack, params: ReconcileParams = ReconcileParams()) -> ReconcileOutput` | Same reconciliation flow with target-context verifier scores and alignment records attached. |

### `build_alignment_records`

| Signature | Description |
|-----------|-------------|
| `(original: EvidenceExtractionResult, translated: EvidenceExtractionResult, *, entry_id: str = "") -> tuple[EvidenceAlignmentRecord, ...]` | Builds per-field alignment records from the best original/translated evidence items. |

### `CandidateFeatureVector`

| Method | Signature | Description |
|--------|-----------|-------------|
| `to_list` | `(self) -> list[float]` | Serializes the feature vector for downstream modeling. |
| `feature_names` | `() -> tuple[str, ...]` | Returns the stable feature ordering. |

### `extract_features`

| Signature | Description |
|-----------|-------------|
| `(score: CandidateScore, item: EvidenceItem, track: Track) -> CandidateFeatureVector` | Extracts the offline arbitrator feature vector from a candidate score and evidence item. |

### `ReconcileParams`

| Field | Type | Description |
|-------|------|-------------|
| `conflict_margin` | `float` | Margin used when deciding whether a cross-track conflict requires review. |

### `ReconcileOutput`

| Field | Type | Description |
|-------|------|-------------|
| `result` | `EvidenceExtractionResult` | Merged reconciled output. |
| `decisions` | `tuple[FieldDecision, ...]` | Field-level accept/reject decisions. |
| `alignment_records` | `tuple[EvidenceAlignmentRecord, ...]` | Cross-track alignment summary. |

## Internal Design

`reconcile_results()` and `reconcile_with_context()` both build candidate pairs per field, score them, choose accepted evidence, and collect rejected items for review. The reconciled result preserves the original document identity, merges special evidence and normalization issues, and keeps the evidence chains deduplicated.

`build_alignment_records()` compares the best original and translated items per field and labels each pair as aligned, partial, drifted, conflict, or missing. Accepted evidence is expected to have a recoverable source span and a non-drifted alignment state.

`features.py` is intentionally separate from the runtime reconcile path. It turns the existing score decomposition into a fixed-order numeric vector for offline policy evaluation, without reading labels or training a model.

## Usage Patterns

```python
# 1. Simple reconciliation
output = reconcile_results(original_result, translated_result)

# 2. Context-aware reconciliation with target-specific verifier support
output = reconcile_with_context(original_result, translated_result, target_context)

# 3. Inspect accepted vs rejected fields
for decision in output.decisions:
    print(decision.field_id, decision.accepted, decision.requires_review)

# 4. Export alignment records for benchmarking
for record in output.alignment_records:
    print(record.field_id, record.alignment_label, record.support_label)

# 5. Build offline arbitrator features
vector = extract_features(score, evidence_item, Track.ORIGINAL)
features = vector.to_list()
```

## Extension Guide

- Add new reconcile behavior in `core.py` only if it changes deterministic field selection.
- Add new traceability metadata in `contracts.py` and surface it through `ReconcileOutput`.
- Keep alignment-specific logic in `alignment.py`; do not mix it into the selection path.
- Keep learned-policy experimentation in `features.py` or benchmark code, not in runtime reconcile.

## Performance Notes

- The reconcile path is deterministic and in-memory.
- Alignment building is linear in the number of accepted evidence items.
- Feature extraction is cheap enough to use inside benchmark loops.
- The main cost comes from upstream extraction and verifier scoring, not from this module.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `EvidenceExtractionResult` | Input/output contract for dual-track reconciliation. |
| `EvidenceAlignmentRecord` | Traceable cross-track alignment output. |
| `TargetContextPack` | Target-specific verifier context for context-aware reconciliation. |
| `CandidateScore` | Decomposed candidate score used by feature extraction. |

## Testing

Run the focused reconcile and benchmark tests from `backend/`:

```bash
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile -v
uv run pytest tests/benchmark/layer3 -v
```

The current suite covers deterministic field selection, alignment labeling, traceability gates, and feature-vector extraction.
