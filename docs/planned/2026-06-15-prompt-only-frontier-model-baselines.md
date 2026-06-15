# Prompt-Only Frontier Model Baselines Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-06-15
**Completed:** —
**PR:** —

**Goal:** Add a reproducible prompt-only model-sweep benchmark that compares CrossEvidence against several mainstream LLMs using the same prompt, same input, same schema, and no evidence-graph reconciliation.

**Architecture:** Reuse the existing `benchmark/layer3/baselines` runner and OpenAI-compatible LLM adapter. Add a manifest-driven model sweep where each baseline differs only by `model` name and paper-visible model metadata; add a citation-required prompt variant so prompt-only models can be evaluated on both extraction F1 and traceability metrics.

**Tech Stack:** Python 3.12, `uv`, Pydantic/dataclasses/TypedDict contracts, LangChain `ChatOpenAI` via `src.utils.llm_adapter`, existing Layer-3 ClinGen benchmark, pytest, Ruff.

---

## Scientific Purpose

This benchmark answers the reviewer question:

```text
If a strong frontier model is given a good prompt, does CrossEvidence still add value?
```

The paper-facing comparison should be framed as:

```text
Prompt-only frontier models provide strong extraction baselines, but they do not enforce citation-valid accepted evidence by construction. CrossEvidence keeps extraction competitive while adding source-span validation and contradiction-aware reconciliation.
```

Do not claim broad SOTA superiority unless the frozen model-sweep statistics support it. The minimum acceptable claim is:

```text
CrossEvidence is competitive with prompt-only frontier models and stronger on traceable extraction.
```

## Recommended Model Set For 2026-06-15 Run

The backend provider is OpenAI-compatible and supports mainstream models. The benchmark must therefore keep model IDs configurable and record exact provider aliases in the run manifest. Before running, replace the aliases below with the exact names exposed by the integrated supplier dashboard.

Primary paper set:

| Baseline ID | Family | Manifest `model` value | Rationale |
|---|---|---|---|
| `B6_GPT5_PROMPT_CITE` | OpenAI strong | `gpt-5` | Strong closed-model reference; matches current `reasoning_llm.model` family. |
| `B7_CLAUDE_PROMPT_CITE` | Anthropic strong | provider alias for latest Claude Sonnet/Opus | Independent closed-model reference. |
| `B8_GEMINI_PROMPT_CITE` | Google strong | provider alias for latest Gemini Pro | Long-context and general reasoning reference. |
| `B9_QWEN_PROMPT_CITE` | Qwen strong | provider alias for latest Qwen Max/Plus or current `Qwen/Qwen3.6-35B-A3B` family | Chinese/cross-lingual relevance. |
| `B10_DEEPSEEK_PROMPT_CITE` | DeepSeek reasoning | provider alias for latest DeepSeek reasoner | Cost-effective reasoning and Chinese-language relevance. |

Optional cost-control set:

| Baseline ID | Family | Manifest `model` value | Rationale |
|---|---|---|---|
| `B11_GPT5_MINI_PROMPT_CITE` | OpenAI fast | `gpt-5-mini` | Strong low-cost baseline; current `fast_llm.model` default. |
| `B12_DEEPSEEK_CHAT_PROMPT_CITE` | DeepSeek chat | provider alias for latest DeepSeek chat | Non-reasoning cost baseline. |

Primary paper table should use the five primary baselines. Optional baselines can be moved to appendix or omitted if deadline pressure is high.

## Success Criteria

- The model-sweep runner can run all configured models by changing only the manifest `model` field.
- Every model report stores exact `model`, provider label, prompt mode, run date, temperature, max tokens, input truncation policy, and report path.
- Prompt-only baselines do not call CrossEvidence grounding, dual-track reconciliation, verifier scoring, ontology target-safe context, or gold labels.
- Citation-required prompt output includes a `source_quote`; the benchmark only maps that quote to canonical source text for measurement.
- Frozen output includes per-model Precision/Recall/F1, CVR, HCR, SpanBoundaryF1, ESR, TraceableF1, error rate, and latency.
- Main paper tables and claim matrix are updated with conservative wording.

## Non-Goals

- Do not add new providers or provider-specific clients.
- Do not introduce a new extraction algorithm inside the baseline.
- Do not tune prompts per model.
- Do not use expected fields, ClinGen classifications, evaluator matches, or gold relationship labels at runtime.
- Do not change CrossEvidence candidate method while running this comparison.

## Task 1: Add Typed Model-Sweep Manifest Loader

**Files:**
- Create: `benchmark/layer3/baselines/model_sweep_contracts.py`
- Create: `benchmark/layer3/baselines/prompt_model_sweep.example.json`
- Test: `backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py`

**Step 1: Write the failing tests**

Create `backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py`:

