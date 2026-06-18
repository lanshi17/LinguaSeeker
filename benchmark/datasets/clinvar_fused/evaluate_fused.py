"""Evaluate fused ClinGen+ClinVar benchmark entries against pipeline extraction.

Three-layer evaluation:
- Layer 1: Gene-Disease fields (precision_recall) — full P/R/F1
- Layer 2: Variant fields (precision_only) — precision only
- Layer 3: Entity standardization accuracy (gene→HGNC, disease→MONDO, variant→ClinVar)
"""
from __future__ import annotations

import json
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# ── Text normalization (reused from evaluate.py) ───────────────────────

_PUNCT_TRANSLATION = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "-", "―": "-", "−": "-", "－": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
})

_NORMALIZE_CANDIDATE_PUNCT = str.maketrans({",": " ", ";": " ", ":": " ", "，": " ", "；": " ", "：": " "})


def normalize_text(value: str) -> str:
    """Normalize typography differences for benchmark matching."""
    n = unicodedata.normalize("NFKC", value)
    n = n.translate(_PUNCT_TRANSLATION)
    n = n.translate(_NORMALIZE_CANDIDATE_PUNCT)
    n = __import__("re").sub(r"\s+", " ", n)
    return n.strip()


def fuzzy_match(expected: str, extracted: str) -> bool:
    """Fuzzy value matching."""
    if not expected or not extracted:
        return False
    e = normalize_text(expected).lower()
    x = normalize_text(extracted).lower()
    if e == x:
        return True
    if e in x or x in e:
        return True
    # Word overlap
    e_words = set(__import__("re").split(r"[\s\-]+", e))
    x_words = set(__import__("re").split(r"[\s\-]+", x))
    stop = {"disease", "syndrome", "disorder", "type", "the", "a", "an", "of", "due", "to", "with", "and", "or"}
    e_words -= stop
    x_words -= stop
    if e_words and x_words:
        overlap = e_words & x_words
        if len(overlap) / len(e_words) >= 0.6:
            return True
    return False


# ── Data structures ────────────────────────────────────────────────────


@dataclass
class FieldResult:
    """Result for one field evaluation."""

    field_id: str
    expected_value: str
    evaluation_type: str  # precision_recall or precision_only
    matched: bool = False
    extracted_value: str | None = None
    match_type: str = "none"  # exact, fuzzy, none
    is_false_positive: bool = False
    extra_found_values: list[str] = field(default_factory=list)
    source: str = ""  # clingen or clinvar


@dataclass
class EntryResult:
    """Evaluation result for one fused entry."""

    entry_id: str
    gene_symbol: str
    classification: str
    moi: str = ""
    pipeline_status: str = "pending"
    field_results: list[FieldResult] = field(default_factory=list)
    standardization_results: dict[str, dict] = field(default_factory=dict)
    duration_s: float = 0.0
    evidence_count: int = 0
    variant_count: int = 0


# ── Layer 1: Gene-Disease comparison (P/R/F1) ─────────────────────────


def compare_gene_disease(
    expected_fields: list[dict],
    extracted_items: list[dict],
) -> list[FieldResult]:
    """Compare gene-disease fields with full P/R/F1 semantics."""
    results: list[FieldResult] = []

    for expected in expected_fields:
        if expected.get("evaluation_type") != "precision_recall":
            continue

        field_id = expected["field_id"]
        expected_value = str(expected.get("value", ""))
        source = expected.get("source", "")

        candidates = [
            item for item in extracted_items
            if item.get("field_id") == field_id and item.get("status") == "found"
        ]

        if not candidates:
            results.append(FieldResult(
                field_id=field_id, expected_value=expected_value,
                evaluation_type="precision_recall", source=source,
            ))
            continue

        # Find best match
        best: FieldResult | None = None
        extra_values: list[str] = []
        seen_extra: set[str] = set()

        for cand in candidates:
            ext_val = str(cand.get("value", ""))
            e_norm = normalize_text(expected_value).lower()
            x_norm = normalize_text(ext_val).lower()

            if e_norm == x_norm:
                match_type = "exact"
            elif fuzzy_match(expected_value, ext_val):
                match_type = "fuzzy"
            else:
                normalized = normalize_text(ext_val).lower()
                if normalized not in seen_extra:
                    seen_extra.add(normalized)
                    extra_values.append(ext_val)
                continue

            if best is None or (match_type == "exact" and best.match_type != "exact"):
                best = FieldResult(
                    field_id=field_id, expected_value=expected_value,
                    evaluation_type="precision_recall", matched=True,
                    extracted_value=ext_val, match_type=match_type, source=source,
                )

        if best:
            best.extra_found_values = extra_values
            results.append(best)
        else:
            results.append(FieldResult(
                field_id=field_id, expected_value=expected_value,
                evaluation_type="precision_recall",
                extracted_value=str(candidates[0].get("value", "")),
                match_type="wrong_value", source=source,
            ))

    return results


