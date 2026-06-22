"""Baseline: Prompt-engineered LLM extraction vs full pipeline.

Sends each source article to the LLM with a single structured prompt
asking it to extract ACMG/ClinGen evidence fields. No chunking, no
dual-track, no catalog system, no source grounding — just a well-crafted
prompt + raw LLM JSON output.

Evaluates results against the same source-visible adjudication labels
used by the pipeline, producing a direct F1 comparison.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.evaluate_adjudicated import (
    AdjudicatedMetric,
    evaluate_adjudicated_entry,
)
from benchmark.optimization.fused75.run_baseline_tracks import TrackItem

_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication/dev")
_DEFAULT_FUSED_ROOT = Path("benchmark/data/ground_truth/clinvar_fused")
_DEFAULT_OUTPUT = Path("benchmark/optimization/fused75/reports/baseline_prompt_engineering.json")

_EXTRACTION_PROMPT = """\
You are a medical genetics evidence extraction expert. Given the following research article, extract structured evidence fields relevant to ACMG/AMP variant classification and ClinGen gene-disease validity assessment.

For each field listed below, extract the value if it is explicitly stated or clearly implied in the article. If a field is not present, omit it.

**Required fields to extract:**
{field_descriptions}

**Article text:**
---
{article_text}
---

Return your answer as a JSON array of objects, each with "field_id" and "value" keys:
```json
[
  {{"field_id": "A.gene_symbol", "value": "BRCA1"}},
  {{"field_id": "B.disease_diagnosis", "value": "breast cancer"}}
]
```

