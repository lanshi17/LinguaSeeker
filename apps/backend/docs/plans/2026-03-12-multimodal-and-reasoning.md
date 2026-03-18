# Implementation Plan: 7.2 Multimodal Batch VLM & 7.3 Knowledge Graph Reasoning Node

Status: PENDING (P1 post-optimization)
Prerequisites: M1 主工作流完成

## Overview

Two post-P1 optimizations from `langgraph-refactor-plan.md` Section 七:
- **7.2**: Batch image description — send all images in one VLM call instead of per-image sequential calls
- **7.3**: Knowledge graph reasoning node — new `reasoning` node between `extraction→arbitration` that queries Neo4j for variant-gene-disease evidence context

## Part A: 7.2 — Batch Image Description

### Step 1: Add `image_inputs` field to SupervisorState

**File**: `src/state/global_state.py`  
**Action**: Add `image_inputs: list[dict]` after `image_paths` (line 34).

```python
# After line 34 (image_paths: list[str])
image_inputs: list[dict]  # [{path, base64, mime_type}]
```

**Test**: `tests/test_state_schema.py` — add `image_inputs` to the required fields check. Run `uv run pytest tests/test_state_schema.py -v`.

### Step 2: Add `vlm_max_batch_images` config setting

**File**: `src/config.py`  
**Action**: Add `vlm_max_batch_images: int = 10` near other vlm settings.

### Step 3: Add batch image description prompt

**File**: `src/domain/agent/prompts.py`  
**Action**: Add `get_batch_image_description_prompt(image_count: int) -> str` function that returns a prompt instructing the VLM to describe all N images, labeling each by index.

### Step 4: Modify `describe_images` for batch processing

**File**: `src/domain/agent/workflow.py` (lines 653-707)  
**Action**: Replace the per-image loop with batch logic:

```python
def describe_images(self, state: dict) -> dict:
    image_paths = state.get("image_paths", [])
    if not image_paths or not cfg.vlm_enable:
        return state

    vlm = self.get_vlm()
    max_batch = cfg.vlm_max_batch_images

    if len(image_paths) <= max_batch:
        descriptions = self._describe_images_batch(vlm, image_paths)
    else:
        # Chunk into batches
        descriptions = []
        for i in range(0, len(image_paths), max_batch):
            chunk = image_paths[i:i + max_batch]
            descriptions.extend(self._describe_images_batch(vlm, chunk, start_index=i))

    updated = {**state}
    updated["image_descriptions"] = "\n\n".join(descriptions)
    return updated
```

Add `_describe_images_batch(self, vlm, paths, start_index=0) -> list[str]`:
- Reads all images, base64-encodes each
- Builds single HumanMessage with content: [text_prompt, image_url_1, image_url_2, ...]
- Invokes VLM once
- Parses response into per-image descriptions list
- Populates `image_inputs` state field with structured dicts

### Step 5: Write tests for batch describe_images

**File**: `tests/test_batch_vlm.py`  
**Tests**:
1. Single image batch — same output as per-image
2. Multiple images in one batch call
3. Exceeds max_batch_images — chunked into multiple calls
4. Empty image_paths — returns state unchanged
5. vlm_enable=False — skips processing
6. File read error for one image — continues with remaining
7. VLM response parsing — correctly splits per-image descriptions

Run: `uv run pytest tests/test_batch_vlm.py -v`

### Step 6: Update test_state_schema.py

**File**: `tests/test_state_schema.py`  
**Action**: Add `image_inputs` to the field validation test.  
Run: `uv run pytest tests/test_state_schema.py -v`

## Part B: 7.3 — Knowledge Graph Reasoning Node

### Step 7: Add `graph_context` field to SupervisorState

**File**: `src/state/global_state.py`  
**Action**: Add `graph_context: Optional[dict]` after `acmg_result` (line 44).

```python
graph_context: Optional[dict]  # Neo4j evidence graph context for arbitration
```

