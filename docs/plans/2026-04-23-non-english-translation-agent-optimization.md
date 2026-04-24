# Non-English to English Translation Agent Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the existing non-English-to-English translation workflow so that any non-English normalized markdown is converted into stable, terminology-consistent, reviewable English markdown before downstream evidence extraction.

**Architecture:** Keep the existing LangGraph/supervisor pipeline and improve only the translation slice. Reuse the current `EvidenceAgent.translate_markdown(...)`, `translation_validation.py`, and supervisor wiring, but split translation into explicit sub-stages: language gate, terminology planning, structure planning, constrained translation, polishing, and final validation/reporting. Preserve the current contract that downstream extraction consumes a single English markdown string, while adding internal artifacts and warnings so failures are diagnosable without rewriting extraction or arbitration.

**Tech Stack:** Python 3.12, LangGraph, existing EvidenceAgent workflow, existing supervisor graph, existing Lingua language detection, pytest.

---

## Constraints discovered in the current repo

1. `apps/backend/src/domain/agent/workflow.py:681` already owns the main markdown translation path and currently performs segmented direct translation only.
2. `apps/backend/src/services/translation_validation.py:19` already has a skip-English gate and output validation, but validation only checks final output quality, not stage-by-stage translation stability.
3. `apps/backend/src/agents/supervisor.py:103` already skips translation when `translated_markdown` is present and valid, so the optimized flow must keep the same external state contract.
4. Downstream extraction requires `translated_md` to be a plain English markdown string, so intermediate products must stay internal to the translation agent state.
5. The repo already introduced deterministic fallback/review patterns in `apps/backend/src/agents/chinese_fulltext_recovery/agent.py`, so the translation optimization should follow that style instead of inventing a separate orchestration layer.
6. There is already test coverage around translation skip behavior in `apps/backend/tests/test_stream_supervisor.py` and wrapper behavior in `apps/backend/tests/test_tool_wrappers.py`; extend these instead of creating a parallel testing strategy.

## Target behavior

For non-English input markdown, the optimized agent should:
- detect whether translation is required;
- extract a terminology map from the source markdown;
- derive an English-oriented structure plan for long, clause-heavy prose;
- produce a faithful draft that obeys the terminology map;
- optionally polish style without changing meaning;
- validate the final English markdown and surface a structured review report/warnings;
- return only the final English markdown to existing downstream nodes.

For English input markdown, the optimized agent should continue skipping translation exactly as it does now.

### Task 1: Expand the translation state contract for staged processing

**Files:**
- Modify: `apps/backend/src/domain/enums.py`
- Modify: `apps/backend/src/domain/agent/workflow.py:681-724`
- Test: `apps/backend/tests/test_state_schema.py`

**Step 1: Write the failing test**

Add a failing state-schema test proving the processing state supports internal staged translation fields.

```python
def test_processing_state_supports_staged_translation_artifacts() -> None:
    state = ProcessingState(
        markdown_content="原文",
        translated_md="",
        translation_terminology="gene -> gene",
        translation_structure="Subject -> Verb -> Object",
        translation_draft="draft",
        translation_polished="polished",
        translation_review="ok",
        translation_warnings=["needs_review"],
    )

    assert state["translation_draft"] == "draft"
    assert state["translation_warnings"] == ["needs_review"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_state_schema.py -q`
Expected: FAIL because the extra translation-stage fields are not defined in the processing-state type.

**Step 3: Write minimal implementation**

Add these optional fields to the processing state definition used by the agent workflow:

```python
translation_required: bool
translation_terminology: str
translation_structure: str
translation_draft: str
translation_polished: str
translation_review: str
translation_warnings: list[str]
```

Do not expose them in API response DTOs yet. They are internal workflow fields only.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_state_schema.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/domain/enums.py apps/backend/src/domain/agent/workflow.py apps/backend/tests/test_state_schema.py
git commit -m "refactor: add staged translation state fields"
```

### Task 2: Add deterministic language gating and stage reset helpers

**Files:**
- Modify: `apps/backend/src/services/translation_validation.py`
- Modify: `apps/backend/src/domain/agent/workflow.py`
- Create: `apps/backend/tests/unit/test_translation_validation.py`

**Step 1: Write the failing test**

Add failing tests for the translation gate and state reset behavior.

```python
from src.services.translation_validation import should_skip_translation, reset_translation_artifacts