```python
"""Tests for prompt-only model sweep manifest contracts."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.layer3.baselines.model_sweep_contracts import (
    PromptModelSpec,
    load_prompt_model_sweep_manifest,
)


def test_load_prompt_model_sweep_manifest_keeps_model_aliases(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_label": "prompt_frontier_20260615",
                "prompt_mode": "citation_required",
                "temperature": 0.0,
                "max_tokens": 4096,
                "input_max_chars": 50000,
                "models": [
                    {
                        "baseline_id": "B6_GPT5_PROMPT_CITE",
                        "baseline_name": "GPT-5 prompt-only citation-required",
                        "provider_family": "openai",
                        "model": "gpt-5",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_prompt_model_sweep_manifest(manifest_path)

    assert manifest.run_label == "prompt_frontier_20260615"
    assert manifest.prompt_mode == "citation_required"
    assert manifest.models == (
        PromptModelSpec(
            baseline_id="B6_GPT5_PROMPT_CITE",
            baseline_name="GPT-5 prompt-only citation-required",
            provider_family="openai",
            model="gpt-5",
        ),
    )


def test_load_prompt_model_sweep_manifest_rejects_duplicate_baseline_ids(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_label": "bad",
                "prompt_mode": "citation_required",
                "models": [
                    {"baseline_id": "B6", "baseline_name": "one", "provider_family": "x", "model": "m1"},
                    {"baseline_id": "B6", "baseline_name": "two", "provider_family": "x", "model": "m2"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate baseline_id"):
        load_prompt_model_sweep_manifest(manifest_path)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py -q
```

Expected: FAIL because `model_sweep_contracts.py` does not exist.

**Step 3: Implement the contracts**

Create `benchmark/layer3/baselines/model_sweep_contracts.py`:

```python
"""Typed contracts for prompt-only frontier model sweep baselines."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Mapping, cast


PromptMode = Literal["citation_required", "direct_json"]


@dataclass(frozen=True)
class PromptModelSpec:
    """One provider model evaluated under an identical prompt-only baseline."""

    baseline_id: str
    baseline_name: str
    provider_family: str
    model: str


@dataclass(frozen=True)
class PromptModelSweepManifest:
    """Configuration for one prompt-only model sweep."""

    run_label: str
    prompt_mode: PromptMode
    temperature: float
    max_tokens: int
    input_max_chars: int
    models: tuple[PromptModelSpec, ...]


def load_prompt_model_sweep_manifest(path: Path) -> PromptModelSweepManifest:
    """Load and validate a prompt-only model sweep manifest."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    models = tuple(_parse_model_spec(item) for item in _list(payload.get("models")))
    _validate_unique_baseline_ids(models)
    return PromptModelSweepManifest(
        run_label=str(payload.get("run_label") or path.stem),
        prompt_mode=_prompt_mode(payload.get("prompt_mode")),
        temperature=float(payload.get("temperature", 0.0)),
        max_tokens=int(payload.get("max_tokens", 4096)),
        input_max_chars=int(payload.get("input_max_chars", 50000)),
        models=models,
    )


def _parse_model_spec(raw: object) -> PromptModelSpec:
    if not isinstance(raw, Mapping):
        raise ValueError("Each model entry must be an object")
    return PromptModelSpec(
        baseline_id=str(raw.get("baseline_id") or "").strip(),
        baseline_name=str(raw.get("baseline_name") or "").strip(),
        provider_family=str(raw.get("provider_family") or "").strip(),
        model=str(raw.get("model") or "").strip(),
    )


def _validate_unique_baseline_ids(models: tuple[PromptModelSpec, ...]) -> None:
    seen: set[str] = set()
    for model in models:
        if not model.baseline_id:
            raise ValueError("baseline_id is required")
        if not model.baseline_name:
            raise ValueError(f"baseline_name is required for {model.baseline_id}")
        if not model.model:
            raise ValueError(f"model is required for {model.baseline_id}")
        if model.baseline_id in seen:
            raise ValueError(f"Duplicate baseline_id: {model.baseline_id}")
        seen.add(model.baseline_id)


def _prompt_mode(value: object) -> PromptMode:
    text = str(value or "citation_required")
    if text not in {"citation_required", "direct_json"}:
        raise ValueError(f"Unsupported prompt_mode: {text}")
    return cast(PromptMode, text)


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []
```

Create `benchmark/layer3/baselines/prompt_model_sweep.example.json`:

