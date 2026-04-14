# Docs Subdirectory Centralization Implementation Plan

> **归档说明（2026-04-14）**：按计划在隔离 worktree 复核时，Task 1 引用的源路径已不存在，说明结构迁移已经由更早提交完成。因此本实施文档未按 Task 1–4 执行文件移动；本切片最终只补充了 `docs/README.md` 的显式规则，并将该计划归档保留追溯。

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Centralize the remaining project-owned subdirectory `docs/` content into the repository root `docs/` tree and remove the leftover application-level `docs/` directory.

**Architecture:** This change is a small filesystem-level documentation consolidation. Move the two remaining backend archived diagram files from `apps/backend/docs/` into `docs/archive/backend/`, update the root docs index so the rule matches reality, then verify there are no remaining project-owned subdirectory `docs/` directories.

**Tech Stack:** Git, Markdown, shell filesystem operations, repository docs conventions

---

### Task 1: Move the remaining backend archived diagrams into root docs

**Files:**
- Modify: `apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_cd.puml`
- Modify: `apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_sd.puml`
- Create: `docs/archive/backend/2026-03-22-outdated-diagrams/pdf_cd.puml`
- Create: `docs/archive/backend/2026-03-22-outdated-diagrams/pdf_sd.puml`

**Step 1: Verify the source files exist**

Run: `ls -la apps/backend/docs/archive/2026-03-22-outdated-diagrams`
Expected: both `pdf_cd.puml` and `pdf_sd.puml` are present

**Step 2: Verify the target parent directory exists**

Run: `ls -la docs/archive/backend`
Expected: the directory exists; if `2026-03-22-outdated-diagrams` does not yet exist, create only that leaf directory

**Step 3: Move the files**

Run:
```bash
mv apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_cd.puml docs/archive/backend/2026-03-22-outdated-diagrams/pdf_cd.puml
mv apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_sd.puml docs/archive/backend/2026-03-22-outdated-diagrams/pdf_sd.puml
```

**Step 4: Verify the moved files now exist in root docs**

Run: `ls -la docs/archive/backend/2026-03-22-outdated-diagrams`
Expected: both files are present at the new location

**Step 5: Commit**

```bash
git add apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_cd.puml apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_sd.puml docs/archive/backend/2026-03-22-outdated-diagrams/pdf_cd.puml docs/archive/backend/2026-03-22-outdated-diagrams/pdf_sd.puml
git commit -m "docs: centralize remaining backend docs archive"
```

### Task 2: Update the root docs index to state the centralized rule explicitly

**Files:**
- Modify: `docs/README.md:82-113`
- Test: `docs/README.md`

**Step 1: Write the failing expectation as a review checklist**

The document should explicitly say:

```md
- project-owned business docs must live under the root docs/
- app-level docs directories such as apps/*/docs/ are no longer kept
```

**Step 2: Read the current rule section and confirm the statement is missing or incomplete**

Run: `grep -n "apps/\*/docs\|业务文档\|统一归根" docs/README.md`
Expected: no explicit rule covering both points above

**Step 3: Add the minimal wording to the usage/maintenance rules**

Insert wording consistent with existing style, for example:

```md
5. 项目业务文档统一归根目录 `docs/` 管理，不再保留 `apps/*/docs/` 这类应用级文档目录。
```

and optionally reinforce it in the maintenance rules if needed.

**Step 4: Re-read the edited section to verify wording and structure**

Run: `sed -n '82,120p' docs/README.md`
Expected: the new rule appears once, reads cleanly, and does not duplicate existing wording awkwardly

**Step 5: Commit**

```bash
git add docs/README.md
git commit -m "docs: clarify root docs centralization rule"
```

### Task 3: Remove the now-empty backend docs directory

**Files:**
- Modify: `apps/backend/docs/`

**Step 1: Verify the directory is empty except for removable empty parents**

Run: `ls -Rla apps/backend/docs`
Expected: no remaining files under the directory tree

**Step 2: Remove the empty directory tree**

Run: `rmdir apps/backend/docs/archive/2026-03-22-outdated-diagrams apps/backend/docs/archive apps/backend/docs`
Expected: command succeeds without force flags

**Step 3: Verify the directory no longer exists**

Run: `ls -la apps/backend`
Expected: `docs` no longer appears in the listing

**Step 4: Commit**

```bash
git add -u apps/backend/docs
git commit -m "docs: remove empty backend docs directory"
```

### Task 4: Verify there are no remaining project-owned subdirectory docs directories

**Files:**
- Test: repository tree

**Step 1: Run a scoped check for project-owned docs directories**

Run:
```bash
python - <<'PY'
import os
for root, dirs, files in os.walk('.'):
    parts = root.split(os.sep)
    if 'node_modules' in parts or '.git' in parts or '.worktrees' in parts:
        dirs[:] = []
        continue
    if os.path.basename(root) == 'docs' and root not in ('./docs', 'docs'):
        print(root)
PY
```
Expected: no output

**Step 2: Verify git diff matches intended scope**

Run: `git diff --name-status`
Expected: only the two moved `.puml` files, the `docs/README.md` update, and removal of the old backend docs paths

**Step 3: Run a final tree check on the target archive location**

Run: `ls -Rla docs/archive/backend/2026-03-22-outdated-diagrams`
Expected: both `.puml` files are present

**Step 4: Commit**

```bash
git add docs/README.md docs/archive/backend/2026-03-22-outdated-diagrams apps/backend/docs
git commit -m "docs: finish subdirectory docs centralization"
```

### Task 5: Update planning index after completion

**Files:**
- Modify: `docs/plans/README.md`
- Modify: `docs/plans/2026-04-13-docs-subdirectory-centralization-design.md`
- Create: `docs/plans/2026-04-13-docs-subdirectory-centralization-implementation.md`
- Move to archive: `docs/plans/archive/2026-04-13-completed-plans/`

**Step 1: Confirm the implementation is complete**

Run: `git diff --name-status`
Expected: only the intended docs-centralization changes remain and all verification steps above pass

**Step 2: Archive the design and implementation docs if this work is considered complete in the same slice**

Target archive directory:
```text
docs/plans/archive/2026-04-13-completed-plans/
```

**Step 3: Update `docs/plans/README.md` to mention this completed work**

Add a line in the `2026-04-13` completed section for:
- `2026-04-13-docs-subdirectory-centralization-design.md`
- `2026-04-13-docs-subdirectory-centralization-implementation.md`

**Step 4: Re-read the updated plan index**

Run: `sed -n '50,90p' docs/plans/README.md`
Expected: the new completed entries appear in the right section without disturbing active-plan guidance

**Step 5: Commit**

```bash
git add docs/plans/README.md docs/plans/2026-04-13-docs-subdirectory-centralization-design.md docs/plans/2026-04-13-docs-subdirectory-centralization-implementation.md docs/plans/archive/2026-04-13-completed-plans
git commit -m "docs(plans): record docs subdirectory centralization"
```
