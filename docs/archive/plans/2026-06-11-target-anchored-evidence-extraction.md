# Target Anchored Evidence Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make ACMG evidence extraction hypothesis-driven by carrying a target gene-disease context through Phase 2 and Phase 3, rejecting context contamination, and separating primary evidence from phenotype/comparator/context mentions.

**Architecture:** Add a typed `ExtractionTarget` contract to the existing Phase 2 vertical slice, propagate it through the API request, `PipelineGraphState`, `TrackDocument`, prompts, deterministic validation, Phase 2 output, Phase 3 standardization input, and target-aware `entity_scope_hash` generation. Keep orchestrators thin: adapters pass target context, extraction stages enforce target and role rules, and Phase 3 persistence uses target identity for canonical scope isolation. No database migration is planned; `context_contamination` stays run-level and is not eligible for canonical evidence.

**Tech Stack:** Python 3.12, `uv`, pytest, Pydantic v2, LangGraph, SQLAlchemy ORM, loguru, ClinGen layer-3 benchmark utilities.

---

**Status:** completed
**Created:** 2026-06-11
**Completed:** 2026-06-11
**PR:** -

## Context

Current extraction is document-driven: a document goes in, and the LLM extracts any gene/disease/variant content it sees. The target gene-disease hypothesis is not represented in `TrackDocument`, `EvidenceExtractionState`, `PipelineGraphState`, or Phase 3 `StandardizationInput`. Because `entity_scope_hash` is currently derived from matched entities only, the same document extracted for different hypotheses can still collide when the target was never part of extraction or canonical scope.

Old-version check completed: `backend/.old_version/src/domain/agent/prompts.py` contains useful exhaustive gene/disease prompt guidance, but no reusable implementation that carries a target hypothesis through extraction, validation, and canonical scope. Reuse the prompt ideas only.

Read these files before editing:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- `backend/src/agents/contracts.py`
- `backend/src/agents/phase_2_adapter.py`
- `backend/src/api/v1/pipeline.py`
- `backend/src/core/standardize_entities_and_align_knowledge/adapters.py`
- `backend/src/core/standardize_entities_and_align_knowledge/contracts.py`
- `backend/src/core/standardize_entities_and_align_knowledge/normalizers.py`
- `backend/src/core/standardize_entities_and_align_knowledge/repositories.py`
- `benchmark/layer3/evaluate.py`

## Success Criteria

- ABCA3 target runs reject CFTR as `A.gene_symbol` with status `context_contamination`.
- Gene list strings such as `"['ABCA3', 'CFTR']"` are corrected to `ABCA3` only when the target gene is present.
- AARS2 syndrome/subtype findings such as COXPD8/LKENP are preserved as phenotype evidence but do not enter primary `evidence_items` or ACMG scoring.
- Comparator/background diagnoses such as Anti-NF155 autoimmune nodopathy are discarded with audit metadata and do not enter canonical evidence.
- `entity_scope_hash` differs for the same source span when the target gene-disease pair differs.
- ClinGen layer-3 benchmark requests send the expected target from ground truth.
- Focused tests pass through `uv`; no system `pip` is used.

## Task 1: Add Target And Role Contracts

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py`

**Step 1: Write the failing tests**

Add imports in `test_contracts.py`:

```python
    EvidenceRole,
    ExtractionTarget,
```

Append:

```python
def test_extraction_target_contract_normalizes_scope_identity() -> None:
    target = ExtractionTarget(
        gene_symbol=" abca3 ",
        disease_name=" Interstitial lung disease due to ABCA3 deficiency ",
        variant_hgvs_p=" p.Q215* ",
        clingen_entry_id="CGGV:0001",
    )

    assert target.gene_symbol == "ABCA3"
    assert target.disease_name == "Interstitial lung disease due to ABCA3 deficiency"
    assert target.scope_key == (
        "gene=ABCA3|disease=interstitial lung disease due to abca3 deficiency|"
        "variant_p=p.Q215*|clingen=CGGV:0001"
    )


def test_track_document_and_result_carry_extraction_target() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="ABCA3 case",
        page_spans=[],
        extraction_target=target,
    )
    result = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=Track.ORIGINAL,
        extraction_target=target,
    )

    assert doc.extraction_target == target
    assert result.extraction_target == target


def test_evidence_item_defaults_to_primary_role() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="ABCA3",
        confidence=0.9,
    )

    assert item.evidence_role == EvidenceRole.PRIMARY
    assert EvidenceRole.PHENOTYPE.value == "phenotype"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py::test_extraction_target_contract_normalizes_scope_identity -v
```

Expected: FAIL with missing `ExtractionTarget`.

**Step 3: Write minimal implementation**

In `contracts.py`, add:

```python
import re
```

After `Track`, add:

```python
_SPACE_RE = re.compile(r"\s+")


