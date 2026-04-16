# Completed Plan Batch Archive Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the approved strict batch-archive process over the active `docs/plans/` tree, archive only documents that self-declare completed/archived status, and leave the repository unchanged if no eligible documents exist.

**Architecture:** This is a docs-only verification-and-move flow. First replace the overbroad keyword scan with a strict self-status classifier that excludes indexes, partial-progress docs, and “planning complete” docs; then use that classifier result to either (a) move eligible files into `docs/plans/archive/2026-04-16-completed-plans/` and update `docs/plans/README.md`, or (b) verify a no-op if the eligible set is empty. On the current `yangzs-agents` branch, the expected result is branch (b): zero eligible files, no new archive directory, and no README edits.

**Tech Stack:** Markdown docs, Python stdlib (`pathlib`, `re`, `json`, `shutil`), git status/diff commands.

---

## Execution notes

1. Run execution in an isolated workspace via `@using-git-worktrees` before any file move or README edit.
2. If the strict classifier returns any unexpected eligible file, stop and use `@systematic-debugging` before touching `docs/plans/README.md`.
3. Before claiming completion, run the final verification commands in Task 4 with `@verification-before-completion`.
4. This repository often runs under “do not commit unless explicitly requested”; only run commit steps if the user explicitly asks for a commit in the execution session.
5. Expected current-branch outcome: Task 1 passes with `eligible=[]`, so Tasks 2 and 3 are skipped and Task 4 verifies a no-op.

---

### Task 1: Replace the overbroad candidate scan with the strict approved classifier

**Files:**
- Read: `docs/plans/README.md`
- Read: `docs/plans/2026-04-15-rollout-plan-archive-implementation.md`
- Read: `docs/plans/2026-04-15-document-normalization-translation-api-alignment.md`
- Read: `docs/plans/frontend/2026-03-06-state-management-implementation.md`
- Read: `docs/plans/frontend/2026-03-07-agent-interactive-platform-refactor.md`
- Read: `docs/plans/frontend/2026-03-15-frontend-agent-chat-design.md`
- Read: `docs/plans/frontend/2026-03-15-frontend-agent-chat-implementation-plan.md`
- Read: `docs/plans/frontend/2026-03-15-frontend-design.md`
- Read: `docs/plans/frontend/2026-03-15-frontend-mvp-implementation-plan.md`
- Read: `docs/plans/frontend/2026-03-16-agent-mode-choice-design.md`
- Read: `docs/plans/frontend/2026-03-16-agent-mode-choice-implementation-plan.md`
- Read: `docs/plans/frontend/state-management-migration-guide.md`
- Read: `docs/plans/frontend/state-management-refactoring.md`
- Test: `docs/plans/`

**Step 1: Write the failing verification script**

Use this intentionally overbroad keyword scan first. It should fail because it produces false positives.

```python
from pathlib import Path

ROOT = Path("docs/plans")
TERMS = ("completed", "archived", "executed", "已完成", "已归档")

naive = []
for path in sorted(ROOT.rglob("*.md")):
    if "archive" in path.parts:
        continue
    text = path.read_text()
    lowered = text.lower()
    if any(term in lowered for term in TERMS[:3]) or any(term in text for term in TERMS[3:]):
        naive.append(str(path))

assert "docs/plans/README.md" not in naive
assert "docs/plans/2026-04-15-rollout-plan-archive-implementation.md" not in naive
assert "docs/plans/frontend/state-management-migration-guide.md" not in naive
assert "docs/plans/frontend/state-management-refactoring.md" not in naive
```

**Step 2: Run the script to verify it fails**

Run:
```bash
python - <<'PY'
from pathlib import Path

ROOT = Path("docs/plans")
TERMS = ("completed", "archived", "executed", "已完成", "已归档")

naive = []
for path in sorted(ROOT.rglob("*.md")):
    if "archive" in path.parts:
        continue
    text = path.read_text()
    lowered = text.lower()
    if any(term in lowered for term in TERMS[:3]) or any(term in text for term in TERMS[3:]):
        naive.append(str(path))

assert "docs/plans/README.md" not in naive
assert "docs/plans/2026-04-15-rollout-plan-archive-implementation.md" not in naive
assert "docs/plans/frontend/state-management-migration-guide.md" not in naive
assert "docs/plans/frontend/state-management-refactoring.md" not in naive
PY
```

Expected: FAIL because the naive scan incorrectly includes at least `docs/plans/README.md`, `docs/plans/2026-04-15-rollout-plan-archive-implementation.md`, `docs/plans/frontend/state-management-migration-guide.md`, and `docs/plans/frontend/state-management-refactoring.md`.

**Step 3: Write the minimal implementation**

Replace the naive scan with this strict self-status classifier and persist the result for later tasks.

