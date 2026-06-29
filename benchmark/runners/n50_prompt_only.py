"""C0 prompt-only baseline runner for the BIBM N=50 comparison experiment.

This runner implements the C0 condition described in
``docs/active/2026-06-29-bibm-n50-comparison-ablation-design.md``: a single
citation-required extraction prompt sent directly to the reasoning LLM, with
**no agent workflow, no review validation, no target guard, no
reflection/retry loop, and no Phase 3 standardization**.  One prompt per
entry -> one response -> score it against the ground truth.

The scoring path reuses the same pure-Python matching infrastructure as the
pipeline-backed runner (:func:`benchmark.core.matching.compare_evidence` and
:func:`benchmark.core.aggregate.compute_aggregate_metrics`) so that C0
results are directly comparable to C1/C2/A1-A4.

Usage::

    cd backend && uv run python -m benchmark.runners.n50_prompt_only \
        --concurrency 4

Reports are written to ``benchmark/data/reports/n50/c0_prompt_only_<ts>.json``
with the same report shape produced by
:func:`benchmark.core.pipeline_client.run_evaluation`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from loguru import logger

from benchmark.core.aggregate import compute_aggregate_metrics
from benchmark.core.contracts import EntryMetrics
from benchmark.core.matching import (
    compare_evidence,
    mark_expected_fields_missing,
    prepare_extracted_items,
)
from benchmark.core.paths import (
    BENCHMARK_ROOT,
    GROUND_TRUTH_UNIFIED_ROOT,
    REPORTS_ROOT,
)
from benchmark.core.pipeline_client import _compute_stratified_metrics

from src.core.config import get_config
from src.utils.llm_adapter import LLMPoolAdapter, create_llm_client
from src.utils.text import strip_json_fences

try:
    from benchmark.core.mondo_hierarchy import MondoHierarchy
except ImportError:  # pragma: no cover - exercised when ontology cache absent
    MondoHierarchy = None  # type: ignore[assignment,misc]

try:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
        CATALOG_GROUPS,
        EvidenceFieldSpec,
    )
except ImportError:  # pragma: no cover - catalog is part of the backend package
    CATALOG_GROUPS = None  # type: ignore[assignment,misc]
    EvidenceFieldSpec = None  # type: ignore[assignment,misc]

__all__ = ["main", "run_prompt_only_evaluation"]


# ── Filesystem constants ────────────────────────────────────────────────

CONDITION_ID: str = "c0_prompt_only"
"""Condition identifier for the prompt-only baseline."""

DEFAULT_MANIFEST: Path = (
    BENCHMARK_ROOT
    / "data"
    / "manifests"
    / "unified_b8_n50_comparison_20260629.json"
)
"""Locked N=50 comparison manifest."""

REPORTS_N50_DIR: Path = REPORTS_ROOT / "n50"
"""Per-condition report output directory for the N=50 experiment."""


# ── Evidence catalog ────────────────────────────────────────────────────


def _eligible_catalog() -> tuple[Any, ...]:
    """Return the field catalog scope for the prompt-only baseline.

    Mirrors the pipeline's ``broad`` extraction scope: every field except
    the cross-paper ClinGen GDV curation category (``K``), which is not
    single-paper extractable.

    Returns:
        Tuple of :class:`EvidenceFieldSpec` objects, or an empty tuple when
        the catalog module is unavailable.
    """
    if CATALOG_GROUPS is None:
        return ()
    return (*CATALOG_GROUPS["high_signal"], *CATALOG_GROUPS["supporting"])


def _catalog_compact_text(catalog: tuple[Any, ...]) -> str:
    """Render the catalog as ``field_id: field_name [acmg_codes]`` lines.

    Args:
        catalog: Tuple of :class:`EvidenceFieldSpec` objects.

    Returns:
        Newline-joined compact catalog text for the extraction prompt.
    """
    lines: list[str] = []
    for spec in catalog:
        codes = ",".join(spec.acmg_codes) if spec.acmg_codes else "-"
        req = "*" if spec.required_for_scorable else ""
        lines.append(f"{spec.field_id}{req}: {spec.field_name} [{codes}]")
    return "\n".join(lines)


# ── Prompt construction ─────────────────────────────────────────────────


def build_extraction_prompt(
    gene_symbol: str,
    disease_label: str,
    source_text: str,
    catalog_text: str,
) -> str:
    """Build the single citation-required extraction prompt for one entry.

    The prompt is fully self-contained: it embeds the target gene-disease
    pair, the eligible evidence field catalog, and the full source markdown.
    It instructs the model to return one JSON object whose ``evidence_items``
    list carries a ``status``, ``value``, ``confidence``, and a verbatim
    ``source_span.text_snippet`` citation for every ``found`` field.

    Args:
        gene_symbol: Target gene symbol (e.g. ``"ABCA3"``).
        disease_label: Target disease label (e.g. ``"ABCA3 deficiency"``).
        source_text: Full source markdown text for the entry.
        catalog_text: Compact catalog text from :func:`_catalog_compact_text`.

    Returns:
        The complete prompt string to send to the LLM.
    """
    return f"""You are extracting structured evidence from a biomedical document for a SPECIFIC target gene-disease pair.