class ExtractionTarget(BaseModel):
    """Target gene-disease hypothesis for extraction."""

    gene_symbol: str
    disease_name: str
    variant_hgvs_p: str = ""
    clingen_entry_id: str = ""

    @model_validator(mode="after")
    def normalize_target_fields(self) -> "ExtractionTarget":
        self.gene_symbol = _SPACE_RE.sub(" ", self.gene_symbol.strip()).upper()
        self.disease_name = _SPACE_RE.sub(" ", self.disease_name.strip())
        self.variant_hgvs_p = _SPACE_RE.sub(" ", self.variant_hgvs_p.strip())
        self.clingen_entry_id = _SPACE_RE.sub(" ", self.clingen_entry_id.strip())
        if not self.gene_symbol:
            raise ValueError("gene_symbol is required")
        if not self.disease_name:
            raise ValueError("disease_name is required")
        return self

    @property
    def scope_key(self) -> str:
        return "|".join([
            f"gene={self.gene_symbol}",
            f"disease={self.disease_name.casefold()}",
            f"variant_p={self.variant_hgvs_p}",
            f"clingen={self.clingen_entry_id}",
        ])


class EvidenceRole(str, Enum):
    PRIMARY = "primary"
    PHENOTYPE = "phenotype"
    COMPARATOR = "comparator"
    CONTEXT = "context"
```

Extend:

```python
class TrackDocument(BaseModel):
    ...
    extraction_target: ExtractionTarget | None = None


class EvidenceStatus(str, Enum):
    ...
    CONTEXT_CONTAMINATION = "context_contamination"


class EvidenceItem(BaseModel):
    ...
    evidence_role: EvidenceRole = EvidenceRole.PRIMARY


class QualityReport(BaseModel):
    ...
    context_contamination_count: int = 0


class EvidenceExtractionResult(BaseModel):
    ...
    extraction_target: ExtractionTarget | None = None
    phenotype_evidence: list[EvidenceItem] = Field(default_factory=list)
    discarded_evidence: list[EvidenceItem] = Field(default_factory=list)


class EvidenceExtractionState(BaseModel):
    ...
    phenotype_evidence: list[EvidenceItem] = Field(default_factory=list)
    discarded_evidence: list[EvidenceItem] = Field(default_factory=list)
```

Add `"context_contamination"` to `QualityIssue.issue_type`.

**Step 4: Run test**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py
git commit -m "feat: add extraction target contracts"
```

## Task 2: Carry Target Through Pipeline Request And State

**Files:**

- Modify: `backend/src/agents/contracts.py`
- Modify: `backend/src/api/v1/pipeline.py`
- Test: `backend/tests/agents/test_contracts.py`
- Test: `backend/tests/api/test_pipeline_api.py`

**Step 1: Write the failing tests**

Append to `test_contracts.py`:

```python
def test_pipeline_graph_state_carries_extraction_target() -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        ExtractionTarget,
    )

    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        extraction_target=target,
    )

    assert state.extraction_target == target
    assert state.model_dump()["extraction_target"]["gene_symbol"] == "ABCA3"
```

Append to `test_pipeline_api.py`:

```python
@pytest.mark.asyncio
async def test_post_pipeline_run_accepts_extraction_target(async_client: AsyncClient):
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.start = MagicMock(return_value=MagicMock())
        mock_runner.is_running_for_source = MagicMock(return_value=False)
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "filename": "abca3.md",
                "pre_parsed_markdown": "ABCA3 and CFTR are discussed.",
                "target": {
                    "gene_symbol": "ABCA3",
                    "disease_name": "ABCA3 deficiency",
                    "variant_hgvs_p": "p.Q215*",
                    "clingen_entry_id": "CGGV:0001",
                },
                "mode": "full",
            },
        )

    assert response.status_code == 202
    state = mock_runner.start.call_args[0][0]
    assert state.extraction_target.gene_symbol == "ABCA3"
    assert "gene=ABCA3" in state.source_key
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend
uv run pytest tests/agents/test_contracts.py::test_pipeline_graph_state_carries_extraction_target \
  tests/api/test_pipeline_api.py::test_post_pipeline_run_accepts_extraction_target -v
```

Expected: FAIL because state/request models do not carry target context.

**Step 3: Write minimal implementation**

In `agents/contracts.py`, import and add to `PipelineGraphState`:

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ExtractionTarget,
)

extraction_target: ExtractionTarget | None = None
```

In `api/v1/pipeline.py`, import `ExtractionTarget` and add to `PipelineRunRequest`:

```python
extraction_target: ExtractionTarget | None = Field(default=None, alias="target")
```

Add helper:

```python
def _build_source_key(body: PipelineRunRequest) -> str:
    base_key = body.filename or (body.query or "")
    if body.extraction_target is None:
        return base_key
    return f"{base_key}|{body.extraction_target.scope_key}"
