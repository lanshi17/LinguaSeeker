# Target-Aware Source-Visible Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-06-20
**Goal:** Add a production Phase 2 extraction variant that improves fused-75 source-visible recall and F1 by scoping catalog prompts to target-aware eligible fields before LLM extraction.

**Architecture:** Keep the current Phase 2 topology. Add deterministic field eligibility logic inside the `extract_evidence` vertical slice, wire it into `CatalogExtractionStage`, expand target block selection conservatively, and evaluate through the existing fused75 dev/test benchmark loop. Do not change adjudication labels or scorer semantics.

**Tech Stack:** Python 3.12, Pydantic/dataclasses, pytest, Ruff, uv, existing fused75 benchmark tooling.

---

## Phase 1: Field Eligibility Core

### Task 1.1: Add typed eligibility contracts and policy

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/field_eligibility.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_field_eligibility.py`

**Step 1: Write failing tests**

Cover:
- no target returns all non-curation extractable field IDs,
- target always includes `A.gene_symbol`, `A.gene_disease_relationship`, and `B.disease_diagnosis`,
- target variant cues include variant fields,
- functional cues include functional fields,
- population cues include population/frequency fields,
- returned contract is typed and deterministic.

Example test shape:

```python
def test_target_policy_always_includes_core_identity_fields() -> None:
    policy = FieldEligibilityPolicy()
    target = ExtractionTarget(gene_symbol="ABCA4", disease_name="ABCA4-related retinopathy")

    decision = policy.decide(extraction_target=target, evidence_map_summary="", selected_text="")

    assert "A.gene_symbol" in decision.allowed_field_ids
    assert "A.gene_disease_relationship" in decision.allowed_field_ids
    assert "B.disease_diagnosis" in decision.allowed_field_ids
```

**Step 2: Run tests to verify failure**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_field_eligibility.py -v
```

Expected: import failure for `field_eligibility`.

**Step 3: Implement minimal policy**

Use dataclasses, not bare dict returns:

```python
@dataclass(frozen=True)
class FieldEligibilityDecision:
    allowed_field_ids: frozenset[str]
    reasons: tuple[str, ...]
```

Add `FieldEligibilityPolicy.decide(...) -> FieldEligibilityDecision`.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_field_eligibility.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/field_eligibility.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_field_eligibility.py
```

## Phase 2: Catalog Prompt Scoping

### Task 2.1: Wire field eligibility into catalog extraction

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog_extraction.py`

**Step 1: Write failing tests**

Add tests that:
- when `ExtractionTarget` is absent, provider calls still cover the existing non-curation catalog groups,
- when `ExtractionTarget` is present, prompts do not contain disallowed field IDs,
- empty groups are skipped rather than sent to the LLM,
- stage names remain stable for non-empty groups.

**Step 2: Run failing focused tests**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog_extraction.py -v
```

**Step 3: Implement scoped catalog groups**

In `CatalogExtractionStage`, compute `FieldEligibilityDecision` after block selection and before prompt construction. Filter each existing catalog tuple by `allowed_field_ids`; skip empty tuples.

Do not change the public return type of `run()` or `run_async()`.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog_extraction.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py
```

### Task 2.2: Update catalog prompt wording for eligible fields

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Write failing prompt test**

Assert that `get_catalog_extraction_prompt(...)` says:
- the catalog is pre-scoped,
- fields outside the catalog must not be invented,
- `not_found` is still required for listed fields.

**Step 2: Run failing test**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_declares_pre_scoped_eligible_fields -v
```

**Step 3: Implement wording only**

Keep all existing target, source-grounding, relationship, and disease-boundary guidance.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
```

## Phase 3: Recall-First Block Expansion

### Task 3.1: Include bounded neighbor blocks around target evidence

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`

**Step 1: Write failing tests**

Cover:
- selected target-gene block includes one adjacent block when under `max_blocks`,
- neighbor expansion never exceeds `max_blocks`,
- no target preserves current empty selection behavior,
- selected indices remain sorted by priority and stable by block index.

**Step 2: Run failing tests**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py -v
```

**Step 3: Implement bounded neighbor expansion**

Add a small helper such as `_expand_with_neighbors(...) -> tuple[SelectedBlock, ...]`. Neighbor blocks should receive a lower score and reason `target_neighbor`.

