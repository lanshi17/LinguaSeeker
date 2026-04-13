# Backend 6-Node Contract Cleanup Design

## Goal
Finish the backend-only cleanup so the public `processing_steps` contract exposes exactly six steps: `acquisition`, `parsing`, `translation`, `extraction`, `classification`, and `adjudication`.

## Scope
In scope:
- backend processing-step normalization and serialization
- supervisor finalization behavior that writes terminal processing steps
- backend regression tests and fixtures that still expect `reasoning` in `processing_steps`

Out of scope:
- removing the internal `reasoning` graph node from the supervisor pipeline
- frontend or documentation sweeps outside this focused backend cleanup
- changing domain evidence payload fields that use the word `reasoning` in other contexts

## Chosen Approach
Keep `reasoning` as an internal execution node, but remove it from the user-visible processing-step contract.

### Why this approach
This is the smallest change that completes the six-node contract without altering the actual supervisor execution topology. It keeps runtime behavior stable while making the serialized processing state match the frozen v1 contract.

## Design

### 1. Contract boundary remains in `src/services/enum.py`
`src/services/enum.py` remains the single source of truth for public processing steps.

Required contract:
- `PROCESSING_STEP_ORDER` contains exactly 6 steps
- `PROCESSING_NODE_TO_STEP` has no mapping for `reasoning`
- `STEP_TO_WORKFLOW_STATUS` has no processing-step mapping for `reasoning`
- `normalize_processing_steps()` ignores any incoming `reasoning` entry in persisted payloads or node traces

This means legacy stored data may still contain `reasoning`, but normalization drops it before responses are returned.

### 2. Supervisor finalize phase must stop emitting `reasoning`
`src/agents/supervisor.py` currently writes terminal completion records for `reasoning`, `classification`, and `adjudication` during `finalize()`.

The cleanup changes `finalize()` so it writes only:
- `classification`
- `adjudication`

The graph can still execute the `reasoning` node internally. It just cannot surface as a user-visible processing step.

### 3. Streaming progress remains internal-node based
`src/services/task_manager.py` currently treats `reasoning` as one of `_SUPERVISOR_PROGRESS_NODES` for streamed node logging.

That can remain unchanged for this cleanup because:
- those are internal supervisor nodes, not the public `processing_steps` contract
- `reasoning` still exists in the graph topology
- node-level operational logging and user-visible processing-step serialization are separate concerns

So this cleanup does **not** remove `reasoning` from `_SUPERVISOR_PROGRESS_NODES`.

### 4. Regression coverage
Tests should prove the six-node contract explicitly.

Required regression updates:
- `tests/test_supervisor_e2e.py` must assert `reasoning` is absent from `processing_steps`
- `tests/test_state_transitions.py` must lock the six-step order
- `tests/test_golden_fixtures.py` and `tests/fixtures/golden_processing_state.json` must exclude `processing_steps.reasoning`

Optional focused safety check:
- add or strengthen a normalization assertion that legacy input containing `reasoning` is ignored

## Error handling and compatibility
No API shape expansion is needed. This is a narrowing cleanup:
- legacy `reasoning` input in stored JSON is tolerated
- normalized output drops unknown or obsolete steps
- workflow execution order is unchanged

## Validation plan
Run focused backend tests covering:
- state transition helpers
- supervisor happy-path finalization
- golden fixture validation

Primary target commands:
- `uv run pytest -q tests/test_state_transitions.py`
- `uv run pytest -q tests/test_supervisor_e2e.py`
- `uv run pytest -q tests/test_golden_fixtures.py`

If needed, run a combined command for the touched suite after focused fixes pass.