```

Use it in `start_pipeline_run()`:

```python
source_key = _build_source_key(body)
...
extraction_target=body.extraction_target,
```

> **Note on source_key dedup:** Appending `scope_key` to `source_key` makes the duplicate-run detection target‑aware — the same filename submitted with different targets is treated as a distinct run (no 409 conflict). This is the correct behavior: the same document extracted for different hypotheses should produce separate runs.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/agents/test_contracts.py tests/api/test_pipeline_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/agents/contracts.py backend/src/api/v1/pipeline.py \
  backend/tests/agents/test_contracts.py backend/tests/api/test_pipeline_api.py
git commit -m "feat: carry extraction target in pipeline state"
```

## Task 3: Propagate Target Through Phase 2 Documents And Results

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Modify: `backend/src/agents/phase_2_adapter.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py`
- Test: `backend/tests/agents/test_phase_2_adapter.py`

**Step 1: Write the failing tests**

Append to `test_api_contracts.py`:

```python
def test_build_dual_documents_accepts_extraction_target(tmp_path) -> None:
    payload = {
        "metadata": {"doc_id": "doc-target", "source_language": "en"},
        "formatted_text": "ABCA3 and CFTR are both mentioned.",
        "blocks": [],
    }
    (tmp_path / "original.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "translated.json").write_text(json.dumps(payload), encoding="utf-8")

    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    docs = EvidenceExtractionService.build_dual_documents_from_output_dir(tmp_path, target)

    assert docs.original.extraction_target == target
    assert docs.translated.extraction_target == target
```

Update `test_phase_2_adapter_success` to set `sample_state.extraction_target` and assert:

```python
mock_build.assert_called_once()
assert mock_build.call_args.args[1] == sample_state.extraction_target
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py::test_build_dual_documents_accepts_extraction_target \
  tests/agents/test_phase_2_adapter.py::test_phase_2_adapter_success -v
```

Expected: FAIL because `build_dual_documents_from_output_dir()` accepts only one argument.

**Step 3: Write minimal implementation**

In `api.py`, accept and pass `ExtractionTarget | None`:

```python
@staticmethod
def build_dual_documents_from_output_dir(
    output_dir: str | Path,
    extraction_target: ExtractionTarget | None = None,
) -> DualTrackDocuments:
    ...
    original = _build_track_document_from_json(base / "original.json", Track.ORIGINAL, extraction_target)
    translated = _build_track_document_from_json(base / "translated.json", Track.TRANSLATED, extraction_target)
```

Return target and routed evidence in `run()`:

```python
return EvidenceExtractionResult(
    ...
    extraction_target=document.extraction_target,
    phenotype_evidence=state.phenotype_evidence,
    discarded_evidence=state.discarded_evidence,
)
```

In `phase_2_adapter.py`:

```python
dual_documents = await asyncio.to_thread(
    EvidenceExtractionService.build_dual_documents_from_output_dir,
    cross_lingual_output.output_dir,
    state.extraction_target,
)
```

Include target in summary:

```python
"target_gene": state.extraction_target.gene_symbol if state.extraction_target else None,
```

**Step 4: Run focused tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py \
  tests/agents/test_phase_2_adapter.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py \
  backend/src/agents/phase_2_adapter.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py \
  backend/tests/agents/test_phase_2_adapter.py
git commit -m "feat: propagate extraction target through phase 2"
```

## Task 4: Anchor Prompts To Target And Evidence Role

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Write the failing tests**

Append to `test_prompts.py`:

```python
def test_catalog_prompt_declares_target_and_strict_entity_rules() -> None:
    target = ExtractionTarget(
        gene_symbol="ABCA3",
        disease_name="interstitial lung disease due to ABCA3 deficiency",
    )

    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="ABCA3 and CFTR are mentioned.",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="Genes: ABCA3, CFTR",
        extraction_target=target,
    )

    assert "TARGET GENE: ABCA3" in prompt
    assert "TARGET DISEASE: interstitial lung disease due to ABCA3 deficiency" in prompt
    assert "Extract evidence ONLY for the target gene-disease pair" in prompt
    assert "Other genes mentioned for comparison" in prompt
    assert "gene_symbol field MUST be a single string" in prompt
    assert "evidence_role" in prompt
    assert '"primary"' in prompt
    assert '"phenotype"' in prompt
    assert '"comparator"' in prompt
    assert '"context"' in prompt
```

**Step 2: Run test to verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py::test_catalog_prompt_declares_target_and_strict_entity_rules -v
```

Expected: FAIL because prompt builders do not accept `extraction_target`.

**Step 3: Write minimal implementation**