TARGET GENE: {gene_symbol}
TARGET DISEASE: {disease_label}

STRICT TARGET RULES:
1. Extract evidence ONLY for the target gene-disease pair above.
2. Other genes mentioned for comparison, controls, family history, or differential diagnosis are context; do NOT extract them as primary findings.
3. If the document discusses multiple diseases, extract ONLY evidence relevant to the target disease as primary evidence.
4. The A.gene_symbol field MUST be a single string, not a list.

EVIDENCE CATALOG (field_id: field_name [ACMG_codes], * = required for scoring):
{catalog_text}

CATALOG SCOPE:
- Extract only the listed eligible fields. Do not add fields outside this catalog.
- Set status="not_found" for listed eligible fields when the document does not support a value.

RULES:
1. For each catalog field, set status="found" with the extracted value, or status="not_found" if absent.
2. Do not score or classify ACMG/GDV evidence.
3. For every "found" item, you MUST provide a source_span with a verbatim text_snippet quoted directly from the source document. This is a citation-required task: no found field may omit its source quote.
4. The text_snippet MUST be a verbatim continuous substring of the source document. Copy punctuation exactly as it appears. Do not paraphrase, translate, or use "..." to bridge gaps.
5. Set confidence based on extraction certainty (0.0-1.0).
6. Use status="ocr_gap" only when the document indicates the evidence is in an image/table/figure but the text needed for extraction is unavailable.
7. Do not invent external database values. If allele frequency or ClinVar-like data is absent, mark it not_found.
8. For A.gene_symbol, extract a standalone HGNC-style gene symbol from titles, abstracts, variant descriptions, tables, and disease modifiers. If the gene appears as a disease-name prefix (e.g. "AARS1-associated disease"), extract the gene symbol independently.
9. For A.gene_disease_relationship, the value MUST be one of: "causative", "associated", "susceptibility", "uncertain", "disputed", "refuted", "no_relationship". Do NOT return sentences or descriptions.
10. For B.disease_diagnosis, extract ONLY the primary disease name relevant to the target gene. Do NOT extract lists of unrelated diseases, background comorbidities, or general medical history.

OUTPUT FORMAT:
Return a single JSON object (no markdown fences, no prose) with this exact shape:

{{
  "evidence_items": [
    {{
      "field_id": "A.gene_symbol",
      "status": "found",
      "value": "ABCA3",
      "confidence": 0.95,
      "source_span": {{
        "text_snippet": "ATP-binding cassette transporter 3 (ABCA3) deficiency",
        "context_type": "text"
      }}
    }},
    {{
      "field_id": "A.variant_hgvs_p",
      "status": "not_found",
      "value": "",
      "confidence": 0.0,
      "source_span": null
    }}
  ]
}}

Return ONLY the JSON object.

