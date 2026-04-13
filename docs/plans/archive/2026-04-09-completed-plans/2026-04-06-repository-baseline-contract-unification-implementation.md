# Repository Baseline Contract Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Synchronize repository-level execution guidance and residual wording to the frozen `v1.0` multi-source acquisition + 6-node workflow contract without falsifying historical progress records.

**Architecture:** Treat the frozen `docs/` set as the only source of truth for the active baseline. Update `AGENTS.md` to match that baseline, mark older `progress.txt` entries as historical where they conflict, and relabel legacy direct-task comments in `src/services/task_manager.py` so contributors can distinguish active workflow guidance from implementation provenance.

**Tech Stack:** Markdown, Python comments, `rg`, `uv`, git tracking files.

**Git Note:** This repository often runs under "do not commit unless explicitly requested." Suggested commit steps are included for completeness but should be skipped unless the user explicitly asks for a commit.

---

### Task 1: Align the root execution contract to the frozen baseline

**Files:**
- Modify: `AGENTS.md`
- Create: `docs/plans/2026-04-06-repository-baseline-contract-unification-design.md`
- Create: `docs/plans/2026-04-06-repository-baseline-contract-unification-implementation.md`
- Modify: `docs/plans/README.md`

**Step 1: Verify the frozen baseline sources before editing**

Run:
```bash
rg -n "多源|6 节点|专家裁决|multi-source|6-node" docs/PRD.md docs/APP_FLOW.md docs/TECH_STACK.md docs/BACKEND_STRUCTURE.md docs/IMPLEMENTATION_PLAN.md docs/CONSTANTS.md
```

Expected: matches confirming the frozen docs already define multi-source acquisition and the 6-node workflow.

**Step 2: Update `AGENTS.md` to the active contract**

Required outcomes:
1. scope says `6-node workflow`
2. node list includes `Expert adjudication`
3. acquisition section lists approved multi-source adapters
4. retry wording matches the defaults/caps model from `docs/CONSTANTS.md`

**Step 3: Register the new provenance docs in `docs/plans/README.md`**

Required outcomes:
1. both new files are discoverable
2. they are marked as reference-only provenance rather than active release backlog

**Step 4: Verify the root contract wording**

Run:
```bash
rg -n "5-node|PubMed only|Non-PubMed production crawler integrations" AGENTS.md
```

Expected: no matches.

**Step 5: Commit**

```bash
git add AGENTS.md docs/plans/README.md docs/plans/2026-04-06-repository-baseline-contract-unification-design.md docs/plans/2026-04-06-repository-baseline-contract-unification-implementation.md
git commit -m "docs: sync repository baseline contract wording"
```

### Task 2: Reframe historical progress notes and legacy implementation hints

**Files:**
- Modify: `progress.txt`
- Modify: `src/services/task_manager.py`

**Step 1: Add an explicit current-baseline note and historical supersession wording to `progress.txt`**

Required outcomes:
1. the active baseline is clearly stated as multi-source + 6-node
2. early 2026-03-03 progress items are marked as historical where they conflict
3. this session adds a new latest progress entry documenting the wording sync

**Step 2: Relabel legacy direct-task comments in `src/services/task_manager.py`**

Required outcomes:
1. comments no longer present the direct path as the active workflow baseline
2. legacy ACMG/graph-sync node comments are explicitly marked as pre-adjudication direct-path behavior

**Step 3: Run the repository wording verification**

Run:
```bash
rg -n "5-node|PubMed only|MVP source: PubMed only|Implement the main 5-node workflow" AGENTS.md progress.txt src/services/task_manager.py
```

Expected: no matches.

**Step 4: Run a broader targeted verification**

Run:
```bash
rg -n "single-source|pre-adjudication|legacy direct-task|multi-source|6-node" AGENTS.md progress.txt src/services/task_manager.py docs/plans/README.md docs/plans/2026-04-06-repository-baseline-contract-unification-design.md docs/plans/2026-04-06-repository-baseline-contract-unification-implementation.md
```

Expected: the edited files clearly distinguish current baseline wording from historical provenance.

**Step 5: Commit**

```bash
git add progress.txt src/services/task_manager.py
git commit -m "docs: clarify repository baseline history"
```
