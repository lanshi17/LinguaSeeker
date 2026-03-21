# Acquisition Strategy + Adapter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor literature acquisition to use a registry-backed strategy + adapter architecture while preserving the current external gateway/API surface and existing provider behavior.

**Architecture:** Keep `src/agents/acquisition/node.py` as the orchestration layer and `src/domain/literature/acquisition_agent.py` as the planning layer. Introduce provider adapters and a registry under `src/domain/literature/gateway/`, then refactor `src/domain/literature/gateway/api_gateway.py` into a façade that dispatches to adapters but still returns the current gateway result shape.

**Tech Stack:** Python, FastAPI, LangGraph-style workflow, pytest, existing literature provider modules under `src/domain/literature/api/*`, `pubmed_service.py`, and existing gateway download helpers.

---

### Task 1: Freeze current acquisition gateway behavior with regression tests

**Files:**
- Modify: `tests/test_api_gateway_download.py`
- Modify: `tests/test_literature_unified_workflow.py`
- Modify: `tests/test_agents_acquisition.py`

**Step 1: Identify the current public gateway entrypoints to freeze**

Read and list the exact functions/call paths currently used by callers:
- `src/domain/literature/gateway/api_gateway.py`
- `src/domain/literature/unified/workflow.py`
- `src/agents/acquisition/node.py`

Expected result: you know which externally visible behaviors must remain unchanged.

**Step 2: Add/adjust a failing regression test for gateway provider dispatch shape**

In `tests/test_api_gateway_download.py`, add a focused test that exercises `call_api_gateway(...)` through one existing provider path and asserts the current result contract (status/result fields/output shape) without depending on the future adapter internals.

Expected: FAIL if the result contract changes.

**Step 3: Add/adjust a failing regression test for unified workflow compatibility**

In `tests/test_literature_unified_workflow.py`, add a focused test that proves the unified workflow still calls the gateway through the current façade and still receives the same gateway-level output semantics.

Expected: FAIL if workflow/gateway compatibility breaks.

**Step 4: Add/adjust a failing regression test for agent-node orchestration boundary**

In `tests/test_agents_acquisition.py`, add a test that proves `src/agents/acquisition/node.py` remains orchestration-only and does not need provider-specific branching knowledge beyond the current gateway/planner boundary.

Expected: FAIL if node behavior changes incompatibly.

**Step 5: Run the targeted tests and verify the baseline**

Run:
```bash
uv run pytest -q tests/test_api_gateway_download.py tests/test_literature_unified_workflow.py tests/test_agents_acquisition.py
```

Expected: either PASS as baseline or FAIL only on the newly added expectations you are about to implement.

**Step 6: Commit the test baseline**

```bash
git add tests/test_api_gateway_download.py tests/test_literature_unified_workflow.py tests/test_agents_acquisition.py
git commit -m "test: freeze acquisition gateway compatibility"
```

---

### Task 2: Introduce adapter base contract and registry

**Files:**
- Create: `src/domain/literature/gateway/base.py`
- Create: `src/domain/literature/gateway/registry.py`
- Modify: `src/domain/literature/gateway/__init__.py`
- Test: `tests/domain/literature/gateway/test_registry.py`

**Step 1: Write the failing registry test**

Create `tests/domain/literature/gateway/test_registry.py` with focused tests that prove:
- an adapter can register under a provider name
- lookup returns the expected adapter
- unknown provider raises the unified gateway/registry error you choose
- duplicate registration is rejected or explicitly overwritten (pick one behavior and test it)

Expected: FAIL because the registry does not exist yet.

**Step 2: Define the provider adapter contract**

Create `src/domain/literature/gateway/base.py` with the minimal abstraction needed for this refactor:
- abstract/base adapter interface
- provider identity contract
- execute contract returning the current gateway result shape or the narrowest intermediate type needed before gateway normalization

Keep it intentionally small. No speculative fallback framework.

**Step 3: Implement the registry**

Create `src/domain/literature/gateway/registry.py` with:
- provider registration
- provider lookup
- centralized unsupported-provider handling

Do not implement fallback chains yet.

**Step 4: Export the new gateway primitives**

Modify `src/domain/literature/gateway/__init__.py` to export the new base contract and registry in the smallest clean way.

**Step 5: Run targeted verification**