```json
{
  "run_label": "prompt_frontier_20260615",
  "prompt_mode": "citation_required",
  "temperature": 0.0,
  "max_tokens": 4096,
  "input_max_chars": 50000,
  "models": [
    {
      "baseline_id": "B6_GPT5_PROMPT_CITE",
      "baseline_name": "GPT-5 prompt-only citation-required",
      "provider_family": "openai",
      "model": "gpt-5"
    },
    {
      "baseline_id": "B7_CLAUDE_PROMPT_CITE",
      "baseline_name": "Claude prompt-only citation-required",
      "provider_family": "anthropic",
      "model": "REPLACE_WITH_PROVIDER_ALIAS"
    },
    {
      "baseline_id": "B8_GEMINI_PROMPT_CITE",
      "baseline_name": "Gemini Pro prompt-only citation-required",
      "provider_family": "google",
      "model": "REPLACE_WITH_PROVIDER_ALIAS"
    },
    {
      "baseline_id": "B9_QWEN_PROMPT_CITE",
      "baseline_name": "Qwen prompt-only citation-required",
      "provider_family": "qwen",
      "model": "REPLACE_WITH_PROVIDER_ALIAS"
    },
    {
      "baseline_id": "B10_DEEPSEEK_PROMPT_CITE",
      "baseline_name": "DeepSeek prompt-only citation-required",
      "provider_family": "deepseek",
      "model": "REPLACE_WITH_PROVIDER_ALIAS"
    }
  ]
}
```

**Step 4: Run the test to verify it passes**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add benchmark/layer3/baselines/model_sweep_contracts.py benchmark/layer3/baselines/prompt_model_sweep.example.json backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py
git commit -m "feat(benchmark): add prompt model sweep contracts"
```

## Task 2: Add Benchmark Metadata To Baseline Reports

**Files:**
- Modify: `benchmark/layer3/baselines/runner.py`
- Test: `backend/tests/benchmark/layer3/test_baseline_runner.py`

**Step 1: Write the failing test**

Append to `backend/tests/benchmark/layer3/test_baseline_runner.py`:

```python
def test_baseline_report_serializes_metadata(tmp_path: Path) -> None:
    report = BaselineReport(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        total_entries=0,
        total_duration_s=0.0,
        aggregates={"overall": {"precision": 0.0, "recall": 0.0, "f1": 0.0}},
        per_entry=[],
    )
    config = BaselineConfig(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        ground_truth_dir=tmp_path,
        reports_dir=tmp_path,
        metadata={
            "model": "gpt-5",
            "prompt_mode": "citation_required",
            "temperature": 0.0,
        },
    )

    payload = _serialize_report(report, config, None)

    assert payload["config"]["model"] == "gpt-5"
    assert payload["config"]["prompt_mode"] == "citation_required"
    assert payload["config"]["temperature"] == 0.0
```

Import `_serialize_report`, `BaselineConfig`, and `BaselineReport` if the file does not already import them.

**Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_baseline_runner.py -q
```

Expected: FAIL because `BaselineConfig.metadata` does not exist.

**Step 3: Implement metadata support**

Modify `BaselineConfig` in `benchmark/layer3/baselines/runner.py`:

```python
@dataclass(frozen=True)
class BaselineConfig:
    """Configuration for a baseline evaluation run."""

    baseline_id: str
    baseline_name: str
    ground_truth_dir: Path = GROUND_TRUTH_DIR
    reports_dir: Path = REPORTS_DIR
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None
    save_report: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)
```

Add `Mapping` to imports from `collections.abc`.

Modify `_serialize_report` config block:

```python
        "config": {
            "ground_truth_dir": str(config.ground_truth_dir),
            "limit": config.limit,
            "entry_ids": list(config.entry_ids),
            "report_path": str(report_path) if report_path else None,
            **dict(config.metadata),
        },
```

**Step 4: Run the test to verify it passes**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_baseline_runner.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add benchmark/layer3/baselines/runner.py backend/tests/benchmark/layer3/test_baseline_runner.py
git commit -m "feat(benchmark): record baseline model metadata"
```

## Task 3: Add Citation-Required Prompt-Only Extraction Mode

**Files:**
- Modify: `benchmark/layer3/baselines/llm_common.py`
- Test: `backend/tests/benchmark/layer3/test_prompt_only_citation_baseline.py`

**Step 1: Write the failing tests**

Create `backend/tests/benchmark/layer3/test_prompt_only_citation_baseline.py`:

```python
"""Tests for prompt-only citation-required LLM baseline behavior."""
from __future__ import annotations

from benchmark.layer3.baselines.llm_common import (
    BaselineLLMEvidenceItem,
    quote_to_source_span,
)


def test_baseline_llm_evidence_item_accepts_source_quote() -> None:
    item = BaselineLLMEvidenceItem.model_validate(
        {
            "field_id": "A.gene_symbol",
            "status": "found",
            "value": "MECP2",
            "confidence": "high",
            "source_quote": "Mutations in MECP2 cause Rett syndrome.",
        }
    )

    assert item.confidence == 0.9
    assert item.source_quote == "Mutations in MECP2 cause Rett syndrome."


def test_quote_to_source_span_maps_exact_quote() -> None:
    source_text = "Intro.\nMutations in MECP2 cause Rett syndrome.\nDiscussion."

    span = quote_to_source_span("Mutations in MECP2 cause Rett syndrome.", source_text)

    assert span == {
        "span_id": "llm-quote",
        "start_offset": 7,
        "end_offset": 46,
        "text_snippet": "Mutations in MECP2 cause Rett syndrome.",
        "source_precision": "llm_quote_exact",
    }


