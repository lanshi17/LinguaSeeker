# ACMG Agent Architecture Refactor

## TL;DR
> **Summary**: Restructure existing FastAPI + Celery + LangGraph backend into `state/`, `agents/`, `tools/`, `knowledge/` layers with a top-level LangGraph Supervisor graph, keeping Celery as the outer executor. Compatibility-first: old code preserved, feature flag switching, zero threshold/prompt content changes.
> **Deliverables**: New `state/`, `agents/`, `tools/`, `knowledge/` packages; Supervisor graph; prompt externalization; golden test fixtures; backward-compatible re-exports
> **Effort**: Large (2 weeks)
> **Parallel**: YES — 6 waves
> **Critical Path**: Wave 0 (safety net) → Wave 1 (skeleton) → Wave 2 (agent migration) → Wave 3 (workflow split) → Wave 4 (supervisor integration) → Wave 5 (prompt externalization)

## Context

### Original Request
Restructure an ACMG PS3/BS3 evidence assessment backend from a flat `domain/agent/` + `service/tasks.py` orchestration into a modular agent architecture with `state/`, `agents/`, `tools/`, `knowledge/` layers and a top-level LangGraph Supervisor graph, while keeping Celery as the outer executor and preserving all existing behavior.

### Interview Summary
**Decisions made:**
1. LangGraph + Celery coexistence (Celery=outer executor/retry, LangGraph=inner orchestration)
2. New top-level Supervisor graph, invoked inside Celery tasks
3. Full prompt externalization (phased, extraction/arbitration first)
4. Core refactor scope: 2 weeks
5. Compatibility: old code preserved until new flow verified; feature flag `USE_AGENT_WORKFLOW` in config.py
6. Hard logic isolation: ACMG thresholds/OddsPath in pure code, LLM excluded from calculations
7. `GlobalState` (actually `SupervisorState`) as TypedDict runtime state wrapping `ProcessingState`; DB remains truth source
8. `database/` rename to `infrastructure/` DEFERRED — too much import churn for zero behavioral gain
9. `presentation/` rename to `api/` DEFERRED — same reason
10. Feature flag granularity: per-task-type (PDF/PubMed/Web can independently switch)
11. Supervisor handles all 3 task types via conditional routing, not 3 separate graphs
12. Translation lives as a standalone Supervisor node (not embedded in extraction subgraph)
13. Prompt externalization means YAML files in `knowledge/prompts/`, loaded by wrapper functions

### Metis Review (gaps addressed)
- **Threshold synchronization**: Added Wave 0 threshold sync test (G1)
- **Golden test fixtures**: Added Wave 0 fixture creation (G2)
- **State transition documentation**: Added to Wave 0 (G3)
- **Graph sync idempotency**: Added verification task to Wave 0 (G4)
- **Celery task signature freeze**: Explicit in Wave 4 — Supervisor is internal detail (G5)
- **asyncio.run() consolidation**: Wave 4 Supervisor runs single `asyncio.run()` context
- **EvidenceAgent singleton**: Preserved as-is (prefork worker assumption)
- **Translation dedup**: Wave 3 resolves — extraction subgraph skips internal translation
- **Three task types**: Wave 4 Supervisor has conditional acquisition/parsing branches
- **HGVS correction, sentence alignment, MinIO keys, node_trace**: All preserved in Supervisor nodes
- **Arbitration feedback loop**: max_iterations preserved, no double-retry risk
- **Redis cache, graph sync asymmetry**: Preserved in finalize node

## Work Objectives

### Core Objective
Restructure the backend into a modular agent architecture that separates concerns (state, agents, tools, knowledge) and introduces a top-level Supervisor graph for workflow orchestration, while preserving 100% behavioral equivalence with the current system.

### Deliverables
- `src/state/` package with `SupervisorState`, `GlobalState`, and extracted schemas
- `src/agents/` package with `supervisor.py` and 5 agent sub-packages (interaction, acquisition, parsing, extraction, arbitration)
- `src/tools/` package wrapping existing DB/file/external capabilities
- `src/knowledge/prompts/` with externalized YAML prompts (extraction + arbitration)
- Golden test fixtures and threshold synchronization tests
- Feature flag `USE_AGENT_WORKFLOW` for per-task-type rollout
- Backward-compatible re-exports in old module locations

### Definition of Done (verifiable conditions with commands)
- `python -m pytest tests/ -x` passes with zero regressions
- All 3 Celery task signatures unchanged (verify via `ast_grep_search`)
- `python -c "from src.domain.agent.workflow import EvidenceAgent"` still works (backward compat)
- `python -c "from src.agents.supervisor import build_supervisor_graph"` works (new path)
- Golden fixture comparison passes (structural equivalence of `EvidenceOutput`)
- Threshold sync test passes (prompts.py values == enums.py/classifier.py values)
- Feature flag toggles between old `tasks.py` orchestration and new Supervisor without code changes

### Must Have
- All existing API endpoint contracts preserved
- All existing Celery task signatures preserved
- All ACMG thresholds, scoring formulas, and classification logic byte-identical
- Backward-compatible imports for all moved modules
- Golden test fixtures created BEFORE any structural changes
- Feature flag for per-task-type rollout
- HGVS correction, sentence alignment, MinIO key conventions, node_trace all preserved

### Must NOT Have (guardrails, scope boundaries)
- **NO** threshold value changes (ARBITRATION_SCORE_THRESHOLD, ODDSPATH_THRESHOLDS, classifier weighting 0.6/0.4)
- **NO** prompt content changes during externalization (byte-identical moves only)
- **NO** database schema changes (no migrations, no model consolidation)
- **NO** Task/PaperTask model consolidation
- **NO** error handling standardization (copy existing verbatim)
- **NO** RAG/knowledge base architecture changes (stays inside extraction node)
- **NO** `database/` → `infrastructure/` rename in this sprint
- **NO** `presentation/` → `api/` rename in this sprint
- **NO** Celery pool type changes
- **NO** new external dependencies

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: Tests-after (golden fixtures + threshold sync + import verification)
- QA policy: Every task has agent-executed scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy

### Parallel Execution Waves

**Wave 0**: Safety Net (2 tasks, foundation)
- Golden test fixtures + threshold synchronization tests

**Wave 1**: Skeleton + Schema Extraction (3 tasks, parallel)
- Create directory skeletons, extract schemas, add feature flag

**Wave 2**: Agent Migration — Low Risk (3 tasks, parallel)
- Migrate interaction, parsing, acquisition agents with backward compat

**Wave 3**: Workflow Split — High Value (2 tasks, sequential)
- Split workflow.py into extraction/ + arbitration/, isolate hard logic

**Wave 4**: Supervisor Integration (2 tasks, sequential)
- Build Supervisor graph, integrate into tasks.py behind feature flag

**Wave 5**: Prompt Externalization (2 tasks, parallel)
- Externalize extraction + arbitration prompts to YAML

### Dependency Matrix
```
Wave 0: [T1, T2] — no dependencies (MUST complete before all other waves)
Wave 1: [T3, T4, T5] — depends on Wave 0
Wave 2: [T6, T7, T8] — depends on Wave 1; T6/T7/T8 are parallel
Wave 3: [T9, T10] — depends on Wave 2; T9 before T10
Wave 4: [T11, T12] — depends on Wave 3; T11 before T12
Wave 5: [T13, T14] — depends on Wave 4; T13/T14 are parallel
```

### Agent Dispatch Summary
| Wave | Tasks | Categories |
|------|-------|-----------|
| 0 | 2 | deep, deep |
| 1 | 3 | quick, unspecified-high, quick |
| 2 | 3 | unspecified-high, unspecified-high, unspecified-high |
| 3 | 2 | deep, deep |
| 4 | 2 | deep, deep |
| 5 | 2 | unspecified-high, unspecified-high |

## TODOs

### Wave 0: Safety Net

