# Release Artifact Consistency Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the checked-in acceptance manifest, release report, and rollout tracking records self-consistent after the real 100-paper run so the published `v1.0` gate state can be trusted.

**Architecture:** The current branch already has terminal acceptance rows and a published release report, but the artifact layer drifts because manifest-level notes are preserved verbatim and the report timestamp is derived from manifest curation time. Fix the drift at the artifact boundary only: normalize stale pre-execution notes during manifest sync, render reports with an explicit report-generation timestamp, add regression coverage that loads the checked-in artifacts, and then republish the canonical JSON/Markdown/docs from the current manifest state.

**Tech Stack:** Python, Pydantic, pytest, argparse scripts, JSON/Markdown release artifacts, `uv`.

**Execution note:** Run this in a dedicated worktree. Do not rerun the 100-paper acceptance set in this plan; this is a release-artifact remediation pass, not a workflow rerun.

**Git Note:** This repository usually operates under “do not commit unless explicitly requested.” Each task includes a commit step for execution sessions that are explicitly doing commits; otherwise skip the commit step.

---

## Scope anchor

Current concrete inconsistency to remediate:
1. `docs/release/v1.0-release-report.md` says `PASSED` but still includes the stale note `Manifest is populated and locked, but the acceptance run has not been executed yet.`
2. `docs/acceptance/v1.0-100-paper-manifest.json` still carries pre-execution notes even though the rows now contain terminal `status`, `paper_task_id`, and durations.
3. The release report’s `Generated at:` value currently follows manifest curation time instead of report render time.
4. `progress.txt` still records the earlier `FAILED / DURATION_SLA_BREACHED` state, but there is no matching final artifact-publication milestone that explains the later `PASSED` claim in the active plan docs.

Non-goals:
1. Do not change release-gate thresholds, success counting, or duration SLA math.
2. Do not rerun acceptance execution or reopen paper tasks.
3. Do not redesign the manifest schema beyond what is needed to publish consistent artifacts.

---

### Task 1: Pin the terminal-manifest note contract with failing tests

**Files:**
- Modify: `tests/unit/test_acceptance_runner.py`
- Modify: `tests/unit/test_release_reporting.py`
- Modify: `src/services/acceptance_runner.py`
- Modify: `src/services/release_reporting.py`

**Step 1: Write the failing tests**

Add one sync-path test and one render-path test.

```python
def test_sync_manifest_from_postgres_removes_pre_execution_note_after_terminal_run(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "release_no": "v1.0",
                "locked": True,
                "expected_paper_count": 1,
                "notes": [
                    "Manifest is populated and locked, but the acceptance run has not been executed yet."
                ],
                "papers": [{"paper_id": "paper-a", "paper_task_id": "task-1", "status": "queued"}],
            }
        ),
        encoding="utf-8",
    )

    class FakePostgres:
        def get_acceptance_result_by_paper_id(self, paper_id: str) -> Any:
            return SimpleNamespace(
                paper_task_id="task-1",
                status="success",
                error_code=None,
                processing_duration_seconds=123.0,
            )

    manifest = sync_manifest_from_postgres(manifest_path, postgres=FakePostgres(), write=True)

    assert "Manifest is populated and locked, but the acceptance run has not been executed yet." not in manifest.notes
    assert any(note.startswith("Acceptance run reached terminal state:") for note in manifest.notes)
```

```python
def test_render_release_report_drops_unfinished_note_for_terminal_manifest() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "expected_paper_count": 1,
            "notes": ["Actual 100-paper acceptance run remains unfinished."],
            "papers": [{"paper_id": "paper-a", "status": "success", "duration_seconds": 120.0}],
        }
    )

    summary = calculate_release_gate_summary(manifest)
    rendered = render_release_report(manifest, summary)

    assert "Actual 100-paper acceptance run remains unfinished." not in rendered
    assert "Acceptance run reached terminal state:" in rendered
```

**Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_runner.py::test_sync_manifest_from_postgres_removes_pre_execution_note_after_terminal_run tests/unit/test_release_reporting.py::test_render_release_report_drops_unfinished_note_for_terminal_manifest
```

Expected: FAIL because manifest notes are currently preserved verbatim in both the sync and render paths.

**Step 3: Write the minimal implementation**

In `src/services/release_reporting.py`, add one small helper that normalizes manifest-level notes from the actual gate summary instead of trusting stale pre-execution prose forever.

```python
PRE_EXECUTION_NOTES = {
    "Manifest is populated and locked, but the acceptance run has not been executed yet.",
    "Actual 100-paper acceptance run remains unfinished.",
}


