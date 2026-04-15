# Rollout Plan Archive Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md` from an incorrectly active baseline into a validated archived historical plan with current paths and an updated plan index.

**Architecture:** This is a docs-only migration. First normalize stale references while the file is still in place, then move it to `docs/plans/archive/2026-04-15-completed-plans/`, and finally update `docs/plans/README.md` so active-vs-archived state stays accurate. Use small Python file-assertion checks instead of repo-wide test suites because the change only touches Markdown docs and archive placement.

**Tech Stack:** Markdown docs, Python stdlib (`pathlib`) for verification, git file moves.

**Git Note:** This repository often runs under “do not commit unless explicitly requested.” Each task includes a commit step for completeness, but only run it if the user explicitly asks for a commit in the execution session.

---

### Task 1: Normalize the rollout plan while it is still in the active location

**Files:**
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md:3-9`
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md:27-29`
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md:37-39`
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md:47-52`
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md:75-108`
- Read: `docs/plans/2026-04-14-rollout-plan-archive-design.md`
- Read: `apps/backend/progress.txt`

**Step 1: Write the failing verification script**

```python
from pathlib import Path

text = Path("docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md").read_text()

assert "COMPLETED / ARCHIVED" in text
assert "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-design.md" in text
assert "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-implementation.md" in text
assert "docs/plans/archive/2026-04-05-completed-plans/2026-04-05-m3-service-boundary-hardening-batch-1.md" in text
assert "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-design.md" in text
assert "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-implementation.md" in text
assert "`apps/backend/progress.txt`" in text
assert "`apps/backend/tests/test_supervisor.py`" in text
assert "`apps/backend/tests/test_supervisor_e2e.py`" in text
assert "`apps/backend/src/services/kg_events.py`" in text
assert "`apps/frontend/src/pages/requests/request-monitor-page.tsx`" in text
assert "docs/archive/" not in text
assert "`../frontend/" not in text
assert "> **Plan Status:** `ACTIVE (v1.0 baseline)`" not in text
PY
```

**Step 2: Run the script to verify it fails**

Run:
```bash
python - <<'PY'
from pathlib import Path

text = Path("docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md").read_text()

assert "COMPLETED / ARCHIVED" in text
assert "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-design.md" in text
assert "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-implementation.md" in text
assert "docs/plans/archive/2026-04-05-completed-plans/2026-04-05-m3-service-boundary-hardening-batch-1.md" in text
assert "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-design.md" in text
assert "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-implementation.md" in text
assert "`apps/backend/progress.txt`" in text
assert "`apps/backend/tests/test_supervisor.py`" in text
assert "`apps/backend/tests/test_supervisor_e2e.py`" in text
assert "`apps/backend/src/services/kg_events.py`" in text
assert "`apps/frontend/src/pages/requests/request-monitor-page.tsx`" in text
assert "docs/archive/" not in text
assert "`../frontend/" not in text
assert "> **Plan Status:** `ACTIVE (v1.0 baseline)`" not in text
PY
```

Expected: FAIL because the file still contains the active status, old `docs/archive/...` references, old backend/frontend root-relative paths, and the outdated `progress.txt` reference.

**Step 3: Write the minimal implementation**

Apply only the documented path/status corrections below. Do not rewrite milestone conclusions.

Replace the top metadata block with:

```markdown
> **Plan Status:** `COMPLETED / ARCHIVED on 2026-04-15`
> **Archive Note:** Current-branch recheck on `yangzs-agents` confirmed the rollout body is complete; this file is retained as a historical baseline and should not receive new execution items.
> **Conflict Rule:** Frozen docs still win. If a new release risk appears, create a new incremental plan instead of reopening this archived baseline.
> **Current Branch Snapshot (`yangzs-agents` after merging local worktrees):** `M1/M2 completed, release-closure program tasks 1-15 executed on 2026-04-09; 100-paper acceptance has reached terminal state and the published release report is now PASSED after duration-SLA follow-up`
> **Historical Execution Detail:** `docs/plans/2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md` now remains for Task 1-6 provenance only.
> **Reference Rollout Docs:** `docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-design.md`, `docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-implementation.md`
> **Completed Slice Archive:** `docs/plans/archive/2026-04-05-completed-plans/2026-04-05-m3-service-boundary-hardening-batch-1.md`
> **Current Release Program Archive:** `docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-design.md`, `docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-implementation.md`
```

Make these exact reference updates in the body:
1. `progress.txt` → `apps/backend/progress.txt`
2. `tests/test_supervisor.py` → `apps/backend/tests/test_supervisor.py`
3. `tests/test_supervisor_e2e.py` → `apps/backend/tests/test_supervisor_e2e.py`
4. `docs/archive/...` → `docs/plans/archive/...`
5. `src/services/kg_events.py` → `apps/backend/src/services/kg_events.py`
6. `src/services/kg_consumer.py` → `apps/backend/src/services/kg_consumer.py`
7. `src/services/kg_backfill.py` → `apps/backend/src/services/kg_backfill.py`
8. `src/services/kg_tasks.py` → `apps/backend/src/services/kg_tasks.py`
9. `src/domain/graph/sync.py` → `apps/backend/src/domain/graph/sync.py`
10. `src/services/acceptance_runner.py` → `apps/backend/src/services/acceptance_runner.py`
11. `tests/unit/test_kg_events.py` → `apps/backend/tests/unit/test_kg_events.py`
12. `tests/unit/test_kg_consumer.py` → `apps/backend/tests/unit/test_kg_consumer.py`
13. `tests/unit/test_kg_backfill.py` → `apps/backend/tests/unit/test_kg_backfill.py`
14. `tests/unit/test_graph_variant_fanout.py` → `apps/backend/tests/unit/test_graph_variant_fanout.py`
15. `tests/unit/test_acceptance_runner.py` → `apps/backend/tests/unit/test_acceptance_runner.py`
16. `tests/unit/test_release_reporting.py` → `apps/backend/tests/unit/test_release_reporting.py`
17. `../frontend/src/pages/requests/request-monitor-page.tsx` → `apps/frontend/src/pages/requests/request-monitor-page.tsx`
18. `../frontend/src/pages/documents/document-page.tsx` → `apps/frontend/src/pages/documents/document-page.tsx`
19. `../frontend/src/pages/requests/request-export-page.tsx` → `apps/frontend/src/pages/requests/request-export-page.tsx`
20. `npm --prefix ../frontend` → `npm --prefix apps/frontend`
21. `uv run pytest -q ...` backend commands rooted at repo root → `uv run --directory apps/backend pytest -q ...`
22. `uv run basedpyright src/` → `uv run --directory apps/backend basedpyright src/`
23. `uv run ruff check src/ tests/` → `uv run --directory apps/backend ruff check src/ tests/`

Replace `## Remaining Work` with:

