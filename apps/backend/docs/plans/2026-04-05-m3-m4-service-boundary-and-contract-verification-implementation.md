# M3 M4 Service Boundary and Contract Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> **Plan Status:** `ACTIVE (Task 7 remaining; 100-paper acceptance still pending)`
> **Archived Completed Slice:** `docs/archive/2026-04-05-completed-plans/2026-04-05-m3-service-boundary-hardening-batch-1.md`

**Goal:** Harden the remaining parser/translation/extraction service boundaries and add a concrete M4 release-verification surface so `yangzs-agents` can finish the active `v1.0` rollout backlog.

**Architecture:** This plan follows the active rollout baseline in `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md`, where `M3` means service-boundary hardening and `M4` means contract/release verification. The older `docs/IMPLEMENTATION_PLAN.md` phase labels still use `M3` for KG work, so do not use that document to redefine the scope of this slice. Implementation should converge legacy compatibility layers on the same typed runtime contracts already used by `task_manager`, then add explicit release-gate calculation/reporting on top of those contracts.

**Tech Stack:** FastAPI backend, Pydantic models, pytest, MinIO, PostgreSQL, Qdrant, `uv`, repository docs under `docs/`, scripts under `scripts/`.

## Current Status

Completed and archived:
1. Task 1: parser compatibility contract
2. Task 2: translation warning/alignment contract
3. Task 3: extraction evidence source contract
4. Task 4: trace-chain contract
5. Task 5: release-gate calculation
6. Task 6: CLI/reporting surface

Still active in this plan:
1. Task 7: docs closeout + focused regression
2. Real 100-paper acceptance execution remains intentionally separate from the targeted Task 4-6 tooling slice.

---

## Archived Completed Tasks

Task 1 through Task 3 have been completed and moved out of the active execution surface. See:

`docs/archive/2026-04-05-completed-plans/2026-04-05-m3-service-boundary-hardening-batch-1.md`

---

### Task 4: Add a stable trace-chain contract to the pipeline result and task-status API

**Files:**
- Modify: `tests/unit/test_tasks.py`
- Modify: `tests/integration/test_task_api.py`
- Modify: `tests/test_golden_fixtures.py`
- Modify: `tests/fixtures/golden_pipeline_result.json`
- Modify: `src/domain/models.py`
- Modify: `src/services/dtos.py`
- Modify: `src/services/task_manager.py`
- Modify: `src/api/routes/task.py`

**Step 1: Write the failing trace-chain contract tests**

```python
def test_process_pdf_task_exposes_trace_chain(monkeypatch):
    ...
    result = _invoke_bound_task(tasks_module.process_pdf_task, ["file.pdf"])
    assert result["trace_chain"]["node_trace"]["translation"] == "success"
    assert result["trace_chain"]["processing_steps"]["classification"]["status"] == "COMPLETED"
    assert result["trace_chain"]["parsing_metadata"]["parser_backend"] == "mineru"
```

```python
def test_get_task_status_returns_warning_codes_and_trace_chain(...):
    ...
    assert payload["warning_codes"] == ["HGVS_AUTOCORRECT_FAILED"]
    assert payload["trace_chain"]["processing_steps"]["parsing"]["status"] == "COMPLETED"
```

**Step 2: Run the targeted trace-contract tests**

Run: `uv run pytest -q tests/unit/test_tasks.py::test_process_pdf_task_exposes_trace_chain tests/integration/test_task_api.py::test_get_task_status_returns_warning_codes_and_trace_chain tests/test_golden_fixtures.py::TestGoldenFixtures::test_pipeline_result_validates`

Expected: FAIL because `PipelineResult` and `TaskStatusResponse` do not yet expose `trace_chain` / `warning_codes`.

**Step 3: Implement the minimal trace-chain contract**

Add contract fields:

```python
class PipelineResult(BaseModel):
    ...
    warning_codes: List[str] = Field(default_factory=list)
    trace_chain: Dict[str, Any] = Field(default_factory=dict)
```

```python
class TaskStatusResponse(BaseModel):
    ...
    warning_codes: Optional[List[str]] = None
    trace_chain: Optional[Dict[str, Any]] = None
```

Build the trace payload in `task_manager` from existing runtime state:

```python
payload.setdefault(
    "trace_chain",
    {
        "node_trace": node_trace,
        "processing_steps": processing_steps,
        "parsing_metadata": parsing_metadata,
    },
)
payload.setdefault("warning_codes", warning_codes)
```

In `task.py`, surface the same shape from async payload or DB fields when present.

**Step 4: Run the trace-contract slice**

Run: `uv run pytest -q tests/unit/test_tasks.py tests/integration/test_task_api.py tests/test_golden_fixtures.py`

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 5: Add release-gate calculation tests for the 100-paper acceptance contract

**Files:**
- Create: `tests/unit/test_release_gate.py`
- Create: `tests/fixtures/release_gate_sample.json`
- Create: `src/services/release_gate.py`
- Read: `docs/PRD.md`
- Read: `docs/BACKEND_STRUCTURE.md`

**Step 1: Write the failing release-gate tests**

```python
def test_release_gate_counts_file_duplicate_in_both_numerator_and_denominator():
    summary = summarize_release_gate(
        [
            {"paper_task_id": "p1", "status": "success", "error_code": None, "processing_duration_seconds": 120.0},
            {"paper_task_id": "p2", "status": "success", "error_code": "FILE_DUPLICATE", "processing_duration_seconds": 1.0},
            {"paper_task_id": "p3", "status": "failed", "error_code": "PARSE_FAILED", "processing_duration_seconds": 80.0},
        ]
    )
    assert summary.paper_count == 3
    assert summary.success_count == 2
    assert summary.success_rate == pytest.approx(2 / 3)
```