SOURCE DOCUMENT:
{source_text}
"""


# ── LLM client ──────────────────────────────────────────────────────────


def _build_llm_client() -> tuple[LLMPoolAdapter, str, str]:
    """Create the reasoning-LLM client used for the prompt-only baseline.

    Reads the ``REASONING_LLM`` configuration via :func:`get_config` and
    builds an :class:`LLMPoolAdapter` with the reasoning model, its key pool,
    and the configured ``reasoning_effort``.

    Returns:
        A ``(client, model_name, reasoning_effort)`` triple.
    """
    cfg = get_config()
    reasoning = cfg.reasoning
    model = reasoning.model or cfg.llm.model
    api_keys = reasoning.all_api_keys or cfg.llm.all_api_keys
    base_url = reasoning.base_url or cfg.llm.base_url
    effort = reasoning.reasoning_effort or ""
    model_kwargs: dict[str, Any] = {}
    if effort:
        model_kwargs["reasoning_effort"] = effort
    client = create_llm_client(
        model=model,
        base_url=base_url,
        api_key=api_keys[0] if api_keys else "",
        api_keys=api_keys or None,
        temperature=reasoning.temperature if reasoning.temperature is not None else 0.0,
        max_tokens=reasoning.max_tokens,
        timeout=reasoning.timeout,
        model_kwargs=model_kwargs or None,
    )
    return client, model, effort


# ── Entry loading ───────────────────────────────────────────────────────


def _load_entry_expected(entry_id: str) -> dict[str, Any] | None:
    """Load the ``expected.json`` ground-truth file for one entry.

    Args:
        entry_id: Unified entry ID (e.g. ``"gs_002"``).

    Returns:
        Parsed expected dict, or ``None`` if the file is missing.
    """
    expected_path = GROUND_TRUTH_UNIFIED_ROOT / entry_id / "expected.json"
    if not expected_path.exists():
        logger.warning("[{}] expected.json not found at {}", entry_id, expected_path)
        return None
    return json.loads(expected_path.read_text(encoding="utf-8"))


def _load_manifest_entries(
    manifest_path: Path,
    entry_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Load merged manifest+expected entries for the prompt-only run.

    Each returned dict carries both the manifest provenance fields
    (``source_dataset``, ``original_entry_id``) and the evaluation fields
    from ``expected.json`` (``expected_evidence``, ``expected_standardization``,
    ``gene_symbol``, ``disease_label``).

    Args:
        manifest_path: Path to the locked N=50 manifest.
        entry_ids: Optional explicit entry-ID allowlist.
        limit: Optional cap on the number of entries.

    Returns:
        Ordered list of merged entry dicts.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_entries = manifest.get("entries", [])
    if entry_ids:
        id_set = set(entry_ids)
        raw_entries = [e for e in raw_entries if e.get("entry_id") in id_set]
    if limit:
        raw_entries = raw_entries[:limit]

    merged: list[dict[str, Any]] = []
    for item in raw_entries:
        entry_id = item["entry_id"]
        expected = _load_entry_expected(entry_id)
        if expected is None:
            continue
        merged.append({
            "entry_id": entry_id,
            "gene_symbol": expected.get("gene_symbol") or item.get("gene_symbol", ""),
            "classification": expected.get("classification") or item.get("classification", ""),
            "moi": expected.get("moi") or item.get("moi", ""),
            "disease_label": expected.get("disease_label", ""),
            "source_dataset": item.get("source_dataset", expected.get("source_dataset", "")),
            "original_entry_id": item.get("original_entry_id", expected.get("original_entry_id", "")),
            "expected_evidence": expected.get("expected_evidence", []),
            "expected_standardization": expected.get("expected_standardization", {}),
            "expected_entities": expected.get("expected_entities", {}),
        })
    return merged


# ── Per-entry evaluation ────────────────────────────────────────────────


def _parse_evidence_items(content: str) -> list[dict[str, Any]]:
    """Parse the LLM JSON response into a list of extracted evidence items.

    Tolerates markdown fences and a top-level ``evidence_items`` wrapper.
    On any parse failure returns an empty list so the entry is scored as
    all-missing rather than crashing the run.

    Args:
        content: Raw LLM response text.

    Returns:
        List of evidence-item dicts with ``field_id``, ``status``,
        ``value``, ``confidence``, ``source_span`` keys.
    """
    if not content:
        return []
    cleaned = strip_json_fences(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Last-resort: extract the first {...} block.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM JSON response")
                return []
        else:
            logger.warning("Failed to parse LLM JSON response")
            return []
    if isinstance(parsed, dict):
        items = parsed.get("evidence_items", [])
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = []
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or "field_id" not in item:
            continue
        normalized.append({
            "field_id": str(item.get("field_id", "")),
            "status": str(item.get("status", "not_found")),
            "value": str(item.get("value", "")),
            "confidence": float(item.get("confidence", 0.0) or 0.0),
            "source_span": item.get("source_span")
            if isinstance(item.get("source_span"), dict)
            else None,
        })
    return normalized


async def evaluate_one_prompt_only(
    entry: dict[str, Any],
    source_text: str,
    client: LLMPoolAdapter,
    semaphore: asyncio.Semaphore,
    catalog_text: str,
    mondo: Any | None = None,
) -> EntryMetrics:
    """Evaluate one entry with a single prompt-only LLM call.

    Sends one citation-required extraction prompt to the reasoning LLM,
    parses the JSON response, and scores it against the entry's
    ``expected_evidence`` via :func:`compare_evidence`.

    Args:
        entry: Merged manifest+expected entry dict.
        source_text: Full source markdown text.
        client: LLM pool adapter (reasoning model).
        semaphore: Concurrency limiter.
        catalog_text: Compact catalog text for the prompt.
        mondo: Optional MONDO hierarchy for ontology ancestry matching.

    Returns:
        :class:`EntryMetrics` for the entry.
    """
    entry_id = entry["entry_id"]
    metrics = EntryMetrics(
        entry_id=entry_id,
        gene_symbol=entry["gene_symbol"],
        classification=entry.get("classification", ""),
        language="en",
        moi=entry.get("moi", ""),
        source_dataset=entry.get("source_dataset", ""),
        original_entry_id=entry.get("original_entry_id", ""),
    )

    prompt = build_extraction_prompt(
        gene_symbol=entry["gene_symbol"],
        disease_label=entry.get("disease_label", ""),
        source_text=source_text,
        catalog_text=catalog_text,
    )

    async with semaphore:
        t0 = time.time()
        try:
            response = await client.ainvoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else str(response)
            if isinstance(content, list):
                # Some models return a list of content blocks; join text parts.
                content = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            metrics.duration_s = round(time.time() - t0, 2)
            metrics.pipeline_status = "completed"
        except Exception as exc:  # noqa: BLE001 - any LLM failure is per-entry
            metrics.duration_s = round(time.time() - t0, 2)
            metrics.pipeline_status = "error"
            metrics.error_message = str(exc)
            mark_expected_fields_missing(metrics, entry, mondo=mondo)
            logger.error("[{}] LLM call failed: {}", entry_id, exc)
            return metrics

    extracted_items = _parse_evidence_items(content)
    metrics.evidence_count = len(extracted_items)
    found_count = sum(1 for i in extracted_items if i["status"] == "found")
    metrics.found_rate = found_count / len(extracted_items) if extracted_items else 0.0
    # Source grounding: fraction of found items carrying a source_span citation.
    grounded = sum(
        1 for i in extracted_items
        if i["status"] == "found" and i.get("source_span")
    )
    metrics.grounding_rate = grounded / found_count if found_count else 0.0

    cleaned_items = prepare_extracted_items(extracted_items)
    metrics.field_matches = compare_evidence(
        entry.get("expected_evidence", []),
        cleaned_items,
        mondo=mondo,
        expected_standardization=entry.get("expected_standardization"),
    )
    # Prompt-only baseline has no entity standardization or cross-lingual track.
    metrics.standardization_accuracy = 0.0
    metrics.track_consistency = 0.0

    tp = sum(1 for f in metrics.field_matches if f.matched)
    total = len(metrics.field_matches)
    logger.info(
        "[{}] ✓ prompt-only | {}/{} fields | found={} grounding={:.0%} | {:.0f}s",
        entry_id, tp, total, metrics.evidence_count, metrics.grounding_rate,
        metrics.duration_s,
    )
    return metrics


# ── Top-level orchestrator ──────────────────────────────────────────────


async def run_prompt_only_evaluation(
    concurrency: int = 4,
    manifest_path: Path = DEFAULT_MANIFEST,
    entry_ids: list[str] | None = None,
    limit: int | None = None,
) -> Path:
    """Run the C0 prompt-only baseline across the N=50 manifest.

    Args:
        concurrency: Max concurrent LLM calls.
        manifest_path: Path to the locked N=50 manifest.
        entry_ids: Optional explicit entry-ID allowlist.
        limit: Optional cap on the number of entries.

    Returns:
        Path to the written report JSON file.
    """
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    REPORTS_N50_DIR.mkdir(parents=True, exist_ok=True)

    entries = _load_manifest_entries(manifest_path, entry_ids=entry_ids, limit=limit)
    if not entries:
        raise ValueError(f"No loadable entries found in manifest {manifest_path}")
    logger.info(
        "C0 prompt-only baseline: {} entries | concurrency={}", len(entries), concurrency
    )

    # Build LLM client + catalog.
    client, model_name, effort = _build_llm_client()
    catalog = _eligible_catalog()
    catalog_text = _catalog_compact_text(catalog)
    logger.info(
        "LLM: model={} effort={} | catalog fields={}", model_name, effort or "-", len(catalog)
    )

    # Load MONDO hierarchy for ontology ancestry matching (optional).
    mondo = None
    if MondoHierarchy is not None:
        try:
            mondo = MondoHierarchy.load()
            logger.info("MONDO hierarchy loaded for ontology ancestry matching")
        except Exception as exc:  # noqa: BLE001 - ontology cache is optional
            logger.warning("MONDO hierarchy not available: {}", exc)

    semaphore = asyncio.Semaphore(concurrency)
    t0 = time.time()
    all_metrics: list[EntryMetrics] = []
    for entry in entries:
        source_path = GROUND_TRUTH_UNIFIED_ROOT / entry["entry_id"] / "source.md"
        if not source_path.exists():
            logger.warning("[{}] source.md missing; scoring as all-missing", entry["entry_id"])
            metrics = EntryMetrics(
                entry_id=entry["entry_id"],
                gene_symbol=entry["gene_symbol"],
                classification=entry.get("classification", ""),
                language="en",
                moi=entry.get("moi", ""),
                source_dataset=entry.get("source_dataset", ""),
                original_entry_id=entry.get("original_entry_id", ""),
                pipeline_status="no_source",
            )
            mark_expected_fields_missing(metrics, entry, mondo=mondo)
            all_metrics.append(metrics)
            continue
        source_text = source_path.read_text(encoding="utf-8")
        if len(source_text) < 100:
            metrics = EntryMetrics(
                entry_id=entry["entry_id"],
                gene_symbol=entry["gene_symbol"],
                classification=entry.get("classification", ""),
                language="en",
                moi=entry.get("moi", ""),
                source_dataset=entry.get("source_dataset", ""),
                original_entry_id=entry.get("original_entry_id", ""),
                pipeline_status="source_too_small",
            )
            mark_expected_fields_missing(metrics, entry, mondo=mondo)
            all_metrics.append(metrics)
            continue
        metrics = await evaluate_one_prompt_only(
            entry, source_text, client, semaphore, catalog_text, mondo=mondo
        )
        all_metrics.append(metrics)

    elapsed = time.time() - t0
    aggregates = compute_aggregate_metrics(all_metrics)

    # Build report — same shape as run_evaluation output for comparability.
    report: dict[str, Any] = {
        "evaluation_id": f"eval_c0_prompt_only_{uuid.uuid4().hex[:8]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "condition_id": CONDITION_ID,
        "config": {
            "condition_id": CONDITION_ID,
            "is_prompt_only": True,
            "prompt_only_model": "reasoning",
            "model": model_name,
            "reasoning_effort": effort or None,
            "concurrency": concurrency,
            "manifest_path": str(manifest_path),
            "ground_truth_root": str(GROUND_TRUTH_UNIFIED_ROOT),
            "dataset": "unified",
            "catalog_field_count": len(catalog),
            "disabled_components": [
                "agent_workflow",
                "primary_review_split",
                "review_validation",
                "target_guard",
                "reflection_loop",
                "retry_on_review_failure",
                "phase3_standardization",
                "entity_standardization",
            ],
            "base_url": None,
            "extraction_mode": "broad",
        },
        "total_entries": len(entries),
        "total_duration_s": round(elapsed, 2),
        "aggregates": aggregates,
        "per_entry": [
            {
                "entry_id": m.entry_id,
                "gene_symbol": m.gene_symbol,
                "classification": m.classification,
                "moi": m.moi,
                "source_dataset": m.source_dataset,
                "original_entry_id": m.original_entry_id,
                "run_id": m.run_id,
                "status_url": m.status_url,
                "pipeline_status": m.pipeline_status,
                "error_message": m.error_message,
                "last_pipeline_status": m.last_pipeline_status,
                "last_current_phase": m.last_current_phase,
                "duration_s": m.duration_s,
                "evidence_count": m.evidence_count,
                "found_rate": m.found_rate,
                "grounding_rate": m.grounding_rate,
                "standardization_accuracy": m.standardization_accuracy,
                "track_consistency": m.track_consistency,
                "field_matches": [
                    {
                        "field_id": f.field_id,
                        "expected": f.expected_value,
                        "matched": f.matched,
                        "extracted": f.extracted_value,
                        "source_span": f.source_span,
                        "match_type": f.match_type,
                        "extra_found_values": f.extra_found_values,
                        "best_score": f.best_score,
                        "source_score": f.source_score,
                        "confidence_score": f.confidence_score,
                        "agreement_score": f.agreement_score,
                        "status_score": f.status_score,
                        "verifier_support_score": f.verifier_support_score,
                        "target_specificity_score": f.target_specificity_score,
                        "contradiction_penalty": f.contradiction_penalty,
                        "accepted_track": f.accepted_track,
                        "normalized_value": f.normalized_value,
                    }
                    for f in m.field_matches
                ],
                "entity_matches": m.entity_matches,
            }
            for m in all_metrics
        ],
    }

    # Stratify by source_dataset + record errors (matches run_evaluation shape).
    report["aggregates"]["by_source_dataset"] = _compute_stratified_metrics(all_metrics)
    report["aggregates"]["timeout_and_errors"] = [
        {
            "entry_id": m.entry_id,
            "source_dataset": m.source_dataset,
            "pipeline_status": m.pipeline_status,
            "error_message": m.error_message,
        }
        for m in all_metrics
        if m.pipeline_status in ("timeout", "error", "failed", "no_source", "source_too_small")
    ]

    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_N50_DIR / f"c0_prompt_only_{ts}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Print summary.
    o = aggregates["overall"]
    logger.info("=== C0 Prompt-Only Baseline Complete ===")
    logger.info("  Entries: {} | Duration: {:.0f}s", len(entries), elapsed)
    logger.info("  Field P/R/F1: {:.1%} / {:.1%} / {:.1%}", o["precision"], o["recall"], o["f1"])
    logger.info("  TP={} FP={} FN={}", o["true_positives"], o["false_positives"], o["false_negatives"])
    logger.info("  Over-extractions: {}", o["over_extractions"])
    for cls, m in aggregates["by_classification"].items():
        logger.info(
            "  {}: P={:.1%} R={:.1%} F1={:.1%} (n={})",
            cls, m["precision"], m["recall"], m["f1"], m["count"],
        )
    for sds, m in report["aggregates"].get("by_source_dataset", {}).items():
        logger.info(
            "  source={}: P={:.1%} R={:.1%} F1={:.1%} (n={})",
            sds, m["precision"], m["recall"], m["f1"], m["count"],
        )
    logger.info("Report: {}", report_path)
    return report_path


# ── CLI ─────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="benchmark.runners.n50_prompt_only",
        description=(
            "C0 prompt-only baseline runner for the BIBM N=50 comparison "
            "experiment. Sends a single citation-required extraction prompt "
            "to the reasoning LLM per entry, with no agent workflow."
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max concurrent LLM calls (default: 4).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "Pipeline base URL (accepted for CLI parity with the pipeline "
            "runner but unused — C0 makes direct LLM calls, no pipeline)."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the locked N=50 manifest JSON.",
    )
    parser.add_argument(
        "--entry-ids",
        nargs="*",
        default=None,
        help="Optional explicit list of entry IDs to evaluate.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of entries (after entry-id filtering).",
    )
    return parser


async def _arun(args: argparse.Namespace) -> int:
    """Async entry point for the CLI."""
    entry_ids = args.entry_ids if args.entry_ids else None
    await run_prompt_only_evaluation(
        concurrency=args.concurrency,
        manifest_path=args.manifest,
        entry_ids=entry_ids,
        limit=args.limit,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ``python -m benchmark.runners.n50_prompt_only``.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code ``0`` on success.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_arun(args))


if __name__ == "__main__":
    raise SystemExit(main())