- [ ] 1. Create Golden Test Fixtures

  **What to do**:
  1. Read `src/domain/models.py` to understand `EvidenceOutput`, `ExtractedEvidenceFields`, `PipelineResult`, `DocumentParsingResult` schemas.
  2. Read `src/service/tasks.py` to understand the full pipeline output shape — specifically what `process_pdf_task` returns and stores to MinIO.
  3. Read `src/domain/agent/workflow.py` to understand `ProcessingState` intermediate shapes and `EvidenceAgent.process_medical_evidence()` return contract.
  4. Create `tests/fixtures/` directory if it doesn't exist.
  5. Create `tests/fixtures/golden_evidence_output.json`: a structurally complete `EvidenceOutput` fixture with all fields populated with realistic test data (use field definitions from `ExtractedEvidenceFields` for nested structure). Include `ps3_evidence`, `arbitration_confidence`, `image_descriptions`, `final_evidence_strength`, `status`, `origin_format_md`, `en_format_md`, `extracted_fields` (all 10 sub-models), `field_confidence_scores`, `overall_confidence`, `evidence_classification`, `acmg_evidence_levels`.
  6. Create `tests/fixtures/golden_processing_state.json`: a complete `ProcessingState` dict with all 22+ fields from `src/domain/enums.py::ProcessingState` plus the ad-hoc fields from `tasks.py` (`node_trace`, `processing_steps`, `paper_task_id`, `document_id`, `request_id`).
  7. Create `tests/fixtures/golden_pipeline_result.json`: a complete `PipelineResult` fixture.
  8. Create `tests/fixtures/golden_parsing_result.json`: a complete `DocumentParsingResult` fixture.
  9. Write `tests/test_golden_fixtures.py` that:
     - Loads each JSON fixture
     - Validates it against the corresponding Pydantic model (`EvidenceOutput.model_validate(data)`, etc.)
     - Asserts all required fields are present and correctly typed
     - Exports a `validate_evidence_output_equivalence(actual, expected)` helper that compares structure (field names, types, nesting) without requiring value equality

  **Must NOT do**:
  - Do NOT use real patient data or real paper content
  - Do NOT change any model definitions
  - Do NOT add new dependencies

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Requires understanding multiple interconnected model schemas and creating structurally faithful fixtures
  - Skills: [] — No special skills needed
  - Omitted: [`test-driven-development`] — This IS the test creation task

  **Parallelization**: Can Parallel: YES (with T2) | Wave 0 | Blocks: [T3-T14] | Blocked By: []

  **References**:
  - Pattern: `src/domain/models.py` — All Pydantic model definitions for EvidenceOutput, ExtractedEvidenceFields, PipelineResult, DocumentParsingResult, and 10 evidence field sub-models
  - Pattern: `src/domain/enums.py` — ProcessingState TypedDict definition
  - Pattern: `src/service/tasks.py` — Ad-hoc state fields (node_trace, processing_steps, paper_task_id etc.) and pipeline output assembly
  - Pattern: `src/domain/agent/workflow.py` — EvidenceAgent.process_medical_evidence() return shape
  - Pattern: `src/domain/evidence/classifier.py` — EvidenceStrengthClassification and scoring output shape

  **Acceptance Criteria** (agent-executable only):
  - [ ] `ls tests/fixtures/golden_*.json | wc -l` returns 4
  - [ ] `python -m pytest tests/test_golden_fixtures.py -v` passes — all fixtures validate against their models
  - [ ] `python -c "from tests.test_golden_fixtures import validate_evidence_output_equivalence; print('OK')"` exits 0

  **QA Scenarios**:
  ```
  Scenario: Golden fixtures validate against models
    Tool: Bash
    Steps: python -m pytest tests/test_golden_fixtures.py -v
    Expected: All tests pass, 4+ assertions
    Evidence: .sisyphus/evidence/task-1-golden-fixtures.txt

  Scenario: Fixture has all required EvidenceOutput fields
    Tool: Bash
    Steps: python -c "import json; d=json.load(open('tests/fixtures/golden_evidence_output.json')); assert 'ps3_evidence' in d and 'extracted_fields' in d and 'acmg_evidence_levels' in d; print('PASS')"
    Expected: Prints PASS
    Evidence: .sisyphus/evidence/task-1-field-check.txt
  ```

  **Commit**: YES | Message: `test(safety): add golden test fixtures for pipeline models` | Files: tests/fixtures/*.json, tests/test_golden_fixtures.py

---

- [ ] 2. Threshold Synchronization Tests + State Transition Documentation

  **What to do**:
  1. Read `src/domain/agent/prompts.py` and extract all threshold constants: `ARBITRATION_SCORE_THRESHOLD` (85.0), `ARBITRATION_CONFIDENCE_THRESHOLD` (0.85), and any `ODDSPATH_THRESHOLDS` embedded in prompt text.
  2. Read `src/domain/enums.py` and extract: `ODDSPATH_STRENGTH_MAP`, `SCORE_CLASSIFICATION_MAP`, `EVIDENCE_VALIDITY_THRESHOLD`.
  3. Read `src/domain/evidence/classifier.py` and extract: `oddspath_to_strength` thresholds (<0.0029, <0.053, <0.23, <=1.0, <=4.3, <=18.7, <=350).
  4. Read `src/domain/evidence/evaluation_framework.py` and extract: `determine_strength_by_oddpath` thresholds and the 4-step decision flow constants.
  5. Write `tests/test_threshold_sync.py` that asserts all threshold values are synchronized:
     - `prompts.ARBITRATION_SCORE_THRESHOLD == 85.0`
     - `prompts.ARBITRATION_CONFIDENCE_THRESHOLD == 0.85`
     - All OddsPath breakpoints in `classifier.py` match `evaluation_framework.py`
     - Classifier weighting formula is `overall_score = total_score * 0.6 + field_confidence * 0.4`
  6. Write `tests/test_state_transitions.py` that documents and asserts valid `PaperTask` processing step status transitions:
     - Valid: `queued → running → completed`, `queued → running → failed`, `queued → skipped`
     - Invalid: `completed → running`, `failed → queued`
     - Uses `src/service/enum.py::ProcessingStepStatus` and `PROCESSING_STEP_ORDER`
  7. Verify graph sync idempotency: read `src/database/postgre_client.py::create_evidence_record` and check if it uses upsert or insert. If insert (creates duplicates on retry), add a `# WARNING: not idempotent` comment to the test documenting this known issue — do NOT fix it.

  **Must NOT do**:
  - Do NOT change any threshold values
  - Do NOT fix the graph sync idempotency issue (just document it)
  - Do NOT modify any production code

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Cross-module threshold tracing requires careful reading of 4+ files
  - Skills: [] — No special skills needed
  - Omitted: [`systematic-debugging`] — Not a bug fix

  **Parallelization**: Can Parallel: YES (with T1) | Wave 0 | Blocks: [T3-T14] | Blocked By: []

  **References**:
  - Pattern: `src/domain/agent/prompts.py` — ARBITRATION_SCORE_THRESHOLD (85.0), ARBITRATION_CONFIDENCE_THRESHOLD (0.85)
  - Pattern: `src/domain/enums.py` — ODDSPATH_STRENGTH_MAP, SCORE_CLASSIFICATION_MAP, ProcessingStepStatus, PROCESSING_STEP_ORDER
  - Pattern: `src/domain/evidence/classifier.py` — oddspath_to_strength breakpoints, classify() weighting formula (0.6/0.4)
  - Pattern: `src/domain/evidence/evaluation_framework.py` — determine_strength_by_oddpath thresholds, 4-step decision flow
  - Pattern: `src/database/postgre_client.py` — create_evidence_record method (check upsert vs insert)

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest tests/test_threshold_sync.py -v` passes
  - [ ] `python -m pytest tests/test_state_transitions.py -v` passes
  - [ ] `grep -r "ARBITRATION_SCORE_THRESHOLD" tests/test_threshold_sync.py` returns matches

  **QA Scenarios**:
  ```
  Scenario: Threshold values are synchronized
    Tool: Bash
    Steps: python -m pytest tests/test_threshold_sync.py -v
    Expected: All threshold assertions pass
    Evidence: .sisyphus/evidence/task-2-threshold-sync.txt

  Scenario: State transitions documented
    Tool: Bash
    Steps: python -m pytest tests/test_state_transitions.py -v
    Expected: Valid transitions pass, invalid transitions raise assertion
    Evidence: .sisyphus/evidence/task-2-state-transitions.txt
  ```

  **Commit**: YES | Message: `test(safety): add threshold sync and state transition tests` | Files: tests/test_threshold_sync.py, tests/test_state_transitions.py

---

### Wave 1: Skeleton + Schema Extraction

- [ ] 3. Create Directory Skeletons with __init__.py

  **What to do**:
  1. Create the following directory structure with empty `__init__.py` files:
     ```
     src/state/__init__.py
     src/agents/__init__.py
     src/agents/interaction/__init__.py
     src/agents/acquisition/__init__.py
     src/agents/parsing/__init__.py
     src/agents/extraction/__init__.py
     src/agents/arbitration/__init__.py
     src/tools/__init__.py
     src/tools/db/__init__.py
     src/tools/file/__init__.py
     src/tools/external/__init__.py
     src/knowledge/__init__.py
     src/knowledge/prompts/__init__.py
     ```
  2. Each `__init__.py` should contain a module docstring explaining the package purpose.
  3. Verify all directories are importable: `python -c "import src.state; import src.agents; import src.tools; import src.knowledge"`.

  **Must NOT do**:
  - Do NOT create any implementation files yet (only __init__.py)
  - Do NOT modify any existing files
  - Do NOT add the directories to `pyproject.toml` packages list yet

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Pure directory/file creation, no logic
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T4, T5) | Wave 1 | Blocks: [T6-T14] | Blocked By: [T1, T2]

  **References**:
  - Pattern: `src/domain/__init__.py` — Follow existing __init__.py style
  - Pattern: `src/database/__init__.py` — Follow existing package docstring convention

  **Acceptance Criteria** (agent-executable only):
  - [ ] `find src/state src/agents src/tools src/knowledge -name '__init__.py' | wc -l` returns 13
  - [ ] `python -c "import src.state, src.agents, src.tools, src.knowledge; print('OK')"` exits 0

  **QA Scenarios**:
  ```
  Scenario: All packages importable
    Tool: Bash
    Steps: python -c "import src.state; import src.agents.interaction; import src.agents.acquisition; import src.agents.parsing; import src.agents.extraction; import src.agents.arbitration; import src.tools.db; import src.tools.file; import src.tools.external; import src.knowledge.prompts; print('ALL OK')"
    Expected: Prints ALL OK
    Evidence: .sisyphus/evidence/task-3-imports.txt
  ```

  **Commit**: YES | Message: `refactor(skeleton): create state/agents/tools/knowledge package skeletons` | Files: src/state/*, src/agents/*/*, src/tools/*/*, src/knowledge/*

---

- [ ] 4. Extract Schemas to state/schemas.py + Define SupervisorState

  **What to do**:
  1. Read `src/domain/models.py` completely.
  2. Create `src/state/schemas.py` that **re-exports** (not copies) the following from `src.domain.models`:
     ```python
     from src.domain.models import (
         EvidenceOutput,
         ExtractedEvidenceFields,
         EvidenceStrengthClassification,
         DocumentParsingResult,
         DocumentParsingArtifact,
         PipelineFiles,
         PipelineResult,
         # All 10 evidence field sub-models
         GeneInfo, TranscriptInfo, ReferenceGenomeInfo,
         ExperimentData, DiseaseInfo, SpeciesInfo,
         PhenotypeInfo, VariantInfo, ControlInfo, PedigreeInfo,
     )
     ```
  3. Create `src/state/global_state.py` that defines `SupervisorState` as a TypedDict:
     ```python
     from typing import TypedDict, Optional
     from src.state.schemas import (
         DocumentParsingResult, EvidenceOutput,
         ExtractedEvidenceFields, PipelineFiles, PipelineResult,
     )

     class SupervisorState(TypedDict, total=False):
         # identity
         request_id: str
         paper_task_id: int
         document_id: int
         celery_task_id: str
         source: str  # Literal['upload', 'pubmed', 'web']

         # inputs
         file_paths: list[str]
         urls: list[str]
         pmids: list[str]

         # workflow control
         current_node: str
         workflow_status: str
         processing_steps: dict[str, dict]
         node_trace: dict[str, str]
         retries: dict[str, int]
         warnings: list[str]
         errors: list[str]
         requires_human_review: bool

         # acquisition/parsing
         parsing_result: Optional[DocumentParsingResult]
         parser_backend: Optional[str]
         markdown_content: Optional[str]
         image_paths: list[str]
         sentence_alignments: list[dict]

         # translation/extraction/arbitration
         translated_markdown: Optional[str]
         image_descriptions: Optional[str]
         evidence_output: Optional[EvidenceOutput]
         extracted_fields: Optional[ExtractedEvidenceFields]
         arbitration_confidence: Optional[float]
         final_evidence_strength: Optional[str]
         acmg_result: Optional[dict]

         # provenance
         evidence_sources: list[dict]

         # persistence/output
         output_files: Optional[PipelineFiles]
         final_result: Optional[PipelineResult]

         # inner agent state (wrapped, not extended)
         _inner_processing_state: Optional[dict]
     ```
  4. Update `src/state/__init__.py` to export `SupervisorState` and key schemas.
  5. **Do NOT** remove or change anything in `src/domain/models.py` — state/schemas.py is a re-export layer.
  6. Write a test `tests/test_state_schema.py` that validates `SupervisorState` is a valid TypedDict and that all re-exported schemas are importable from both old and new paths.

  **Must NOT do**:
  - Do NOT copy model code (use re-exports only)
  - Do NOT modify `src/domain/models.py`
  - Do NOT remove any existing imports anywhere

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Careful schema extraction with cross-file awareness
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T3, T5) | Wave 1 | Blocks: [T6-T14] | Blocked By: [T1, T2]

  **References**:
  - Pattern: `src/domain/models.py` — All model definitions to re-export
  - Pattern: `src/domain/enums.py` — `ProcessingState` TypedDict (the inner state SupervisorState wraps)
  - Pattern: `src/service/tasks.py` — Ad-hoc fields: `node_trace`, `processing_steps`, `paper_task_id`, `document_id`, `request_id` that must be in SupervisorState
  - Pattern: `src/domain/agent/workflow.py` — `ProcessingState` usage patterns

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.state.global_state import SupervisorState; print(SupervisorState.__annotations__.keys())"` shows all fields
  - [ ] `python -c "from src.state.schemas import EvidenceOutput, ExtractedEvidenceFields, PipelineResult; print('OK')"` exits 0
  - [ ] `python -c "from src.domain.models import EvidenceOutput; from src.state.schemas import EvidenceOutput as EO2; assert EvidenceOutput is EO2; print('SAME')"` prints SAME
  - [ ] `python -m pytest tests/test_state_schema.py -v` passes

  **QA Scenarios**:
  ```
  Scenario: SupervisorState is valid TypedDict
    Tool: Bash
    Steps: python -c "from src.state.global_state import SupervisorState; import typing; assert typing.get_type_hints(SupervisorState); print('VALID')"
    Expected: Prints VALID
    Evidence: .sisyphus/evidence/task-4-supervisor-state.txt

  Scenario: Re-exports are identity (not copies)
    Tool: Bash
    Steps: python -c "from src.domain.models import EvidenceOutput as A; from src.state.schemas import EvidenceOutput as B; assert A is B; print('IDENTITY')"
    Expected: Prints IDENTITY
    Evidence: .sisyphus/evidence/task-4-identity.txt
  ```

  **Commit**: YES | Message: `refactor(state): add SupervisorState and schema re-exports` | Files: src/state/global_state.py, src/state/schemas.py, src/state/__init__.py, tests/test_state_schema.py

---

- [ ] 5. Add Feature Flag to config.py

  **What to do**:
  1. Read `src/config.py` to understand the `Settings` class structure.
  2. Add 3 feature flag fields to `Settings`:
     ```python
     # Agent workflow feature flags (per-task-type rollout)
     use_agent_workflow_pdf: bool = False
     use_agent_workflow_pubmed: bool = False
     use_agent_workflow_web: bool = False
     ```
  3. Add a helper method:
     ```python
     def use_agent_workflow(self, task_type: str) -> bool:
         """Check if agent workflow is enabled for a task type."""
         return getattr(self, f"use_agent_workflow_{task_type}", False)
     ```
  4. Place these fields near the existing node config section (after `node_acmg_*` fields).
  5. Write a test `tests/test_feature_flags.py` that:
     - Asserts all 3 flags default to `False`
     - Asserts `use_agent_workflow('pdf')` returns `False` by default
     - Asserts setting `USE_AGENT_WORKFLOW_PDF=true` env var flips the flag

  **Must NOT do**:
  - Do NOT remove or modify any existing Settings fields
  - Do NOT set any flag to `True` by default
  - Do NOT add any workflow logic — just the flags

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: 3 fields + 1 helper method + 1 simple test
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T3, T4) | Wave 1 | Blocks: [T11, T12] | Blocked By: [T1, T2]

  **References**:
  - Pattern: `src/config.py` — Settings(BaseSettings) class, field naming convention, section organization

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.config import settings; assert not settings.use_agent_workflow_pdf; print('OK')"` exits 0
  - [ ] `python -c "from src.config import settings; assert not settings.use_agent_workflow('pubmed'); print('OK')"` exits 0
  - [ ] `python -m pytest tests/test_feature_flags.py -v` passes

  **QA Scenarios**:
  ```
  Scenario: Feature flags default to False
    Tool: Bash
    Steps: python -c "from src.config import settings; assert not settings.use_agent_workflow_pdf and not settings.use_agent_workflow_pubmed and not settings.use_agent_workflow_web; print('ALL FALSE')"
    Expected: Prints ALL FALSE
    Evidence: .sisyphus/evidence/task-5-flags.txt
  ```

  **Commit**: YES | Message: `feat(config): add per-task-type agent workflow feature flags` | Files: src/config.py, tests/test_feature_flags.py

---

### Wave 2: Agent Migration — Low Risk

- [ ] 6. Migrate InteractionAgent to agents/interaction/

  **What to do**:
  1. Read `src/domain/agent/interaction.py` completely.
  2. Create `src/agents/interaction/node.py`:
     - Import `InteractionAgent` from `src.domain.agent.interaction`
     - Define `run_interaction_node(state: SupervisorState) -> SupervisorState`:
       - If `state.get('source')` is already set and input is clear, return state unchanged
       - Otherwise delegate to `InteractionAgent.start_interaction()` or `.respond_interaction()`
       - Write extracted task form fields back to state
     - This is a THIN WRAPPER — all logic stays in the original module
  3. Create `src/agents/interaction/prompts.py`:
     - Re-export the interaction-related prompt strings from `src.domain.agent.interaction` (the hardcoded system prompt in `_analyze_input`)
     - For now, just define `INTERACTION_SYSTEM_PROMPT` as a module-level constant copied from the original (this is the ONLY prompt copy allowed — it's a stepping stone for Wave 5)
  4. Update `src/agents/interaction/__init__.py` to export `run_interaction_node`.
  5. Add backward-compatible re-export in `src/domain/agent/interaction.py`: add nothing (it already works as-is since we're importing FROM it).
  6. Write `tests/test_agents_interaction.py` that verifies:
     - `run_interaction_node` is importable from `src.agents.interaction`
     - `InteractionAgent` is still importable from `src.domain.agent.interaction`
     - `run_interaction_node({})` doesn't crash (basic smoke test)

  **Must NOT do**:
  - Do NOT modify `src/domain/agent/interaction.py`
  - Do NOT move any code — only wrap/re-export
  - Do NOT change the InteractionAgent's session storage (Redis) behavior

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Requires understanding existing agent contract and creating faithful wrapper
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T7, T8) | Wave 2 | Blocks: [T11] | Blocked By: [T3, T4]

  **References**:
  - Pattern: `src/domain/agent/interaction.py` — InteractionAgent class, TaskFormStructured, SessionState, start_interaction(), respond_interaction(), _analyze_input()
  - Pattern: `src/state/global_state.py` — SupervisorState (from T4)
  - Type: `src/service/dtos.py` — InteractionStartRequest, InteractionRespondRequest (API contracts to preserve)

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.agents.interaction import run_interaction_node; print('OK')"` exits 0
  - [ ] `python -c "from src.domain.agent.interaction import InteractionAgent; print('COMPAT')"` exits 0
  - [ ] `python -m pytest tests/test_agents_interaction.py -v` passes

  **QA Scenarios**:
  ```
  Scenario: Interaction node importable and callable
    Tool: Bash
    Steps: python -c "from src.agents.interaction.node import run_interaction_node; result = run_interaction_node({}); print(type(result))"
    Expected: Returns dict (SupervisorState), no crash
    Evidence: .sisyphus/evidence/task-6-interaction.txt

  Scenario: Old import path still works
    Tool: Bash
    Steps: python -c "from src.domain.agent.interaction import InteractionAgent; print(InteractionAgent.__name__)"
    Expected: Prints InteractionAgent
    Evidence: .sisyphus/evidence/task-6-compat.txt
  ```

  **Commit**: YES | Message: `refactor(agents): migrate InteractionAgent to agents/interaction/` | Files: src/agents/interaction/*.py, tests/test_agents_interaction.py

---

- [ ] 7. Migrate DocumentParsingAgent to agents/parsing/

  **What to do**:
  1. Read `src/domain/agent/document_parsing.py` completely.
  2. Create `src/agents/parsing/node.py`:
     - Import `DocumentParsingAgent` from `src.domain.agent.document_parsing`
     - Define `run_parsing_node(state: SupervisorState) -> SupervisorState`:
       - Extract `file_paths` from state
       - Call `DocumentParsingAgent().parse_documents(file_paths)`
       - Write `parsing_result`, `parser_backend`, `markdown_content`, `image_paths` back to state
       - Handle `DocumentParsingResult` to state mapping
     - This is a THIN WRAPPER
  3. Create `src/agents/parsing/mineru_tool.py`:
     - Re-export `MinerUComponent` from wherever it's imported in `document_parsing.py`
     - This is a re-export, not a rewrite
  4. Update `src/agents/parsing/__init__.py` to export `run_parsing_node`.
  5. Write `tests/test_agents_parsing.py` that verifies:
     - `run_parsing_node` is importable
     - `DocumentParsingAgent` is still importable from old path
     - State mapping is correct (mock `parse_documents` return)

  **Must NOT do**:
  - Do NOT modify `src/domain/agent/document_parsing.py`
  - Do NOT change MinerU or PaddleOCR fallback behavior
  - Do NOT remove the existing `DocumentParsingState` TypedDict

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Requires understanding existing LangGraph subgraph and creating faithful state adapter
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T6, T8) | Wave 2 | Blocks: [T11] | Blocked By: [T3, T4]

  **References**:
  - Pattern: `src/domain/agent/document_parsing.py` — DocumentParsingAgent, DocumentParsingState, parse_documents(), _parse(), _collect()
  - Pattern: `src/state/global_state.py` — SupervisorState parsing-related fields
  - Pattern: `src/service/tasks.py::run_node_parsing` — How parsing result is currently consumed and logged

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.agents.parsing import run_parsing_node; print('OK')"` exits 0
  - [ ] `python -c "from src.domain.agent.document_parsing import DocumentParsingAgent; print('COMPAT')"` exits 0
  - [ ] `python -m pytest tests/test_agents_parsing.py -v` passes

  **QA Scenarios**:
  ```
  Scenario: Parsing node importable
    Tool: Bash
    Steps: python -c "from src.agents.parsing.node import run_parsing_node; print('OK')"
    Expected: Prints OK
    Evidence: .sisyphus/evidence/task-7-parsing.txt

  Scenario: Old import path preserved
    Tool: Bash
    Steps: python -c "from src.domain.agent.document_parsing import DocumentParsingAgent, DocumentParsingState; print('COMPAT')"
    Expected: Prints COMPAT
    Evidence: .sisyphus/evidence/task-7-compat.txt
  ```

  **Commit**: YES | Message: `refactor(agents): migrate DocumentParsingAgent to agents/parsing/` | Files: src/agents/parsing/*.py, tests/test_agents_parsing.py

---

- [ ] 8. Migrate LiteratureAcquisitionAgent to agents/acquisition/

  **What to do**:
  1. Read `src/domain/literature/acquisition_agent.py` completely.
  2. Create `src/agents/acquisition/node.py`:
     - Import `LiteratureAcquisitionAgent` from `src.domain.literature.acquisition_agent`
     - Define `run_acquisition_node(state: SupervisorState) -> SupervisorState`:
       - Determine source type from `state['source']`
       - For 'upload': validate file_paths exist, set `current_node='acquisition'`, mark step completed
       - For 'pubmed': delegate to `LiteratureAcquisitionAgent.plan_pubmed_request()` if it exists, or prepare pubmed-specific state
       - For 'web': delegate to `LiteratureAcquisitionAgent.plan_web_request()`
       - Write acquisition plan results back to state
     - Match the behavior of `src/service/tasks.py::run_node_acquisition`
  3. Create `src/agents/acquisition/pubmed_tool.py`: re-export PubMed service getter
  4. Create `src/agents/acquisition/firecrawl_tool.py`: re-export Firecrawl service getter
  5. Update `src/agents/acquisition/__init__.py` to export `run_acquisition_node`.
  6. Write `tests/test_agents_acquisition.py`.

  **Must NOT do**:
  - Do NOT modify `src/domain/literature/acquisition_agent.py`
  - Do NOT move the API-layer dedup logic (duplicate detection stays in `task_api.py`)
  - Do NOT change URL fingerprinting logic

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Three different source types require careful routing
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T6, T7) | Wave 2 | Blocks: [T11] | Blocked By: [T3, T4]

  **References**:
  - Pattern: `src/domain/literature/acquisition_agent.py` — LiteratureAcquisitionAgent, AcquisitionPlanItem, AcquisitionPlanningState, plan_web_request()
  - Pattern: `src/service/tasks.py::run_node_acquisition` — Current acquisition node behavior (file path validation for uploads)
  - Pattern: `src/presentation/task_api.py` — PubMed/web request orchestration (API-layer dedup — NOT moved)

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.agents.acquisition import run_acquisition_node; print('OK')"` exits 0
  - [ ] `python -c "from src.domain.literature.acquisition_agent import LiteratureAcquisitionAgent; print('COMPAT')"` exits 0
  - [ ] `python -m pytest tests/test_agents_acquisition.py -v` passes

  **QA Scenarios**:
  ```
  Scenario: Acquisition node handles upload source
    Tool: Bash
    Steps: python -c "from src.agents.acquisition.node import run_acquisition_node; state = {'source': 'upload', 'file_paths': ['/tmp/test.pdf']}; result = run_acquisition_node(state); print(result.get('current_node', 'MISSING'))"
    Expected: Prints acquisition (or similar indicator)
    Evidence: .sisyphus/evidence/task-8-acquisition.txt
  ```

  **Commit**: YES | Message: `refactor(agents): migrate LiteratureAcquisitionAgent to agents/acquisition/` | Files: src/agents/acquisition/*.py, tests/test_agents_acquisition.py

---

### Wave 3: Workflow Split — High Value

- [ ] 9. Split workflow.py → agents/extraction/ (extraction + translation + image description)

  **What to do**:
  1. Read `src/domain/agent/workflow.py` completely — focus on `translate_markdown`, `describe_images`, `extract_ps3_evidence`, `_invoke_with_tools`, `_retrieve_knowledge_context`, `build_evidence_workflow` (the translate→describe→extract portion).
  2. Read `src/domain/evidence/tools.py` completely — understand the ToolProxy pattern and `EVIDENCE_TOOLS`.
  3. Create `src/agents/extraction/node.py`:
     - Define `run_extraction_node(state: SupervisorState) -> SupervisorState`:
       - Build a `ProcessingState` from SupervisorState fields (translation input, images, etc.)
       - Instantiate `EvidenceAgent` (imported from `src.domain.agent.workflow`)
       - Call the translation, image description, and extraction steps
       - Map results back to SupervisorState
     - **CRITICAL**: Do NOT inline the EvidenceAgent logic. Import and call the existing class methods.
     - Handle the fact that translation may already be done (check `state.get('translated_markdown')`)
  4. Create `src/agents/extraction/extraction_tool.py`:
     - Re-export `EVIDENCE_TOOLS`, `get_evidence_tools`, `get_evidence_tool_map` from `src.domain.evidence.tools`
  5. Create `src/agents/extraction/validator_tool.py`:
     - Placeholder for future HGVS/HPO validation (for now, re-export the HGVS correction logic from `src/service/tasks.py` if it exists as a standalone function)
  6. Update `src/agents/extraction/__init__.py`.
  7. Write `tests/test_agents_extraction.py` that verifies:
     - Node is importable
     - Tool re-exports are identity (same objects)
     - EvidenceAgent is still importable from old path

  **Must NOT do**:
  - Do NOT copy EvidenceAgent logic into the new module
  - Do NOT modify `src/domain/agent/workflow.py`
  - Do NOT change the RAG retrieval behavior (_retrieve_knowledge_context stays inside EvidenceAgent)
  - Do NOT change the arbitration feedback loop (that goes to T10)

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Most complex module split; requires understanding LangGraph subgraph, tool binding, and ProcessingState mapping
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [T10] | Blocked By: [T6, T7, T8]

  **References**:
  - Pattern: `src/domain/agent/workflow.py` — EvidenceAgent class, translate_markdown(), describe_images(), extract_ps3_evidence(), build_evidence_workflow(), process_medical_evidence()
  - Pattern: `src/domain/evidence/tools.py` — ToolProxy, EVIDENCE_TOOLS, get_evidence_tools(), get_evidence_tool_map()
  - Pattern: `src/service/tasks.py::run_node_translation` — Translation invocation pattern
  - Pattern: `src/service/tasks.py::run_node_extraction` — Extraction invocation pattern
  - Type: `src/state/global_state.py` — SupervisorState fields for extraction

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.agents.extraction import run_extraction_node; print('OK')"` exits 0
  - [ ] `python -c "from src.agents.extraction.extraction_tool import EVIDENCE_TOOLS; print(len(EVIDENCE_TOOLS))"` prints 3 (same count as original)
  - [ ] `python -c "from src.domain.agent.workflow import EvidenceAgent; print('COMPAT')"` exits 0
  - [ ] `python -m pytest tests/test_agents_extraction.py -v` passes

  **QA Scenarios**:
  ```
  Scenario: Extraction tools are identity re-exports
    Tool: Bash
    Steps: python -c "from src.domain.evidence.tools import EVIDENCE_TOOLS as A; from src.agents.extraction.extraction_tool import EVIDENCE_TOOLS as B; assert A is B; print('IDENTITY')"
    Expected: Prints IDENTITY
    Evidence: .sisyphus/evidence/task-9-tools-identity.txt

  Scenario: Old workflow.py still fully functional
    Tool: Bash
    Steps: python -c "from src.domain.agent.workflow import EvidenceAgent; a = EvidenceAgent(); print(hasattr(a, 'process_medical_evidence'))"
    Expected: Prints True
    Evidence: .sisyphus/evidence/task-9-compat.txt
  ```

  **Commit**: YES | Message: `refactor(agents): create extraction agent wrapper around EvidenceAgent` | Files: src/agents/extraction/*.py, tests/test_agents_extraction.py

---

- [ ] 10. Split workflow.py → agents/arbitration/ (arbitration + hard logic isolation)

  **What to do**:
  1. Read `src/domain/agent/workflow.py` — focus on `arbitrate_score`, `_apply_arbitration_feedback`, `route_decision`.
  2. Read `src/domain/evidence/classifier.py` completely.
  3. Read `src/domain/evidence/evaluation_framework.py` completely.
  4. Create `src/agents/arbitration/ps3_bs3_evaluator.py`:
     - Re-export from `src.domain.evidence.classifier`:
       - `EvidenceClassifier` (the whole class)
     - Re-export from `src.domain.evidence.evaluation_framework`:
       - `calculate_oddpath`, `determine_strength_by_oddpath`, `determine_evidence_strength`
       - All 4-step evaluation functions
     - Add module docstring: "Pure-code ACMG PS3/BS3 evaluator. NO LLM involvement in threshold calculations."
  5. Create `src/agents/arbitration/rule_checker.py`:
     - Re-export the 4-step functions from `evaluation_framework.py`:
       - `evaluate_disease_mechanism_defined`
       - `evaluate_assay_validity_approved`
       - `evaluate_assay_validity_basic_controls`
       - `evaluate_assay_validity_verified_method`
       - `evaluate_assay_validity_control`
       - `evaluate_assay_contains_known_variants`
       - `count_pathogenic_benign_variants`
     - Add module docstring: "Four-step PS3/BS3 rule engine. Pure deterministic logic."
  6. Create `src/agents/arbitration/node.py`:
     - Define `run_arbitration_node(state: SupervisorState) -> SupervisorState`:
       - Build `ProcessingState` from SupervisorState
       - Call `EvidenceAgent.arbitrate_score()` (imported from workflow.py)
       - Map arbitration results back: `arbitration_confidence`, `final_evidence_strength`, `acmg_result`, `requires_human_review`
       - Apply `route_decision` logic: if confidence < 0.85, set `requires_human_review=True`
     - **CRITICAL**: Preserve the feedback loop behavior (max_iterations from config)
  7. Update `src/agents/arbitration/__init__.py`.
  8. Write `tests/test_agents_arbitration.py` that verifies:
     - All re-exports are identity
     - `run_arbitration_node` is importable
     - Threshold values unchanged (cross-reference with T2 threshold tests)
     - Classifier weighting formula unchanged: `total_score * 0.6 + field_confidence * 0.4`

  **Must NOT do**:
  - Do NOT modify `src/domain/evidence/classifier.py`
  - Do NOT modify `src/domain/evidence/evaluation_framework.py`
  - Do NOT modify `src/domain/agent/workflow.py`
  - Do NOT change ANY threshold values
  - Do NOT change the classifier weighting formula
  - Do NOT change the feedback loop max_iterations

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Most critical module for correctness — ACMG classification logic must be byte-identical
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [T11] | Blocked By: [T9]

  **References**:
  - Pattern: `src/domain/agent/workflow.py` — arbitrate_score(), _apply_arbitration_feedback(), route_decision(), ARBITRATION_SCORE_THRESHOLD, ARBITRATION_CONFIDENCE_THRESHOLD
  - Pattern: `src/domain/evidence/classifier.py` — EvidenceClassifier, oddspath_to_strength(), classify(), weighting formula (0.6/0.4)
  - Pattern: `src/domain/evidence/evaluation_framework.py` — determine_evidence_strength(), 4-step functions, calculate_oddpath()
  - Pattern: `src/domain/agent/prompts.py` — ARBITRATION_SCORE_THRESHOLD (85.0), ARBITRATION_CONFIDENCE_THRESHOLD (0.85)

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.agents.arbitration.ps3_bs3_evaluator import EvidenceClassifier; print('OK')"` exits 0
  - [ ] `python -c "from src.agents.arbitration.rule_checker import determine_evidence_strength; print('OK')"` exits 0
  - [ ] `python -c "from src.agents.arbitration import run_arbitration_node; print('OK')"` exits 0
  - [ ] `python -c "from src.domain.evidence.classifier import EvidenceClassifier as A; from src.agents.arbitration.ps3_bs3_evaluator import EvidenceClassifier as B; assert A is B; print('IDENTITY')"` prints IDENTITY
  - [ ] `python -m pytest tests/test_agents_arbitration.py -v` passes

  **QA Scenarios**:
  ```
  Scenario: Hard logic re-exports are identity
    Tool: Bash
    Steps: python -c "from src.domain.evidence.evaluation_framework import determine_evidence_strength as A; from src.agents.arbitration.rule_checker import determine_evidence_strength as B; assert A is B; print('IDENTITY')"
    Expected: Prints IDENTITY
    Evidence: .sisyphus/evidence/task-10-identity.txt

  Scenario: Threshold values unchanged
    Tool: Bash
    Steps: python -m pytest tests/test_threshold_sync.py -v
    Expected: All threshold tests still pass
    Evidence: .sisyphus/evidence/task-10-thresholds.txt
  ```

  **Commit**: YES | Message: `refactor(agents): create arbitration agent with isolated hard logic` | Files: src/agents/arbitration/*.py, tests/test_agents_arbitration.py

---

### Wave 4: Supervisor Integration

- [ ] 11. Build Supervisor Graph

  **What to do**:
  1. Read all `src/agents/*/node.py` files created in Waves 2-3.
  2. Read `src/service/tasks.py` to understand the 5-node pipeline flow, per-node retry policies (`_get_node_policy`, `_run_async_with_node_policy`, `_run_sync_with_node_policy`), and the processing_steps update pattern.
  3. Read `src/service/enum.py` for `PROCESSING_STEP_ORDER`, status helpers.
  4. Create `src/agents/supervisor.py`:
     ```python
     from langgraph.graph import StateGraph, START, END
     from src.state.global_state import SupervisorState

     def build_supervisor_graph() -> StateGraph:
         """Build the top-level ACMG pipeline supervisor graph.

         Flow: START → route_by_source → acquisition → parsing → translation
               → extraction → arbitration → finalize → END

         Conditional branches:
         - route_by_source: upload/pubmed/web determine acquisition behavior
         - post_parsing: if parsing fails → finalize_failed
         - post_arbitration: if confidence < 0.85 → human_review → finalize
         """
     ```
     - Define nodes: `route_by_source`, `acquisition`, `parsing`, `translation`, `extraction`, `arbitration`, `finalize`, `finalize_failed`, `human_review`
     - Each node calls the corresponding `run_*_node()` from `src/agents/*/node.py`
     - Each node updates `state['current_node']`, `state['processing_steps']`, and `state['node_trace']`
     - Conditional edges:
       - After `route_by_source`: branch by `state['source']` to set acquisition behavior
       - After `parsing`: if `state['parsing_result'] is None` → `finalize_failed`
       - After `arbitration`: if `state.get('requires_human_review')` → `human_review`; else → `finalize`
     - `finalize` node: handles HGVS correction, sentence alignment persistence, MinIO storage, graph sync, Redis caching, node_trace finalization
     - `finalize_failed` node: marks workflow failed, logs error
     - `human_review` node: placeholder with `interrupt_before` for future HITL
     - Use `asyncio.to_thread()` for sync operations (graph sync) inside async nodes
  5. Add `compile_supervisor() -> CompiledGraph` helper.
  6. **CRITICAL**: Preserve all side effects from `tasks.py`: HGVS correction, sentence alignment writes, MinIO artifact storage, graph sync (with asymmetric error handling per task type), Redis caching, processing_steps updates, node_trace.
  7. Write `tests/test_supervisor.py` that:
     - Verifies graph structure (node names, edge connections)
     - Verifies conditional routing logic with mock states
     - Verifies that `compile_supervisor()` returns a valid compiled graph

  **Must NOT do**:
  - Do NOT change any existing Celery task signatures
  - Do NOT modify `src/service/tasks.py` (that's T12)
  - Do NOT remove any side effects from the pipeline
  - Do NOT change error handling asymmetry (graph sync fatal for PDF, non-fatal for PubMed/Web)
  - Do NOT add streaming/WebSocket support yet

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Core architectural piece; must faithfully reproduce the current 5-node pipeline orchestration
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: [T12] | Blocked By: [T9, T10]

  **References**:
  - Pattern: `src/service/tasks.py` — process_pdf_task, process_pubmed_paper_task (full pipeline flow), run_node_* functions, _get_node_policy, _run_async_with_node_policy, _update_processing_step_status, HGVS correction, sentence alignment, MinIO storage, graph sync, Redis caching
  - Pattern: `src/service/enum.py` — PROCESSING_STEP_ORDER, default_processing_steps, normalize_processing_steps, merge_processing_step_update, derive_workflow_status
  - Pattern: `src/agents/interaction/node.py` — run_interaction_node (T6)
  - Pattern: `src/agents/acquisition/node.py` — run_acquisition_node (T8)
  - Pattern: `src/agents/parsing/node.py` — run_parsing_node (T7)
  - Pattern: `src/agents/extraction/node.py` — run_extraction_node (T9)
  - Pattern: `src/agents/arbitration/node.py` — run_arbitration_node (T10)
  - Type: `src/state/global_state.py` — SupervisorState
  - External: LangGraph StateGraph API — `add_node`, `add_edge`, `add_conditional_edges`, `compile`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -c "from src.agents.supervisor import build_supervisor_graph, compile_supervisor; g = compile_supervisor(); print(type(g))"` prints CompiledGraph type
  - [ ] `python -m pytest tests/test_supervisor.py -v` passes
  - [ ] Graph has all expected nodes: `grep -c 'add_node' src/agents/supervisor.py` returns ≥ 8

  **QA Scenarios**:
  ```
  Scenario: Supervisor graph compiles successfully
    Tool: Bash
    Steps: python -c "from src.agents.supervisor import compile_supervisor; g = compile_supervisor(); print('COMPILED'); print(sorted(g.nodes.keys()) if hasattr(g, 'nodes') else 'OK')"
    Expected: Prints COMPILED and node list
    Evidence: .sisyphus/evidence/task-11-supervisor.txt

  Scenario: Conditional routing works for failed parsing
    Tool: Bash
    Steps: python -m pytest tests/test_supervisor.py -k "test_routing_parsing_failed" -v
    Expected: Test passes — state with no parsing_result routes to finalize_failed
    Evidence: .sisyphus/evidence/task-11-routing.txt
  ```

  **Commit**: YES | Message: `feat(supervisor): add top-level LangGraph Supervisor graph` | Files: src/agents/supervisor.py, tests/test_supervisor.py

---

- [ ] 12. Integrate Supervisor into tasks.py Behind Feature Flag

  **What to do**:
  1. Read `src/service/tasks.py` completely — focus on `process_pdf_task`, `process_pubmed_paper_task`, `process_web_page_task`.
  2. Read `src/config.py` for the feature flag fields added in T5.
  3. Modify `process_pdf_task` in `src/service/tasks.py`:
     - At the top of the function, after initial setup (PaperTask creation, knowledge base init):
       ```python
       if cfg.use_agent_workflow('pdf'):
           return _run_supervisor_pipeline(
               source='upload',
               file_paths=file_paths,
               paper_task_id=paper_task_id,
               document_id=document_id,
               request_id=request_id,
               file_hash=file_hash,
           )
       # ... existing code unchanged below ...
       ```
     - Define `_run_supervisor_pipeline(...)` helper:
       - Build initial `SupervisorState` from arguments
       - Call `compile_supervisor().invoke(state)` inside a single `asyncio.run()`
       - After invoke: persist results to DB (update PaperTask, refresh TaskRequest status)
       - Return the result in the same format as current pipeline
     - Apply same pattern to `process_pubmed_paper_task` (with `cfg.use_agent_workflow('pubmed')`) and `process_web_page_task` (with `cfg.use_agent_workflow('web')`)
  4. **CRITICAL**: The `_run_supervisor_pipeline` helper must:
     - Use a single `asyncio.run()` call (fix the current multi-call pattern)
     - Preserve all PaperTask/PaperTaskLog updates
     - Preserve Redis caching
     - Preserve the Celery task return value format
  5. **CRITICAL**: Keep ALL existing code paths intact — the feature flag just adds an early-return branch
  6. Write `tests/test_supervisor_integration.py` that:
     - Verifies feature flag OFF → old code path runs (mock verification)
     - Verifies feature flag ON → supervisor path runs (mock verification)
     - Verifies both paths produce the same return value structure

  **Must NOT do**:
  - Do NOT delete any existing code in tasks.py
  - Do NOT change Celery task signatures (name, args, kwargs)
  - Do NOT change the task return value format
  - Do NOT enable feature flags by default
  - Do NOT modify any other file besides tasks.py and the test

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Modifying the production orchestration file; must preserve all existing behavior while adding new path
  - Skills: [`verification-before-completion`] — Must verify zero regressions
  - Omitted: [`test-driven-development`] — Integration, not TDD

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: [T13, T14] | Blocked By: [T11]

  **References**:
  - Pattern: `src/service/tasks.py` — process_pdf_task (full function), process_pubmed_paper_task, process_web_page_task, _run_async_with_node_policy, _run_sync_with_node_policy
  - Pattern: `src/config.py` — use_agent_workflow() helper (T5)
  - Pattern: `src/agents/supervisor.py` — compile_supervisor() (T11)
  - Pattern: `src/state/global_state.py` — SupervisorState (T4)
  - Pattern: `src/celery_app.py` — Task routing and naming conventions

  **Acceptance Criteria** (agent-executable only):
  - [ ] `grep -c 'use_agent_workflow' src/service/tasks.py` returns ≥ 3 (one per task type)
  - [ ] `grep -c '_run_supervisor_pipeline' src/service/tasks.py` returns ≥ 4 (definition + 3 calls)
  - [ ] `python -c "from src.service.tasks import process_pdf_task; print('OK')"` exits 0
  - [ ] `python -m pytest tests/test_supervisor_integration.py -v` passes
  - [ ] `python -m pytest tests/ -x` passes (zero regressions)

  **QA Scenarios**:
  ```
  Scenario: Feature flag OFF preserves existing behavior
    Tool: Bash
    Steps: python -m pytest tests/test_supervisor_integration.py -k "test_flag_off" -v
    Expected: Old code path executed, supervisor not invoked
    Evidence: .sisyphus/evidence/task-12-flag-off.txt

  Scenario: Feature flag ON routes to supervisor
    Tool: Bash
    Steps: python -m pytest tests/test_supervisor_integration.py -k "test_flag_on" -v
    Expected: Supervisor path executed
    Evidence: .sisyphus/evidence/task-12-flag-on.txt

  Scenario: Full test suite passes
    Tool: Bash
    Steps: python -m pytest tests/ -x --timeout=120
    Expected: Zero test failures
    Evidence: .sisyphus/evidence/task-12-full-suite.txt
  ```

  **Commit**: YES | Message: `feat(supervisor): integrate Supervisor into Celery tasks behind feature flag` | Files: src/service/tasks.py, tests/test_supervisor_integration.py

---

### Wave 5: Prompt Externalization

- [ ] 13. Externalize Extraction Prompts to YAML

  **What to do**:
  1. Read `src/domain/agent/prompts.py` — focus on `get_ps3_evidence_extraction_prompt`, `get_image_description_prompt`, `get_layout_fusion_prompt`, `get_translation_prompt`.
  2. Create `src/knowledge/prompts/extraction.yaml`:
     - Structure: key-value pairs where key is prompt name, value is the template string
     - Include: `ps3_evidence_extraction`, `image_description`, `layout_fusion`, `translation`
     - Use `{variable_name}` placeholders matching the current Python f-string/format variables
     - **BYTE-IDENTICAL content** — copy the exact prompt text, only change the container format
  3. Create `src/knowledge/prompts/loader.py`:
     - `load_prompt(category: str, name: str, **kwargs) -> str` that:
       - Loads `src/knowledge/prompts/{category}.yaml`
       - Returns `template.format(**kwargs)`
       - Caches loaded YAML files (module-level dict)
       - Raises `ValueError` if prompt not found or YAML is empty/malformed
  4. Update `src/domain/agent/prompts.py` — modify the extraction prompt functions to delegate to loader:
     ```python
     def get_ps3_evidence_extraction_prompt(translated_md, image_descriptions, knowledge_context=""):
         try:
             return load_prompt("extraction", "ps3_evidence_extraction",
                 translated_md=translated_md,
                 image_descriptions=image_descriptions,
                 knowledge_context=knowledge_context)
         except Exception:
             # Fallback to hardcoded (safety net during migration)
             return _original_get_ps3_evidence_extraction_prompt(translated_md, image_descriptions, knowledge_context)
     ```
     - Rename original functions with `_original_` prefix as fallback
  5. Write `tests/test_prompt_externalization.py` that:
     - Asserts YAML-loaded prompt == original hardcoded prompt for same inputs
     - Asserts loader raises on missing prompt
     - Asserts loader raises on empty YAML

  **Must NOT do**:
  - Do NOT edit prompt text content (byte-identical)
  - Do NOT remove the hardcoded fallback
  - Do NOT change prompt function signatures
  - Do NOT externalize arbitration prompts yet (that's T14)

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Large prompt text extraction requiring byte-identical preservation
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T14) | Wave 5 | Blocks: [] | Blocked By: [T11, T12]

  **References**:
  - Pattern: `src/domain/agent/prompts.py` — get_ps3_evidence_extraction_prompt, get_image_description_prompt, get_layout_fusion_prompt, get_translation_prompt (exact function signatures and format variables)

  **Acceptance Criteria** (agent-executable only):
  - [ ] `ls src/knowledge/prompts/extraction.yaml` exists
  - [ ] `python -c "from src.knowledge.prompts.loader import load_prompt; print('OK')"` exits 0
  - [ ] `python -m pytest tests/test_prompt_externalization.py -v` passes
  - [ ] Prompt equality test passes: YAML output == original function output for same inputs

  **QA Scenarios**:
  ```
  Scenario: Externalized prompt matches original
    Tool: Bash
    Steps: python -m pytest tests/test_prompt_externalization.py -k "test_extraction_prompt_equality" -v
    Expected: YAML-loaded prompt byte-identical to hardcoded
    Evidence: .sisyphus/evidence/task-13-equality.txt

  Scenario: Loader fails gracefully on missing prompt
    Tool: Bash
    Steps: python -m pytest tests/test_prompt_externalization.py -k "test_missing_prompt" -v
    Expected: ValueError raised
    Evidence: .sisyphus/evidence/task-13-error.txt
  ```

  **Commit**: YES | Message: `refactor(prompts): externalize extraction prompts to YAML` | Files: src/knowledge/prompts/extraction.yaml, src/knowledge/prompts/loader.py, src/domain/agent/prompts.py, tests/test_prompt_externalization.py

---

- [ ] 14. Externalize Arbitration Prompts to YAML

  **What to do**:
  1. Read `src/domain/agent/prompts.py` — focus on `get_arbitration_prompt`, `get_feedback_refinement_prompt`, `get_ps3_evidence_feedback_prompt`.
  2. Create `src/knowledge/prompts/arbitration.yaml`:
     - Include: `arbitration`, `feedback_refinement`, `ps3_evidence_feedback`
     - Include threshold constants section: `ARBITRATION_SCORE_THRESHOLD: 85.0`, `ARBITRATION_CONFIDENCE_THRESHOLD: 0.85`
     - **BYTE-IDENTICAL content**
  3. Update `src/domain/agent/prompts.py` — modify arbitration prompt functions to delegate to loader with fallback (same pattern as T13).
  4. Create `src/knowledge/prompts/acmg_rules.yaml`:
     - Extract the `EVIDENCE_FIELD_RULES` constant
     - Extract the OddsPath threshold table that appears in prompt text
     - This is REFERENCE documentation, not loaded at runtime (yet)
  5. Write `tests/test_arbitration_prompts.py` that:
     - Asserts YAML-loaded prompt == original hardcoded prompt
     - Asserts threshold values in YAML match code constants
     - Asserts EVIDENCE_FIELD_RULES in YAML matches code constant

  **Must NOT do**:
  - Do NOT edit prompt text content
  - Do NOT remove the hardcoded fallback
  - Do NOT change threshold values
  - Do NOT change EVIDENCE_FIELD_RULES content

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Same pattern as T13 but for arbitration-specific prompts
  - Skills: [] — No special skills needed

  **Parallelization**: Can Parallel: YES (with T13) | Wave 5 | Blocks: [] | Blocked By: [T11, T12]

  **References**:
  - Pattern: `src/domain/agent/prompts.py` — get_arbitration_prompt, get_feedback_refinement_prompt, get_ps3_evidence_feedback_prompt, EVIDENCE_FIELD_RULES, ARBITRATION_SCORE_THRESHOLD, ARBITRATION_CONFIDENCE_THRESHOLD
  - Pattern: `src/knowledge/prompts/loader.py` — load_prompt() function (created in T13)

  **Acceptance Criteria** (agent-executable only):
  - [ ] `ls src/knowledge/prompts/arbitration.yaml src/knowledge/prompts/acmg_rules.yaml` both exist
  - [ ] `python -m pytest tests/test_arbitration_prompts.py -v` passes
  - [ ] Prompt equality test passes

  **QA Scenarios**:
  ```
  Scenario: Arbitration prompt matches original
    Tool: Bash
    Steps: python -m pytest tests/test_arbitration_prompts.py -k "test_arbitration_prompt_equality" -v
    Expected: YAML-loaded prompt byte-identical to hardcoded
    Evidence: .sisyphus/evidence/task-14-equality.txt

  Scenario: Threshold values in YAML match code
    Tool: Bash
    Steps: python -m pytest tests/test_arbitration_prompts.py -k "test_threshold_values" -v
    Expected: YAML thresholds match prompts.py constants
    Evidence: .sisyphus/evidence/task-14-thresholds.txt
  ```

  **Commit**: YES | Message: `refactor(prompts): externalize arbitration prompts to YAML` | Files: src/knowledge/prompts/arbitration.yaml, src/knowledge/prompts/acmg_rules.yaml, src/domain/agent/prompts.py, tests/test_arbitration_prompts.py

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Full Pipeline Smoke Test — deep (+ manual QA via curl/pytest)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Wave 0: `test(safety): add golden fixtures and threshold sync tests`
- Wave 1: `refactor(skeleton): create state/agents/tools/knowledge packages`
- Wave 2: `refactor(agents): migrate interaction/parsing/acquisition agents`
- Wave 3: `refactor(agents): split workflow.py into extraction and arbitration`
- Wave 4: `feat(supervisor): add top-level Supervisor graph with feature flag`
- Wave 5: `refactor(prompts): externalize extraction/arbitration prompts to YAML`

## Success Criteria
1. `python -m pytest tests/ -x` — zero regressions
2. All 3 Celery tasks produce identical outputs with feature flag ON vs OFF
3. Golden fixture comparison passes for EvidenceOutput
4. Threshold sync test passes
5. All old import paths work (backward compat)
6. All new import paths work (new architecture)
7. Feature flag toggles cleanly between old and new orchestration