```python
from pathlib import Path
import json
import re

ROOT = Path("docs/plans")
OUTPUT = Path("/tmp/completed_plan_archive_candidates.json")

STRICT_STATUS_PATTERNS = [
    re.compile(r"^>\s*\*\*Status:\*\*.*\b(COMPLETED|ARCHIVED|EXECUTED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\*\*Status\*\*:\s*.*\b(COMPLETED|ARCHIVED|EXECUTED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Status:\s*.*\b(COMPLETED|ARCHIVED|EXECUTED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^>\s*\*\*Plan Status:\*\*.*\b(COMPLETED|ARCHIVED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^>\s*\*\*状态:\*\*.*(已完成|已归档)", re.MULTILINE),
    re.compile(r"^\*\*状态\*\*:\s*(已完成|已归档)", re.MULTILINE),
    re.compile(r"^状态:\s*(已完成|已归档)", re.MULTILINE),
]

DISQUALIFY_PATTERNS = [
    re.compile(r"^>\s*\*\*Status:\*\*.*\b(APPROVED|READY FOR IMPLEMENTATION|APPROVED FOR EXECUTION|APPROVED FOR IMPLEMENTATION)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\*\*Status\*\*:\s*.*\b(Planning Complete|Phase\s+\d+\s+Complete)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Status:\s*.*\b(PENDING|IN_PROGRESS|ACTIVE)\b", re.IGNORECASE | re.MULTILINE),
]

FALSE_POSITIVE_CONTROLS = {
    "docs/plans/2026-04-15-rollout-plan-archive-implementation.md",
    "docs/plans/2026-04-15-document-normalization-translation-api-alignment.md",
    "docs/plans/frontend/state-management-migration-guide.md",
    "docs/plans/frontend/state-management-refactoring.md",
}

active_docs = [
    path
    for path in sorted(ROOT.rglob("*.md"))
    if "archive" not in path.parts and path.name != "README.md"
]


def is_eligible(text: str) -> bool:
    return any(pattern.search(text) for pattern in STRICT_STATUS_PATTERNS) and not any(
        pattern.search(text) for pattern in DISQUALIFY_PATTERNS
    )


eligible = []
for path in active_docs:
    text = path.read_text()
    if is_eligible(text):
        eligible.append(str(path))

assert eligible == []
assert FALSE_POSITIVE_CONTROLS.isdisjoint(eligible)

payload = {
    "eligible": eligible,
    "scanned": [str(path) for path in active_docs],
    "false_positive_controls": sorted(FALSE_POSITIVE_CONTROLS),
}
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
print(OUTPUT.read_text(), end="")
```

**Step 4: Run the classifier to verify it passes**

Run:
```bash
python - <<'PY'
from pathlib import Path
import json
import re

ROOT = Path("docs/plans")
OUTPUT = Path("/tmp/completed_plan_archive_candidates.json")

STRICT_STATUS_PATTERNS = [
    re.compile(r"^>\s*\*\*Status:\*\*.*\b(COMPLETED|ARCHIVED|EXECUTED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\*\*Status\*\*:\s*.*\b(COMPLETED|ARCHIVED|EXECUTED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Status:\s*.*\b(COMPLETED|ARCHIVED|EXECUTED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^>\s*\*\*Plan Status:\*\*.*\b(COMPLETED|ARCHIVED)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^>\s*\*\*状态:\*\*.*(已完成|已归档)", re.MULTILINE),
    re.compile(r"^\*\*状态\*\*:\s*(已完成|已归档)", re.MULTILINE),
    re.compile(r"^状态:\s*(已完成|已归档)", re.MULTILINE),
]

DISQUALIFY_PATTERNS = [
    re.compile(r"^>\s*\*\*Status:\*\*.*\b(APPROVED|READY FOR IMPLEMENTATION|APPROVED FOR EXECUTION|APPROVED FOR IMPLEMENTATION)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\*\*Status\*\*:\s*.*\b(Planning Complete|Phase\s+\d+\s+Complete)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Status:\s*.*\b(PENDING|IN_PROGRESS|ACTIVE)\b", re.IGNORECASE | re.MULTILINE),
]

FALSE_POSITIVE_CONTROLS = {
    "docs/plans/2026-04-15-rollout-plan-archive-implementation.md",
    "docs/plans/2026-04-15-document-normalization-translation-api-alignment.md",
    "docs/plans/frontend/state-management-migration-guide.md",
    "docs/plans/frontend/state-management-refactoring.md",
}

active_docs = [
    path
    for path in sorted(ROOT.rglob("*.md"))
    if "archive" not in path.parts and path.name != "README.md"
]


def is_eligible(text: str) -> bool:
    return any(pattern.search(text) for pattern in STRICT_STATUS_PATTERNS) and not any(
        pattern.search(text) for pattern in DISQUALIFY_PATTERNS
    )


eligible = []
for path in active_docs:
    text = path.read_text()
    if is_eligible(text):
        eligible.append(str(path))

assert eligible == []
assert FALSE_POSITIVE_CONTROLS.isdisjoint(eligible)

payload = {
    "eligible": eligible,
    "scanned": [str(path) for path in active_docs],
    "false_positive_controls": sorted(FALSE_POSITIVE_CONTROLS),
}
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
print(OUTPUT.read_text(), end="")
PY
```