# ── Layer 2: Variant precision comparison ──────────────────────────────


def compare_variant_precision(
    expected_fields: list[dict],
    extracted_items: list[dict],
) -> list[FieldResult]:
    """Compare variant fields with precision-only semantics.

    For each extracted value with matching field_id:
    - If value ∈ gold candidates → TP
    - If value ∉ gold candidates → FP
    - No FN counting (recall not measurable without human annotation)
    """
    results: list[FieldResult] = []

    for expected in expected_fields:
        if expected.get("evaluation_type") != "precision_only":
            continue

        field_id = expected["field_id"]
        source = expected.get("source", "")
        candidates = expected.get("candidates", [])
        if not candidates and expected.get("value"):
            candidates = [expected["value"]]

        # Normalize gold candidates
        gold_normalized = set()
        for c in candidates:
            gold_normalized.add(normalize_text(str(c)).lower())

        # Find all extracted values for this field_id
        extracted_for_field = [
            item for item in extracted_items
            if item.get("field_id") == field_id and item.get("status") == "found"
        ]

        if not extracted_for_field:
            # No extraction — not a false negative (precision-only)
            results.append(FieldResult(
                field_id=field_id, expected_value=candidates[0] if candidates else "",
                evaluation_type="precision_only", source=source,
            ))
            continue

        for ext_item in extracted_for_field:
            ext_val = str(ext_item.get("value", ""))
            ext_norm = normalize_text(ext_val).lower()

            # Check if extracted value matches any gold candidate
            is_match = False
            for g in gold_normalized:
                if ext_norm == g or ext_norm in g or g in ext_norm:
                    is_match = True
                    break

            results.append(FieldResult(
                field_id=field_id,
                expected_value=candidates[0] if candidates else "",
                evaluation_type="precision_only",
                matched=is_match,
                extracted_value=ext_val,
                match_type="candidate_match" if is_match else "not_in_candidates",
                is_false_positive=not is_match,
                source=source,
            ))

    return results


# ── Full entry evaluation ──────────────────────────────────────────────


def evaluate_entry_from_preprocessed(entry: dict) -> EntryResult:
    """Evaluate one fused entry using preprocessed Phase 2 data."""
    entry_id = entry["entry_id"]
    gene = entry.get("clingen", {}).get("gene_symbol", "")
    classification = entry.get("clingen", {}).get("classification", "")
    moi = entry.get("clingen", {}).get("moi", "")

    result = EntryResult(
        entry_id=entry_id,
        gene_symbol=gene,
        classification=classification,
        moi=moi,
    )

    # Load preprocessed extraction
    preprocessed_path = GROUND_TRUTH_DIR / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    if not preprocessed_path.exists():
        result.pipeline_status = "no_preprocessed"
        return result

    t0 = time.time()
    try:
        with open(preprocessed_path) as f:
            extraction_data = json.load(f)

        # Merge items from original + translated tracks
        extracted_items: list[dict] = []
        for track_key in ("original_result", "translated_result"):
            track_data = extraction_data.get(track_key, {})
            for item in track_data.get("evidence_items", []):
                extracted_items.append({
                    "field_id": item.get("field_id", ""),
                    "status": item.get("status", ""),
                    "value": item.get("value", ""),
                    "confidence": float(item.get("confidence", 0) or 0),
                })

        result.evidence_count = len(extracted_items)
        result.variant_count = len(entry.get("clinvar_variants", []))
        result.pipeline_status = "preprocessed"

        # Layer 1: Gene-Disease
        gd_results = compare_gene_disease(
            entry.get("expected_evidence", []),
            extracted_items,
        )
        result.field_results.extend(gd_results)

        # Layer 2: Variant Precision
        vp_results = compare_variant_precision(
            entry.get("expected_evidence", []),
            extracted_items,
        )
        result.field_results.extend(vp_results)

        result.duration_s = round(time.time() - t0, 2)

    except Exception as e:
        logger.error("[{}] Evaluation failed: {}", entry_id, e)
        result.pipeline_status = "error"

    return result


# ── Aggregate metrics ──────────────────────────────────────────────────


