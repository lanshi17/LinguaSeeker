"""Ablation study: dual-track (EN+ZH) vs original-only (EN only).

For each entry, runs the pipeline twice:
  1. ablation_original_only=True  → English-only evidence extraction
  2. ablation_original_only=False → Dual-track (EN+ZH) evidence extraction

Then compares the evidence items to measure the marginal contribution
of multilingual processing for ACMG variant classification.

This is the core experiment for the GIM submission, measuring how much
cross-lingual evidence extraction improves variant classification
compared to English-only processing.

Usage:
    PYTHONPATH=.:backend/src python -m benchmark.datasets.clinvar_fused.run_ablation_study \
        --base-url http://localhost:8000 \
        --concurrency 2 \
        --limit 30 \
        --write
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from loguru import logger

from benchmark.core.paths import GROUND_TRUTH_CLINVAR_FUSED_ROOT

GROUND_TRUTH_DIR = GROUND_TRUTH_CLINVAR_FUSED_ROOT


def _adapt_fused_entry(raw: dict) -> dict:
    """Flatten fused entry to the shape ``evaluate_one`` expects."""
    clingen = raw.get("clingen", {})
    return {
        "entry_id": raw["entry_id"],
        "gene_symbol": clingen.get("gene_symbol", ""),
        "disease_label": clingen.get("disease_label", ""),
        "classification": clingen.get("classification", ""),
        "moi": clingen.get("moi", ""),
        "source_dataset": "clinvar_fused",
        "expected_evidence": raw.get("expected_evidence", []),
        "expected_standardization": raw.get("expected_standardization", {}),
    }


async def _run_one_mode(
    entry: dict,
    client,
    sf,
    semaphore: asyncio.Semaphore,
    base_url: str,
    ablation_original_only: bool,
    mondo,
) -> dict:
    """Run pipeline for one entry in one mode, return metrics dict."""
    from benchmark.core.pipeline_client import evaluate_one

    mode_label = "en_only" if ablation_original_only else "dual"
    entry_id = entry["entry_id"]

    m = await evaluate_one(
        client,
        base_url,
        entry,
        sf,
        semaphore,
        ground_truth_dir=GROUND_TRUTH_DIR,
        mondo=mondo,
        force_reextract=True,
        ablation_original_only=ablation_original_only,
    )

    return {
        "entry_id": entry_id,
        "mode": mode_label,
        "pipeline_status": m.pipeline_status,
        "run_id": m.run_id,
        "evidence_count": m.evidence_count,
        "found_rate": m.found_rate,
        "grounding_rate": getattr(m, "grounding_rate", 0.0),
        "field_matches": [
            {
                "field_id": fm.field_id,
                "matched": fm.matched,
                "expected_value": fm.expected_value,
                "extracted_value": fm.extracted_value,
                "match_type": fm.match_type,
            }
            for fm in m.field_matches
        ],
        "entity_matches": {k: bool(v) for k, v in m.entity_matches.items()},
        "standardization_accuracy": m.standardization_accuracy,
        "duration_s": m.duration_s,
        "error_message": m.error_message,
    }


async def run_ablation_study(
    base_url: str,
    concurrency: int,
    api_key: str | None = None,
    limit: int | None = None,
    write_report: bool = False,
) -> dict:
    """Run ablation study: dual-track vs EN-only for each entry."""
    from benchmark.core.pipeline_client import (
        load_proxy,
        async_session_factory,
        build_async_engine,
        preflight_database_connection,
    )

    selection_path = GROUND_TRUTH_DIR / "selection.json"
    if not selection_path.exists():
        logger.error("selection.json not found at {}", GROUND_TRUTH_DIR)
        sys.exit(1)

    raw_entries = json.loads(selection_path.read_text(encoding="utf-8"))
    if limit:
        raw_entries = raw_entries[:limit]

    entries = [_adapt_fused_entry(e) for e in raw_entries]
    n = len(entries)
    logger.info("Ablation study: {} entries × 2 modes = {} runs at {}", n, n * 2, base_url)

    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    semaphore = asyncio.Semaphore(concurrency)
    engine = build_async_engine()
    sf = async_session_factory(engine)
    await preflight_database_connection(sf)

    mondo = None
    try:
        from benchmark.core.mondo_hierarchy import MondoHierarchy
        mondo = MondoHierarchy.load()
        logger.info("MONDO hierarchy loaded")
    except Exception as e:
        logger.warning("MONDO hierarchy not available: {}", e)

    client_kwargs: dict = dict(transport_kwargs)
    if api_key:
        client_kwargs["headers"] = {"X-API-Key": api_key}

    import httpx

    t0 = time.time()
    all_results: list[dict] = []

    async with httpx.AsyncClient(**client_kwargs) as client:
        # Phase 1: EN-only for all entries
        logger.info("Phase 1/2: Running EN-only mode for {} entries", n)
        en_results: list[dict] = []

        async def run_en(entry: dict) -> dict:
            r = await _run_one_mode(entry, client, sf, semaphore, base_url, True, mondo)
            en_results.append(r)
            tp = sum(1 for fm in r["field_matches"] if fm["matched"])
            total = len(r["field_matches"])
            logger.info("[{}] EN-only: {} | {}/{} fields | {:.0f}s",
                        r["entry_id"], r["pipeline_status"], tp, total, r["duration_s"])
            return r

        await asyncio.gather(*(run_en(e) for e in entries))

        # Phase 2: Dual-track for all entries
        logger.info("Phase 2/2: Running dual-track mode for {} entries", n)
        dual_results: list[dict] = []

        async def run_dual(entry: dict) -> dict:
            r = await _run_one_mode(entry, client, sf, semaphore, base_url, False, mondo)
            dual_results.append(r)
            tp = sum(1 for fm in r["field_matches"] if fm["matched"])
            total = len(r["field_matches"])
            logger.info("[{}] Dual:   {} | {}/{} fields | {:.0f}s",
                        r["entry_id"], r["pipeline_status"], tp, total, r["duration_s"])
            return r

        await asyncio.gather(*(run_dual(e) for e in entries))

    duration = time.time() - t0

    # Per-entry comparison
    en_by_id = {r["entry_id"]: r for r in en_results}
    dual_by_id = {r["entry_id"]: r for r in dual_results}

    comparison_results = []
    for entry_id in en_by_id:
        en_r = en_by_id.get(entry_id)
        dual_r = dual_by_id.get(entry_id)
        if not en_r or not dual_r:
            continue

        en_matched = sum(1 for fm in en_r["field_matches"] if fm["matched"])
        dual_matched = sum(1 for fm in dual_r["field_matches"] if fm["matched"])
        en_total = len(en_r["field_matches"])
        dual_total = len(dual_r["field_matches"])

        # Per-field comparison: which fields benefit from ZH?
        field_improvements = []
        en_fields = {fm["field_id"]: fm for fm in en_r["field_matches"]}
        dual_fields = {fm["field_id"]: fm for fm in dual_r["field_matches"]}

        for fid in set(en_fields.keys()) | set(dual_fields.keys()):
            en_fm = en_fields.get(fid, {})
            dual_fm = dual_fields.get(fid, {})
            en_ok = en_fm.get("matched", False)
            dual_ok = dual_fm.get("matched", False)
            if not en_ok and dual_ok:
                field_improvements.append({
                    "field_id": fid,
                    "improvement": "en_missed_dual_found",
                    "dual_value": dual_fm.get("extracted_value"),
                })
            elif en_ok and not dual_ok:
                field_improvements.append({
                    "field_id": fid,
                    "improvement": "en_found_dual_missed",
                })

        comparison_results.append({
            "entry_id": entry_id,
            "en_evidence_count": en_r["evidence_count"],
            "dual_evidence_count": dual_r["evidence_count"],
            "evidence_gain": dual_r["evidence_count"] - en_r["evidence_count"],
            "en_matched_fields": en_matched,
            "dual_matched_fields": dual_matched,
            "field_improvements": field_improvements,
            "en_found_rate": en_r["found_rate"],
            "dual_found_rate": dual_r["found_rate"],
        })

    # Aggregate statistics
    valid_comparisons = [c for c in comparison_results
                         if en_by_id[c["entry_id"]]["pipeline_status"] in ("completed", "preprocessed")
                         and dual_by_id[c["entry_id"]]["pipeline_status"] in ("completed", "preprocessed")]

    avg_en_evidence = sum(c["en_evidence_count"] for c in valid_comparisons) / len(valid_comparisons) if valid_comparisons else 0
    avg_dual_evidence = sum(c["dual_evidence_count"] for c in valid_comparisons) / len(valid_comparisons) if valid_comparisons else 0
    avg_evidence_gain = sum(c["evidence_gain"] for c in valid_comparisons) / len(valid_comparisons) if valid_comparisons else 0

    avg_en_matched = sum(c["en_matched_fields"] for c in valid_comparisons) / len(valid_comparisons) if valid_comparisons else 0
    avg_dual_matched = sum(c["dual_matched_fields"] for c in valid_comparisons) / len(valid_comparisons) if valid_comparisons else 0

    # Count field improvements by type
    field_gain_count: dict[str, int] = {}
    for c in valid_comparisons:
        for imp in c["field_improvements"]:
            if imp["improvement"] == "en_missed_dual_found":
                fid = imp["field_id"]
                field_gain_count[fid] = field_gain_count.get(fid, 0) + 1

    entries_with_gain = sum(1 for c in valid_comparisons if c["evidence_gain"] > 0)
    entries_with_field_gain = sum(1 for c in valid_comparisons if any(
        imp["improvement"] == "en_missed_dual_found" for imp in c["field_improvements"]
    ))

    report = {
        "study": "ablation_dual_vs_en_only",
        "dataset": "clinvar_fused",
        "total_entries": n,
        "valid_comparisons": len(valid_comparisons),
        "duration_s": round(duration, 1),
        "en_only": {
            "avg_evidence_count": round(avg_en_evidence, 2),
            "avg_matched_fields": round(avg_en_matched, 2),
        },
        "dual_track": {
            "avg_evidence_count": round(avg_dual_evidence, 2),
            "avg_matched_fields": round(avg_dual_matched, 2),
        },
        "marginal_contribution": {
            "avg_evidence_gain": round(avg_evidence_gain, 2),
            "entries_with_evidence_gain": entries_with_gain,
            "entries_with_field_improvement": entries_with_field_gain,
            "field_gain_by_type": field_gain_count,
            "evidence_gain_pct": round(avg_evidence_gain / avg_en_evidence * 100, 1) if avg_en_evidence > 0 else 0,
            "field_match_improvement_pct": round(
                (avg_dual_matched - avg_en_matched) / 8 * 100, 1
            ),  # 8 fields per entry
        },
        "per_entry": comparison_results,
    }

    # Save report
    reports_dir = GROUND_TRUTH_DIR.parent.parent / "reports" / "nar_ablation"
    reports_dir.mkdir(parents=True, exist_ok=True)

    en_path = reports_dir / "en_only_metrics.json"
    en_path.write_text(json.dumps(en_results, indent=2, ensure_ascii=False), encoding="utf-8")

    dual_path = reports_dir / "dual_track_metrics.json"
    dual_path.write_text(json.dumps(dual_results, indent=2, ensure_ascii=False), encoding="utf-8")

    report_path = reports_dir / "ablation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Reports saved to {}", reports_dir)

    # Print summary
    print("\n" + "=" * 60)
    print("Ablation Study: Dual-Track (EN+ZH) vs English-Only")
    print("=" * 60)
    print(f"Entries: {len(valid_comparisons)}/{n}")
    print(f"Duration: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"\n{'Metric':<35} {'EN-only':>10} {'Dual':>10} {'Gain':>10}")
    print("-" * 65)
    print(f"{'Avg evidence items':<35} {avg_en_evidence:>10.1f} {avg_dual_evidence:>10.1f} {avg_evidence_gain:>+10.1f}")
    print(f"{'Avg matched fields (/8)':<35} {avg_en_matched:>10.1f} {avg_dual_matched:>10.1f} {avg_dual_matched - avg_en_matched:>+10.1f}")
    print(f"\nMarginal contribution of ZH track:")
    print(f"  Entries with evidence gain: {entries_with_gain}/{len(valid_comparisons)}")
    print(f"  Entries with field improvement: {entries_with_field_gain}/{len(valid_comparisons)}")
    print(f"  Evidence gain %: {report['marginal_contribution']['evidence_gain_pct']:.1f}%")
    print(f"\nField-level improvements (EN missed → Dual found):")
    for fid, count in sorted(field_gain_count.items(), key=lambda x: -x[1]):
        print(f"  {fid}: {count}/{len(valid_comparisons)} entries")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablation study: dual-track vs EN-only")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None, help="Process only N entries")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    asyncio.run(run_ablation_study(
        base_url=args.base_url,
        concurrency=args.concurrency,
        api_key=args.api_key,
        limit=args.limit,
        write_report=args.write,
    ))


if __name__ == "__main__":
    main()