Expected: PASS with JSON showing `"eligible": []`.

**Step 5: Commit**

Do not commit in this task. This task should only create `/tmp/completed_plan_archive_candidates.json`, not modify tracked repository files.

---

### Task 2: Conditionally move eligible plans into the 2026-04-16 archive slice

**Files:**
- Create: `docs/plans/archive/2026-04-16-completed-plans/` (only if Task 1 returns non-empty `eligible`)
- Move: each file listed in `/tmp/completed_plan_archive_candidates.json` → `docs/plans/archive/2026-04-16-completed-plans/<same filename>`
- Test: `docs/plans/archive/2026-04-16-completed-plans/`

**Run this task only if Task 1 prints a non-empty `eligible` list. On the current branch, skip this task.**

**Step 1: Write the failing pre-move verification script**

```python
from pathlib import Path
import json

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
destination = Path("docs/plans/archive/2026-04-16-completed-plans")

assert eligible, "No eligible files; skip Task 2."
for source in eligible:
    source_path = Path(source)
    assert source_path.exists()
    assert not (destination / source_path.name).exists()
```

**Step 2: Run the script to verify it fails (or confirms skip)**

Run:
```bash
python - <<'PY'
from pathlib import Path
import json

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
destination = Path("docs/plans/archive/2026-04-16-completed-plans")

assert eligible, "No eligible files; skip Task 2."
for source in eligible:
    source_path = Path(source)
    assert source_path.exists()
    assert not (destination / source_path.name).exists()
PY
```

Expected:
- Current branch: FAIL with `No eligible files; skip Task 2.`
- Future branch with candidates: PASS and continue to Step 3.

**Step 3: Write the minimal implementation**

Only if `eligible` is non-empty, run this move script:

```bash
python - <<'PY'
from pathlib import Path
import json
import shutil

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
destination = Path("docs/plans/archive/2026-04-16-completed-plans")

if not eligible:
    raise SystemExit("No eligible files; nothing to move.")

destination.mkdir(parents=True, exist_ok=True)
for source in eligible:
    source_path = Path(source)
    target_path = destination / source_path.name
    if target_path.exists():
        raise SystemExit(f"Destination already exists: {target_path}")
    shutil.move(str(source_path), str(target_path))
    print(f"moved {source_path} -> {target_path}")
PY
```

**Step 4: Run the same verification script to verify it passes**

Run the exact command from Step 2.

Expected on a future branch with candidates: PASS.

**Step 5: Commit**

```bash
git add docs/plans/archive/2026-04-16-completed-plans
git commit -m "docs(plans): archive completed plan slice"
```

Only run this commit if the user explicitly asks for one and Step 3 actually moved tracked files.

---

### Task 3: Conditionally update the root plan index after file moves

**Files:**
- Modify: `docs/plans/README.md`
- Read: `docs/plans/archive/README.md`
- Test: `docs/plans/README.md`

**Run this task only if Task 2 moved at least one file. On the current branch, skip this task.**

**Step 1: Write the failing README verification script**

```python
from pathlib import Path
import json

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
readme = Path("docs/plans/README.md").read_text()
pre_archive, _, _ = readme.partition("## 已完成并归档的计划")

assert eligible, "No moved files; skip Task 3."
assert "已于 `2026-04-16` 归档到 `docs/plans/archive/2026-04-16-completed-plans/`：" in readme
assert "- `docs/plans/archive/2026-04-16-completed-plans/`" in readme
for source in eligible:
    filename = Path(source).name
    assert f"- `{filename}`" in readme
    assert filename not in pre_archive
```

**Step 2: Run the script to verify it fails (or confirms skip)**

Run:
```bash
python - <<'PY'
from pathlib import Path
import json

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
readme = Path("docs/plans/README.md").read_text()
pre_archive, _, _ = readme.partition("## 已完成并归档的计划")

assert eligible, "No moved files; skip Task 3."
assert "已于 `2026-04-16` 归档到 `docs/plans/archive/2026-04-16-completed-plans/`：" in readme
assert "- `docs/plans/archive/2026-04-16-completed-plans/`" in readme
for source in eligible:
    filename = Path(source).name
    assert f"- `{filename}`" in readme
    assert filename not in pre_archive
PY
```