Only include fields where you found evidence in the article. Do not fabricate values.
"""


@dataclass(frozen=True)
class PromptResult:
    entry_id: str
    extracted_items: tuple[TrackItem, ...]
    raw_response: str
    latency_s: float
    token_count: int


def _build_field_descriptions(labels: Sequence[Any]) -> str:
    lines = []
    for label in labels:
        if label.visibility != "source_visible":
            continue
        lines.append(f"- `{label.field_id}`: expected type of value for this field")
    return "\n".join(lines) if lines else "(no fields specified)"


def _build_field_descriptions_with_hints(labels: Sequence[Any]) -> str:
    """Build field descriptions with expected value type hints but NOT the actual expected values."""
    hints = {
        "A.gene_symbol": "HGNC gene symbol (e.g., CFTR, MECP2)",
        "A.variant_hgvs_c": "HGVS coding DNA notation (e.g., c.1521_1523del)",
        "A.variant_hgvs_p": "HGVS protein notation (e.g., p.Phe508del)",
        "A.variant_type": "variant type (e.g., missense, nonsense, deletion, insertion)",
        "A.gene_disease_relationship": "relationship type (e.g., causative, associated, modifier)",
        "B.disease_diagnosis": "disease name (e.g., cystic fibrosis, Rett syndrome)",
        "B.mode_of_inheritance_reported": "inheritance pattern abbreviation (AD, AR, XL, etc.)",
        "C.phase_status": "cis/trans/in-phase status",
        "C.in_trans_confirmation": "confirmation of in-trans configuration",
        "F.assay_type": "functional assay type description",
        "F.functional_result": "functional assay result description",
        "F.quantitative_result": "quantitative functional measurement",
        "J.clinvar_assertion": "ClinVar clinical significance (Pathogenic, Likely pathogenic, etc.)",
    }
    lines = []
    for label in labels:
        if label.visibility != "source_visible":
            continue
        hint = hints.get(label.field_id, "text value")
        lines.append(f"- `{label.field_id}`: {hint}")
    return "\n".join(lines) if lines else "(no fields specified)"


async def _call_llm(
    article_text: str,
    field_descriptions: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> tuple[str, float]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    prompt = _EXTRACTION_PROMPT.format(
        field_descriptions=field_descriptions,
        article_text=article_text[:30000],
    )

    start = time.perf_counter()
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=4096,
    )
    latency = time.perf_counter() - start
    content = response.choices[0].message.content or ""
    return content, latency


def _parse_response(raw: str) -> tuple[TrackItem, ...]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return ()
        else:
            return ()

    if not isinstance(data, list):
        return ()

    items: list[TrackItem] = []
    for entry in data:
        if isinstance(entry, dict):
            field_id = entry.get("field_id")
            value = entry.get("value")
            if field_id and value and isinstance(value, str) and value.strip():
                items.append(TrackItem(field_id=str(field_id), value=value.strip()))
    return tuple(items)


async def run_prompt_baseline(
    *,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    fused_root: Path = _DEFAULT_FUSED_ROOT,
    output_path: Path = _DEFAULT_OUTPUT,
    model: str = "gpt-5-mini",
    base_url: str = "",
    api_key: str = "",
    limit: int | None = None,
) -> dict[str, Any]:
    paths = sorted(adjudication_root.glob("*.json"))
    adjudications = tuple(
        Fused75EntryAdjudication.model_validate_json(p.read_text(encoding="utf-8"))
        for p in paths
    )
    adjudications = tuple(a for a in adjudications if a.is_complete)
    if limit:
        adjudications = adjudications[:limit]

    if not base_url or not api_key:
        from src.core.config import get_config
        cfg = get_config()
        base_url = base_url or cfg.fast_llm_base_url
        model = model or cfg.fast_llm_model
        if not api_key:
            if cfg.fast_llm_api_keys:
                api_key = cfg.fast_llm_api_keys[0]
            elif cfg.fast_llm_api_key:
                api_key = cfg.fast_llm_api_key

    total_tp = 0
    total_fp = 0
    total_fn = 0
    per_entry: list[dict[str, Any]] = []
    prompt_results: list[dict[str, Any]] = []

    for adjudication in adjudications:
        source_path = fused_root / adjudication.entry_id / "source.md"
        if not source_path.exists():
            continue

        article_text = source_path.read_text(encoding="utf-8")
        field_descriptions = _build_field_descriptions_with_hints(adjudication.labels)

        raw_response, latency = await _call_llm(
            article_text,
            field_descriptions,
            base_url=base_url,
            api_key=api_key,
            model=model,
        )
        items = _parse_response(raw_response)

        allowed_fields = {label.field_id for label in adjudication.labels}
        filtered_items = tuple(i for i in items if i.field_id in allowed_fields)

        result = evaluate_adjudicated_entry(adjudication, extracted_items=filtered_items)

        total_tp += result.metric.tp
        total_fp += result.metric.fp
        total_fn += result.metric.fn

        entry_detail = {
            "entry_id": adjudication.entry_id,
            "tp": result.metric.tp,
            "fp": result.metric.fp,
            "fn": result.metric.fn,
            "f1": result.metric.f1,
            "latency_s": round(latency, 2),
            "raw_items_count": len(items),
            "filtered_items_count": len(filtered_items),
            "field_results": [
                {"field_id": fr.field_id, "expected": fr.expected_value, "extracted": fr.extracted_value, "outcome": fr.outcome}
                for fr in result.field_results
            ],
        }
        per_entry.append(entry_detail)
        prompt_results.append({
            "entry_id": adjudication.entry_id,
            "raw_response": raw_response[:500],
            "latency_s": round(latency, 2),
        })

    tp, fp, fn = total_tp, total_fp, total_fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    pipeline_f1 = 0.7438
    pipeline_p = 0.8036
    pipeline_r = 0.6923

    report = {
        "baseline_type": "prompt_engineering",
        "description": "Single-prompt LLM extraction vs full pipeline (dual-track + catalog + chunking + normalization)",
        "model": model,
        "base_url": base_url,
        "entry_count": len(adjudications),
        "entry_ids": [a.entry_id for a in adjudications],
        "prompt_baseline": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "per_entry": per_entry,
        },
        "pipeline": {
            "precision": pipeline_p,
            "recall": pipeline_r,
            "f1": pipeline_f1,
            "variant": "target-span-field-recovery",
        },
        "comparison": {
            "f1_gap": round(pipeline_f1 - f1, 4),
            "precision_gap": round(pipeline_p - precision, 4),
            "recall_gap": round(pipeline_r - recall, 4),
            "tp_gain": 45 - tp,
            "fp_reduction": 11 - fp,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Limit entries (for testing)")
    parser.add_argument("--model", type=str, default="gpt-5-mini")
    parser.add_argument("--base-url", type=str, default="")
    parser.add_argument("--api-key", type=str, default="")
    args = parser.parse_args()

    report = asyncio.run(run_prompt_baseline(
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        limit=args.limit,
    ))

    pt = report["prompt_baseline"]
    pp = report["pipeline"]
    cmp = report["comparison"]

    print("=== Prompt Engineering Baseline ===\n")
    print(f"Model: {report['model']} @ {report['base_url']}")
    print(f"Entries: {report['entry_count']}\n")
    print(f"{'Method':<25} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"{'Prompt-engineered LLM':<25} {pt['precision']:>10.4f} {pt['recall']:>10.4f} {pt['f1']:>10.4f}")
    print(f"{'Full Pipeline':<25} {pp['precision']:>10.4f} {pp['recall']:>10.4f} {pp['f1']:>10.4f}")
    print(f"\nPipeline advantage:")
    print(f"  F1:        +{cmp['f1_gap']:.4f}")
    print(f"  Precision: +{cmp['precision_gap']:.4f}")
    print(f"  Recall:    +{cmp['recall_gap']:.4f}")
    print(f"  TP gain:   +{cmp['tp_gain']}")
    print(f"\nReport: {report.get('_output', 'benchmark/optimization/fused75/reports/baseline_prompt_engineering.json')}")


if __name__ == "__main__":
    main()
