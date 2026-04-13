# Docs Root Reorganization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize the repository-level `docs/` directory so its root keeps only `README.md` plus the six canonical core documents, with all other documentation moved into purpose-based subdirectories.

**Architecture:** Use `apps/backend/docs/` as the source of truth for the six root-level canonical documents, then migrate all remaining backend and frontend docs into a shared repository-level taxonomy: `plans/`, `guides/`, `reference/`, `archive/`, `data/`, and `templates/`. Keep changes structural rather than editorial: prefer moves, path updates, and index fixes over rewriting document bodies.

**Tech Stack:** Git worktree-aware repository reorganization, Markdown docs, JSON assets, existing repo docs under `docs/`, `apps/backend/docs/`, and `apps/frontend/docs/`.

---

### Task 1: Inventory and classify all documents

**Files:**
- Read: `docs/README.md`
- Read: `docs/plans/2026-04-11-docs-root-reorganization-design.md`
- Read: `apps/backend/docs/**/*`
- Read: `apps/frontend/docs/**/*`
- Modify: `docs/plans/2026-04-11-docs-root-reorganization-implementation.md`

**Step 1: Record the canonical root files**

List the six canonical files that must end up in `docs/` root:
- `PRD.md`
- `APP_FLOW.md`
- `TECH_STACK.md`
- `FRONTEND_GUIDELINES.md`
- `BACKEND_STRUCTURE.md`
- `IMPLEMENTATION_PLAN.md`

**Step 2: Confirm canonical source files**

Treat these backend files as the source of truth:
- `apps/backend/docs/PRD.md`
- `apps/backend/docs/APP_FLOW.md`
- `apps/backend/docs/TECH_STACK.md`
- `apps/backend/docs/FRONTEND_GUIDELINES.md`
- `apps/backend/docs/BACKEND_STRUCTURE.md`
- `apps/backend/docs/IMPLEMENTATION_PLAN.md`

**Step 3: Build a migration inventory**

Create a checklist in the implementation plan grouping remaining docs into:
- `plans/`
- `guides/`
- `reference/`
- `archive/`
- `data/`
- `templates/`

**Step 4: Verify the inventory is complete**

Run: `git ls-files "docs" "apps/backend/docs" "apps/frontend/docs"`
Expected: every tracked docs file is accounted for in one destination bucket.

**Step 5: Commit**

Do not commit yet. This task is planning/inventory only.

### Task 2: Promote canonical backend documents to root docs/

**Files:**
- Create or overwrite: `docs/PRD.md`
- Create or overwrite: `docs/APP_FLOW.md`
- Create or overwrite: `docs/TECH_STACK.md`
- Create or overwrite: `docs/FRONTEND_GUIDELINES.md`
- Create or overwrite: `docs/BACKEND_STRUCTURE.md`
- Create or overwrite: `docs/IMPLEMENTATION_PLAN.md`
- Source: `apps/backend/docs/PRD.md`
- Source: `apps/backend/docs/APP_FLOW.md`
- Source: `apps/backend/docs/TECH_STACK.md`
- Source: `apps/backend/docs/FRONTEND_GUIDELINES.md`
- Source: `apps/backend/docs/BACKEND_STRUCTURE.md`
- Source: `apps/backend/docs/IMPLEMENTATION_PLAN.md`

**Step 1: Write the canonical root file set**

Copy each backend canonical file to its root `docs/` destination without rewriting content.

**Step 2: Verify root file presence**

Run: `ls docs`
Expected: root contains `README.md` plus the six canonical docs and subdirectories only.

**Step 3: Verify file content source**

Run exact diffs for each promoted file against backend source, for example:
`diff -u apps/backend/docs/PRD.md docs/PRD.md`
Expected: no diff for each canonical file.

**Step 4: Commit**

```bash
git add docs/PRD.md docs/APP_FLOW.md docs/TECH_STACK.md docs/FRONTEND_GUIDELINES.md docs/BACKEND_STRUCTURE.md docs/IMPLEMENTATION_PLAN.md
git commit -m "docs: promote canonical root documents"
```

### Task 3: Rehome backend non-core docs into purpose directories

**Files:**
- Move: `apps/backend/docs/plans/**/*` → `docs/plans/`
- Move: `apps/backend/docs/archive/**/*` → `docs/archive/` or `docs/plans/archive/` as appropriate
- Move: `apps/backend/docs/CHANGE_CONTROL.md` → `docs/reference/CHANGE_CONTROL.md`
- Move: `apps/backend/docs/CONSTANTS.md` → `docs/reference/CONSTANTS.md`
- Move: `apps/backend/docs/EVALUATION_FRAMEWORK.md` → `docs/reference/EVALUATION_FRAMEWORK.md`
- Move: `apps/backend/docs/PS3_BS3_VALIDATION_REPORT.md` → `docs/reference/PS3_BS3_VALIDATION_REPORT.md`
- Move: `apps/backend/docs/release/v1.0-release-report.md` → `docs/reference/v1.0-release-report.md`
- Move: `apps/backend/docs/acceptance/v1.0-100-paper-manifest.json` → `docs/data/v1.0-100-paper-manifest.json`
- Move: `apps/backend/docs/templates/release_report.md.template` → `docs/templates/release_report.md.template`
- Consider handling: `apps/backend/docs/README.md`

**Step 1: Move plan and archive docs**

Preserve existing plan/archive relationships. Do not flatten archived plans into root.

**Step 2: Move reference docs**

Move each backend non-core Markdown doc into its purpose-based destination.

**Step 3: Move non-Markdown support files**

Move JSON manifests into `docs/data/` and templates into `docs/templates/`.