In `prompts.py`, add:

```python
def _target_prompt_section(extraction_target: ExtractionTarget | None) -> str:
    if extraction_target is None:
        return "TARGET: Not provided."
    return f"""TARGET GENE: {extraction_target.gene_symbol}
TARGET DISEASE: {extraction_target.disease_name}
TARGET VARIANT P: {extraction_target.variant_hgvs_p or "not specified"}
CLINGEN ENTRY: {extraction_target.clingen_entry_id or "not specified"}"""
```

Add optional `extraction_target` to the **catalog extraction prompt builder only** (`get_catalog_extraction_prompt`). Leave `get_evidence_map_prompt` and `get_special_evidence_prompt` unchanged — the evidence map scan is about detecting *any* relevant content (pre-target), and the special-evidence pass operates on already-filtered items. Insert this block near the top of the catalog prompt:

```text
You are extracting evidence for a specific gene-disease pair.

{_target_prompt_section(extraction_target)}

STRICT TARGET RULES:
1. Extract evidence ONLY for the target gene-disease pair above when a target is provided.
2. Other genes mentioned for comparison, controls, family history, or differential diagnosis are context; do NOT extract them as primary findings.
3. If the document discusses multiple diseases, extract ONLY evidence relevant to the target disease as primary evidence.
4. The A.gene_symbol field MUST be a single string, not a list.

For each evidence item, assign evidence_role:
- "primary": directly supports or describes the TARGET gene-disease pair
- "phenotype": syndrome, subtype, HPO term, or downstream manifestation caused by the target disease
- "comparator": disease/gene mentioned only for differential diagnosis, comparison, controls, or exclusion
- "context": background information not specific to this target
```

Pass `document.extraction_target` from `CatalogExtractionStage` only, including in the `_max_group_overhead` calculation.

**Step 4: Run prompt tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
git commit -m "feat: anchor extraction prompts to target"
```

## Task 5: Route Non-Primary Evidence Roles

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/role_routing.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_role_routing.py`

**Important: graph ordering rationale**

Role routing must run **after** group assignment and **before** value normalization. Reason:
- `GroupAssigner` currently sees ALL items (primary + non-primary) to build group IDs. Moving it before role routing preserves this existing behavior — non-primary items get group IDs before being separated.
- Value normalization (`AcmegEvidenceValueNormalizer`) should only normalize primary evidence items, since non-primary items (phenotype, comparator, context) are routed to separate lists and do not enter the primary evidence flow.
- This avoids reordering the existing graph edges: `group_assignment → role_routing → value_normalization` fits naturally.

**No reordering needed.** The current edge sequence is `catalog → special → group_assignment → value_normalization → source_grounding → chain_assembly → quality_gate`. Role routing is inserted between `group_assignment` and `value_normalization`.

**Step 1: Write the failing test**

Create `test_role_routing.py`:

```python
"""Tests for evidence role routing."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceRole,
    EvidenceStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.role_routing import (
    EvidenceRoleRouter,
)


def _item(field_id: str, value: str, role: EvidenceRole) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        evidence_role=role,
    )


def test_role_router_keeps_only_primary_for_extraction_flow() -> None:
    primary, phenotype, discarded = EvidenceRoleRouter().route([
        _item("A.gene_symbol", "AARS2", EvidenceRole.PRIMARY),
        _item("B.disease_diagnosis", "COXPD8", EvidenceRole.PHENOTYPE),
        _item("B.disease_diagnosis", "Anti-NF155 autoimmune nodopathy", EvidenceRole.COMPARATOR),
        _item("A.gene_symbol", "CFTR", EvidenceRole.CONTEXT),
    ])

    assert [item.value for item in primary] == ["AARS2"]
    assert [item.value for item in phenotype] == ["COXPD8"]
    assert [item.value for item in discarded] == [
        "Anti-NF155 autoimmune nodopathy",
        "CFTR",
    ]
```

**Step 2: Run test to verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_role_routing.py -v
```

Expected: FAIL because `EvidenceRoleRouter` does not exist.

**Step 3: Write minimal implementation**

Create `stages/role_routing.py`:

```python
"""Role routing stage — separates primary evidence from phenotype/comparator/context."""
from __future__ import annotations

from loguru import logger

from ..contracts import EvidenceItem, EvidenceRole


class EvidenceRoleRouter:
    """Routes extracted items by evidence role before normalization."""

    def route(
        self,
        items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], list[EvidenceItem], list[EvidenceItem]]:
        primary: list[EvidenceItem] = []
        phenotype: list[EvidenceItem] = []
        discarded: list[EvidenceItem] = []
        for item in items:
            if item.evidence_role == EvidenceRole.PRIMARY:
                primary.append(item)
            elif item.evidence_role == EvidenceRole.PHENOTYPE:
                phenotype.append(item)
            else:
                logger.info(
                    "Discarding non-primary evidence item: field_id={}, role={}, value={}",
                    item.field_id,
                    item.evidence_role.value,
                    item.value,
                )
                discarded.append(item)
        return primary, phenotype, discarded