```markdown
## Remaining Work
当前没有需要继续在本基线计划内执行的 rollout 实现工作。

后续若出现新的 release 风险项、额外验证批次或复盘动作，应新建增量计划，而不是继续把这份已归档基线当作 active plan 使用。
```

Replace the line at the end of the prior section:

```markdown
后续若派生更小执行批次，应作为新的增量整改计划编写；本基线计划在归档后仅保留历史追溯用途。
```

**Step 4: Run the same verification script to verify it passes**

Run the exact command from Step 2.

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 2: Move the normalized plan into the completed-plans archive slice

**Files:**
- Create: `docs/plans/archive/2026-04-15-completed-plans/`
- Move: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md` → `docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md`
- Test: `docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md`

**Step 1: Write the failing verification script**

```python
from pathlib import Path

archive_path = Path("docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md")
active_path = Path("docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md")

assert archive_path.exists()
assert not active_path.exists()
PY
```

**Step 2: Run the script to verify it fails**

Run:
```bash
python - <<'PY'
from pathlib import Path

archive_path = Path("docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md")
active_path = Path("docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md")

assert archive_path.exists()
assert not active_path.exists()
PY
```

Expected: FAIL because the archive destination does not exist yet and the file is still in the active top-level plans directory.

**Step 3: Write the minimal implementation**

Run:
```bash
mkdir -p docs/plans/archive/2026-04-15-completed-plans
git mv docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md
```

If `git mv` is not appropriate in the execution session, use a plain filesystem move instead, but keep the destination path exactly the same.

**Step 4: Run the same verification script to verify it passes**

Run the exact command from Step 2.

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 3: Update the active-plan index so it no longer advertises the archived rollout plan as active

**Files:**
- Modify: `docs/plans/README.md:12-32`
- Modify: `docs/plans/README.md:57-80`
- Read: `docs/plans/archive/README.md`
- Test: `docs/plans/README.md`

**Step 1: Write the failing verification script**

```python
from pathlib import Path

text = Path("docs/plans/README.md").read_text()
pre_archive, _, _ = text.partition("## 已完成并归档的计划")

assert "2026-03-22-v1.0-multi-source-6node-rollout.md" not in pre_archive
assert "docs/plans/archive/2026-04-15-completed-plans/" in text
assert "- `2026-03-22-v1.0-multi-source-6node-rollout.md`" in text
assert "当前顶层 `docs/plans/` 暂无 backend/root active baseline" in text
PY
```

**Step 2: Run the script to verify it fails**

Run:
```bash
python - <<'PY'
from pathlib import Path

text = Path("docs/plans/README.md").read_text()
pre_archive, _, _ = text.partition("## 已完成并归档的计划")

assert "2026-03-22-v1.0-multi-source-6node-rollout.md" not in pre_archive
assert "docs/plans/archive/2026-04-15-completed-plans/" in text
assert "- `2026-03-22-v1.0-multi-source-6node-rollout.md`" in text
assert "当前顶层 `docs/plans/` 暂无 backend/root active baseline" in text
PY
```

Expected: FAIL because the README still lists the rollout file under `ACTIVE` and does not yet mention the new archive slice.

**Step 3: Write the minimal implementation**

Replace the `### ACTIVE` subsection with:

```markdown
### `ACTIVE`

当前顶层 `docs/plans/` 暂无 backend/root active baseline。若后续出现新的 release 风险、补充验证或复盘任务，请基于已归档的 `2026-03-22-v1.0-multi-source-6node-rollout.md` 重新派生新计划；前端计划继续保留在 `docs/plans/frontend/`。
```

Update `## 当前状态（已同步到真实执行结果）` so item 4 becomes:

```markdown
4. 当前根 `docs/plans/` 已不再保留 rollout active baseline；后续如需继续 release 风险整改，应从归档基线重新派生增量计划。
```

Update `## 建议后续顺序` so item 1 becomes:

```markdown
1. 如需继续 release 风险整改或复盘，基于归档的 `2026-03-22-v1.0-multi-source-6node-rollout.md` 派生新的执行批次，不再恢复该基线到 active 目录。
```

Add a new archive entry block before the existing `已于 2026-04-13 归档...` block:

```markdown
已于 `2026-04-15` 归档到 `docs/plans/archive/2026-04-15-completed-plans/`：

- `2026-03-22-v1.0-multi-source-6node-rollout.md`
```

Add the new archive directory to `## 历史归档目录`:

```markdown
- `docs/plans/archive/2026-04-15-completed-plans/`
```

Update `## 当前整理结论` so item 1 becomes:

```markdown
1. 当前根 `docs/plans/` 已移除已完成的 rollout baseline active 入口，仅保留仍需继续推进的计划入口与前端计划目录。
```

Update `## 当前整理结论` so item 4 becomes:

```markdown
4. 后续主线如需恢复 release 风险整改，应从已归档的 `v1.0` 基线计划重新派生新的增量计划。
```

**Step 4: Run the same verification script to verify it passes**

Run the exact command from Step 2.

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 4: Run final archive consistency validation

**Files:**
- Test: `docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md`
- Test: `docs/plans/README.md`
- Read: `docs/plans/archive/README.md`

**Step 1: Write the final validation script**

```python
from pathlib import Path

archive = Path("docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md")
active = Path("docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md")
readme = Path("docs/plans/README.md").read_text()
text = archive.read_text()

required_paths = [
    "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-design.md",
    "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-implementation.md",
    "docs/plans/archive/2026-04-05-completed-plans/2026-04-05-m3-service-boundary-hardening-batch-1.md",
    "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-design.md",
    "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-implementation.md",
    "`apps/backend/progress.txt`",
    "`apps/backend/src/services/kg_events.py`",
    "`apps/frontend/src/pages/requests/request-monitor-page.tsx`",
]

assert archive.exists()
assert not active.exists()
for item in required_paths:
    assert item in text, item
assert "docs/archive/" not in text
assert "`../frontend/" not in text
assert "> **Plan Status:** `ACTIVE (v1.0 baseline)`" not in text
assert "> **Plan Status:** `COMPLETED / ARCHIVED on 2026-04-15`" in text
assert "当前没有需要继续在本基线计划内执行的 rollout 实现工作" in text
assert "docs/plans/archive/2026-04-15-completed-plans/" in readme
assert "- `2026-03-22-v1.0-multi-source-6node-rollout.md`" in readme
assert "当前顶层 `docs/plans/` 暂无 backend/root active baseline" in readme
PY
```

**Step 2: Run the validation script**

Run:
```bash
python - <<'PY'
from pathlib import Path

archive = Path("docs/plans/archive/2026-04-15-completed-plans/2026-03-22-v1.0-multi-source-6node-rollout.md")
active = Path("docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md")
readme = Path("docs/plans/README.md").read_text()
text = archive.read_text()

required_paths = [
    "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-design.md",
    "docs/plans/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-implementation.md",
    "docs/plans/archive/2026-04-05-completed-plans/2026-04-05-m3-service-boundary-hardening-batch-1.md",
    "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-design.md",
    "docs/plans/archive/2026-04-09-completed-plans/2026-04-06-release-closure-program-implementation.md",
    "`apps/backend/progress.txt`",
    "`apps/backend/src/services/kg_events.py`",
    "`apps/frontend/src/pages/requests/request-monitor-page.tsx`",
]

assert archive.exists()
assert not active.exists()
for item in required_paths:
    assert item in text, item
assert "docs/archive/" not in text
assert "`../frontend/" not in text
assert "> **Plan Status:** `ACTIVE (v1.0 baseline)`" not in text
assert "> **Plan Status:** `COMPLETED / ARCHIVED on 2026-04-15`" in text
assert "当前没有需要继续在本基线计划内执行的 rollout 实现工作" in text
assert "docs/plans/archive/2026-04-15-completed-plans/" in readme
assert "- `2026-03-22-v1.0-multi-source-6node-rollout.md`" in readme
assert "当前顶层 `docs/plans/` 暂无 backend/root active baseline" in readme
PY
```

Expected: PASS.

**Step 3: Fix only the exact mismatch if validation fails**

If any assertion fails, edit only the referenced Markdown file and only the mismatched path/state text. Do not reopen scope into code, test, or release-remediation work.

**Step 4: Re-run the validation script**

Run the exact command from Step 2.

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.