def test_should_skip_translation_returns_false_for_non_english_markdown() -> None:
    assert should_skip_translation("## 病例摘要\n\n患者表现为肌无力") is False


def test_reset_translation_artifacts_clears_stage_outputs() -> None:
    state = {
        "translation_terminology": "term map",
        "translation_structure": "plan",
        "translation_draft": "draft",
        "translation_polished": "polished",
        "translation_review": "review",
        "translation_warnings": ["warning"],
    }

    reset_translation_artifacts(state)

    assert state["translation_terminology"] == ""
    assert state["translation_warnings"] == []
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_translation_validation.py -q`
Expected: FAIL with missing helper errors.

**Step 3: Write minimal implementation**

Keep `should_skip_translation(...)` as the single skip gate and add a reset helper used before every fresh translation attempt.

```python
def reset_translation_artifacts(state: dict[str, Any]) -> None:
    state["translation_required"] = False
    state["translation_terminology"] = ""
    state["translation_structure"] = ""
    state["translation_draft"] = ""
    state["translation_polished"] = ""
    state["translation_review"] = ""
    state["translation_warnings"] = []
```

In `translate_markdown(...)`, call the reset helper before recomputing stages when the existing translation is missing or invalid.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_translation_validation.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/translation_validation.py apps/backend/src/domain/agent/workflow.py apps/backend/tests/unit/test_translation_validation.py
git commit -m "refactor: add translation gating helpers"
```

### Task 3: Extract terminology planning into a dedicated stage

**Files:**
- Modify: `apps/backend/src/domain/agent/workflow.py`
- Modify: `apps/backend/src/domain/agent/prompts.py`
- Test: `apps/backend/tests/test_agents_parsing.py`

**Step 1: Write the failing test**

Add a failing unit test that proves terminology planning runs before draft translation and stores a reusable artifact.

```python
def test_translate_markdown_generates_terminology_plan(monkeypatch) -> None:
    agent = EvidenceAgent()

    calls = []

    class FakeLLM:
        def invoke(self, messages):
            text = messages[-1].content
            calls.append(text)
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="GLA -> alpha-galactosidase A")
            return AIMessage(content="English draft")

    monkeypatch.setattr(agent, "get_translation_llm", lambda: FakeLLM())

    state = {"markdown_content": "GLA基因变异", "translated_md": ""}
    result = agent.translate_markdown(state)

    assert result["translation_terminology"] == "GLA -> alpha-galactosidase A"
    assert calls[0].find("TERMINOLOGY_STAGE") >= 0
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k terminology`
Expected: FAIL because no terminology stage exists yet.

**Step 3: Write minimal implementation**

In `apps/backend/src/domain/agent/prompts.py`, add a prompt builder for terminology extraction that:
- extracts bilingual terminology pairs from the source markdown;
- forbids full translation;
- prefers stable biomedical English equivalents;
- keeps gene/protein/HGVS strings unchanged where appropriate.

Suggested helper signature:

```python
def get_translation_terminology_prompt(markdown_content: str) -> str:
    ...
```

In `translate_markdown(...)`, invoke the translation LLM once for terminology planning before segmented translation and store the raw text in `state["translation_terminology"]`.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k terminology`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/domain/agent/workflow.py apps/backend/src/domain/agent/prompts.py apps/backend/tests/test_agents_parsing.py
git commit -m "feat: add translation terminology planning stage"
```

### Task 4: Add structure planning for long non-English prose

**Files:**
- Modify: `apps/backend/src/domain/agent/prompts.py`
- Modify: `apps/backend/src/domain/agent/workflow.py`
- Test: `apps/backend/tests/test_agents_parsing.py`

**Step 1: Write the failing test**

Add a failing test showing that clause-heavy non-English markdown produces a structure plan before translation.

