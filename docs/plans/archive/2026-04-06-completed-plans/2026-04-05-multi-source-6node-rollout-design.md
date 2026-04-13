# Multi-Source 6-Node Rollout Design

> **Status:** `APPROVED FOR IMPLEMENTATION`
> **Baseline:** This design refines `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md` into an executable rollout slice aligned with `docs/PRD.md`, `docs/APP_FLOW.md`, and `docs/BACKEND_STRUCTURE.md`.

## Goal
Unblock the actual `v1.0` backend entrypoints so the system runs the frozen multi-source acquisition contract and the 6-node single-paper workflow instead of retaining a hidden `mvp_pubmed_only` restriction in the unified literature workflow.

## Problem Statement
The repository already contains most of the rollout surface:
1. API providers: `pmc`, `crossref`, `doaj`, `jstage`, `unpaywall`
2. Web providers: `hans_publishers`, `pubscholar`, `cyberleninka`
3. 6-node supervisor graph: acquisition -> parsing -> translation -> extraction -> ACMG classification -> expert adjudication
4. Source planning and tracing primitives

But the effective acquisition entrypoint, `src/domain/literature/unified/workflow.py`, still rejects non-PMC API routes and all web routes with `mvp_pubmed_only`. That leaves the codebase in a false-halfway state where:
1. the docs promise multi-source behavior
2. the adapters exist
3. the tests partly cover multi-source behavior
4. the unified workflow still enforces a PubMed-only gate

## Chosen Approach
Use a contract-first incremental rollout:
1. make `literature_unified_workflow` the single multi-source routing and retry surface
2. make the acquisition node consume that unified workflow instead of maintaining separate implicit routing rules
3. keep the supervisor graph on the frozen 6-node order and only tighten status / trace handling where the acquisition contract needs it
4. drive changes by focused failing tests for routing, retry tracing, acquisition-node integration, and 6-node workflow behavior

This avoids two common failure modes:
1. opening providers without preserving `source_trace`
2. claiming “6-node complete” while acquisition still runs under a hidden MVP-only branch

## Architecture
### 1. Unified literature workflow is the only routing authority
`src/domain/literature/unified/workflow.py` becomes the canonical surface for:
1. identifier extraction
2. provider selection
3. search vs download branching
4. provider retries
5. `source_trace` accumulation
6. fallback signaling

The workflow must support:
1. explicit `api_provider` override
2. explicit `web_provider` override
3. `prefer=auto/api/web`
4. API and web sources for both search and download where adapters exist

### 2. Acquisition node becomes a workflow caller, not a policy fork
`src/agents/acquisition/node.py` should still preserve the upload fast path, but non-upload sources should no longer stop at planning only.

The node should:
1. keep upload behavior unchanged
2. preserve normalized planning for `pubmed` and `web`
3. invoke the unified workflow with the planned values
4. store standardized acquisition results and `source_trace` in `node_trace` / state
5. raise contract-aligned failures when acquisition returns no usable result

### 3. Supervisor remains a 6-node chain
The 6-node order remains:
1. acquisition
2. parsing
3. translation
4. extraction
5. reasoning as ACMG classification
6. arbitration as expert adjudication

No extra node is added. The rollout only tightens how the existing nodes expose status and trace data.

### 4. Traceability must stay first-class
The rollout is not complete unless source-level traceability survives end-to-end.

Minimum trace expectations:
1. per-attempt provider trace with `provider/attempt/success/items_count/downloads_count/warnings/error`
2. route summary with selected provider and strategy
3. acquisition detail recorded in `node_trace`
4. downstream workflow status still normalized through `processing_steps`

## Boundaries
### In scope
1. remove `mvp_pubmed_only` restrictions from the unified workflow
2. preserve or expand multi-source retry and `source_trace` tests
3. wire acquisition node to the unified workflow
4. keep supervisor behavior aligned with the 6-node contract
5. update plan docs, `progress.txt`, and `lesson.md`

### Out of scope
1. new provider implementations
2. changing the 6-node order
3. frontend candidate-page redesign
4. KG event refactor
5. acceptance-set execution for the full 100-paper release gate

## Testing Strategy
### Slice 1: Unified workflow routing
Add or update focused tests to prove:
1. non-PMC API providers are allowed when requested or inferred
2. web routing is allowed when requested
3. `source_trace` records retries and warnings correctly
4. failed downloads still produce contract-aligned warnings

### Slice 2: Acquisition node integration
Add focused tests to prove:
1. upload path is unchanged
2. non-upload path calls the unified workflow with normalized planned inputs
3. acquisition results are stored in state in a standard shape
4. no-result acquisition becomes a contract-aligned failure path

### Slice 3: Supervisor workflow regression
Run and extend regression coverage to prove:
1. 6-node happy path still completes
2. parsing failure still short-circuits
3. human-review routes still take precedence over finalize
4. acquisition trace/state additions do not break the compiled graph

## Risks and Mitigations
1. Test drift from old MVP-only assumptions
   - Mitigation: replace those assertions first, before production edits
2. Acquisition-node/state shape mismatch
   - Mitigation: standardize on one acquisition result payload and assert exact keys
3. Provider-specific behavior differences on download flows
   - Mitigation: test routing through monkeypatched gateway calls, not live upstreams
4. Hidden status regressions in supervisor steps
   - Mitigation: rerun focused supervisor and integration suites after each slice

## Definition of Done
This rollout slice is complete when:
1. no code path in the unified literature workflow still enforces `mvp_pubmed_only`
2. multi-source routing tests pass for API and web providers
3. acquisition node consumes the unified workflow and records traceable results
4. 6-node supervisor regressions stay green
5. docs/plans, `progress.txt`, and `lesson.md` reflect the rollout changes