```

In `workflow.py`, import `EvidenceRoleRouter` from the new stage module, instantiate it, add `_node_role_routing()`, and wire it **after** `group_assignment` and **before** `value_normalization` in both sync and async graph builders:

```python
graph.add_edge("group_assignment", "role_routing")
graph.add_edge("role_routing", "value_normalization")
```

The `_node_role_routing` handler reads `state.evidence_items`, routes them, and writes back:
- `state.evidence_items` ← primary items only
- `state.phenotype_evidence` ← phenotype items
- `state.discarded_evidence` ← comparator/context items

**Step 4: Run test**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_role_routing.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/role_routing.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_role_routing.py
git commit -m "feat: route non-primary evidence roles"
```

## Task 6: Add Target Entity Guard

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_guard.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`

**Step 1: Write the failing tests**

Create `test_target_guard.py`:

```python
"""Tests for target entity validation."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
    TargetEntityGuard,
)


def _gene_item(value: object) -> EvidenceItem:
    return EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.91,
    )


def test_target_guard_corrects_gene_list_string_when_target_present() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    guarded = TargetEntityGuard().apply([_gene_item("['ABCA3', 'CFTR']")], target)

    assert guarded[0].status == EvidenceStatus.FOUND
    assert guarded[0].value == "ABCA3"
    assert "list_to_target" in guarded[0].notes


def test_target_guard_marks_wrong_gene_as_context_contamination() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    guarded = TargetEntityGuard().apply([_gene_item("CFTR")], target)

    assert guarded[0].status == EvidenceStatus.CONTEXT_CONTAMINATION
    assert "expected ABCA3" in guarded[0].notes
```

Add to `test_quality_validation.py`:

```python
def test_quality_validation_counts_context_contamination() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.CONTEXT_CONTAMINATION,
        value="CFTR",
        confidence=0.8,
    )

    report = QualityValidator(required_field_ids={"A.gene_symbol"}).validate([item], contradictions=[])

    assert report.context_contamination_count == 1
    assert report.scorable is False
```

Add to `test_repositories.py`:

```python
def test_context_contamination_is_not_canonical_eligible() -> None:
    from src.core.standardize_entities_and_align_knowledge.repositories import (
        CANONICAL_ELIGIBLE_STATUSES,
    )

    assert "context_contamination" not in CANONICAL_ELIGIBLE_STATUSES
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_guard.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py::test_quality_validation_counts_context_contamination -v
```

Expected: FAIL because target validation is not implemented.

**Step 3: Write minimal implementation**

In `core.py`, add `ast` import and implement:

```python
class TargetEntityGuard:
    """Validates primary entity fields against the extraction target."""

    def apply(
        self,
        items: list[EvidenceItem],
        extraction_target: ExtractionTarget | None,
    ) -> list[EvidenceItem]:
        if extraction_target is None:
            return items
        return [self._guard_one(item, extraction_target) for item in items]

    def _guard_one(self, item: EvidenceItem, target: ExtractionTarget) -> EvidenceItem:
        if item.status != EvidenceStatus.FOUND or item.field_id != "A.gene_symbol":
            return item
        values = self._extract_gene_values(item.value)
        if len(values) > 1:
            if target.gene_symbol in values:
                return item.model_copy(update={
                    "value": target.gene_symbol,
                    "notes": self._append_note(item.notes, "target_guard:list_to_target"),
                })
            return self._contaminated(item, f"target gene {target.gene_symbol} not in extracted gene list {values}")
        actual = values[0] if values else str(item.value or "").strip().upper()
        if actual != target.gene_symbol:
            return self._contaminated(item, f"extracted {actual}, expected {target.gene_symbol}")
        return item.model_copy(update={"value": target.gene_symbol})

    def _contaminated(self, item: EvidenceItem, reason: str) -> EvidenceItem:
        return item.model_copy(update={
            "status": EvidenceStatus.CONTEXT_CONTAMINATION,
            "notes": self._append_note(item.notes, f"target_guard:{reason}"),
            "assigned_acmg_codes": [],
            "assigned_clingen_modules": [],
        })

    @staticmethod
    def _extract_gene_values(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(entry).strip().upper() for entry in value if str(entry).strip()]
        text = str(value or "").strip()
        if text.startswith("["):
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return [text.upper()]
            if isinstance(parsed, list):
                return [str(entry).strip().upper() for entry in parsed if str(entry).strip()]
        return [text.upper()] if text else []

    @staticmethod
    def _append_note(existing: str, note: str) -> str:
        return f"{existing}; {note}" if existing else note
```

Wire `TargetEntityGuard` after role routing and before source grounding (it validates primary evidence items' gene_symbol against the target after role separation, before source grounding re-validates sources).

Update status rank maps in `core.py` (`EvidenceItemNormalizer._choose_better` at line 133) and `chunking.py` (`_item_rank` at line 156):

```python
EvidenceStatus.CONTEXT_CONTAMINATION: 0,
```

Update `QualityValidator` to count `context_contamination`, add an error `QualityIssue`, and include the status in scorable-blocking checks. Do not add the status to `CANONICAL_ELIGIBLE_STATUSES`.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_guard.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py \
  tests/core/standardize_entities_and_align_knowledge/test_repositories.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/chunking.py \
  backend/src/core/standardize_entities_and_align_knowledge/repositories.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_guard.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py \
  backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py
git commit -m "feat: reject target context contamination"
```

## Task 7: Include Target In Phase 3 Scope Hashing

**Files:**

- Modify: `backend/src/core/standardize_entities_and_align_knowledge/contracts.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/adapters.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/normalizers.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_normalizers.py`

**Step 1: Write the failing tests**

Append to `test_contracts.py`:

```python
def test_standardization_input_carries_extraction_target() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    input_data = StandardizationInput(
        document_id="doc",
        source_document_id="source",
        processing_run_id="run",
        candidates=(),
        evidence_items=(),
        extraction_target=target,
    )

    assert input_data.extraction_target == target
```

Append to `test_normalizers.py`:

```python
def test_target_scope_bindings_change_entity_scope_hash() -> None:
    abca3 = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    cftr = ExtractionTarget(gene_symbol="CFTR", disease_name="cystic fibrosis")
    entity_bindings = [("subject", "HGNC:33"), ("context", "MONDO:0000001")]

    assert make_entity_scope_hash([*make_target_scope_bindings(abca3), *entity_bindings]) != (
        make_entity_scope_hash([*make_target_scope_bindings(cftr), *entity_bindings])
    )
```

Append to `test_adapters.py`:

```python
def test_dual_result_adapter_carries_target_and_phenotype_evidence() -> None:
    target = ExtractionTarget(gene_symbol="AARS2", disease_name="AARS2-related leukodystrophy")
    result = DualEvidenceExtractionResult(
        document_id="doc-target",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-target",
            track=Track.ORIGINAL,
            extraction_target=target,
            phenotype_evidence=[
                EvidenceItem(
                    field_id="B.disease_diagnosis",
                    category="B",
                    field_name="Disease diagnosis",
                    status=EvidenceStatus.FOUND,
                    value="COXPD8",
                    confidence=0.9,
                    group_id="gene=AARS2|variant=__missing__",
                    evidence_role=EvidenceRole.PHENOTYPE,
                )
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-target",
            track=Track.TRANSLATED,
            extraction_target=target,
        ),
    )

    output = DualResultAdapter().to_standardization_input(
        result,
        source_document_id="source",
        processing_run_id="run",
    )

    assert output.extraction_target == target
    assert any(candidate.raw_text == "COXPD8" for candidate in output.candidates)
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py::test_standardization_input_carries_extraction_target \
  tests/core/standardize_entities_and_align_knowledge/test_adapters.py::test_dual_result_adapter_carries_target_and_phenotype_evidence \
  tests/core/standardize_entities_and_align_knowledge/test_normalizers.py::test_target_scope_bindings_change_entity_scope_hash -v
```

Expected: FAIL because target is not part of Phase 3 input.

**Step 3: Write minimal implementation**

In Phase 3 `contracts.py`, add `ExtractionTarget | None` to `StandardizationInput`.

In `adapters.py`, set:

```python
extraction_target = result.original_result.extraction_target or result.translated_result.extraction_target
```

Pass it to `StandardizationInput`. 

**Important: Update `_add_phenotype_candidates` to also read `result.phenotype_evidence`.** Currently the method only reads `result.evidence_items`. After role routing, phenotype evidence lives in `result.phenotype_evidence` instead of `result.evidence_items`. Add iteration over `result.phenotype_evidence` using the same `_append_candidate` helper with `entity_type=EntityType.PHENOTYPE`:

In `normalizers.py`:

```python
def make_target_scope_bindings(target: ExtractionTarget | None) -> list[tuple[str, str]]:
    if target is None:
        return []
    bindings = [
        ("target_gene", normalize_gene_symbol(target.gene_symbol)),
        ("target_disease", normalize_disease_lookup_text(target.disease_name)),
    ]
    if target.variant_hgvs_p:
        bindings.append(("target_variant_p", target.variant_hgvs_p))
    if target.clingen_entry_id:
        bindings.append(("target_clingen_entry", target.clingen_entry_id))
    return bindings
```

In `repositories.py`, import `make_target_scope_bindings`. Change `_build_chain_scope_hashes()` signature from `(self, matches)` to `(self, input_data, matches)` — prepend target bindings (`make_target_scope_bindings(input_data.extraction_target)`) to each chain's entity bindings, and use a target-only hash as fallback for payload groups without matches:

```python
target_scope_hash = make_entity_scope_hash(make_target_scope_bindings(input_data.extraction_target))
entity_scope_hash=scope_hashes.get(group_id, target_scope_hash)
```

**Step 4: Run Phase 3 tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py \
  tests/core/standardize_entities_and_align_knowledge/test_adapters.py \
  tests/core/standardize_entities_and_align_knowledge/test_normalizers.py \
  tests/core/standardize_entities_and_align_knowledge/test_repositories.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/contracts.py \
  backend/src/core/standardize_entities_and_align_knowledge/adapters.py \
  backend/src/core/standardize_entities_and_align_knowledge/normalizers.py \
  backend/src/core/standardize_entities_and_align_knowledge/repositories.py \
  backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py \
  backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py \
  backend/tests/core/standardize_entities_and_align_knowledge/test_normalizers.py
git commit -m "feat: include extraction target in evidence scope"
```

## Task 8: Send Target From ClinGen Benchmark

**Files:**

- Modify: `benchmark/layer3/evaluate.py`
- Test: `backend/tests/benchmark/layer3/test_evaluate_matching.py`

**Step 1: Write the failing test**

Append to `test_evaluate_matching.py`:

```python
import pytest

from benchmark.layer3.evaluate import submit_and_poll


class FakePipelineClient:
    def __init__(self) -> None:
        self.post_payloads = []

    async def post(self, url: str, json: dict, timeout: float):  # noqa: ANN001
        self.post_payloads.append(json)
        return FakeResponse(202, {"status_url": "/status"})

    async def get(self, url: str, timeout: float):  # noqa: ANN001
        return FakeResponse(200, {"pipeline_status": "completed"})


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_submit_and_poll_sends_extraction_target(monkeypatch) -> None:
    monkeypatch.setattr("benchmark.layer3.evaluate.POLL_INTERVAL_S", 0)
    client = FakePipelineClient()

    await submit_and_poll(
        client,
        "http://test",
        pdf_bytes=None,
        filename="clingen_002.md",
        pre_parsed_markdown="ABCA3 text",
        extraction_target={
            "gene_symbol": "ABCA3",
            "disease_name": "interstitial lung disease due to ABCA3 deficiency",
            "clingen_entry_id": "clingen_002",
        },
    )

    assert client.post_payloads[0]["target"]["gene_symbol"] == "ABCA3"
```

**Step 2: Run test to verify failure**

Run:

```bash
uv --project backend run pytest backend/tests/benchmark/layer3/test_evaluate_matching.py::test_submit_and_poll_sends_extraction_target -v
```

Expected: FAIL because `submit_and_poll()` has no `extraction_target` argument.

**Step 3: Write minimal implementation**

In `submit_and_poll()`, add parameter:

```python
extraction_target: dict | None = None,
```

Add payload field:

```python
if extraction_target is not None:
    payload["target"] = extraction_target
```

In `evaluate_one()`, build and pass:

```python
extraction_target = {
    "gene_symbol": entry["gene_symbol"],
    "disease_name": entry["disease_label"],
    "variant_hgvs_p": "",
    "clingen_entry_id": entry_id,
}
```

**Step 4: Run benchmark tests**

Run:

```bash
uv --project backend run pytest backend/tests/benchmark/layer3/test_evaluate_matching.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add benchmark/layer3/evaluate.py backend/tests/benchmark/layer3/test_evaluate_matching.py
git commit -m "feat: send extraction target in clingen benchmark"
```

## Task 9: Add Disaster-Case Regression Tests

**Files:**

- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_anchoring_regression.py`

**Step 1: Write regression tests**

```python
"""Regression coverage for target anchoring extraction failures."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceRole,
    EvidenceStatus,
    ExtractionTarget,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.role_routing import (
    EvidenceRoleRouter,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
    TargetEntityGuard,
)