```python
def test_translate_markdown_generates_structure_plan(monkeypatch) -> None:
    agent = EvidenceAgent()

    class FakeLLM:
        def __init__(self):
            self.calls = []
        def invoke(self, messages):
            text = messages[-1].content
            self.calls.append(text)
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="term map")
            if "STRUCTURE_STAGE" in text:
                return AIMessage(content="1. restore subject\n2. split clauses")
            return AIMessage(content="English draft")

    fake = FakeLLM()
    monkeypatch.setattr(agent, "get_translation_llm", lambda: fake)

    result = agent.translate_markdown({"markdown_content": "中文属于典型的意合语言……", "translated_md": ""})

    assert result["translation_structure"] == "1. restore subject\n2. split clauses"
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k structure_plan`
Expected: FAIL because no structure-planning stage exists.

**Step 3: Write minimal implementation**

Add a structure-planning prompt helper:

```python
def get_translation_structure_prompt(markdown_content: str) -> str:
    ...
```

The prompt should ask for:
- subject restoration where omitted;
- clause splitting for long sentences;
- explicit logical connectors;
- markdown-aware preservation of headings, bullet lists, and tables.

In `translate_markdown(...)`, run the structure stage after terminology planning and store it in `state["translation_structure"]`.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k structure_plan`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/domain/agent/prompts.py apps/backend/src/domain/agent/workflow.py apps/backend/tests/test_agents_parsing.py
git commit -m "feat: add translation structure planning stage"
```

### Task 5: Replace direct segment translation with constrained draft generation

**Files:**
- Modify: `apps/backend/src/domain/agent/prompts.py`
- Modify: `apps/backend/src/domain/agent/workflow.py:695-724`
- Test: `apps/backend/tests/test_agents_parsing.py`

**Step 1: Write the failing test**

Add a failing test proving each translation segment receives the terminology map and structure plan.

```python
def test_translate_markdown_uses_terminology_and_structure_in_draft_stage(monkeypatch) -> None:
    agent = EvidenceAgent()

    prompts_seen = []

    class FakeLLM:
        def invoke(self, messages):
            text = messages[-1].content
            prompts_seen.append(text)
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="GLA -> alpha-galactosidase A")
            if "STRUCTURE_STAGE" in text:
                return AIMessage(content="restore omitted subject")
            return AIMessage(content="Translated English segment")

    monkeypatch.setattr(agent, "get_translation_llm", lambda: FakeLLM())
    result = agent.translate_markdown({"markdown_content": "GLA基因变异导致...", "translated_md": ""})

    assert result["translation_draft"]
    assert any("GLA -> alpha-galactosidase A" in prompt for prompt in prompts_seen)
    assert any("restore omitted subject" in prompt for prompt in prompts_seen)
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k draft_stage`
Expected: FAIL because the current prompt only sends raw segment content.

**Step 3: Write minimal implementation**

Add a draft prompt helper:

```python
def get_translation_draft_prompt(
    markdown_segment: str,
    terminology: str,
    structure_plan: str,
) -> str:
    ...
```

Requirements for the draft stage:
- preserve markdown structure;
- obey terminology mappings;
- preserve HGVS/gene/protein strings exactly;
- translate faithfully rather than stylistically rewriting;
- do not omit uncertain content; mark ambiguity inline if needed.

Update the segment loop in `translate_markdown(...)` to call this draft prompt and store the joined draft in `state["translation_draft"]` before deciding the final output.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k draft_stage`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/domain/agent/prompts.py apps/backend/src/domain/agent/workflow.py apps/backend/tests/test_agents_parsing.py
git commit -m "feat: constrain draft translation with planning artifacts"
```

### Task 6: Add a polishing stage that can be skipped safely

**Files:**
- Modify: `apps/backend/src/domain/agent/prompts.py`
- Modify: `apps/backend/src/domain/agent/workflow.py`
- Create: `apps/backend/tests/unit/test_translation_polish.py`

**Step 1: Write the failing test**

Add failing tests for polishing behavior and safe fallback.