def test_quote_to_source_span_preserves_unmapped_quote_for_hcr() -> None:
    span = quote_to_source_span("This quote is not present.", "MECP2 source text.")

    assert span["start_offset"] == -1
    assert span["end_offset"] == -1
    assert span["text_snippet"] == "This quote is not present."
    assert span["source_precision"] == "llm_quote_unmapped"
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_only_citation_baseline.py -q
```

Expected: FAIL because `source_quote` and `quote_to_source_span` are not implemented.

**Step 3: Implement source-quote support**

Modify `BaselineMode`:

```python
BaselineMode = Literal[
    "naive",
    "translate_then_extract",
    "original_only",
    "rag",
    "single_agent_cot",
    "citation_required",
    "direct_json",
]
```

Add `source_quote` to `BaselineLLMEvidenceItem`:

```python
    source_quote: str = ""
```

Modify `LLMBaselineExtractor.__init__` to accept model and runtime overrides:

```python
    def __init__(
        self,
        mode: BaselineMode,
        *,
        model_override: str | None = None,
        temperature: float = 0.0,
        max_tokens_override: int | None = None,
    ):
        self._mode = mode
        runtime = _runtime_config(use_reasoning=mode == "single_agent_cot")
        model = model_override or runtime.model
        self._client = create_llm_client(
            model=model,
            base_url=runtime.base_url,
            api_keys=runtime.api_keys,
            temperature=temperature,
            max_tokens=max_tokens_override or runtime.max_tokens,
            timeout=runtime.timeout,
        )
```

Modify `make_extractor`:

```python
def make_extractor(
    mode: BaselineMode,
    *,
    model_override: str | None = None,
    temperature: float = 0.0,
    max_tokens_override: int | None = None,
) -> LLMBaselineExtractor:
    """Create an LLM-backed baseline extractor."""
    return LLMBaselineExtractor(
        mode=mode,
        model_override=model_override,
        temperature=temperature,
        max_tokens_override=max_tokens_override,
    )
```

Modify `extract` item conversion:

```python
        return [
            BaselineEvidenceItem(
                field_id=item.field_id,
                status=item.status,
                value=item.value,
                confidence=item.confidence,
                source_span=(
                    quote_to_source_span(item.source_quote, source_text)
                    if self._mode == "citation_required" and item.status == "found"
                    else None
                ),
            )
            for item in response.evidence_items
        ]
```

Add quote mapping:

```python
def quote_to_source_span(source_quote: str, source_text: str) -> dict[str, object]:
    """Map an LLM-provided quote to canonical source text for measurement only."""
    quote = source_quote.strip()
    if not quote:
        return {
            "span_id": "llm-quote",
            "start_offset": -1,
            "end_offset": -1,
            "text_snippet": "",
            "source_precision": "llm_quote_missing",
        }
    start = source_text.find(quote)
    if start >= 0:
        return {
            "span_id": "llm-quote",
            "start_offset": start,
            "end_offset": start + len(quote),
            "text_snippet": quote,
            "source_precision": "llm_quote_exact",
        }
    return {
        "span_id": "llm-quote",
        "start_offset": -1,
        "end_offset": -1,
        "text_snippet": quote,
        "source_precision": "llm_quote_unmapped",
    }
```

This quote mapping is only for measurement. It is not CrossEvidence grounding, does not repair the value, and does not feed back into acceptance.

**Step 4: Add the citation-required prompt**

Modify `_build_extraction_prompt` mode instructions:

```python
        "citation_required": (
            "Use one direct prompt-only extraction pass. Do not use tools, retrieval, "
            "multi-agent validation, evidence graphs, or reconciliation. For each found "
            "field, include source_quote as a verbatim contiguous quote from the document text."
        ),
        "direct_json": "Use one direct extraction pass. Do not perform multi-stage validation.",
```

Modify the schema instruction:

```python
        "Each evidence item must have field_id, status (found or not_found), value, confidence, "
        "and source_quote. For found items, source_quote must be a verbatim contiguous excerpt "
        "from the document text, preferably <= 240 characters. For not_found items, source_quote "
        "must be an empty string.\n"
```

**Step 5: Run tests**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_only_citation_baseline.py backend/tests/benchmark/layer3/test_baseline_runner.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add benchmark/layer3/baselines/llm_common.py backend/tests/benchmark/layer3/test_prompt_only_citation_baseline.py
git commit -m "feat(benchmark): add citation-required prompt baseline"
```

## Task 4: Add Model-Sweep CLI Runner

**Files:**
- Create: `benchmark/layer3/baselines/prompt_model_sweep.py`
- Test: `backend/tests/benchmark/layer3/test_prompt_model_sweep_runner.py`

**Step 1: Write the failing test**

Create `backend/tests/benchmark/layer3/test_prompt_model_sweep_runner.py`:

