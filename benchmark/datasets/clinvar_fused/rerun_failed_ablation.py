#!/usr/bin/env python3
"""Re-run failed dual-mode entries and update ablation report."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmark.core.pipeline_client import (
    load_proxy,
    async_session_factory,
    build_async_engine,
    preflight_database_connection,
    evaluate_one,
)
from benchmark.core.paths import GROUND_TRUTH_CLINVAR_FUSED_ROOT
from benchmark.core.mondo_hierarchy import MondoHierarchy
import httpx
import time


def _adapt_fused_entry(raw: dict) -> dict:
    """Flatten fused entry to the shape evaluate_one expects."""
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


async def rerun_failed_dual_entries(
    base_url: str,
    failed_entry_ids: list[str],
    concurrency: int = 1,
    api_key: str | None = None,
) -> list[dict]:
    """Re-run specific entries in dual mode."""
    # Load all entries
    selection_path = GROUND_TRUTH_CLINVAR_FUSED_ROOT / "selection.json"
    raw_entries = json.loads(selection_path.read_text(encoding="utf-8"))
    entries = [_adapt_fused_entry(e) for e in raw_entries]

    # Filter to failed entries only
    entries_to_rerun = [e for e in entries if e["entry_id"] in failed_entry_ids]
    print(f"Re-running {len(entries_to_rerun)} failed entries: {failed_entry_ids}")

    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    semaphore = asyncio.Semaphore(concurrency)
    engine = build_async_engine()
    sf = async_session_factory(engine)
    await preflight_database_connection(sf)

    mondo = None
    try:
        mondo = MondoHierarchy.load()
        print("MONDO hierarchy loaded")
    except Exception as e:
        print(f"MONDO hierarchy not available: {e}")

    client_kwargs: dict = dict(transport_kwargs)
    if api_key:
        client_kwargs["headers"] = {"X-API-Key": api_key}

    results = []
    async with httpx.AsyncClient(**client_kwargs) as client:
        for entry in entries_to_rerun:
            entry_id = entry["entry_id"]
            print(f"\n{'='*60}")
            print(f"Re-running {entry_id} in dual mode...")
            print(f"{'='*60}")

            m = await evaluate_one(
                client,
                base_url,
                entry,
                sf,
                semaphore,
                ground_truth_dir=GROUND_TRUTH_CLINVAR_FUSED_ROOT,
                mondo=mondo,
                force_reextract=True,
                ablation_original_only=False,  # dual mode
            )

            result = {
                "entry_id": entry_id,
                "mode": "dual",
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

            results.append(result)
            tp = sum(1 for fm in result["field_matches"] if fm["matched"])
            total = len(result["field_matches"])
            print(f"  Result: status={result['pipeline_status']}, evidence={result['evidence_count']}, "
                  f"fields={tp}/{total}, duration={result['duration_s']:.0f}s")

    await client.aclose()
    return results


def update_ablation_report(new_dual_results: list[dict]) -> None:
    """Update ablation_report.json and dual_track_metrics.json with new results."""
    reports_dir = GROUND_TRUTH_CLINVAR_FUSED_ROOT.parent.parent / "reports" / "nar_ablation"

    # Load existing results
    en_path = reports_dir / "en_only_metrics.json"
    dual_path = reports_dir / "dual_track_metrics.json"
    report_path = reports_dir / "ablation_report.json"

    en_results = json.loads(en_path.read_text(encoding="utf-8"))
    dual_results = json.loads(dual_path.read_text(encoding="utf-8"))

    # Update dual results
    new_dual_by_id = {r["entry_id"]: r for r in new_dual_results}
    for i, r in enumerate(dual_results):
        if r["entry_id"] in new_dual_by_id:
            dual_results[i] = new_dual_by_id[r["entry_id"]]
            print(f"Updated {r['entry_id']}: evidence={new_dual_by_id[r['entry_id']]['evidence_count']}")

    # Rebuild comparison report
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
        "total_entries": len(en_results),
        "valid_comparisons": len(valid_comparisons),
        "duration_s": 0,  # Not updated
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
            ),
        },
        "per_entry": comparison_results,
    }

    # Save updated files
    dual_path.write_text(json.dumps(dual_results, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*60}")
    print("Updated reports:")
    print(f"  {dual_path}")
    print(f"  {report_path}")
    print(f"{'='*60}")

    # Print summary
    print(f"\nSummary after re-run:")
    print(f"  Valid comparisons: {len(valid_comparisons)}/{len(en_results)}")
    print(f"  Avg evidence (EN): {avg_en_evidence:.1f}")
    print(f"  Avg evidence (Dual): {avg_dual_evidence:.1f}")
    print(f"  Evidence gain: {avg_evidence_gain:+.1f} ({report['marginal_contribution']['evidence_gain_pct']:+.1f}%)")
    print(f"  Avg matched fields (EN): {avg_en_matched:.1f}/8")
    print(f"  Avg matched fields (Dual): {avg_dual_matched:.1f}/8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Re-run failed dual-mode ablation entries")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()

    # Load failed entries from report
    reports_dir = GROUND_TRUTH_CLINVAR_FUSED_ROOT.parent.parent / "reports" / "nar_ablation"
    report_path = reports_dir / "ablation_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    failed_entry_ids = [e["entry_id"] for e in report["per_entry"] if e["dual_evidence_count"] == 0]
    print(f"Found {len(failed_entry_ids)} failed entries: {failed_entry_ids}")

    # Re-run failed entries
    new_results = asyncio.run(rerun_failed_dual_entries(
        base_url=args.base_url,
        failed_entry_ids=failed_entry_ids,
        concurrency=args.concurrency,
        api_key=args.api_key,
    ))

    # Update reports
    update_ablation_report(new_results)

    print(f"\n{'='*60}")
    print("Re-run complete!")
    print(f"{'='*60}")
