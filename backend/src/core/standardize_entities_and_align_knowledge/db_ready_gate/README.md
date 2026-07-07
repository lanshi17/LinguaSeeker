# DB-ready Gate

> Pure Phase 3 gate for deciding whether evidence candidates are ready for DB-ready export.

## Quick Start

```python
from src.core.standardize_entities_and_align_knowledge.db_ready_gate import (
    DbReadyCandidate,
    evaluate_db_ready_candidate,
)

candidate = DbReadyCandidate(
    candidate_id="candidate-1",
    source_document_id="source-1",
    processing_run_id="run-1",
    field_id="A.variant_hgvs_p",
    group_id="MECP2|p.R168X",
    status="found",
    track="original",
    source_span={"source_quote": "The MECP2 p.R168X variant was identified."},
    variant_id="ClinVarVariation:11891",
)

result = evaluate_db_ready_candidate(candidate)
```

## Architecture

```text
DbReadyCandidate
      │
      ▼
evaluate_db_ready_candidate()
      │
      ├─ status / review checks
      ├─ source support checks
      ├─ entity binding checks
      └─ field-specific gene / variant / disease requirements
      │
      ▼
DbReadyGateResult

DbReadyCandidate[]
      │
      ▼
evaluate_db_ready_candidates()
      │
      ▼
DbReadyGateReport + rejection reason counts
```

The module is intentionally pure: it has no database session, LLM client, filesystem access, or mutable global state. `StandardizationRepository.upsert_canonical_evidence()` owns the integration boundary: it adapts staged `RunItemSpec` rows plus normalized entity bindings into `DbReadyCandidate` values, calls this module, logs aggregate rejection reasons, and only writes accepted business track rows to canonical evidence.

## Public API

### `DbReadyCandidate`

Dataclass representing one candidate evidence row before DB-ready export.

| Field | Type | Description |
| --- | --- | --- |
| `candidate_id` | `str` | Stable candidate key for audit/debugging. |
| `source_document_id` | `str` | Source document boundary. |
| `processing_run_id` | `str` | Processing run boundary. |
| `field_id` | `str` | Business evidence field, for example `A.variant_hgvs_p`. |
| `group_id` | `str` | Evidence group key. Required by default policy. |
| `status` | `str` | Candidate status. Default policy accepts only `found`. |
| `track` | `str` | Extraction track such as `original` or `translated`. |
| `source_span` | `DbReadySourceSpan | None` | Recoverable source support, including Phase 2 `text_snippet`. |
| `gene_id` / `variant_id` / `disease_id` | `str | None` | Normalized entity bindings used by field-specific rules. |
| `normalized_entity_ids` | `tuple[str, ...]` | Optional generic entity bindings. |
| `review_status` | `str | None` | Rejects values such as `rejected` by default. |
| `expert_override` | `bool` | Allows missing source support only when an explicit expert boundary exists. |

### `DbReadyGatePolicy`

```python
DbReadyGatePolicy(
    accepted_statuses=("found",),
    rejected_review_statuses=("rejected",),
    gene_required_field_ids=("A.gene_symbol", "A.gene_disease_relationship"),
    variant_required_field_ids=(...),
    disease_required_field_ids=("A.gene_disease_relationship", "B.disease_diagnosis"),
    require_group_id=True,
    require_source_support=True,
    require_any_entity_binding=False,
)
```

Use a custom policy to tighten or relax requirements for a specific workflow. For example, a benchmark runner can require gene bindings for `B.clinical_phenotypes` without changing production defaults.

### `evaluate_db_ready_candidate`

```python
def evaluate_db_ready_candidate(
    candidate: DbReadyCandidate,
    policy: DbReadyGatePolicy = DEFAULT_DB_READY_GATE_POLICY,
) -> DbReadyGateResult
```

Returns `DbReadyDecision.ACCEPTED` when no rejection reasons are produced. Rejection reasons are machine-readable `DbReadyRejectReason` enum values.