```python
"""Tests for prompt-only model sweep runner."""
from __future__ import annotations

from pathlib import Path

from benchmark.layer3.baselines.prompt_model_sweep import build_baseline_config
from benchmark.layer3.baselines.model_sweep_contracts import PromptModelSpec, PromptModelSweepManifest


def test_build_baseline_config_records_model_metadata(tmp_path: Path) -> None:
    manifest = PromptModelSweepManifest(
        run_label="prompt_frontier_20260615",
        prompt_mode="citation_required",
        temperature=0.0,
        max_tokens=4096,
        input_max_chars=50000,
        models=(),
    )
    spec = PromptModelSpec(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        provider_family="openai",
        model="gpt-5",
    )

    config = build_baseline_config(
        manifest=manifest,
        spec=spec,
        ground_truth_dir=tmp_path / "gt",
        reports_dir=tmp_path / "reports",
        entry_ids=("clingen_000",),
        limit=None,
        save_report=True,
    )

    assert config.baseline_id == "B6_GPT5_PROMPT_CITE"
    assert config.metadata["model"] == "gpt-5"
    assert config.metadata["prompt_mode"] == "citation_required"
    assert config.metadata["run_label"] == "prompt_frontier_20260615"
```

**Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_model_sweep_runner.py -q
```

Expected: FAIL because `prompt_model_sweep.py` does not exist.

**Step 3: Implement the CLI runner**

Create `benchmark/layer3/baselines/prompt_model_sweep.py`:

```python
"""Run prompt-only extraction baselines across multiple provider model aliases."""
from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from benchmark.layer3.baselines.llm_common import make_extractor
from benchmark.layer3.baselines.model_sweep_contracts import (
    PromptModelSpec,
    PromptModelSweepManifest,
    load_prompt_model_sweep_manifest,
)
from benchmark.layer3.baselines.runner import (
    BaselineConfig,
    GROUND_TRUTH_DIR,
    REPORTS_DIR,
    run_baseline_evaluation,
)


def build_baseline_config(
    *,
    manifest: PromptModelSweepManifest,
    spec: PromptModelSpec,
    ground_truth_dir: Path,
    reports_dir: Path,
    entry_ids: tuple[str, ...],
    limit: int | None,
    save_report: bool,
) -> BaselineConfig:
    """Build a baseline runner config for one model in the sweep."""
    return BaselineConfig(
        baseline_id=spec.baseline_id,
        baseline_name=spec.baseline_name,
        ground_truth_dir=ground_truth_dir,
        reports_dir=reports_dir,
        entry_ids=entry_ids,
        limit=limit,
        save_report=save_report,
        metadata={
            "run_label": manifest.run_label,
            "prompt_mode": manifest.prompt_mode,
            "provider_family": spec.provider_family,
            "model": spec.model,
            "temperature": manifest.temperature,
            "max_tokens": manifest.max_tokens,
            "input_max_chars": manifest.input_max_chars,
            "run_date": time.strftime("%Y-%m-%d"),
        },
    )


