# 7.1 流式输出 — Streaming Output Implementation Plan

## Problem

`_run_supervisor_pipeline` uses `graph.ainvoke()` which blocks until the entire graph completes.
During execution, no progress updates reach the database. The existing WebSocket endpoint
(`/api/v1/stream/{task_id}`) polls the DB but sees nothing until the final result is persisted.

## Solution

Replace `graph.ainvoke()` with `graph.astream(stream_mode="updates")` inside
`_run_supervisor_pipeline` and `_resume_supervisor_pipeline`. On each node completion event,
call the existing `_log_node_start`/`_log_node_end` helpers to persist progress to postgres.
The existing WebSocket polling then picks up real-time node-level progress with zero frontend
changes.

## Architecture

```
Celery worker
  └─ _run_supervisor_pipeline
       └─ async _invoke()
            └─ graph.astream(initial_state, config, stream_mode="updates")
                 ├─ chunk: {"route_by_source": {...}} → _log_node_end(node="route_by_source")
                 ├─ chunk: {"acquisition": {...}}     → _log_node_end(node="acquisition")
                 ├─ chunk: {"parsing": {...}}         → _log_node_end(node="parsing")
                 ├─ chunk: {"translation": {...}}     → _log_node_end(node="translation")
                 ├─ chunk: {"extraction": {...}}      → _log_node_end(node="extraction")
                 ├─ chunk: {"arbitration": {...}}     → _log_node_end(node="arbitration")
                 └─ chunk: {"finalize": {...}}        → _log_node_end(node="finalize")
                      └─ final_state = last chunk's state update
```

## Constraints

- Zero frontend changes — existing WebSocket polling picks up DB changes
- Zero new endpoints — use existing `/api/v1/stream/{task_id}`
- Zero new dependencies — LangGraph `astream` is already available (>=1.0.8)
- Backward compatible — payload shape unchanged, test contract unchanged
- The `_log_node_start`/`_log_node_end` helpers already handle the DB writes

## Implementation Steps

### Step 1: Add `_stream_supervisor_graph` helper (tasks.py)

New async function that replaces `ainvoke` with `astream`:

```python
async def _stream_supervisor_graph(
    graph: CompiledStateGraph,
    initial_state: dict | None,
    config: RunnableConfig,
    postgres,
    paper_task_id: str,
) -> dict:
    """Run graph with streaming, persisting node progress to DB."""
    final_state = {}
    prev_node = None

    async for chunk in graph.astream(
        initial_state, config=config, stream_mode="updates"
    ):
        for node_name, node_output in chunk.items():
            # Log previous node completion when next node starts
            if prev_node is not None:
                _log_node_end(postgres, paper_task_id, prev_node, success=True)

            # Log current node start
            _log_node_start(postgres, paper_task_id, node_name)

            # Track the latest state
            final_state.update(node_output)
            prev_node = node_name

    # Log the final node completion
    if prev_node is not None:
        _log_node_end(postgres, paper_task_id, prev_node, success=True)

    return final_state
```

### Step 2: Modify `_run_supervisor_pipeline` (tasks.py)

Replace:
```python
final_state = await graph.ainvoke(initial_state, config=invoke_config)
```

With:
```python
final_state = await _stream_supervisor_graph(
    graph, initial_state, invoke_config, postgres, paper_task_id
)
```

### Step 3: Modify `_resume_supervisor_pipeline` (tasks.py)

Same change — replace `ainvoke(None, config=...)` with `_stream_supervisor_graph(graph, None, ...)`.

### Step 4: Map supervisor nodes to processing steps

The `PROCESSING_NODE_TO_STEP` mapping needs to include all supervisor graph node names.
Current mapping covers: acquisition, parsing, translation, extraction, classification, adjudication.

Supervisor nodes: route_by_source, interaction, acquisition, parsing, translation, extraction,
arbitration, finalize, finalize_failed, human_review.

Add missing mappings:
- `route_by_source` → skip (routing, not a processing step)
- `interaction` → skip or new step
- `arbitration` → `adjudication` (already mapped via classification?)
- `finalize` / `finalize_failed` / `human_review` → skip (terminal, not processing)

### Step 5: Handle errors in streaming

If a node raises an exception during `astream`, the async generator will propagate it.
Catch it to log the failed node:

```python
try:
    async for chunk in graph.astream(...):
        ...
except Exception as exc:
    if prev_node is not None:
        _log_node_end(postgres, paper_task_id, prev_node, success=False,
                      error_code="NODE_FAILURE", message=str(exc))
    raise
```

### Step 6: Tests

- Test `_stream_supervisor_graph` with a mock graph that yields chunks
- Test that `_log_node_start`/`_log_node_end` are called for each node
- Test error handling — node failure logs correctly
- Test existing stream route tests still pass (contract unchanged)

## Files to Modify

| File | Change |
|---|---|
| `src/service/tasks.py` | Add `_stream_supervisor_graph`, modify `_run_supervisor_pipeline` and `_resume_supervisor_pipeline` |
| `src/service/enum.py` | Add missing supervisor node mappings to `PROCESSING_NODE_TO_STEP` |
| `tests/test_stream_supervisor.py` | New: test streaming helper + integration |

## Verification

1. `uv run pytest tests/test_stream_route.py` — existing tests pass (contract unchanged)
2. `uv run pytest tests/test_stream_supervisor.py` — new streaming tests pass
3. `uv run pytest` — full suite green