### Step 8: Add reasoning step to processing enums

**File**: `src/service/enum.py`  
**Action**:
- Add `"reasoning"` to `PROCESSING_STEP_ORDER` tuple (after `"extraction"`, before `"adjudication"`)
- Add `"reasoning": "reasoning"` to `PROCESSING_NODE_TO_STEP` dict
- Add `"reasoning": WorkflowStatus.REASONING` to `STEP_TO_WORKFLOW_STATUS` dict (if enum value exists, else use PROCESSING)

### Step 9: Add `"reasoning"` to streaming progress nodes

**File**: `src/service/tasks.py` (line 1132)  
**Action**: Add `"reasoning"` to `_SUPERVISOR_PROGRESS_NODES` set.

```python
_SUPERVISOR_PROGRESS_NODES: set[str] = {
    "acquisition", "parsing", "translation", "extraction", "reasoning", "arbitration",
}
```

### Step 10: Create reasoning node module

**File**: `src/agents/reasoning/__init__.py` — empty  
**File**: `src/agents/reasoning/node.py`

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.database.neo4j_client import get_neo4j_client
from src.state.global_state import SupervisorState

logger = logging.getLogger(__name__)


def run_reasoning_node(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    updated["current_node"] = "reasoning"

    evidence_output = state.get("evidence_output")
    extracted_fields = state.get("extracted_fields")

    gene_symbol = _extract_gene_symbol(evidence_output, extracted_fields)
    variant_hgvs_c = _extract_variant_hgvs(evidence_output, extracted_fields)
    protein_change = _extract_protein_change(evidence_output, extracted_fields)

    if not gene_symbol and not variant_hgvs_c:
        logger.info("reasoning: no gene/variant identifiers, skipping graph queries")
        updated["graph_context"] = None
        return updated

    try:
        graph_context = asyncio.get_event_loop().run_until_complete(
            _query_knowledge_graph(gene_symbol, variant_hgvs_c, protein_change)
        )
    except Exception:
        logger.exception("reasoning: Neo4j query failed, proceeding without graph context")
        graph_context = None

    graph_context = graph_context or {}
    if graph_context:
        graph_context["reasoning_summary"] = _build_reasoning_summary(graph_context)

    updated["graph_context"] = graph_context or None
    return updated


async def _query_knowledge_graph(
    gene_symbol: str | None,
    variant_hgvs_c: str | None,
    protein_change: str | None,
) -> dict[str, Any]:
    client = get_neo4j_client()
    results: dict[str, Any] = {}

    if variant_hgvs_c:
        results["variant_evidence"] = await asyncio.to_thread(
            client.find_variant_evidence_graph, variant_hgvs_c, None
        )

    if gene_symbol:
        results["related_variants"] = await asyncio.to_thread(
            client.find_gene_related_variants, gene_symbol
        )

    if gene_symbol or variant_hgvs_c:
        results["multi_document_evidence"] = await asyncio.to_thread(
            client.find_multi_document_evidence,
            gene_symbol or "",
            variant_hgvs_c or "",
            protein_change or "",
        )

    return results


def _extract_gene_symbol(evidence_output: Any, extracted_fields: Any) -> str | None:
    if extracted_fields and hasattr(extracted_fields, "gene_symbol"):
        return extracted_fields.gene_symbol or None
    if evidence_output and hasattr(evidence_output, "gene_symbol"):
        return evidence_output.gene_symbol or None
    return None


def _extract_variant_hgvs(evidence_output: Any, extracted_fields: Any) -> str | None:
    if extracted_fields and hasattr(extracted_fields, "variant_hgvs_c"):
        return extracted_fields.variant_hgvs_c or None
    if evidence_output and hasattr(evidence_output, "variant_hgvs_c"):
        return evidence_output.variant_hgvs_c or None
    return None


def _extract_protein_change(evidence_output: Any, extracted_fields: Any) -> str | None:
    if extracted_fields and hasattr(extracted_fields, "protein_change"):
        return extracted_fields.protein_change or None
    if evidence_output and hasattr(evidence_output, "protein_change"):
        return evidence_output.protein_change or None
    return None


def _build_reasoning_summary(graph_context: dict[str, Any]) -> str:
    parts: list[str] = []

    variant_ev = graph_context.get("variant_evidence", [])
    if variant_ev:
        parts.append(f"Found {len(variant_ev)} existing evidence records for this variant in the knowledge graph.")

    related = graph_context.get("related_variants", [])
    if related:
        parts.append(f"Found {len(related)} related variants for the same gene.")

    multi_doc = graph_context.get("multi_document_evidence", [])
    if multi_doc:
        parts.append(f"Found {len(multi_doc)} cross-document evidence entries.")

    return " ".join(parts) if parts else "No prior evidence found in the knowledge graph."
```

### Step 11: Register reasoning node in supervisor graph

**File**: `src/agents/supervisor.py`  
**Action**:
- Import: `from src.agents.reasoning.node import run_reasoning_node`
- Add node: `graph.add_node("reasoning", run_reasoning_node)` after extraction registration
- Replace edge: `graph.add_edge("extraction", "arbitration")` → `graph.add_edge("extraction", "reasoning")` + `graph.add_edge("reasoning", "arbitration")`

### Step 12: Pass graph_context to arbitration inner state

**File**: `src/agents/arbitration/node.py`  
**Action**: Add `"graph_context": updated.get("graph_context")` to the `inner_state` dict (around line 49, after existing fields).

### Step 13: Include graph_context in arbitration prompt

**File**: `src/domain/agent/workflow.py`  
**Action**: In `arbitrate_score`, check if `state.get("graph_context")` exists. If so, format it as additional context section in the arbitration prompt (before calling arbitration LLM).

### Step 14: Write tests for reasoning node

**File**: `tests/test_reasoning_node.py`  
**Tests**:
1. Happy path — gene_symbol + variant_hgvs_c → all 3 queries run → graph_context populated
2. Only gene_symbol — variant queries skipped
3. Only variant_hgvs_c — gene queries skipped
4. No gene/variant identifiers → graph_context = None, early return
5. Neo4j unavailable (exception) → graph_context = None, no crash
6. Empty query results → graph_context has empty lists
7. reasoning_summary generation — correct text for various result combinations
8. _extract_gene_symbol from extracted_fields vs evidence_output precedence
9. _extract_variant_hgvs from extracted_fields vs evidence_output precedence
10. current_node set to "reasoning"

Run: `uv run pytest tests/test_reasoning_node.py -v`

### Step 15: Update existing tests

- `tests/test_state_schema.py` — add `graph_context` field
- `tests/test_supervisor_e2e.py` — add reasoning node to traversal expectations
- `tests/test_stream_supervisor.py` — verify `reasoning` in `_SUPERVISOR_PROGRESS_NODES`
- `tests/test_supervisor_integration.py` — verify graph still compiles with new node

### Step 16: Run full test suite

Run: `uv run pytest -v`

Expected: all tests pass, 0 failures.

## Execution Order

1. Steps 1-6 (7.2 batch VLM) — can be done independently
2. Steps 7-15 (7.3 reasoning node) — depends on step 7 state change
3. Step 16 — final verification

## Risks

- **VLM model compatibility**: Not all models support multi-image in one call. Fallback to per-image if batch fails.
- **Neo4j availability**: Reasoning node must degrade gracefully (already handled).
- **asyncio.to_thread in sync context**: The reasoning node is called by LangGraph synchronously. If event loop is already running, `asyncio.get_event_loop().run_until_complete` will fail. May need `asyncio.run()` or `loop.run_in_executor` pattern matching existing codebase (see `extract_ps3_evidence_sync`).