async def run_model_sweep(
    *,
    manifest_path: Path,
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
    reports_dir: Path = REPORTS_DIR,
    entry_ids: tuple[str, ...] = (),
    limit: int | None = None,
    save_report: bool = True,
) -> list[Path]:
    """Run all model specs in a prompt-only sweep manifest."""
    manifest = load_prompt_model_sweep_manifest(manifest_path)
    report_paths: list[Path] = []
    for spec in manifest.models:
        extractor = make_extractor(
            manifest.prompt_mode,
            model_override=spec.model,
            temperature=manifest.temperature,
            max_tokens_override=manifest.max_tokens,
        )
        report = await run_baseline_evaluation(
            build_baseline_config(
                manifest=manifest,
                spec=spec,
                ground_truth_dir=ground_truth_dir,
                reports_dir=reports_dir,
                entry_ids=entry_ids,
                limit=limit,
                save_report=save_report,
            ),
            extractor.extract,
        )
        if report.report_path is not None:
            report_paths.append(report.report_path)
    return report_paths


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for prompt-only model sweeps."""
    parser = argparse.ArgumentParser(description="Run prompt-only model-sweep baselines.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)

    report_paths = asyncio.run(
        run_model_sweep(
            manifest_path=args.manifest,
            ground_truth_dir=args.ground_truth_dir,
            reports_dir=args.reports_dir,
            entry_ids=tuple(args.entries),
            limit=args.limit,
            save_report=not args.no_save,
        )
    )
    for report_path in report_paths:
        print(f"REPORT: {report_path}")


if __name__ == "__main__":
    main()
```

If `GROUND_TRUTH_DIR` and `REPORTS_DIR` are not exported by `runner.py`, import them from `benchmark.layer3.evaluate` instead.

**Step 4: Run tests**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_model_sweep_runner.py backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py -q
```

Expected: PASS.

**Step 5: Smoke-test one entry with one cheap model**

Copy the example manifest to a local untracked file and replace one model alias with a known working low-cost model:

```bash
cp benchmark/layer3/baselines/prompt_model_sweep.example.json /tmp/prompt_model_sweep_smoke.json
```

Edit `/tmp/prompt_model_sweep_smoke.json` to contain only one model. Then run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.prompt_model_sweep \
  --manifest /tmp/prompt_model_sweep_smoke.json \
  --entries clingen_000
```

Expected: one `baseline_b*.json` report in `benchmark/layer3/reports/`.

**Step 6: Commit**

```bash
git add benchmark/layer3/baselines/prompt_model_sweep.py backend/tests/benchmark/layer3/test_prompt_model_sweep_runner.py
git commit -m "feat(benchmark): run prompt-only model sweeps"
```

## Task 5: Generate Traceability Reports For Prompt-Only Baselines

**Files:**
- No source changes required unless traceability warnings need refinement.
- Output: `benchmark/layer3/reports/traceability_B6_GPT5_PROMPT_CITE_*.json`, etc.

**Step 1: Run traceability for each generated baseline**

Example:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics \
  --baseline-report benchmark/layer3/reports/baseline_b6_gpt5_prompt_cite_<TIMESTAMP>.json \
  --write
```

Repeat for B7-B10.

**Step 2: Inspect expected metrics**

Expected:

- If the model returned exact quotes, CVR should be high.
- If the model returned paraphrases as citations, HCR should increase.
- If the model omitted quotes, traceability report should warn that citation surface is incomplete.

**Step 3: Do not repair baseline outputs**

Do not use CrossEvidence grounding to correct baseline quotes. The goal is to measure prompt-only citation behavior.

**Step 4: Commit frozen reports only after final run**

```bash
git add benchmark/layer3/reports/baseline_b6_* benchmark/layer3/reports/traceability_B6_* \
        benchmark/layer3/reports/baseline_b7_* benchmark/layer3/reports/traceability_B7_* \
        benchmark/layer3/reports/baseline_b8_* benchmark/layer3/reports/traceability_B8_* \
        benchmark/layer3/reports/baseline_b9_* benchmark/layer3/reports/traceability_B9_* \
        benchmark/layer3/reports/baseline_b10_* benchmark/layer3/reports/traceability_B10_*
git commit -m "test(benchmark): freeze prompt-only model baseline reports"
```

## Task 6: Add Prompt-Model Comparison Table Builder

**Files:**
- Create: `benchmark/layer3/analysis/prompt_model_baseline_tables.py`
- Test: `backend/tests/benchmark/layer3/test_prompt_model_baseline_tables.py`

**Step 1: Write the failing test**

Create `backend/tests/benchmark/layer3/test_prompt_model_baseline_tables.py`:

```python
"""Tests for prompt-only model baseline paper tables."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.prompt_model_baseline_tables import build_prompt_model_table


