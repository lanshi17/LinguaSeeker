# Completed Plan Batch Archive Design

Date: 2026-04-16

## 1. Goal

Run a strict batch-archive pass over the entire `docs/plans/` tree, moving only those non-archive plan documents whose own body clearly marks them as completed or archived.

The archive result should preserve the repository’s current plan taxonomy:
- active plans stay under `docs/plans/`
- completed historical plans move under `docs/plans/archive/`
- archive bookkeeping stays visible through the root plan index

## 2. Chosen Rules

This design follows the user-approved rules below.

1. Scan the whole `docs/plans/` tree.
2. Determine completion from the document’s own content, not file name, git history, or sibling documents.
3. Use explicit completion/archive wording only, such as:
   - `completed`
   - `archived`
   - `EXECUTED`
   - `已完成`
   - `已归档`
4. Move all eligible documents into one new slice directory for this run:
   - `docs/plans/archive/2026-04-16-completed-plans/`
5. Automatically update affected indexes, primarily `docs/plans/README.md`.

## 3. Scope Boundaries

### Included

- Any Markdown file under `docs/plans/` that is not already inside `docs/plans/archive/`
- Root-level plan files such as `docs/plans/*.md`
- Nested plan files such as `docs/plans/frontend/*.md`

### Excluded

- Files already under `docs/plans/archive/`
- Index files such as `docs/plans/README.md` and `docs/plans/archive/README.md`
- Documents that merely mention archived/completed work elsewhere, but do not mark themselves as completed
- Documents with partial-progress language such as “Phase 1 Complete” when the same file still lists pending work
- Documents whose status means “planning finished” rather than “implementation complete”

## 4. Repository Findings From Design-Time Review

Applying the strict rules above to the current active tree yields no unambiguous archive candidates.

### Excluded examples

1. `docs/plans/2026-04-15-rollout-plan-archive-implementation.md`
   - The file discusses an archive operation and references archived material.
   - It does not clearly mark itself as completed/archived in its own status block.
   - Under the approved rule, it must stay out of the batch archive set.

2. `docs/plans/2026-04-15-document-normalization-translation-api-alignment.md`
   - This is an active implementation plan with no completed/archived self-status.
   - It remains in the active set.

3. `docs/plans/frontend/state-management-refactoring.md`
   - Its header says `Planning Complete, Ready for Implementation`.
   - That means planning is done, not that the plan’s execution is complete.
   - It must not be archived by this strict pass.

4. `docs/plans/frontend/state-management-migration-guide.md`
   - Its header says `Phase 1 Complete`, but the document still lists pending page migrations.
   - It is therefore partially complete, not fully completed.
   - Under the approved rule, it must not be archived.

5. Other active frontend design/implementation files
   - Current active files reviewed under `docs/plans/frontend/` do not expose a clear completed/archived self-status line.
   - They are excluded unless a future revision adds explicit completion language.

## 5. Archive Workflow

The archive pass should execute in this order.

### Step 1: Re-scan and classify

Re-scan all non-archive Markdown files under `docs/plans/` and classify them into:
- eligible for archive
- excluded because they are indexes
- excluded because they lack explicit completed/archive self-status
- excluded because they are only partially complete

### Step 2: Stop early if no eligible files exist

If the eligible set is empty:
- do not create `docs/plans/archive/2026-04-16-completed-plans/`
- do not modify `docs/plans/README.md`
- report the batch archive pass as a verified no-op under the strict rules

This prevents empty archive slices and keeps the repository unchanged when the rules do not match any files.

### Step 3: Move eligible files if any appear during re-scan

If the re-scan finds eligible files:
- create `docs/plans/archive/2026-04-16-completed-plans/`
- move each eligible file into that directory without renaming the file itself
- preserve the original filename exactly

### Step 4: Update the root plan index

Only if at least one file moves:
- remove those files from any active-plan listing or active narrative in `docs/plans/README.md`
- add a new archive block under `## 已完成并归档的计划`
- add `docs/plans/archive/2026-04-16-completed-plans/` under `## 历史归档目录`

### Step 5: Update other indexes only if they exist and are affected

During design-time review, no additional README files were found under active `docs/plans/` subdirectories.

Therefore, the expected index update surface is currently limited to:
- `docs/plans/README.md`

## 6. Verification

The implementation should verify the outcome with repository-local checks.

### If the result is a no-op

Verification must prove:
1. No non-archive plan file matched the strict completed/archive status criteria.
2. `docs/plans/archive/2026-04-16-completed-plans/` was not created.
3. `docs/plans/README.md` remained unchanged.

### If files are moved

Verification must prove:
1. Every moved file exists under `docs/plans/archive/2026-04-16-completed-plans/`.
2. No moved file remains in its previous active location.
3. `docs/plans/README.md` contains the new `2026-04-16` archive block.
4. `docs/plans/README.md` lists the new archive directory under historical archive directories.
5. Active-plan sections no longer advertise the moved files as active.

## 7. Recommendation

Implement the strict rules exactly as approved, even though the current expected result is a no-op.

This keeps the archive process objective and reversible. If the user later wants a broader cleanup, that should be a separate change with broader status semantics, for example:
- treating `Planning Complete` as archiveable
- treating partially completed migration guides as archiveable historical artifacts
- allowing manual override for known-finished plans that lack explicit status markers