Run:
```bash
uv run pytest -q tests/domain/literature/gateway/test_registry.py
uv run python -m py_compile src/domain/literature/gateway/base.py src/domain/literature/gateway/registry.py src/domain/literature/gateway/__init__.py
```

Expected: PASS.

**Step 6: Commit the registry layer**

```bash
git add src/domain/literature/gateway/base.py src/domain/literature/gateway/registry.py src/domain/literature/gateway/__init__.py tests/domain/literature/gateway/test_registry.py
git commit -m "feat: add literature provider adapter registry"
```

---

### Task 3: Wrap one provider path end-to-end through an adapter

**Files:**
- Create: `src/domain/literature/gateway/adapters/__init__.py`
- Create: `src/domain/literature/gateway/adapters/pmc_adapter.py`
- Modify: `src/domain/literature/gateway/api_gateway.py`
- Test: `tests/domain/literature/gateway/test_pmc_adapter.py`
- Update if needed: `tests/test_api_gateway_download.py`

**Step 1: Write the failing adapter test**

Create `tests/domain/literature/gateway/test_pmc_adapter.py` covering one real provider path first (recommended: PMC because it is already gateway-oriented). Test that the adapter:
- calls the existing implementation you are wrapping
- maps inputs correctly
- returns the expected gateway-compatible output

Expected: FAIL because the adapter does not exist yet.

**Step 2: Implement the first concrete adapter**

Create `src/domain/literature/gateway/adapters/pmc_adapter.py` that wraps the current PMC-specific implementation instead of reimplementing it.

Keep it thin:
- normalize provider-specific input if needed
- delegate to existing code
- normalize output back to the current gateway contract

**Step 3: Register the adapter in gateway dispatch**

Modify `src/domain/literature/gateway/api_gateway.py` so one provider branch (PMC) goes through the registry/adapter path.

Important: keep `call_api_gateway(...)` externally compatible.

**Step 4: Re-run regression tests for public behavior**

Run:
```bash
uv run pytest -q tests/domain/literature/gateway/test_pmc_adapter.py tests/test_api_gateway_download.py tests/test_literature_unified_workflow.py
```

Expected: PASS, proving the new adapter path preserves existing behavior.

**Step 5: Commit the first migrated provider**

```bash
git add src/domain/literature/gateway/adapters/__init__.py src/domain/literature/gateway/adapters/pmc_adapter.py src/domain/literature/gateway/api_gateway.py tests/domain/literature/gateway/test_pmc_adapter.py tests/test_api_gateway_download.py
git commit -m "feat: route pmc acquisition through adapter registry"
```

---

### Task 4: Migrate the remaining existing provider branches into adapters

**Files:**
- Create as needed:
  - `src/domain/literature/gateway/adapters/jstage_adapter.py`
  - `src/domain/literature/gateway/adapters/unpaywall_adapter.py`
  - `src/domain/literature/gateway/adapters/crossref_adapter.py`
  - any additional adapter file only for providers already implemented in the current codebase
- Modify: `src/domain/literature/gateway/api_gateway.py`
- Modify if needed: `src/domain/literature/gateway/registry.py`
- Tests:
  - `tests/test_api_gateway_download.py`
  - provider-specific tests already in the repo

**Step 1: Add a failing compatibility test for the next provider branch**

Before migrating each provider, add or extend a regression assertion that proves the current public behavior for that provider path.

Expected: FAIL only if the branch is not yet migrated correctly.

**Step 2: Implement thin adapters one provider at a time**

For each already-supported provider:
- create a concrete adapter file
- wrap existing implementation
- avoid rewriting provider-specific fetch/download logic

Keep each adapter thin and delegation-oriented.

**Step 3: Replace provider branching in `api_gateway.py` incrementally**

Move provider dispatch from hardcoded branching to registry lookup incrementally. After each provider migration, re-run the narrow relevant tests instead of changing all branches at once.

**Step 4: Run focused provider regression tests after each migration**

Run the smallest relevant test set after each provider migration, for example:
```bash
uv run pytest -q tests/test_api_gateway_download.py tests/test_literature_unified_workflow.py tests/domain/literature/automated_web/pubscholar/test_pubscholar.py tests/domain/literature/automated_web/hans_publishers/test_hans_publishers.py tests/domain/literature/automated_web/cyberleninka/test_cyberleninka.py
```