Expected:
- Current branch: FAIL with `No moved files; skip Task 3.`
- Future branch with moved files: FAIL because the README has not been updated yet.

**Step 3: Write the minimal implementation**

Only if files were moved in Task 2, update `docs/plans/README.md` with this script:

```bash
python - <<'PY'
from pathlib import Path
import json

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
readme_path = Path("docs/plans/README.md")
text = readme_path.read_text()

if not eligible:
    raise SystemExit("No moved files; nothing to update.")

filenames = [Path(source).name for source in eligible]
lines = text.splitlines()
filtered_lines = [
    line for line in lines
    if not any(filename in line for filename in filenames)
]
text = "\n".join(filtered_lines)

archive_block = (
    "已于 `2026-04-16` 归档到 `docs/plans/archive/2026-04-16-completed-plans/`：\n\n"
    + "\n".join(f"- `{filename}`" for filename in filenames)
    + "\n\n"
)

marker = "## 已完成并归档的计划\n"
if archive_block not in text:
    text = text.replace(marker, marker + "\n" + archive_block, 1)

history_line = "- `docs/plans/archive/2026-04-16-completed-plans/`"
if history_line not in text:
    history_marker = "## 历史归档目录\n"
    text = text.replace(history_marker, history_marker + "\n" + history_line + "\n", 1)

readme_path.write_text(text.rstrip() + "\n")
PY
```

**Step 4: Run the same verification script to verify it passes**

Run the exact command from Step 2.

Expected on a future branch with moved files: PASS.

**Step 5: Commit**

```bash
git add docs/plans/README.md docs/plans/archive/2026-04-16-completed-plans
git commit -m "docs(plans): update completed archive index"
```

Only run this commit if the user explicitly asks for one and Task 3 modified tracked files.

---

### Task 4: Run final archive verification for both outcomes

**Files:**
- Test: `/tmp/completed_plan_archive_candidates.json`
- Test: `docs/plans/README.md`
- Test: `docs/plans/archive/2026-04-16-completed-plans/`

**Step 1: Write the final verification script**

```python
from pathlib import Path
import json

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
archive_dir = Path("docs/plans/archive/2026-04-16-completed-plans")
readme = Path("docs/plans/README.md").read_text()

if eligible:
    assert archive_dir.exists()
    pre_archive, _, _ = readme.partition("## 已完成并归档的计划")
    assert "已于 `2026-04-16` 归档到 `docs/plans/archive/2026-04-16-completed-plans/`：" in readme
    assert "- `docs/plans/archive/2026-04-16-completed-plans/`" in readme
    for source in eligible:
        filename = Path(source).name
        assert (archive_dir / filename).exists()
        assert not Path(source).exists()
        assert f"- `{filename}`" in readme
        assert filename not in pre_archive
else:
    assert not archive_dir.exists()
```

**Step 2: Run the script to verify the final state**

Run:
```bash
python - <<'PY'
from pathlib import Path
import json

payload = json.loads(Path("/tmp/completed_plan_archive_candidates.json").read_text())
eligible = payload["eligible"]
archive_dir = Path("docs/plans/archive/2026-04-16-completed-plans")
readme = Path("docs/plans/README.md").read_text()

if eligible:
    assert archive_dir.exists()
    pre_archive, _, _ = readme.partition("## 已完成并归档的计划")
    assert "已于 `2026-04-16` 归档到 `docs/plans/archive/2026-04-16-completed-plans/`：" in readme
    assert "- `docs/plans/archive/2026-04-16-completed-plans/`" in readme
    for source in eligible:
        filename = Path(source).name
        assert (archive_dir / filename).exists()
        assert not Path(source).exists()
        assert f"- `{filename}`" in readme
        assert filename not in pre_archive
else:
    assert not archive_dir.exists()
PY
```

Expected on the current branch: PASS because `eligible` is empty and `docs/plans/archive/2026-04-16-completed-plans/` was never created.

**Step 3: Verify the git state matches the outcome**

Run:
```bash
if python - <<'PY'
from pathlib import Path
import json
payload = json.loads(Path('/tmp/completed_plan_archive_candidates.json').read_text())
raise SystemExit(0 if payload['eligible'] else 1)
PY
then
  git status --short -- docs/plans/README.md docs/plans/archive/2026-04-16-completed-plans
else
  git diff --exit-code -- docs/plans/README.md docs/plans/archive/2026-04-16-completed-plans
fi
```

Expected:
- Current branch: PASS via `git diff --exit-code ...` because no tracked files changed.
- Future branch with moved files: PASS via `git status --short ...` showing only the intended archive/README modifications.

**Step 4: Commit**

Do not create a new commit in this task unless the user explicitly asks for one and earlier tasks actually changed tracked files.