def normalize_manifest_notes(
    manifest: AcceptanceManifest,
    summary: ReleaseGateSummary,
) -> list[str]:
    notes = [note for note in manifest.notes if note not in PRE_EXECUTION_NOTES]
    if summary.completed_paper_count >= manifest.expected_paper_count:
        notes.append(
            f"Acceptance run reached terminal state: success={summary.success_count}, failed={summary.failed_count}."
        )
        if "DURATION_SLA_BREACHED" in summary.blocking_reasons:
            notes.append("Release gate follow-up remains open for DURATION_SLA_BREACHED.")
    return _dedupe_preserve_order(notes)
```

Implementation rules:
1. Strip only the known stale pre-execution notes.
2. Preserve unrelated operator notes in original order.
3. Reuse the same normalization helper from both `sync_manifest_from_postgres(...)` and `render_release_report(...)` so JSON and Markdown stay aligned.
4. Do not change any release-gate math.

**Step 4: Re-run the tests**

Run the same command from Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py src/services/acceptance_runner.py src/services/release_reporting.py
git commit -m "fix: normalize terminal acceptance artifact notes"
```

---

### Task 2: Separate report render time from manifest curation time

**Files:**
- Modify: `tests/unit/test_release_reporting.py`
- Modify: `src/services/release_reporting.py`
- Modify: `src/services/release_report_cli.py`
- Modify: `scripts/release_report.py`

**Step 1: Write the failing timestamp test**

```python
def test_render_release_report_uses_render_timestamp_not_manifest_generated_at() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "generated_at": "2026-04-07T00:00:00+00:00",
            "expected_paper_count": 1,
            "papers": [{"paper_id": "paper-a", "status": "success", "duration_seconds": 120.0}],
        }
    )

    summary = calculate_release_gate_summary(manifest)
    rendered = render_release_report(
        manifest,
        summary,
        rendered_at=datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc),
    )

    assert "Generated at: 2026-04-10T08:00:00+00:00" in rendered
    assert "Generated at: 2026-04-07T00:00:00+00:00" not in rendered
```

**Step 2: Run the test to verify it fails**

Run:
```bash
uv run pytest -q tests/unit/test_release_reporting.py::test_render_release_report_uses_render_timestamp_not_manifest_generated_at
```

Expected: FAIL because `render_release_report(...)` currently renders `manifest.generated_at` as the report timestamp.

**Step 3: Write the minimal implementation**

Update `render_release_report(...)` to accept an explicit render timestamp.

```python
def render_release_report(
    manifest: AcceptanceManifest,
    summary: ReleaseGateSummary,
    *,
    template_text: str | None = None,
    rendered_at: datetime | None = None,
) -> str:
    rendered_at = rendered_at or datetime.now(timezone.utc)
    report_generated_at = rendered_at.isoformat()
    notes = normalize_manifest_notes(manifest, summary)
    ...
```

Implementation rules:
1. Treat `manifest.generated_at` as manifest curation metadata, not report publish time.
2. Use `rendered_at` only for the markdown `Generated at:` field.
3. Keep the CLI thin: `src/services/release_report_cli.py` should call `render_release_report(...)` without reimplementing formatting rules.
4. Do not add new CLI flags unless they are required for testing.

**Step 4: Re-run the test**

Run the same command from Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_release_reporting.py src/services/release_reporting.py src/services/release_report_cli.py scripts/release_report.py
git commit -m "fix: render release reports with publish timestamps"
```

---

### Task 3: Add a checked-in artifact consistency regression and republish the canonical files

**Files:**
- Create: `tests/unit/test_release_artifacts.py`
- Modify: `docs/acceptance/v1.0-100-paper-manifest.json`
- Modify: `docs/release/v1.0-release-report.md`
- Modify: `src/services/release_reporting.py`
- Test: `tests/unit/test_acceptance_runner.py`
- Test: `tests/unit/test_release_reporting.py`

**Step 1: Write the failing checked-in artifact regression**

```python
def test_checked_in_release_artifacts_are_self_consistent() -> None:
    manifest = load_acceptance_manifest("docs/acceptance/v1.0-100-paper-manifest.json")
    summary = calculate_release_gate_summary(manifest)
    report = Path("docs/release/v1.0-release-report.md").read_text(encoding="utf-8")

    assert f"Gate status: {summary.gate_status}" in report
    if summary.completed_paper_count >= manifest.expected_paper_count:
        assert "acceptance run has not been executed yet" not in report.lower()
        assert "Actual 100-paper acceptance run remains unfinished." not in report
