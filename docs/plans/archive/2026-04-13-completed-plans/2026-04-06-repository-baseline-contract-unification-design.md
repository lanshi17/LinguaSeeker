# Repository Baseline Contract Unification Design

> **Status:** `APPROVED FOR IMPLEMENTATION`
> **Baseline:** This design synchronizes repository-level execution guidance with the frozen `v1.0` contract that already defines multi-source acquisition and the 6-node workflow.

## Goal
Remove repository-level wording drift so contributors no longer see competing baselines between the frozen `docs/` specs, the root execution contract, the progress tracker, and residual implementation comments.

## Problem Statement
The frozen `docs/` set already defines the active `v1.0` baseline as:
1. multi-source literature acquisition
2. a fixed 6-node workflow
3. expert adjudication as the sixth node

But several repository-level artifacts still expose older guidance:
1. `AGENTS.md` still describes a 5-node workflow and PubMed-only acquisition
2. `progress.txt` still contains early top-level milestone wording that can be misread as the current baseline
3. `src/services/task_manager.py` still labels legacy direct-task helpers as a generic 5-node pipeline, even though the frozen workflow baseline has moved to the 6-node supervisor path

This mismatch is risky because future work may follow the wrong contract even when the frozen specs are already correct.

## Chosen Approach
Use a contract-sync approach that distinguishes current guidance from historical provenance:
1. align `AGENTS.md` directly to the frozen `docs/` baseline
2. keep `progress.txt` historical, but add explicit supersession wording so old entries are not treated as current requirements
3. relabel legacy implementation comments in `src/services/task_manager.py` so they are clearly marked as legacy direct-path helpers rather than the active workflow baseline
4. store this design and an execution plan under `docs/plans/` for traceability

## Scope
### In scope
1. `AGENTS.md` wording updates for 6 nodes and multi-source acquisition
2. `progress.txt` wording cleanup plus a new latest checkpoint entry
3. legacy comment relabeling in `src/services/task_manager.py`
4. plan/design provenance in `docs/plans/`

### Out of scope
1. changing active business logic from legacy direct-task paths to the 6-node supervisor path
2. renaming existing task functions such as `process_pubmed_paper_task`
3. changing frozen retry semantics beyond syncing wording to `docs/CONSTANTS.md`
4. updating archived historical plans unless they are reactivated later

## Risks and Mitigations
1. Historical entries could be accidentally rewritten as if the newer baseline always existed.
   - Mitigation: use explicit "historical/superseded" wording instead of silently replacing provenance.
2. Comment cleanup could misrepresent current code behavior.
   - Mitigation: label direct-task helpers as legacy rather than pretending those paths already run the full 6-node chain.
3. New plan files could become orphaned.
   - Mitigation: add them to `docs/plans/README.md` as reference-only provenance.

## Definition of Done
This contract-sync slice is complete when:
1. `AGENTS.md` matches the frozen multi-source + 6-node baseline
2. `progress.txt` no longer presents the old baseline as current guidance
3. `src/services/task_manager.py` comments distinguish legacy direct paths from the active workflow baseline
4. the new design/plan documents are saved and discoverable from `docs/plans/README.md`
5. a targeted repository search shows no unqualified current-baseline wording drift in the edited files