Use only the provider tests relevant to the provider(s) migrated in that sub-step.

**Step 5: Commit the completed provider migration set**

Create one or more focused commits grouped by provider/adapter migration.

---

### Task 5: Clean up orchestration boundaries without changing the external API

**Files:**
- Modify: `src/agents/acquisition/node.py`
- Modify if needed: `src/agents/acquisition/api_tool.py`
- Modify if needed: `src/agents/acquisition/crawl_tool.py`
- Modify if needed: `src/domain/literature/acquisition_agent.py`
- Test: `tests/test_agents_acquisition.py`

**Step 1: Write/extend a failing orchestration-boundary test**

Add assertions showing the acquisition node still:
- orchestrates planning/execution
- does not encode provider-specific dispatch details
- stays compatible with the current external API surface

Expected: FAIL if provider logic still leaks into the wrong layer after adapter migration.

**Step 2: Reduce provider-specific knowledge in the node/tool layer**

Modify `src/agents/acquisition/node.py` and thin wrappers only as needed so they call the preserved façade/planning layer without owning provider branching.

Keep this step minimal. Do not redesign planning.

**Step 3: Verify planning layer still owns normalization**

Adjust `src/domain/literature/acquisition_agent.py` only if necessary to keep planning/normalization responsibilities clear while adapter execution stays in the gateway layer.

Do not broaden scope into a planner rewrite.

**Step 4: Run orchestration regression tests**

Run:
```bash
uv run pytest -q tests/test_agents_acquisition.py tests/test_literature_unified_workflow.py
```

Expected: PASS.

**Step 5: Commit the boundary cleanup**

```bash
git add src/agents/acquisition/node.py src/agents/acquisition/api_tool.py src/agents/acquisition/crawl_tool.py src/domain/literature/acquisition_agent.py tests/test_agents_acquisition.py
git commit -m "refactor: isolate acquisition orchestration from provider dispatch"
```

---

### Task 6: Final verification wave

**Files:**
- Verify all touched files from Tasks 1–5
- Update docs only if the current repo already has acquisition architecture docs that must stay consistent

**Step 1: Run targeted Python syntax verification**

Run:
```bash
uv run python -m py_compile src/agents/acquisition/node.py src/agents/acquisition/api_tool.py src/agents/acquisition/crawl_tool.py src/domain/literature/acquisition_agent.py src/domain/literature/gateway/api_gateway.py src/domain/literature/gateway/base.py src/domain/literature/gateway/registry.py src/domain/literature/gateway/adapters/__init__.py src/domain/literature/gateway/adapters/*.py
```

Expected: PASS.

**Step 2: Run the adapter/gateway/acquisition regression suite**

Run:
```bash
uv run pytest -q tests/test_agents_acquisition.py tests/test_literature_unified_workflow.py tests/test_api_gateway_download.py tests/domain/literature/gateway/test_registry.py tests/domain/literature/gateway/test_pmc_adapter.py
```

Add any additional provider-specific test modules for migrated providers.

Expected: PASS.

**Step 3: Run scoped static checks on touched files**

Run:
```bash
uv run basedpyright src/agents/acquisition src/domain/literature/gateway src/domain/literature/acquisition_agent.py
uv run ruff check src/agents/acquisition src/domain/literature/gateway src/domain/literature/acquisition_agent.py tests/test_agents_acquisition.py tests/test_literature_unified_workflow.py tests/test_api_gateway_download.py tests/domain/literature/gateway
```

Expected: no new errors in the touched scope.

**Step 4: Re-read the design and confirm implementation matches it**

Checklist:
- external gateway/API entrypoint preserved
- orchestration stays in `src/agents/acquisition/`
- planning stays in `acquisition_agent.py`
- strategy/adapter logic lives in gateway layer
- existing providers are wrapped, not rewritten

Expected: all boxes satisfied.

**Step 5: Commit final integration fixes if needed**

Make the last focused commit only if verification required additional small fixes.

---

### Task 7: Finish the development branch

**Step 1: Announce the workflow transition**

Say: "I'm using the finishing-a-development-branch skill to complete this work."

**Step 2: Use the required sub-skill**

Invoke `superpowers:finishing-a-development-branch` and follow it exactly.

**Step 3: Present completion options**

After verification, offer the user the appropriate finish options (commit grouping already done above, push/PR if requested later).