def test_build_prompt_model_table_combines_extraction_and_traceability(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline_b6.json"
    traceability_path = tmp_path / "traceability_b6.json"
    baseline_path.write_text(
        json.dumps(
            {
                "baseline_id": "B6_GPT5_PROMPT_CITE",
                "baseline_name": "GPT-5 prompt-only citation-required",
                "config": {
                    "model": "gpt-5",
                    "provider_family": "openai",
                    "prompt_mode": "citation_required",
                },
                "total_entries": 30,
                "total_duration_s": 300.0,
                "aggregates": {"overall": {"precision": 0.9, "recall": 0.8, "f1": 0.8471}},
                "per_entry": [],
            }
        ),
        encoding="utf-8",
    )
    traceability_path.write_text(
        json.dumps(
            {
                "strategy_or_baseline_id": "B6_GPT5_PROMPT_CITE",
                "overall": {
                    "traceability": {
                        "citation_validity_rate": 0.75,
                        "hallucinated_citation_rate": 0.25,
                        "span_boundary_f1": 0.7,
                        "evidence_support_rate": 0.8,
                        "traceable_f1": 0.6353,
                        "cross_lingual_consistency": None,
                    }
                },
                "counts": {"citation_total": 10},
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    table = build_prompt_model_table(
        baseline_report_paths=(baseline_path,),
        traceability_report_paths=(traceability_path,),
        candidate_f1=0.9474,
        candidate_traceable_f1=0.9474,
    )

    row = table.rows[0]
    assert row["baseline_id"] == "B6_GPT5_PROMPT_CITE"
    assert row["model"] == "gpt-5"
    assert row["f1"] == 0.8471
    assert row["delta_f1_vs_ours"] == -0.1003
    assert row["traceable_f1"] == 0.6353
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_model_baseline_tables.py -q
```

Expected: FAIL because the table builder does not exist.

**Step 3: Implement table builder**

Implement a small dataclass-based builder that:

- loads baseline reports;
- loads traceability reports by `strategy_or_baseline_id`;
- emits Markdown and CSV;
- includes candidate deltas.

Columns:

```text
baseline_id
baseline_name
provider_family
model
prompt_mode
total_entries
precision
recall
f1
delta_f1_vs_ours
citation_validity_rate
hallucinated_citation_rate
span_boundary_f1
evidence_support_rate
traceable_f1
delta_traceable_f1_vs_ours
citation_total
error_rate
avg_latency_s
warnings
```

Use typed dataclasses or `TypedDict` payloads. Do not return naked `dict`.

**Step 4: Run test**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_prompt_model_baseline_tables.py -q
```

Expected: PASS.

**Step 5: Generate final table**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.prompt_model_baseline_tables \
  --candidate-f1 0.9474 \
  --candidate-traceable-f1 0.9474 \
  --baseline-reports benchmark/layer3/reports/baseline_b6_*.json benchmark/layer3/reports/baseline_b7_*.json benchmark/layer3/reports/baseline_b8_*.json benchmark/layer3/reports/baseline_b9_*.json benchmark/layer3/reports/baseline_b10_*.json \
  --traceability-reports benchmark/layer3/reports/traceability_B6_*.json benchmark/layer3/reports/traceability_B7_*.json benchmark/layer3/reports/traceability_B8_*.json benchmark/layer3/reports/traceability_B9_*.json benchmark/layer3/reports/traceability_B10_*.json \
  --write
```

Expected: `prompt_model_baseline_tables_<TIMESTAMP>.md` and `.csv` are written.

**Step 6: Commit**

```bash
git add benchmark/layer3/analysis/prompt_model_baseline_tables.py backend/tests/benchmark/layer3/test_prompt_model_baseline_tables.py benchmark/layer3/reports/prompt_model_baseline_tables_*
git commit -m "feat(benchmark): summarize prompt-only model baselines"
```

## Task 7: Run Full Prompt-Only Model Sweep

**Files:**
- Create local runtime manifest first: `/tmp/prompt_model_sweep_20260615.json`
- Freeze final manifest copy: `benchmark/layer3/baselines/prompt_model_sweep_20260615.json`
- Output: `benchmark/layer3/reports/baseline_b6_*.json` through `baseline_b10_*.json`

**Step 1: Create final run manifest**

Copy example manifest:

```bash
cp benchmark/layer3/baselines/prompt_model_sweep.example.json /tmp/prompt_model_sweep_20260615.json
```

Replace each `REPLACE_WITH_PROVIDER_ALIAS` with the exact model alias exposed by the integrated supplier on 2026-06-15.

**Step 2: Run one-entry canary across all models**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.prompt_model_sweep \
  --manifest /tmp/prompt_model_sweep_20260615.json \
  --entries clingen_000
```

Expected:

- All configured models return valid JSON or explicit errors.
- No secret values are printed.
- No model-specific prompt edits are needed.

**Step 3: Run full N=30 sweep**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.baselines.prompt_model_sweep \
  --manifest /tmp/prompt_model_sweep_20260615.json
```

Expected:

- B6-B10 report files are generated.
- `total_entries` equals 30 for every primary baseline.

**Step 4: Freeze manifest copy**

After the run succeeds, copy the exact manifest used:

```bash
cp /tmp/prompt_model_sweep_20260615.json benchmark/layer3/baselines/prompt_model_sweep_20260615.json
```

Verify the manifest contains model names but no API keys.

**Step 5: Generate traceability reports and tables**

Use Task 5 and Task 6 commands.

**Step 6: Commit**

```bash
git add benchmark/layer3/baselines/prompt_model_sweep_20260615.json benchmark/layer3/reports/baseline_b*_prompt_cite_* benchmark/layer3/reports/traceability_B*_PROMPT_CITE_* benchmark/layer3/reports/prompt_model_baseline_tables_*
git commit -m "test(benchmark): freeze prompt-only frontier model sweep"
```

## Task 8: Update Main Paper Package

**Files:**
- Modify: `docs/active/2026-06-15-bibm-main-paper-claim-matrix.md`
- Modify: `docs/active/2026-06-15-bibm-main-paper-manuscript-draft.md`
- Modify: `docs/active/2026-06-15-bibm-main-paper-outline.md`
- Modify: `benchmark/layer3/reports/main_paper_tables_<NEW>.md` only if the prompt table is folded into the main table package.

**Step 1: Update claim matrix**

Add a new evidence row:

```markdown
| Prompt-only model sweep | `benchmark/layer3/reports/prompt_model_baseline_tables_<TIMESTAMP>.md` | B6-B10 model aliases, P/R/F1, CVR/HCR, TraceableF1 |
```

Add safe claim:

```markdown
CrossEvidence remains competitive with prompt-only frontier models while adding citation-valid-by-construction acceptance and explicit traceability metrics.
```

Add forbidden claim unless supported:

```markdown
"CrossEvidence significantly outperforms every frontier model baseline."
```

**Step 2: Update manuscript results**

Add one paragraph after the existing baseline table:

```markdown
To separate model strength from method design, we additionally ran a prompt-only model sweep across five mainstream frontier-model families using the same citation-required JSON prompt and the same input context. These baselines differ only in the provider model alias. This comparison tests whether prompt engineering alone can replace evidence-graph grounding and reconciliation.
```

Then insert the generated prompt-model table.

**Step 3: Update limitations**

Add:

```markdown
The prompt-only model sweep is provider-alias dependent. We freeze exact model names and run date in the benchmark manifest, but hosted model behavior may change over time.
```

**Step 4: Run docs sanity check**

Run:

```bash
rg -n "significantly outperforms all|100% semantically|No hallucination risk|native multilingual superiority" docs/active/2026-06-15-bibm-main-paper-*.md
```

Expected: no unsafe wording except inside explicit forbidden-claim tables.

**Step 5: Commit**

```bash
git add docs/active/2026-06-15-bibm-main-paper-claim-matrix.md docs/active/2026-06-15-bibm-main-paper-manuscript-draft.md docs/active/2026-06-15-bibm-main-paper-outline.md
git commit -m "docs(bibm): add prompt-only model baseline results"
```

## Task 9: Verification Gate

**Files:**
- No new files unless fixing failures.

**Step 1: Run focused tests**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_baseline_runner.py \
  backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py \
  backend/tests/benchmark/layer3/test_prompt_only_citation_baseline.py \
  backend/tests/benchmark/layer3/test_prompt_model_sweep_runner.py \
  backend/tests/benchmark/layer3/test_prompt_model_baseline_tables.py \
  backend/tests/benchmark/layer3/test_traceability_metrics.py \
  -q
```

Expected: PASS.

**Step 2: Run Ruff**

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  benchmark/layer3/baselines/model_sweep_contracts.py \
  benchmark/layer3/baselines/llm_common.py \
  benchmark/layer3/baselines/prompt_model_sweep.py \
  benchmark/layer3/analysis/prompt_model_baseline_tables.py \
  backend/tests/benchmark/layer3/test_prompt_model_sweep_contracts.py \
  backend/tests/benchmark/layer3/test_prompt_only_citation_baseline.py \
  backend/tests/benchmark/layer3/test_prompt_model_sweep_runner.py \
  backend/tests/benchmark/layer3/test_prompt_model_baseline_tables.py
```

Expected: PASS.

**Step 3: Verify no answer-key leakage**

Run:

```bash
rg -n "expected_evidence|expected_standardization|classification|ClinGen validity|gold" benchmark/layer3/baselines/model_sweep_contracts.py benchmark/layer3/baselines/llm_common.py benchmark/layer3/baselines/prompt_model_sweep.py benchmark/layer3/analysis/prompt_model_baseline_tables.py
```

Expected:

- `expected_evidence` and `expected_standardization` may appear only in evaluator/runner comparison code, not prompt construction.
- `classification` and gold relationship labels must not be included in runtime prompts.

**Step 4: Verify report completeness**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python - <<'PY'
import json
from pathlib import Path

reports = sorted(Path("benchmark/layer3/reports").glob("baseline_b*_prompt_cite_*.json"))
for path in reports:
    payload = json.loads(path.read_text())
    assert payload["total_entries"] == 30, path
    assert payload["config"].get("model"), path
    assert payload["config"].get("prompt_mode") == "citation_required", path
print(f"checked {len(reports)} prompt-only reports")
PY
```

Expected: `checked 5 prompt-only reports` for the primary paper set.

**Step 5: Final commit if verification changed docs or reports**

```bash
git status --short
git add <only files from this plan>
git commit -m "docs(bibm): finalize prompt-only baseline evidence"
```

Do not stage `frontend/src/features/evidence-search/components/MarkdownDocumentViewer.tsx` unless the user explicitly asks; it is unrelated and currently user-owned.

## Paper Decision Gate After This Plan

Use the following interpretation:

| Outcome | Paper stance |
|---|---|
| CrossEvidence beats all prompt-only models on F1 and TraceableF1 | Strong Main Paper claim, but still report significance before saying "outperforms." |
| CrossEvidence is close on F1 but wins TraceableF1/CVR/HCR | Best expected outcome; claim traceability-centered competitive method. |
| A prompt-only model beats CrossEvidence on F1 but has lower traceability | Still publishable if the novelty is framed around auditable evidence acceptance. |
| A prompt-only model beats CrossEvidence on F1 and traceability | Main Paper claim must shift; method may need stronger reconciliation or a resource/demo framing. |

The target result for the current BIBM submission is not necessarily highest raw F1. The target is:

```text
competitive extraction + stronger traceable extraction + no answer-key leakage + frozen reproducible manifest
```

## Execution Order

1. Implement Tasks 1-4.
2. Run one-entry canary.
3. Run full N=30 prompt-only model sweep.
4. Generate traceability reports and prompt-model table.
5. Update paper claims and manuscript.
6. Run verification gate.
7. Commit only benchmark, report, and docs files from this plan.

