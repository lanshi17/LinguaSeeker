# Acquisition Strategy + Adapter Design

> **Plan Status:** `ACTIVE (v1.0 aligned)`
> **Conflict Rule:** Frozen docs define final contract; this plan implements within that contract.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor literature acquisition so multiple API/web retrieval strategies are selected through a strategy + adapter architecture while preserving the current external gateway/API surface.

**Architecture:** Keep `src/agents/acquisition/` as the orchestration layer and `src/domain/literature/acquisition_agent.py` as the planning layer. Move provider dispatch to a registry-backed adapter layer under `src/domain/literature/gateway/`, and keep `src/domain/literature/gateway/api_gateway.py` as the single façade that preserves current caller-facing behavior.

**Tech Stack:** Python, FastAPI, LangGraph-style acquisition workflow, existing literature provider modules under `src/domain/literature/api/*`, pytest.

---

## Design Summary

### 1. Layer boundaries
- `src/agents/acquisition/node.py`
  - remains the acquisition node entrypoint
  - reads supervisor state
  - triggers planning/execution
  - does **not** own provider-specific branching
- `src/domain/literature/acquisition_agent.py`
  - remains responsible for planning, normalization, and acquisition-plan generation
  - decides source/provider intent, but does **not** own adapter execution details
- `src/domain/literature/gateway/`
  - becomes the strategy/adapter core
  - owns provider registration, provider lookup, adapter dispatch, and unified result shaping
- `src/domain/literature/api/*` and other provider-specific service modules
  - remain the concrete provider implementation layer
  - are wrapped by adapters instead of being rewritten

### 2. Core abstractions
- `ProviderAdapter`
  - provider-scoped execution contract
  - accepts a normalized acquisition/gateway input shape
  - returns the same gateway-facing result model currently expected by callers
- `ProviderAdapterRegistry`
  - owns registration and lookup of provider adapters
  - centralizes unsupported-provider handling
  - is the future place for fallback/priority logic if needed
- `call_api_gateway(...)`
  - remains the external façade for current callers
  - internally becomes: normalize input → resolve adapter from registry → execute adapter → normalize/return result

### 3. Data flow
1. `src/agents/acquisition/node.py` receives acquisition state.
2. `src/domain/literature/acquisition_agent.py` normalizes request data and produces provider/source intent.
3. `src/domain/literature/gateway/api_gateway.py` receives the normalized request and resolves the provider adapter.
4. The selected adapter calls the existing provider-specific implementation (`src/domain/literature/api/*`, `pubmed_service.py`, firecrawl-related services, or existing gateway helper logic).
5. The adapter returns a unified result compatible with the current gateway contract.
6. The orchestration layer continues without requiring upper-layer API changes.

### 4. Error handling
- provider-specific exceptions are translated inside adapters into unified gateway-level failures/results
- unknown provider handling belongs in the registry, not the agent node
- fallback or partial-failure policy belongs in the registry/gateway layer, not in `src/agents/acquisition/node.py`
- logging split:
  - provider details in adapters
  - orchestration logs in `src/agents/acquisition/node.py`

### 5. Testing strategy
- add adapter/registry dispatch unit tests
- preserve and extend compatibility tests around `call_api_gateway(...)`
- use these existing regression surfaces first:
  - `tests/test_api_gateway_download.py`
  - `tests/test_literature_unified_workflow.py`
  - `tests/test_agents_acquisition.py`
- reuse provider-specific integration tests instead of duplicating provider behavior coverage through adapters

### 6. Scope boundaries
**In scope**
- adapter interface + registry
- gateway dispatch refactor
- preserving current external API/call signatures
- wrapping existing providers behind adapters

**Out of scope**
- adding brand-new providers
- major redesign of the acquisition planner
- rewriting provider-specific download logic from scratch
- changing the upper-layer acquisition node contract

### 7. Recommended placement
- `src/agents/acquisition/` = orchestration only
- `src/domain/literature/acquisition_agent.py` = planning only
- `src/domain/literature/gateway/` = adapter/strategy core
- `src/domain/literature/api/*` = wrapped provider implementations

### 8. Planned adapter candidates
Initial adapters should map to providers/paths already implemented in the codebase, for example:
- `PubMedAdapter`
- `PMCAdapter`
- `JStageAdapter`
- `UnpaywallAdapter`
- `CrossrefAdapter`

The first migration should wrap existing provider logic rather than invent new execution paths.