def _item(field_id: str, value: object, role: EvidenceRole = EvidenceRole.PRIMARY) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        evidence_role=role,
    )


def test_abca3_target_rejects_cftr_context_gene() -> None:
    target = ExtractionTarget(
        gene_symbol="ABCA3",
        disease_name="interstitial lung disease due to ABCA3 deficiency",
    )

    guarded = TargetEntityGuard().apply([_item("A.gene_symbol", "CFTR")], target)

    assert guarded[0].status == EvidenceStatus.CONTEXT_CONTAMINATION


def test_abca3_target_corrects_gene_list_containing_target() -> None:
    target = ExtractionTarget(
        gene_symbol="ABCA3",
        disease_name="interstitial lung disease due to ABCA3 deficiency",
    )

    guarded = TargetEntityGuard().apply([_item("A.gene_symbol", "['CFTR', 'ABCA3']")], target)

    assert guarded[0].status == EvidenceStatus.FOUND
    assert guarded[0].value == "ABCA3"


def test_aars2_syndromes_and_nodopathy_do_not_enter_primary_evidence() -> None:
    primary, phenotype, discarded = EvidenceRoleRouter().route([
        _item("A.gene_symbol", "AARS2"),
        _item("B.disease_diagnosis", "COXPD8", EvidenceRole.PHENOTYPE),
        _item("B.disease_diagnosis", "LKENP", EvidenceRole.PHENOTYPE),
        _item("B.disease_diagnosis", "Anti-NF155 autoimmune nodopathy", EvidenceRole.COMPARATOR),
    ])

    assert [item.value for item in primary] == ["AARS2"]
    assert [item.value for item in phenotype] == ["COXPD8", "LKENP"]
    assert [item.value for item in discarded] == ["Anti-NF155 autoimmune nodopathy"]