**Step 4: Verify**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py
```

## Phase 4: Fused75 Variant Benchmark

### Task 4.1: Add a production-behavior variant config and dev artifact run

**Files:**
- Create: `benchmark/optimization/fused75/target_aware_source_visible_dev_config.json`
- Output: `benchmark/optimization/fused75/reports/target_aware_source_visible_dev_full.json`
- Output: new Phase 2 artifacts for dev entries, only if generated by the modified production pipeline
- Modify: `progress.txt`
- Modify: `lesson.md` if the run exposes environment or artifact-root issues

**Step 1: Run focused production tests**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

**Step 2: Generate dev artifacts through live Phase 2**

Use the existing artifact batch runner. Confirm the active backend server cwd before selecting `--pipeline-root`.

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.phase2_artifact_batch \
  --entries fused_000 fused_001 fused_002 fused_003 fused_004 fused_005 fused_006 fused_007 fused_008 fused_009 \
  --poll-interval-s 5 \
  --max-poll-attempts 120 \
  --concurrency 1 \
  --write
```

**Step 3: Run dev variant report**

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.run_variant \
  --split dev \
  --config ../benchmark/optimization/fused75/target_aware_source_visible_dev_config.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/target_aware_source_visible_dev_full.json
```

**Step 4: Build error taxonomy and leaderboard**

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.error_taxonomy \
  --split dev \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/target_aware_source_visible_dev_error_taxonomy.json

PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.build_leaderboard \
  --reports-dir ../benchmark/optimization/fused75/reports \
  --json-output ../benchmark/optimization/fused75/reports/leaderboard_current.json \
  --markdown-output ../benchmark/optimization/fused75/reports/leaderboard_current.md
```

**Acceptance:** Dev result is explainable. If dev recall drops, stop and revise field eligibility before any test checkpoint.

## Phase 5: Held-Out Test Checkpoint

### Task 5.1: Run frozen test only if dev passes the gate

**Files:**
- Create: `benchmark/optimization/fused75/target_aware_source_visible_test_config.json`
- Output: `benchmark/optimization/fused75/reports/target_aware_source_visible_test_checkpoint.json`
- Modify: `benchmark/optimization/fused75/reports/leaderboard_current.json`
- Modify: `benchmark/optimization/fused75/reports/leaderboard_current.md`

**Gate before starting:**
- Dev source-visible F1 beats `0.5138`, or recall improves enough to justify a precision tradeoff.
- Artifact coverage is `10/10`.
- No adjudication labels changed.

**Step 1: Run test checkpoint**

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.run_variant \
  --split test \
  --config ../benchmark/optimization/fused75/target_aware_source_visible_test_config.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/target_aware_source_visible_test_checkpoint.json \
  --checkpoint
```

**Step 2: Refresh leaderboard**

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.build_leaderboard \
  --reports-dir ../benchmark/optimization/fused75/reports \
  --json-output ../benchmark/optimization/fused75/reports/leaderboard_current.json \
  --markdown-output ../benchmark/optimization/fused75/reports/leaderboard_current.md
```

**Acceptance:** Test source-visible F1 beats `0.4340`, with recall target `>= 0.45` preferred.

## Phase 6: Final Decision

### Task 6.1: Document and decide promotion

**Files:**
- Create: `docs/active/2026-06-20-target-aware-source-visible-extraction-results.md`
- Modify: `progress.txt`
- Modify: `lesson.md` if any failed variants or wrong assumptions occurred

**Step 1: Record final metrics**

Include dev/test precision, recall, F1, source-visible F1, artifact coverage, runtime seconds, LLM calls, and token counts.

**Step 2: State promotion decision**

Promote only if held-out test beats `0.4340` and the change is production behavior, not benchmark-only scoring.

**Step 3: Final verification**

```bash
cd backend
PYTHONPATH=.. uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/benchmark/optimization -v
uv run ruff check src/core/cross_lingual_process_and_extract_evidence/extract_evidence tests/core/cross_lingual_process_and_extract_evidence/extract_evidence ../benchmark/optimization tests/benchmark/optimization
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.validate_adjudication \
  --split-manifest ../benchmark/optimization/fused75/fused75_split_manifest.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication
```

**Step 4: Commit**

Use Conventional Commit, likely:

```bash
git commit -m "perf(extract-evidence): add target-aware source-visible extraction"
```

## Do Not Do

- Do not tune on frozen test.
- Do not edit frozen adjudication labels.
- Do not add a parallel Phase 2 pipeline.
- Do not rely on benchmark-side field filtering as the final claimed improvement.
- Do not use system `python` or `pip`; use `uv`.