def compute_aggregate_metrics(results: list[EntryResult]) -> dict:
    """Compute aggregate metrics across all entries."""
    # Layer 1: Gene-Disease P/R/F1
    gd_fields: dict[str, dict] = {}
    for r in results:
        for f in r.field_results:
            if f.evaluation_type != "precision_recall":
                continue
            if f.field_id not in gd_fields:
                gd_fields[f.field_id] = {"tp": 0, "fp": 0, "fn": 0}
            if f.matched:
                gd_fields[f.field_id]["tp"] += 1
            elif f.match_type == "wrong_value":
                gd_fields[f.field_id]["fp"] += 1
            else:
                gd_fields[f.field_id]["fn"] += 1
            gd_fields[f.field_id]["fp"] += len(f.extra_found_values)

    gd_overall_tp = sum(c["tp"] for c in gd_fields.values())
    gd_overall_fp = sum(c["fp"] for c in gd_fields.values())
    gd_overall_fn = sum(c["fn"] for c in gd_fields.values())
    gd_p = gd_overall_tp / (gd_overall_tp + gd_overall_fp) if (gd_overall_tp + gd_overall_fp) > 0 else 0
    gd_r = gd_overall_tp / (gd_overall_tp + gd_overall_fn) if (gd_overall_tp + gd_overall_fn) > 0 else 0
    gd_f1 = 2 * gd_p * gd_r / (gd_p + gd_r) if (gd_p + gd_r) > 0 else 0

    gd_by_field: dict[str, dict] = {}
    for fid, counts in gd_fields.items():
        p = counts["tp"] / (counts["tp"] + counts["fp"]) if (counts["tp"] + counts["fp"]) > 0 else 0
        r = counts["tp"] / (counts["tp"] + counts["fn"]) if (counts["tp"] + counts["fn"]) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        gd_by_field[fid] = {
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "tp": counts["tp"], "fp": counts["fp"], "fn": counts["fn"],
        }

    # Layer 2: Variant Precision
    vp_fields: dict[str, dict] = {}
    for r in results:
        for f in r.field_results:
            if f.evaluation_type != "precision_only":
                continue
            if f.field_id not in vp_fields:
                vp_fields[f.field_id] = {"tp": 0, "fp": 0}
            if f.matched:
                vp_fields[f.field_id]["tp"] += 1
            elif f.is_false_positive:
                vp_fields[f.field_id]["fp"] += 1

    vp_overall_tp = sum(c["tp"] for c in vp_fields.values())
    vp_overall_fp = sum(c["fp"] for c in vp_fields.values())
    vp_precision = vp_overall_tp / (vp_overall_tp + vp_overall_fp) if (vp_overall_tp + vp_overall_fp) > 0 else 0

    vp_by_field: dict[str, dict] = {}
    for fid, counts in vp_fields.items():
        p = counts["tp"] / (counts["tp"] + counts["fp"]) if (counts["tp"] + counts["fp"]) > 0 else 0
        vp_by_field[fid] = {
            "precision": round(p, 4), "tp": counts["tp"], "fp": counts["fp"],
        }

    # By classification
    by_cls: dict[str, list[EntryResult]] = {}
    for r in results:
        by_cls.setdefault(r.classification, []).append(r)

    cls_metrics: dict[str, dict] = {}
    for cls, cls_results in by_cls.items():
        cls_gd_tp = sum(1 for r in cls_results for f in r.field_results if f.evaluation_type == "precision_recall" and f.matched)
        cls_gd_fp = sum(1 for r in cls_results for f in r.field_results if f.evaluation_type == "precision_recall" and f.match_type == "wrong_value")
        cls_gd_fn = sum(1 for r in cls_results for f in r.field_results if f.evaluation_type == "precision_recall" and f.match_type == "none")
        cls_gd_fp += sum(len(f.extra_found_values) for r in cls_results for f in r.field_results if f.evaluation_type == "precision_recall")
        cls_p = cls_gd_tp / (cls_gd_tp + cls_gd_fp) if (cls_gd_tp + cls_gd_fp) > 0 else 0
        cls_r = cls_gd_tp / (cls_gd_tp + cls_gd_fn) if (cls_gd_tp + cls_gd_fn) > 0 else 0
        cls_f1 = 2 * cls_p * cls_r / (cls_p + cls_r) if (cls_p + cls_r) > 0 else 0

        cls_vp_tp = sum(1 for r in cls_results for f in r.field_results if f.evaluation_type == "precision_only" and f.matched)
        cls_vp_fp = sum(1 for r in cls_results for f in r.field_results if f.evaluation_type == "precision_only" and f.is_false_positive)
        cls_vp_prec = cls_vp_tp / (cls_vp_tp + cls_vp_fp) if (cls_vp_tp + cls_vp_fp) > 0 else 0

        cls_metrics[cls] = {
            "count": len(cls_results),
            "gene_disease_f1": round(cls_f1, 4),
            "gene_disease_precision": round(cls_p, 4),
            "gene_disease_recall": round(cls_r, 4),
            "variant_precision": round(cls_vp_prec, 4),
        }

    return {
        "total_entries": len(results),
        "evaluated_entries": sum(1 for r in results if r.pipeline_status == "preprocessed"),
        "layer1_gene_disease": {
            "overall": {
                "precision": round(gd_p, 4),
                "recall": round(gd_r, 4),
                "f1": round(gd_f1, 4),
                "tp": gd_overall_tp,
                "fp": gd_overall_fp,
                "fn": gd_overall_fn,
            },
            "by_field": gd_by_field,
        },
        "layer2_variant": {
            "overall_precision": round(vp_precision, 4),
            "tp": vp_overall_tp,
            "fp": vp_overall_fp,
            "by_field": vp_by_field,
        },
        "by_classification": cls_metrics,
    }


