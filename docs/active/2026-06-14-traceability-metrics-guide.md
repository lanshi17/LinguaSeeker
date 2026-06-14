# Traceability Metrics Developer Guide

**Status:** in-progress
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> Developer reference for `benchmark/layer3/analysis/traceability_metrics.py`.

## Quick Start

Run candidate traceability on the frozen BIBM ablation report:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics \
  --system-report benchmark/layer3/reports/reconcile_ablation_20260614_155845.json \
  --strategy context_verifier_reconcile \
  --ground-truth-root benchmark/layer3/ground_truth \
  --reports-dir benchmark/layer3/reports \
  --write
```

Run a citation-surface check for a baseline report:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics \
  --baseline-report benchmark/layer3/reports/baseline_b0_20260613_013114.json \
  --ground-truth-root benchmark/layer3/ground_truth \
  --reports-dir benchmark/layer3/reports \
  --write
```

## Architecture

```text
report JSON
  -> select system strategy or baseline payload
  -> read per_entry field_matches
  -> validate source spans against ground_truth/<entry_id>/source.md
  -> compute counts
  -> derive metrics and warnings
  -> write traceability_<label>_<timestamp>.json
```

The module is intentionally offline and deterministic. It does not call LLMs and does not use expected field values as runtime method input. For semantic support, it uses the evaluator's `matched` flag as the current gold-audit proxy.

## Public API

| Function | Signature | Purpose |
|---|---|---|
| `span_boundary_f1` | `span_boundary_f1(predicted: str, gold: str) -> float` | Token-overlap F1 between a predicted citation span and a support span. |
| `traceable_f1` | `traceable_f1(*, extraction_f1: float, citation_validity_rate: float) -> float` | Multiplicative utility metric: extraction F1 constrained by CVR. |
| `build_traceability_report` | `build_traceability_report(*, system_report_path: Path | None = None, strategy: str | None = None, baseline_report_path: Path | None = None, ground_truth_root: Path = GROUND_TRUTH_DIR) -> TraceabilityReport` | Builds typed metrics from one system strategy or baseline report. |
| `traceability_report_to_payload` | `traceability_report_to_payload(report: TraceabilityReport) -> TraceabilityReportPayload` | Converts typed results to JSON payload. |
| `write_traceability_report` | `write_traceability_report(report: TraceabilityReport, reports_dir: Path = REPORTS_DIR) -> Path` | Persists a timestamped report. |
| `format_traceability_report` | `format_traceability_report(report: TraceabilityReport) -> str` | Prints a compact terminal summary. |

## Metrics

| Metric | Implementation | Interpretation |
|---|---|---|
| CVR | `citation_valid / citation_total` | Accepted cited span is recoverable from canonical source text. |
| HCR | `hallucinated / citation_total` | Accepted citation cannot be mapped back to canonical source text. |
| Span Boundary F1 | token overlap from `span_boundary_tp/fp/fn` | Boundary tightness. Without manual gold spans, the canonical offset text is used. |
| ESR | `evidence_supported / evidence_total` | Current proxy for semantic support, based on evaluator `matched`. |
| TraceableF1 | `extraction_f1 * CVR` | Extraction utility constrained by citation validity. |
| CLC | original/translated field value agreement | Dual-track consistency from `preprocessed/phase_2/extraction_result.json`. |

## Citation Validity Logic

Validation is deliberately stronger than regex matching:

1. Use span offsets when they point to source text containing the predicted snippet.
2. Fall back to normalized whole-text containment.
3. Fall back to contiguous token-sequence containment, with optional article removal for `a/an/the`.

The token fallback handles offset drift and harmless punctuation differences while rejecting loose word-bag matches.

## Current G2 Snapshot

Frozen candidate report:

```text
benchmark/layer3/reports/traceability_context_verifier_reconcile_20260614_213054.json
CVR=1.0
HCR=0.0
SpanBoundaryF1=0.744
ESR=0.8636
TraceableF1=0.9157
CLC=0.194
```

Limitations:

- `SpanBoundaryF1` currently uses canonical offset text when no manual gold source spans are annotated.
- B0-B4 full-N baseline reports do not emit citation spans, so their CVR/HCR are intentionally `null` with `baseline_has_no_citation_surface`.
- CLC is low because it compares raw original/translated field-value sets before final arbitration.

## Extension Guide

Add metric fields by extending:

1. `TraceabilityCounts`
2. `TraceabilityMetrics`
3. `TraceabilityMetricPayload`
4. `_metrics_from_counts`
5. `backend/tests/benchmark/layer3/test_traceability_metrics.py`

Keep new metrics deterministic and report warnings when a value is not computable. Do not silently coerce missing citation surfaces into success.

## Testing

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_traceability_metrics.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  benchmark/layer3/analysis/traceability_metrics.py \
  backend/tests/benchmark/layer3/test_traceability_metrics.py
```