```python
from src.domain.agent.workflow import EvidenceAgent


def test_polish_stage_improves_style_but_keeps_meaning(monkeypatch) -> None:
    agent = EvidenceAgent()

    monkeypatch.setattr(agent, "_run_translation_polish", lambda draft, terminology: "Polished English markdown")

    state = {"translation_draft": "Draft English markdown", "translation_terminology": "term map"}
    result = agent._apply_translation_polish(state)

    assert result["translation_polished"] == "Polished English markdown"


def test_polish_stage_falls_back_to_draft_on_failure(monkeypatch) -> None:
    agent = EvidenceAgent()

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("llm failed")

    monkeypatch.setattr(agent, "_run_translation_polish", raise_error)

    state = {"translation_draft": "Draft English markdown", "translation_terminology": "term map", "translation_warnings": []}
    result = agent._apply_translation_polish(state)

    assert result["translation_polished"] == "Draft English markdown"
    assert "translation_polish_failed" in result["translation_warnings"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_translation_polish.py -q`
Expected: FAIL because polish helpers do not exist.

**Step 3: Write minimal implementation**

Add two small helpers on `EvidenceAgent`:

```python
def _run_translation_polish(self, draft: str, terminology: str) -> str:
    ...


def _apply_translation_polish(self, state: ProcessingState) -> ProcessingState:
    ...
```

Polish prompt requirements:
- improve fluency for academic English;
- keep markdown layout unchanged;
- do not change scientific meaning;
- avoid obvious AI-stock phrasing.

If polishing fails, keep the draft unchanged and append `translation_polish_failed` to warnings.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_translation_polish.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/domain/agent/prompts.py apps/backend/src/domain/agent/workflow.py apps/backend/tests/unit/test_translation_polish.py
git commit -m "feat: add safe translation polishing stage"
```

### Task 7: Add final review and validation reporting

**Files:**
- Modify: `apps/backend/src/services/translation_validation.py`
- Modify: `apps/backend/src/domain/agent/prompts.py`
- Modify: `apps/backend/src/domain/agent/workflow.py`
- Test: `apps/backend/tests/test_agents_parsing.py`

**Step 1: Write the failing test**

Add a failing test proving the final stage records a review artifact and uses validated English output as `translated_md`.

```python
def test_translate_markdown_stores_review_and_final_output(monkeypatch) -> None:
    agent = EvidenceAgent()

    class FakeLLM:
        def invoke(self, messages):
            text = messages[-1].content
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="term map")
            if "STRUCTURE_STAGE" in text:
                return AIMessage(content="structure plan")
            if "POLISH_STAGE" in text:
                return AIMessage(content="Polished English")
            if "REVIEW_STAGE" in text:
                return AIMessage(content="No unresolved ambiguity")
            return AIMessage(content="Draft English")

    monkeypatch.setattr(agent, "get_translation_llm", lambda: FakeLLM())

    result = agent.translate_markdown({"markdown_content": "原文内容", "translated_md": ""})

    assert result["translation_review"] == "No unresolved ambiguity"
    assert result["translated_md"] == "Polished English"
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k review_stage`
Expected: FAIL because there is no review stage and no structured warnings.

**Step 3: Write minimal implementation**

Add a review prompt helper:

```python
def get_translation_review_prompt(source_markdown: str, translated_markdown: str) -> str:
    ...
```

Then in `translate_markdown(...)`:
1. review the polished text against the source;
2. store the review text in `translation_review`;
3. run `validate_translation_output(...)` on the final candidate;
4. if validation passes, set `translated_md` to polished output;
5. if polishing was skipped, validate the draft and use that instead.

Add one helper in `translation_validation.py` to turn validation exceptions into warning strings when needed:

```python
def summarize_translation_validation_error(exc: Exception) -> str:
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_parsing.py -q -k review_stage`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/translation_validation.py apps/backend/src/domain/agent/prompts.py apps/backend/src/domain/agent/workflow.py apps/backend/tests/test_agents_parsing.py
git commit -m "feat: add translation review and validation reporting"
```

### Task 8: Keep supervisor compatibility and skip semantics intact

**Files:**
- Modify: `apps/backend/src/agents/supervisor.py`
- Modify: `apps/backend/tests/test_stream_supervisor.py`
- Modify: `apps/backend/tests/test_tool_wrappers.py`

**Step 1: Write the failing test**

Add a failing supervisor test ensuring staged translation artifacts do not change skip behavior for English or pretranslated content.

```python
async def test_supervisor_translation_still_skips_when_existing_translation_is_valid(self):
    state = {
        "markdown_content": "English source text",
        "translated_markdown": "Valid English translation",
        "image_paths": [],
        "image_descriptions": [],
    }

    updated = translation(state)

    assert updated["translated_markdown"] == "Valid English translation"
    assert updated.get("translation_review", "") == ""
```