# ── Main ───────────────────────────────────────────────────────────────


def run_evaluation(
    limit: int | None = None,
    entry_ids: list[str] | None = None,
    write: bool = False,
) -> dict:
    """Run fused benchmark evaluation on preprocessed data."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load ground truth
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    if not selection_path.exists():
        raise FileNotFoundError(f"selection.json not found at {selection_path}")

    entries = json.loads(selection_path.read_text(encoding="utf-8"))
    if entry_ids:
        id_set = set(entry_ids)
        entries = [e for e in entries if e["entry_id"] in id_set]
    if limit:
        entries = entries[:limit]
    logger.info("Evaluating {} fused entries", len(entries))

    t0 = time.time()
    results: list[EntryResult] = []

    for entry in entries:
        r = evaluate_entry_from_preprocessed(entry)
        results.append(r)
        gd_tp = sum(1 for f in r.field_results if f.evaluation_type == "precision_recall" and f.matched)
        gd_total = sum(1 for f in r.field_results if f.evaluation_type == "precision_recall")
        vp_tp = sum(1 for f in r.field_results if f.evaluation_type == "precision_only" and f.matched)
        vp_fp = sum(1 for f in r.field_results if f.evaluation_type == "precision_only" and f.is_false_positive)
        logger.info("[{}] {} | GD: {}/{} | VP: {}tp/{}fp | {:.1f}s",
                     r.entry_id, r.pipeline_status, gd_tp, gd_total, vp_tp, vp_fp, r.duration_s)

    elapsed = time.time() - t0

    # Compute aggregates
    aggregates = compute_aggregate_metrics(results)

    # Build report
    report = {
        "evaluation_id": f"eval_fused_{int(time.time())}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {"limit": limit, "entry_ids": entry_ids},
        "total_duration_s": round(elapsed, 2),
        "aggregates": aggregates,
        "per_entry": [
            {
                "entry_id": r.entry_id,
                "gene_symbol": r.gene_symbol,
                "classification": r.classification,
                "moi": r.moi,
                "pipeline_status": r.pipeline_status,
                "evidence_count": r.evidence_count,
                "variant_count": r.variant_count,
                "duration_s": r.duration_s,
                "field_results": [
                    {
                        "field_id": f.field_id,
                        "expected_value": f.expected_value,
                        "evaluation_type": f.evaluation_type,
                        "matched": f.matched,
                        "extracted_value": f.extracted_value,
                        "match_type": f.match_type,
                        "is_false_positive": f.is_false_positive,
                        "extra_found_values": f.extra_found_values,
                        "source": f.source,
                    }
                    for f in r.field_results
                ],
            }
            for r in results
        ],
    }

    # Print summary
    a = aggregates
    gd = a["layer1_gene_disease"]["overall"]
    vp = a["layer2_variant"]
    logger.info("=== Fused Benchmark Evaluation ===")
    logger.info("  Entries: {}/{}", a["evaluated_entries"], a["total_entries"])
    logger.info("  Layer 1 Gene-Disease: P={:.1%} R={:.1%} F1={:.1%}", gd["precision"], gd["recall"], gd["f1"])
    logger.info("  Layer 2 Variant Precision: {:.1%} (TP={} FP={})", vp["overall_precision"], vp["tp"], vp["fp"])
    for fid, fm in a["layer1_gene_disease"]["by_field"].items():
        logger.info("    {}: P={:.1%} R={:.1%} F1={:.1%}", fid, fm["precision"], fm["recall"], fm["f1"])
    for fid, vm in a["layer2_variant"]["by_field"].items():
        logger.info("    {}: Prec={:.1%} (TP={} FP={})", fid, vm["precision"], vm["tp"], vm["fp"])

    if write:
        ts = time.strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"fused_eval_{ts}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Report saved: {}", report_path)

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate fused ClinGen+ClinVar benchmark")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--entries", nargs="+", default=None)
    parser.add_argument("--write", action="store_true", help="Save report to file")
    args = parser.parse_args()

    run_evaluation(limit=args.limit, entry_ids=args.entries, write=args.write)