```

**Step 2: Run regression tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_anchoring_regression.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_aars2_regression.py -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_target_anchoring_regression.py
git commit -m "test: cover target anchoring regressions"
```

## Task 10: Documentation And Final Verification

**Files:**

- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/README.md`
- Modify: `backend/src/agents/README.md`
- Modify: `docs/README.md`
- Modify: `progress.txt`
- Modify if debugging occurred: `lesson.md`

**Step 1: Run focused verification**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ \
  tests/core/standardize_entities_and_align_knowledge/ \
  tests/agents/ \
  tests/api/test_pipeline_api.py -v
uv run ruff check src tests
```

Run benchmark tests:

```bash
uv --project backend run pytest backend/tests/benchmark/layer3/test_evaluate_matching.py -v
```

Expected: all focused tests pass. If unrelated pre-existing failures appear, record exact failures in the final notes and do not mask them.

**Step 2: Update module guides**

Because backend modules changed, use @module-guide after tests pass. Update only affected sections:

- `extract_evidence/README.md`: `ExtractionTarget`, `EvidenceRole`, `context_contamination`, role routing, target guard.
- `standardize_entities_and_align_knowledge/README.md`: target-aware `entity_scope_hash`, `phenotype_evidence`.
- `agents/README.md`: `PipelineGraphState.extraction_target`, API `target` payload.