Add a wrapper test ensuring `translation_tool.translate_markdown(...)` still returns a flat `translated_md` field usable by callers.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_stream_supervisor.py apps/backend/tests/test_tool_wrappers.py -q -k translation`
Expected: FAIL once staged fields are added but not reset consistently.

**Step 3: Write minimal implementation**

Keep the public supervisor behavior unchanged:
- valid existing English translation still short-circuits;
- invalid cached translation still clears and reruns;
- downstream nodes still read only `translated_markdown` / `translated_md`.

Only copy staged artifacts into supervisor state if they already exist in the returned inner state; do not make downstream nodes depend on them.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_stream_supervisor.py apps/backend/tests/test_tool_wrappers.py -q -k translation`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/agents/supervisor.py apps/backend/tests/test_stream_supervisor.py apps/backend/tests/test_tool_wrappers.py
git commit -m "fix: preserve supervisor translation compatibility"
```

### Task 9: Verify the end-to-end non-English translation path

**Files:**
- Modify: `apps/backend/tests/test_supervisor_e2e.py`
- Modify: `apps/backend/tests/test_supervisor_integration.py`
- Optional reference: `apps/backend/tests/fixtures/`

**Step 1: Write the failing test**

Add one focused integration test for a non-English markdown sample.

```python
async def test_non_english_markdown_reaches_extraction_with_valid_english_translation(...):
    result = await run_supervisor_with_stubbed_translation(
        markdown_content="# 病例摘要\n\n患者携带 GLA c.92C>A 变异",
        ...
    )

    assert result["translated_markdown"]
    assert "GLA c.92C>A" in result["translated_markdown"]
    assert result["workflow_status"] == "completed"
```

Add one sibling test for English input proving the translation node still skips.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_supervisor_e2e.py apps/backend/tests/test_supervisor_integration.py -q -k translation`
Expected: FAIL until the staged translation flow is wired cleanly through the existing pipeline.

**Step 3: Write minimal implementation**

Adjust only the wiring required for tests to pass. Do not add new API endpoints or persistence layers in this slice.

If a fixture is needed, keep it tiny and markdown-only.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_supervisor_e2e.py apps/backend/tests/test_supervisor_integration.py -q -k translation`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/tests/test_supervisor_e2e.py apps/backend/tests/test_supervisor_integration.py apps/backend/tests/fixtures
git commit -m "test: cover staged non-english translation pipeline"
```

### Task 10: Run the full targeted regression suite

**Files:**
- No code changes required

**Step 1: Run targeted backend tests**

Run:

```bash
uv run --project apps/backend pytest \
  apps/backend/tests/unit/test_translation_validation.py \
  apps/backend/tests/unit/test_translation_polish.py \
  apps/backend/tests/test_agents_parsing.py \
  apps/backend/tests/test_stream_supervisor.py \
  apps/backend/tests/test_tool_wrappers.py \
  apps/backend/tests/test_supervisor_e2e.py \
  apps/backend/tests/test_supervisor_integration.py \
  apps/backend/tests/test_state_schema.py -q
```

Expected: PASS

**Step 2: Run broader translation-adjacent regressions**

Run:

```bash
uv run --project apps/backend pytest \
  apps/backend/tests/test_arbitration_prompts.py \
  apps/backend/tests/test_reasoning_node.py \
  apps/backend/tests/test_agents_extraction.py -q
```

Expected: PASS

**Step 3: Commit**

```bash
git status
```

Expected: clean working tree or only intentional unstaged follow-ups.

## Notes for the implementing engineer

- Do not add a brand-new translation microservice in this slice; the repo already has the right insertion point in `EvidenceAgent.translate_markdown(...)`.
- Do not change API contracts unless a test proves they need adjustment.
- Keep all new stage artifacts internal to workflow state.
- Prefer one small helper per stage over a second orchestration class.
- Preserve biomedical literals exactly: HGVS, gene symbols, protein names, accession IDs, PMID/PMCID/DOI strings.
- If a polishing or review stage fails, degrade gracefully to the validated draft rather than aborting the whole workflow.