**Step 4: Decide backend README handling**

If `apps/backend/docs/README.md` remains useful as backend-specific navigation, move it to `docs/reference/backend/README.md` rather than keeping a second root README.

**Step 5: Verify moved files**

Run: `git diff --name-status`
Expected: moves are readable as renames/additions into the new root `docs/` taxonomy.

**Step 6: Commit**

```bash
git add docs apps/backend/docs
git commit -m "docs: reorganize backend documentation into root taxonomy"
```

### Task 4: Rehome frontend docs into shared purpose directories

**Files:**
- Move frontend plans into: `docs/plans/frontend/`
- Move frontend guide docs into: `docs/guides/frontend/`
- Move frontend long-lived references into: `docs/reference/frontend/`
- Move frontend one-off reports/fixes/summaries into: `docs/archive/frontend/`
- Source: `apps/frontend/docs/**/*`

**Step 1: Classify frontend docs by purpose**

Use these rules:
- `plans/*.md` → `docs/plans/frontend/`
- Quickstart/troubleshooting/how-to docs → `docs/guides/frontend/`
- Stable design/reference docs → `docs/reference/frontend/`
- `*_SUMMARY.md`, `*_FIX*.md`, `FINAL_*`, `IMPLEMENTATION_SUMMARY.md`, refactor summaries, lessons learned → `docs/archive/frontend/`

**Step 2: Move files without renaming unnecessarily**

Preserve filenames where possible; only change directories.

**Step 3: Verify nothing remains directly under apps/frontend/docs except maybe empty dirs pending cleanup**

Run: `git ls-files apps/frontend/docs`
Expected: either empty, or only intentionally retained files if any were explicitly deferred.

**Step 4: Commit**

```bash
git add docs apps/frontend/docs
git commit -m "docs: rehome frontend documentation into shared taxonomy"
```

### Task 5: Rewrite docs/README.md as the canonical index

**Files:**
- Modify: `docs/README.md`
- Reference: `docs/PRD.md`
- Reference: `docs/APP_FLOW.md`
- Reference: `docs/TECH_STACK.md`
- Reference: `docs/FRONTEND_GUIDELINES.md`
- Reference: `docs/BACKEND_STRUCTURE.md`
- Reference: `docs/IMPLEMENTATION_PLAN.md`
- Reference: `docs/plans/`
- Reference: `docs/guides/`
- Reference: `docs/reference/`
- Reference: `docs/archive/`
- Reference: `docs/data/`
- Reference: `docs/templates/`

**Step 1: Replace the old directory tree**

Write a new `docs/README.md` that reflects the new root shape and subdirectory taxonomy.

**Step 2: Add canonical root section**

List the six canonical root docs and what each one is for.

**Step 3: Add subdirectory usage section**

Explain exactly what belongs in `plans/`, `guides/`, `reference/`, `archive/`, `data/`, and `templates/`.

**Step 4: Remove stale references**

Delete references that still assume docs are rooted under `apps/backend/docs/`, `apps/frontend/docs/`, or the previous flatter layout.

**Step 5: Verify README consistency**

Run: `grep -n "apps/backend/docs\|apps/frontend/docs" docs/README.md`
Expected: no stale path references unless explicitly intentional.

**Step 6: Commit**

```bash
git add docs/README.md
git commit -m "docs: rewrite root documentation index"
```

### Task 6: Update cross-document links and references

**Files:**
- Modify any tracked Markdown files that still reference old paths in:
  - `docs/**/*.md`
  - `apps/backend/AGENTS.md`
  - `apps/frontend/AGENTS.md`
  - any remaining docs that point at moved files

**Step 1: Write the failing search checks**

Run searches for stale paths before editing:

```bash
rg -n "apps/backend/docs/|apps/frontend/docs/|docs/README.md|../docs/PRD.md|../docs/IMPLEMENTATION_PLAN.md" .
```

Expected: matches identify stale references that need updating.

**Step 2: Update links minimally**

Only change path references; do not rewrite prose unless needed for clarity.

**Step 3: Re-run search to verify cleanup**

Run the same search again.
Expected: only intentional references remain.

**Step 4: Spot-check critical entry points**

At minimum verify:
- `apps/backend/AGENTS.md`
- `apps/frontend/AGENTS.md`
- `docs/plans/README.md`
- any moved frontend plan docs with relative links

**Step 5: Commit**

```bash
git add docs apps/backend/AGENTS.md apps/frontend/AGENTS.md
git commit -m "docs: update links after documentation reorganization"
```

### Task 7: Verify final structure and clean removal of legacy layouts

**Files:**
- Verify: `docs/**/*`
- Verify: `apps/backend/docs/**/*`
- Verify: `apps/frontend/docs/**/*`

**Step 1: Verify root layout**

Run: `ls docs`
Expected: root contains only `README.md`, the six canonical docs, and subdirectories.

**Step 2: Verify legacy doc trees are cleared or intentionally minimized**

Run:
```bash
git ls-files apps/backend/docs apps/frontend/docs
```
Expected: no stale duplicate trees remain unless explicitly preserved by design.

**Step 3: Verify git movement summary**

Run:
```bash
git diff --name-status origin/yangzs-agents...HEAD
```
Expected: structure changes are understandable and align with the design.

**Step 4: Final documentation verification**

Run:
```bash
rg -n "apps/backend/docs/|apps/frontend/docs/" docs apps/backend/AGENTS.md apps/frontend/AGENTS.md
```
Expected: no stale internal references to the old doc layout, unless explicitly intentional.

**Step 5: Final commit**

```bash
git add docs apps/backend apps/frontend
git commit -m "docs: normalize repository documentation structure"
```