```

**Step 2: Run the regression to verify it fails**

Run:
```bash
uv run pytest -q tests/unit/test_release_artifacts.py
```

Expected: FAIL because the checked-in report still contains stale pre-execution wording.

**Step 3: Republish the manifest and report from the current manifest state**

Run:
```bash
uv run python scripts/sync_acceptance_manifest.py --manifest docs/acceptance/v1.0-100-paper-manifest.json --write
uv run python scripts/release_report.py --manifest docs/acceptance/v1.0-100-paper-manifest.json --output docs/release/v1.0-release-report.md
```

Expected outcomes:
1. `docs/acceptance/v1.0-100-paper-manifest.json` keeps its actual paper rows but no longer carries stale pre-execution notes.
2. `docs/release/v1.0-release-report.md` uses a fresh report render timestamp.
3. The checked-in report’s notes and gate status now match the manifest-derived summary.

**Step 4: Re-run the release-artifact regression plus the supporting unit slice**

Run:
```bash
uv run pytest -q tests/unit/test_release_artifacts.py tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_release_artifacts.py docs/acceptance/v1.0-100-paper-manifest.json docs/release/v1.0-release-report.md src/services/release_reporting.py tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py
git commit -m "test: pin checked-in release artifact consistency"
```

---

### Task 4: Record the final artifact-publication provenance in rollout tracking docs

**Files:**
- Modify: `progress.txt`
- Modify: `lesson.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md`

**Step 1: Append the missing publication milestone to `progress.txt`**

Record one concrete milestone covering:
1. manifest-note normalization
2. report republish with fresh render timestamp
3. the verified gate result after artifact finalization
4. the fact that this pass changed artifacts only, not acceptance execution rows

**Step 2: Add one `lesson.md` entry for the root cause**

Use this structure:

```markdown
2026-04-10 - release artifacts drift when report rendering trusts stale manifest notes and curation timestamps
- Symptom: published report gate/status text and notes contradicted the executed manifest state.
- Root cause: manifest notes were preserved verbatim after execution, and report generation reused manifest curation time as publication time.
- Fix: normalize terminal-manifest notes during sync/render, render reports with explicit publish timestamps, and pin checked-in artifact consistency with a regression test.
- Prevention: whenever acceptance artifacts are republished, validate the checked-in manifest/report pair from disk rather than assuming the latest runtime summary matches the last committed markdown.
```

**Step 3: Make the active plan docs match the republished artifacts exactly**

Required outcomes:
1. `docs/plans/README.md` and `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md` must reference the same final gate state as the regenerated report.
2. Remove any remaining wording that implies the duration-SLA follow-up is still pending if the regenerated report proves it is closed.
3. Keep the docs honest if the regenerated report still shows any blocker.

**Step 4: Re-run the artifact regression after the doc updates**

Run:
```bash
uv run pytest -q tests/unit/test_release_artifacts.py tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add progress.txt lesson.md docs/plans/README.md docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md
git commit -m "docs: record release artifact finalization provenance"
```

---

### Task 5: Final verification sweep for the remediation slice

**Files:**
- Verify only

**Step 1: Run the full targeted backend slice for this remediation**

```bash
uv run pytest -q tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py tests/unit/test_release_artifacts.py
```

Expected: PASS.

**Step 2: Verify the published artifacts directly**

```bash
test -f docs/acceptance/v1.0-100-paper-manifest.json
test -f docs/release/v1.0-release-report.md
```

Expected: PASS.

**Step 3: Manually spot-check the two critical strings**

Confirm:
1. `docs/release/v1.0-release-report.md` no longer contains `Manifest is populated and locked, but the acceptance run has not been executed yet.`
2. `docs/release/v1.0-release-report.md` shows the same gate status as `calculate_release_gate_summary(load_acceptance_manifest(...))`

**Step 4: Commit**

Only if the execution session is explicitly doing commits and there are still unstaged remediation changes.
