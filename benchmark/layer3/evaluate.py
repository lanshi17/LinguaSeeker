"""Layer 3 evaluation: submit articles to pipeline and compare against ClinGen ground truth.

Flow:
1. For each ground truth entry with source.md:
   a. Convert markdown to PDF (fpdf2)
   b. Submit PDF to pipeline API
   c. Wait for completion
   d. Query extracted evidence from PG
   e. Compare against ground truth expected fields
2. Aggregate metrics: Precision, Recall, F1 per field type
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml
from loguru import logger

from benchmark.pipeline.evidence_metrics import query_evidence_metrics
from src.dao.postgresql.connection import async_session_factory, build_async_engine

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

POLL_INTERVAL_S = 5.0
MAX_POLL_ATTEMPTS = 360  # 30 min max per entry
TERMINAL_STATUSES = {"awaiting_review", "completed", "failed"}


# ── PDF generation ─────────────────────────────────────────────────────

def _sanitize_for_pdf(text: str) -> str:
    """Remove characters that can't be encoded in latin-1."""
    # Replace common Unicode chars with ASCII equivalents
    replacements = {
        "–": "-", "—": "-", "‘": "'", "’": "'",
        "“": '"', "”": '"', "…": "...", "°": "deg",
        "µ": "u", "×": "x", "±": "+/-", "≤": "<=",
        "≥": ">=", "α": "alpha", "β": "beta", "γ": "gamma",
        "→": "->", "←": "<-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Encode to latin-1, replacing unknown chars
    return text.encode("latin-1", errors="replace").decode("latin-1")


def markdown_to_pdf_bytes(md_text: str, title: str = "") -> bytes:
    """Convert markdown text to PDF bytes using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=10)

    if title:
        pdf.set_font("Helvetica", "B", 14)
        pdf.multi_cell(0, 8, _sanitize_for_pdf(title[:200]))
        pdf.ln(5)
        pdf.set_font("Helvetica", size=10)

    lines = md_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        # Truncate very long lines
        if len(line) > 2000:
            line = line[:2000] + "..."
        text = _sanitize_for_pdf(line)
        if not text.strip():
            continue
        try:
            if line.startswith("## "):
                pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 6, text[3:] if len(text) > 3 else text)
                pdf.set_font("Helvetica", size=10)
            elif line.startswith("# "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, text[2:] if len(text) > 2 else text)
                pdf.set_font("Helvetica", size=10)
            else:
                pdf.multi_cell(0, 5, text)
        except Exception:
            # Skip problematic lines
            continue

    return bytes(pdf.output())


# ── Comparison ─────────────────────────────────────────────────────────

@dataclass
class FieldMatch:
    """Result of matching one expected field against extracted evidence."""

    field_id: str
    expected_value: str
    matched: bool
    extracted_value: str | None = None
    extracted_confidence: float | None = None
    match_type: str = "none"  # exact, fuzzy, none


@dataclass
class EntryMetrics:
    """Metrics for one ground truth entry evaluation."""

    entry_id: str
    gene_symbol: str
    classification: str
    language: str
    run_id: str | None = None
    pipeline_status: str = "pending"
    duration_s: float = 0.0
    field_matches: list[FieldMatch] = field(default_factory=list)
    entity_matches: dict[str, bool] = field(default_factory=dict)
    evidence_count: int = 0
    found_rate: float = 0.0
    grounding_rate: float = 0.0


def fuzzy_match_value(expected: str, extracted: str) -> bool:
    """Fuzzy value matching with word-overlap for disease names."""
    if not expected or not extracted:
        return False
    exp_lower = expected.lower().strip()
    ext_lower = extracted.lower().strip()
    # Exact match
    if exp_lower == ext_lower:
        return True
    # Substring containment
    if exp_lower in ext_lower or ext_lower in exp_lower:
        return True
    # Gene symbol exact match (case-sensitive)
    if expected.strip() == extracted.strip():
        return True
    # Word-overlap matching for disease names
    # e.g., "Charcot-Marie-Tooth disease" matches "Charcot-Marie-Tooth disease axonal type 2N"
    exp_words = set(re.split(r"[\s\-]+", exp_lower))
    ext_words = set(re.split(r"[\s\-]+", ext_lower))
    # Remove common stop words
    stop_words = {"disease", "syndrome", "disorder", "type", "the", "a", "an", "of", "due", "to", "with", "and", "or"}
    exp_words -= stop_words
    ext_words -= stop_words
    if exp_words and ext_words:
        overlap = exp_words & ext_words
        # If >60% of expected words are found in extracted, consider it a match
        if len(overlap) / len(exp_words) >= 0.6:
            return True
    return False


def compare_evidence(
    expected_fields: list[dict],
    extracted_items: list[dict],
) -> list[FieldMatch]:
    """Compare expected evidence fields against extracted items."""
    matches: list[FieldMatch] = []

    for expected in expected_fields:
        field_id = expected["field_id"]
        expected_value = str(expected.get("value", ""))

        # Find matching extracted items
        candidates = [
            item for item in extracted_items
            if item.get("field_id") == field_id and item.get("status") == "found"
        ]

        if not candidates:
            matches.append(FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=False,
                match_type="missing",
            ))
            continue

        # Check each candidate for value match
        best_match: FieldMatch | None = None
        for cand in candidates:
            extracted_value = str(cand.get("value", ""))
            confidence = cand.get("confidence", 0.0)

            if fuzzy_match_value(expected_value, extracted_value):
                match_type = "exact" if expected_value.lower() == extracted_value.lower() else "fuzzy"
                candidate_match = FieldMatch(
                    field_id=field_id,
                    expected_value=expected_value,
                    matched=True,
                    extracted_value=extracted_value,
                    extracted_confidence=confidence,
                    match_type=match_type,
                )
                if best_match is None or (match_type == "exact" and best_match.match_type != "exact"):
                    best_match = candidate_match

        if best_match:
            matches.append(best_match)
        else:
            # Found field but wrong value
            matches.append(FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=False,
                extracted_value=str(candidates[0].get("value", "")),
                extracted_confidence=candidates[0].get("confidence", 0.0),
                match_type="wrong_value",
            ))

    return matches


# ── Pipeline interaction ───────────────────────────────────────────────

async def submit_and_poll(
    client: httpx.AsyncClient,
    base_url: str,
    pdf_bytes: bytes,
    filename: str,
) -> dict:
    """Submit PDF and poll until completion."""
    content_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    resp = await client.post(
        f"{base_url}/api/v1/pipeline/run",
        json={
            "source_type": "local",
            "mode": "full",
            "filename": filename,
            "content_base64": content_b64,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    run_id = data["processing_run_id"]
    status_url = data["status_url"]

    # Poll
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_S)
        try:
            resp = await client.get(f"{base_url}{status_url}", timeout=30.0)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            status_data = resp.json()
            ps = status_data.get("pipeline_status", "")
            if ps in TERMINAL_STATUSES:
                return status_data
        except Exception:
            continue

    return {"pipeline_status": "timeout", "error_message": "Poll timed out"}


def load_proxy() -> str | None:
    config_path = Path(__file__).resolve().parent.parent.parent / "backend" / "config" / "environments" / "development.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return cfg.get("network", {}).get("proxy", "")
    return None


# ── Main evaluation ────────────────────────────────────────────────────

async def evaluate_one(
    client: httpx.AsyncClient,
    base_url: str,
    entry: dict,
    sf,
    semaphore: asyncio.Semaphore,
) -> EntryMetrics:
    """Evaluate one ground truth entry."""
    entry_id = entry["entry_id"]
    gene = entry["gene_symbol"]
    classification = entry.get("classification", "")

    metrics = EntryMetrics(
        entry_id=entry_id,
        gene_symbol=gene,
        classification=classification,
        language="en",
    )

    # Check for source text
    source_path = GROUND_TRUTH_DIR / entry_id / "source.md"
    if not source_path.exists():
        metrics.pipeline_status = "no_source"
        return metrics

    md_text = source_path.read_text(encoding="utf-8")
    if len(md_text) < 100:
        metrics.pipeline_status = "source_too_small"
        return metrics

    # Convert to PDF
    pdf_bytes = markdown_to_pdf_bytes(md_text, title=f"{gene} - {entry.get('disease_label', '')}")

    async with semaphore:
        t0 = time.time()
        try:
            status_data = await submit_and_poll(client, base_url, pdf_bytes, f"{entry_id}.pdf")
            metrics.duration_s = round(time.time() - t0, 2)
            metrics.pipeline_status = status_data.get("pipeline_status", "unknown")

            if metrics.pipeline_status in ("awaiting_review", "completed"):
                run_id = status_data.get("processing_run_id")
                metrics.run_id = run_id

                # Query evidence metrics from PG
                try:
                    ev_metrics = await query_evidence_metrics(sf, run_id)
                    metrics.evidence_count = ev_metrics.run_evidence_count
                    metrics.found_rate = ev_metrics.found_rate
                    metrics.grounding_rate = ev_metrics.source_grounding.grounding_rate

                    # Get detailed evidence items for comparison
                    from sqlalchemy import select
                    from src.dao.postgresql.models import RunEvidenceItem
                    async with sf() as session:
                        stmt = select(
                            RunEvidenceItem.field_id,
                            RunEvidenceItem.status,
                            RunEvidenceItem.value,
                            RunEvidenceItem.confidence,
                        ).where(RunEvidenceItem.processing_run_id == uuid.UUID(run_id))
                        rows = (await session.execute(stmt)).all()
                        extracted_items = [
                            {"field_id": r.field_id, "status": r.status, "value": r.value, "confidence": float(r.confidence) if r.confidence else 0.0}
                            for r in rows
                        ]

                    # Compare
                    metrics.field_matches = compare_evidence(
                        entry.get("expected_evidence", []),
                        extracted_items,
                    )

                except Exception as e:
                    logger.warning("[{}] Evidence query failed: {}", entry_id, e)

        except Exception as e:
            metrics.duration_s = round(time.time() - t0, 2)
            metrics.pipeline_status = "error"
            logger.error("[{}] Pipeline error: {}", entry_id, e)

    return metrics


def compute_aggregate_metrics(all_metrics: list[EntryMetrics]) -> dict:
    """Compute aggregate P/R/F1 from per-entry metrics."""
    # Field-level P/R/F1
    tp = sum(1 for m in all_metrics for f in m.field_matches if f.matched)
    fp = sum(1 for m in all_metrics for f in m.field_matches if f.match_type == "wrong_value")
    fn = sum(1 for m in all_metrics for f in m.field_matches if f.match_type in ("missing", "none"))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Per-field-type breakdown
    by_field: dict[str, dict] = {}
    for m in all_metrics:
        for f in m.field_matches:
            if f.field_id not in by_field:
                by_field[f.field_id] = {"tp": 0, "fp": 0, "fn": 0}
            if f.matched:
                by_field[f.field_id]["tp"] += 1
            elif f.match_type == "wrong_value":
                by_field[f.field_id]["fp"] += 1
            else:
                by_field[f.field_id]["fn"] += 1

    field_f1 = {}
    for fid, counts in by_field.items():
        p = counts["tp"] / (counts["tp"] + counts["fp"]) if (counts["tp"] + counts["fp"]) > 0 else 0
        r = counts["tp"] / (counts["tp"] + counts["fn"]) if (counts["tp"] + counts["fn"]) > 0 else 0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0
        field_f1[fid] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}

    # By classification
    by_cls: dict[str, list] = {}
    for m in all_metrics:
        by_cls.setdefault(m.classification, []).append(m)

    cls_metrics = {}
    for cls, metrics_list in by_cls.items():
        cls_tp = sum(1 for m in metrics_list for f in m.field_matches if f.matched)
        cls_fp = sum(1 for m in metrics_list for f in m.field_matches if f.match_type == "wrong_value")
        cls_fn = sum(1 for m in metrics_list for f in m.field_matches if f.match_type in ("missing", "none"))
        cls_p = cls_tp / (cls_tp + cls_fp) if (cls_tp + cls_fp) > 0 else 0
        cls_r = cls_tp / (cls_tp + cls_fn) if (cls_tp + cls_fn) > 0 else 0
        cls_f1 = 2 * cls_p * cls_r / (cls_p + cls_r) if (cls_p + cls_r) > 0 else 0
        cls_metrics[cls] = {
            "count": len(metrics_list),
            "precision": round(cls_p, 4),
            "recall": round(cls_r, 4),
            "f1": round(cls_f1, 4),
        }

    return {
        "overall": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "by_field": field_f1,
        "by_classification": cls_metrics,
    }


async def run_evaluation(base_url: str, concurrency: int, limit: int | None = None):
    """Main evaluation orchestrator."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load ground truth
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))
    # Only entries with source text
    entries = [e for e in entries if (GROUND_TRUTH_DIR / e["entry_id"] / "source.md").exists()]
    if limit:
        entries = entries[:limit]
    logger.info("Evaluating {} entries", len(entries))

    # Setup
    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    semaphore = asyncio.Semaphore(concurrency)
    engine = build_async_engine()
    sf = async_session_factory(engine)

    t0 = time.time()
    all_metrics: list[EntryMetrics] = []

    async with httpx.AsyncClient(**transport_kwargs) as client:
        for entry in entries:
            m = await evaluate_one(client, base_url, entry, sf, semaphore)
            all_metrics.append(m)
            status_icon = "✓" if m.pipeline_status in ("awaiting_review", "completed") else "✗"
            tp = sum(1 for f in m.field_matches if f.matched)
            total = len(m.field_matches)
            logger.info("[{}] {} | {} | {}/{} fields matched | {:.0f}s",
                        m.entry_id, status_icon, m.pipeline_status, tp, total, m.duration_s)

    elapsed = time.time() - t0

    # Compute aggregates
    aggregates = compute_aggregate_metrics(all_metrics)

    # Build report
    report = {
        "evaluation_id": f"eval_clingen_{uuid.uuid4().hex[:8]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {"base_url": base_url, "concurrency": concurrency, "limit": limit},
        "total_entries": len(entries),
        "total_duration_s": round(elapsed, 2),
        "aggregates": aggregates,
        "per_entry": [
            {
                "entry_id": m.entry_id,
                "gene_symbol": m.gene_symbol,
                "classification": m.classification,
                "pipeline_status": m.pipeline_status,
                "duration_s": m.duration_s,
                "evidence_count": m.evidence_count,
                "found_rate": m.found_rate,
                "grounding_rate": m.grounding_rate,
                "field_matches": [
                    {"field_id": f.field_id, "expected": f.expected_value,
                     "matched": f.matched, "extracted": f.extracted_value,
                     "match_type": f.match_type}
                    for f in m.field_matches
                ],
            }
            for m in all_metrics
        ],
    }

    # Save report
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"eval_{ts}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print summary
    o = aggregates["overall"]
    logger.info("=== Layer 3 Evaluation Complete ===")
    logger.info("  Entries: {} | Duration: {:.0f}s", len(entries), elapsed)
    logger.info("  Field P/R/F1: {:.1%} / {:.1%} / {:.1%}", o["precision"], o["recall"], o["f1"])
    logger.info("  TP={} FP={} FN={}", o["true_positives"], o["false_positives"], o["false_negatives"])
    for cls, m in aggregates["by_classification"].items():
        logger.info("  {}: P={:.1%} R={:.1%} F1={:.1%} (n={})", cls, m["precision"], m["recall"], m["f1"], m["count"])
    logger.info("Report: {}", report_path)

    await engine.dispose()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run_evaluation(args.base_url, args.concurrency, args.limit))
