#!/usr/bin/env python3
"""GIM ablation: measure multilingual evidence contribution.

For each entry, runs in dual mode and reads extraction_result.json to
measure the evidence contribution of each language track:

  - English track "found" items (baseline)
  - Chinese track "found" items (translation contribution)
  - Combined unique "found" items (union)
  - Incremental evidence from translation = combined - English

This directly shows: multilingual processing produces MORE evidence
than English-only processing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

from benchmark.core.paths import GROUND_TRUTH_CLINVAR_FUSED_ROOT
from benchmark.core.pipeline_client import (
    load_proxy,
    async_session_factory,
    build_async_engine,
    preflight_database_connection,
    evaluate_one,
)
import httpx

GROUND_TRUTH_DIR = GROUND_TRUTH_CLINVAR_FUSED_ROOT


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


def _count_found_by_track(extraction_result_path: Path) -> dict:
    """Read extraction_result.json and count 'found' evidence per track."""
    if not extraction_result_path.exists():
        return {"error": f"File not found: {extraction_result_path}"}

    with open(extraction_result_path) as f:
        data = json.load(f)

    result = {}
    for track_name in ("original_result", "translated_result", "reconciled_result"):
        track_data = data.get(track_name, {})
        items = track_data.get("evidence_items", [])
        found_items = [i for i in items if i.get("status") == "found"]
        found_fields = set(i.get("field_id", "") for i in found_items)
        result[track_name] = {
            "total_items": len(items),
            "found_count": len(found_items),
            "found_fields": sorted(found_fields),
            "found_values": {
                i["field_id"]: i.get("value", "")
                for i in found_items
            },
        }

    # Compute unique fields per track
    orig_fields = set(result["original_result"]["found_fields"])
    trans_fields = set(result["translated_result"]["found_fields"])
    combined_fields = orig_fields | trans_fields

    # Fields only found in translated track (contribution of multilingual)
    trans_only = trans_fields - orig_fields
    orig_only = orig_fields - trans_fields
    common = orig_fields & trans_fields

    result["contribution"] = {
        "english_only_fields": sorted(orig_only),
        "chinese_only_fields": sorted(trans_only),
        "common_fields": sorted(common),
        "combined_unique_fields": sorted(combined_fields),
        "multilingual_gain": len(combined_fields) - len(orig_fields),
    }

    return result


async def run_multilingual_ablation(
    base_url: str,
    concurrency: int,
    api_key: str | None = None,
    limit: int | None = None,
    entries_filter: list[str] | None = None,
) -> dict:
    """Run all entries in dual mode and measure per-track evidence contribution."""
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    if not selection_path.exists():
        logger.error("selection.json not found at {}", GROUND_TRUTH_DIR)
        sys.exit(1)

    raw_entries = json.loads(selection_path.read_text(encoding="utf-8"))
    if limit:
        raw_entries = raw_entries[:limit]
    if entries_filter:
        raw_entries = [e for e in raw_entries if e["entry_id"] in entries_filter]

    entries = [_adapt_fused_entry(e) for e in raw_entries]
    n = len(entries)
    logger.info("Multilingual ablation: {} entries in dual mode at {}", n, base_url)

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

    t0 = time.time()
    per_entry_results: list[dict] = []

    async with httpx.AsyncClient(**client_kwargs) as client:
        for i, entry in enumerate(entries):
            entry_id = entry["entry_id"]
            logger.info("[{}/{}] Running {} in dual mode...", i + 1, n, entry_id)

            m = await evaluate_one(
                client,
                base_url,
                entry,
                sf,
                semaphore,
                ground_truth_dir=GROUND_TRUTH_DIR,
                mondo=mondo,
                force_reextract=True,
                ablation_original_only=False,  # dual mode
            )

            # Read extraction_result.json for per-track analysis
            run_id = m.run_id
            pipeline_data_dir = Path(os.environ.get("PIPELINE_DATA_DIR", "/data/yangzs/Projects/01_ACMG_Lingua/data/pipeline"))
            extraction_path = pipeline_data_dir / run_id / "phase_2" / "extraction_result.json"
            track_analysis = _count_found_by_track(extraction_path)

            entry_result = {
                "entry_id": entry_id,
                "run_id": run_id,
                "pipeline_status": m.pipeline_status,
                "duration_s": m.duration_s,
                "field_matches": [
                    {
                        "field_id": fm.field_id,
                        "matched": fm.matched,
                        "expected_value": fm.expected_value,
                        "extracted_value": fm.extracted_value,
                    }
                    for fm in m.field_matches
                ],
                "track_analysis": track_analysis,
            }

            if "error" not in track_analysis:
                contrib = track_analysis.get("contribution", {})
                en_found = track_analysis.get("original_result", {}).get("found_count", 0)
                zh_found = track_analysis.get("translated_result", {}).get("found_count", 0)
                gain = contrib.get("multilingual_gain", 0)
                zh_only = contrib.get("chinese_only_fields", [])
                logger.info(
                    "[{}] EN found={}, ZH found={}, combined_gain={}, ZH-only fields={}",
                    entry_id, en_found, zh_found, gain, zh_only,
                )

            per_entry_results.append(entry_result)

    duration = time.time() - t0

    # Aggregate statistics
    en_found_total = 0
    zh_found_total = 0
    combined_found_total = 0
    zh_only_items_total = 0
    entries_with_zh_contribution = 0
    entries_with_zh_only_fields = 0
    valid = 0

    for r in per_entry_results:
        ta = r.get("track_analysis", {})
        if "error" in ta:
            continue
        valid += 1
        contrib = ta.get("contribution", {})
        en_found = ta.get("original_result", {}).get("found_count", 0)
        zh_found = ta.get("translated_result", {}).get("found_count", 0)
        combined = len(contrib.get("combined_unique_fields", []))
        zh_only = len(contrib.get("chinese_only_fields", []))

        en_found_total += en_found
        zh_found_total += zh_found
        combined_found_total += combined
        zh_only_items_total += zh_only

        if zh_found > 0:
            entries_with_zh_contribution += 1
        if contrib.get("chinese_only_fields"):
            entries_with_zh_only_fields += 1

    avg_en = en_found_total / valid if valid else 0
    avg_zh = zh_found_total / valid if valid else 0
    avg_combined = combined_found_total / valid if valid else 0
    avg_zh_only = zh_only_items_total / valid if valid else 0

    # Per-field analysis: which fields benefit from Chinese track?
    field_zh_benefit: dict[str, int] = {}
    for r in per_entry_results:
        ta = r.get("track_analysis", {})
        if "error" in ta:
            continue
        contrib = ta.get("contribution", {})
        for f in contrib.get("chinese_only_fields", []):
            field_zh_benefit[f] = field_zh_benefit.get(f, 0) + 1

    report = {
        "study": "multilingual_evidence_contribution",
        "dataset": "clinvar_fused",
        "total_entries": n,
        "valid_entries": valid,
        "duration_s": round(duration, 1),
        "aggregate": {
            "avg_en_track_found": round(avg_en, 2),
            "avg_zh_track_found": round(avg_zh, 2),
            "avg_combined_unique_found": round(avg_combined, 2),
            "multilingual_gain_items": round(avg_zh_only, 2),
            "multilingual_gain_pct": round(avg_zh_only / avg_en * 100, 1) if avg_en > 0 else 0,
            "entries_with_zh_contribution": entries_with_zh_contribution,
            "entries_with_zh_only_fields": entries_with_zh_only_fields,
        },
        "field_level_zh_benefit": field_zh_benefit,
    }

    # Save report
    reports_dir = GROUND_TRUTH_DIR.parent.parent / "reports" / "nar_ablation"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "multilingual_contribution_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Report saved to {}", report_path)

    # Print summary
    print("\n" + "=" * 70)
    print("MULTILINGUAL EVIDENCE CONTRIBUTION ANALYSIS")
    print("=" * 70)
    print(f"Valid entries: {valid}/{n}")
    print(f"Duration: {duration:.0f}s ({duration/60:.1f} min)")
    print()
    print(f"{'Metric':<45} {'Value':>10}")
    print("-" * 55)
    print(f"{'Avg EN track found items':<45} {avg_en:>10.1f}")
    print(f"{'Avg ZH track found items':<45} {avg_zh:>10.1f}")
    print(f"{'Avg combined unique fields':<45} {avg_combined:>10.1f}")
    print(f"{'Multilingual gain (ZH-only items)':<45} {avg_zh_only:>+10.1f}")
    print(f"{'Multilingual gain % (of EN-track mean)':<45} {avg_zh_only / avg_en * 100 if avg_en > 0 else 0:>+9.1f}%")
    print()
    print(f"Entries with ZH track contribution: {entries_with_zh_contribution}/{valid}")
    print(f"Entries with ZH-only fields: {entries_with_zh_only_fields}/{valid}")
    print()
    print("Field-level benefit from Chinese track (fields only found in ZH):")
    for fid, count in sorted(field_zh_benefit.items(), key=lambda x: -x[1]):
        print(f"  {fid}: {count}/{valid} entries")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Multilingual evidence contribution ablation")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--entries", nargs="*", default=None, help="Specific entry IDs to process")
    args = parser.parse_args()

    asyncio.run(run_multilingual_ablation(
        base_url=args.base_url,
        concurrency=args.concurrency,
        api_key=args.api_key,
        limit=args.limit,
        entries_filter=args.entries,
    ))


if __name__ == "__main__":
    main()