### `evaluate_db_ready_candidates`

```python
def evaluate_db_ready_candidates(
    candidates: Iterable[DbReadyCandidate],
    policy: DbReadyGatePolicy = DEFAULT_DB_READY_GATE_POLICY,
) -> DbReadyGateReport
```

Evaluates a batch and aggregates rejection counts for reporting.

## Internal Design

The default policy is conservative but not exhaustive:

- source document ID, processing run ID, field ID, and group ID must be present;
- status must be `found`;
- `review_status="rejected"` is rejected;
- source support must include either source text/quote/snippet or a recoverable location such as page + block index;
- `A.variant_*` fields and selected clinical variant fields such as `C.de_novo_status` require `variant_id`;
- `A.gene_symbol` and `A.gene_disease_relationship` require `gene_id`;
- `A.gene_disease_relationship` and `B.disease_diagnosis` require `disease_id`.

The gate reports every applicable rejection reason instead of stopping at the first one. That makes audit reports more useful: a candidate can be simultaneously rejected for unsupported status, missing source support, and missing variant binding.

## Usage Patterns

### Evaluate a batch and inspect rejection reasons

```python
from src.core.standardize_entities_and_align_knowledge.db_ready_gate import (
    evaluate_db_ready_candidates,
)

report = evaluate_db_ready_candidates(candidates)
for count in report.rejection_counts:
    print(count.reason.value, count.count)
```

### Inspect the repository integration report

```python
await repository.upsert_canonical_evidence(input_data, matches, entity_ids)
report = repository.db_ready_gate_report
if report is not None:
    print(report.accepted_count, report.rejected_count)
```

The repository report is populated when `input_data.track_payloads` are present. Match-fallback rows remain compatibility persistence and do not go through this DB-ready export gate.

### Tighten policy for phenotype export

```python
from src.core.standardize_entities_and_align_knowledge.db_ready_gate import (
    DbReadyGatePolicy,
    evaluate_db_ready_candidate,
)

policy = DbReadyGatePolicy(
    gene_required_field_ids=("B.clinical_phenotypes",),
    require_any_entity_binding=True,
)

result = evaluate_db_ready_candidate(candidate, policy)
```

### Allow an expert override

```python
from dataclasses import replace

candidate = replace(candidate_without_source_span, expert_override=True)
```

Use this only when the caller has an explicit expert review boundary. It is meant for post-adjudication export, not raw model output.

## Extension Guide

- Add new rejection reasons in `contracts.py` when the reason should be visible in audit output.
- Add field-specific requirements by extending `DbReadyGatePolicy`; avoid hard-coding benchmark-specific IDs in `core.py`.
- Repository wiring lives in `StandardizationRepository._filter_db_ready_run_item_rows()`. Keep new persistence behavior there; keep this module pure.
- Keep this module pure. Database reads, source-link lookups, and expert-review writes belong in providers/repositories around this gate.

## Performance Notes

The implementation is O(n) over candidates. Each candidate check is string and tuple membership only. The only aggregation cost is a `Counter` over rejection reasons.

## Dependencies

| Dependency | Purpose |
| --- | --- |
| Python standard library `dataclasses` | Immutable typed contracts. |
| Python standard library `enum` | Stable decision and rejection reason labels. |
| Python standard library `collections.Counter` | Batch rejection aggregation. |

## Testing

Run focused tests from `backend/`:

```bash
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_db_ready_gate.py -q
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_repositories.py -q
uv run ruff check src/core/standardize_entities_and_align_knowledge/db_ready_gate src/core/standardize_entities_and_align_knowledge/repositories.py tests/core/standardize_entities_and_align_knowledge/test_db_ready_gate.py tests/core/standardize_entities_and_align_knowledge/test_repositories.py
```

Current coverage verifies accepted candidates, Phase 2 `text_snippet` source support, variant binding rejection, source-support rejection and expert override, review rejection, custom policy requirements, batch reason counts, and repository-level canonical filtering.