**Step 3: Update progress and docs**

Append to `progress.txt`:

```text
[2026-06-11] [Target anchored evidence extraction implementation] [completed] Added ExtractionTarget propagation, role routing, context contamination guard, target-aware scope hashing, and ClinGen benchmark target payload. Focused backend tests passing.
```

If debugging or iterative failures occurred, update `lesson.md`.

Because docs changed, use @doc-organize. Keep this plan in `docs/plans/` until implementation is complete and reviewed.

**Step 4: Commit docs**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/README.md \
  backend/src/core/standardize_entities_and_align_knowledge/README.md \
  backend/src/agents/README.md docs/README.md progress.txt lesson.md
git commit -m "docs: document target anchored extraction"
```

## Implementation Notes

- Use @test-driven-development for each implementation task.
- Use @systematic-debugging before fixing any failed verification.
- Use @verification-before-completion before claiming success.
- Use `uv` for Python commands. Do not use system `pip`.
- Keep all business logic under `backend/src/`.
- Keep new tests under `backend/tests/`.
- Do not add a DB migration for `context_contamination`.
- Do not write phenotype/comparator/context items into primary `evidence_items`.

### Interaction: FieldValueNormalizer and TargetEntityGuard

The existing `FieldValueNormalizer` (in `core.py`) normalizes `A.gene_symbol` values during `CatalogExtractionStage._extract_group()`, which runs **before** `TargetEntityGuard`. This is safe because:

- `FieldValueNormalizer` uppercases well-formed gene symbols and extracts clean symbols from disease-prefix phrases (e.g., `"AARS2-related disease"` → `"AARS2"`).
- List‑string values like `"['ABCA3', 'CFTR']"` pass through `FieldValueNormalizer` unchanged (they don't match the gene‑symbol regex), so `TargetEntityGuard` can parse them via `ast.literal_eval`.
- By the time `TargetEntityGuard` runs, `FieldValueNormalizer` has already cleaned any simple gene‑symbol values, and `EvidenceRoleRouter` has removed phenotype/comparator/context items.

**No code change needed.** The interaction is safe by design; this note documents why.
