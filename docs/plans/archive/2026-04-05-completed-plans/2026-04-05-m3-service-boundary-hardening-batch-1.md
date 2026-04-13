# M3 Service Boundary Hardening Batch 1 Archive

> **Archive Status:** `COMPLETED`
> **Source Plan:** `docs/plans/2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
> **Archived On:** `2026-04-05`

## Scope

This archive records the completed M3 slice from the active M3/M4 implementation plan. The finished items correspond to Task 1 through Task 3 from the source plan.

## Completed Tasks

### Task 1: Align the application-layer parser compatibility contract

Completed:
1. Added `tests/unit/application/test_document_service.py`.
2. Updated `src/application/dtos/document_dto.py` so parser artifact fields are first-class while legacy ZIP/MinIO fields remain optional.
3. Updated `src/application/services/document_service.py` to accept the current `parse_documents(...)` parsing contract and map `DocumentParsingResult` artifacts into the application DTO.

Verification:
1. `uv run pytest -q tests/unit/application/test_document_service.py tests/unit/domain/test_document_parser.py`
2. Result: `4 passed`

### Task 2: Harden the translation-service contract with explicit warning/alignment outputs

Completed:
1. Added runtime and golden-fixture assertions for `warning_codes` and `alignment_count`.
2. Extended `src/domain/models.py::PipelineResult` with `warning_codes` and `alignment_count`.
3. Updated `src/services/task_manager.py` to surface translation warnings and alignment counts in the returned pipeline payload.
4. Updated `tests/fixtures/golden_pipeline_result.json` to match the active contract.

Verification:
1. `uv run pytest -q tests/unit/test_task_manager_alignment.py tests/unit/test_task_manager_minio_outputs.py tests/unit/test_tasks.py tests/test_golden_fixtures.py`
2. Result: `50 passed`

### Task 3: Harden the extraction-service contract with explicit evidence source output

Completed:
1. Added `evidence_sources` assertions in extraction-node tests, task payload tests, and golden fixtures.
2. Extended `src/domain/models.py::EvidenceOutput` with `evidence_sources`.
3. Preserved `evidence_sources` through `src/agents/extraction/node.py` and `src/domain/agent/workflow.py`.
4. Updated `tests/fixtures/golden_evidence_output.json` and `tests/fixtures/golden_pipeline_result.json`.

Verification:
1. `uv run pytest -q tests/test_agents_extraction.py tests/unit/test_tasks.py tests/test_golden_fixtures.py`
2. Result: `49 passed`

## Remaining Work

The remaining open work from the source plan stays active in `docs/plans/2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`:

1. Task 4: trace-chain contract for pipeline result and task-status API
2. Task 5: release-gate calculation service for the 100-paper acceptance contract
3. Task 6: release-report CLI/reporting surface and acceptance manifest scaffolding
4. Task 7: rollout docs closeout and focused M3/M4 regression suite