```python
def test_release_gate_flags_duration_breach():
    summary = summarize_release_gate(
        [{"paper_task_id": "p1", "status": "success", "error_code": None, "processing_duration_seconds": 1801.0}]
    )
    assert summary.duration_pass is False
```

**Step 2: Run the release-gate tests**

Run: `uv run pytest -q tests/unit/test_release_gate.py`

Expected: FAIL because `src/services/release_gate.py` does not exist yet.

**Step 3: Implement the minimal release-gate calculation service**

Create a dedicated service with typed calculations:

```python
@dataclass
class ReleaseGateSummary:
    paper_count: int
    success_count: int
    success_rate: float
    duration_pass: bool
    max_duration_seconds: float


def summarize_release_gate(rows: list[dict[str, Any]]) -> ReleaseGateSummary:
    denominator = len(rows)
    success_count = sum(
        1
        for row in rows
        if row.get("status") == "success"
        and row.get("error_code") in {None, "FILE_DUPLICATE"}
    )
    max_duration = max((float(row.get("processing_duration_seconds") or 0.0) for row in rows), default=0.0)
    return ReleaseGateSummary(
        paper_count=denominator,
        success_count=success_count,
        success_rate=(success_count / denominator) if denominator else 0.0,
        duration_pass=max_duration <= 1800.0,
        max_duration_seconds=max_duration,
    )
```

**Step 4: Run the release-gate test slice**

Run: `uv run pytest -q tests/unit/test_release_gate.py`

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 6: Add the M4 CLI/reporting surface and acceptance-set scaffolding

**Files:**
- Create: `scripts/generate_v1_release_report.py`
- Create: `docs/release/README.md`
- Create: `docs/release/v1_0_acceptance_manifest.template.json`
- Create: `docs/release/v1_0_release_report.template.md`
- Modify: `tests/unit/test_release_gate.py`
- Modify: `src/services/release_gate.py`

**Step 1: Write the failing CLI/report rendering tests**

```python
def test_render_release_report_markdown_includes_gate_metrics():
    summary = ReleaseGateSummary(
        paper_count=100,
        success_count=97,
        success_rate=0.97,
        duration_pass=True,
        max_duration_seconds=1740.0,
    )
    markdown = render_release_report("v1.0", summary)
    assert "97.00%" in markdown
    assert "1740.0" in markdown
    assert "PASS" in markdown
```

**Step 2: Run the reporting tests**

Run: `uv run pytest -q tests/unit/test_release_gate.py::test_render_release_report_markdown_includes_gate_metrics`

Expected: FAIL because markdown rendering and the CLI wrapper do not exist yet.

**Step 3: Implement the minimal reporting surface**

Add rendering to `src/services/release_gate.py`:

```python
def render_release_report(release_no: str, summary: ReleaseGateSummary) -> str:
    gate = "PASS" if summary.success_rate >= 0.95 and summary.duration_pass else "FAIL"
    return f\"\"\"# {release_no} Release Report

- Papers: {summary.paper_count}
- Successes: {summary.success_count}
- Success rate: {summary.success_rate:.2%}
- Max duration (s): {summary.max_duration_seconds}
- Gate: {gate}
\"\"\"
```

Create a script wrapper under `scripts/` that reads a JSON input, calls the service, and writes a markdown report to a target path.

**Step 4: Run the reporting slice**

Run: `uv run pytest -q tests/unit/test_release_gate.py`

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 7: Update rollout docs and run the focused M3/M4 regression suite

**Files:**
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md`
- Modify: `docs/plans/README.md`
- Modify: `progress.txt`
- Modify: `lesson.md`
- Test: `tests/unit/application/test_document_service.py`
- Test: `tests/unit/test_task_manager_alignment.py`
- Test: `tests/unit/test_task_manager_minio_outputs.py`
- Test: `tests/unit/test_release_gate.py`
- Test: `tests/test_agents_extraction.py`
- Test: `tests/unit/test_tasks.py`
- Test: `tests/integration/test_task_api.py`
- Test: `tests/test_golden_fixtures.py`

**Step 1: Update the active rollout baseline**

Mark `M3` and `M4` with concrete completion notes only for the slices that actually shipped, and keep any still-open release-gate or acceptance-set work explicit.

**Step 2: Record progress and lessons**

Add one `progress.txt` milestone for the M3/M4 boundary + release-verification slice. If any new root cause appeared during implementation, add one `lesson.md` entry.

**Step 3: Run the focused M3/M4 regression suite**

Run:

`uv run pytest -q tests/unit/application/test_document_service.py tests/unit/test_task_manager_alignment.py tests/unit/test_task_manager_minio_outputs.py tests/unit/test_release_gate.py tests/test_agents_extraction.py tests/unit/test_tasks.py tests/integration/test_task_api.py tests/test_golden_fixtures.py`

Expected: PASS.

**Step 4: Run the broader rollout safety slice**

Run:

`uv run pytest -q tests/test_literature_unified_workflow.py tests/unit/test_unified_source_selection_and_trace.py tests/test_agents_acquisition.py tests/test_supervisor.py tests/test_supervisor_e2e.py`

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.
