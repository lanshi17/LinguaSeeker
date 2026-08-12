"""Run NAR Web Server benchmark evaluation on fused-75 dataset.

Submits all 75 entries to the pipeline, waits for completion,
then runs three-layer evaluation (gene-disease P/R/F1, variant precision,
entity standardization accuracy).

Uses ``benchmark.core.pipeline_client.evaluate_one`` which handles
pipeline submission, polling, PG evidence query, and per-entry metrics.

Usage:
    PYTHONPATH=.:backend/src python -m benchmark.datasets.clinvar_fused.run_nar_benchmark \
        --base-url http://localhost:8000 \
        --concurrency 3 \
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


async def run_benchmark(
    base_url: str,
    concurrency: int,
    api_key: str | None = None,
    limit: int | None = None,
    force_reextract: bool = False,
    write_report: bool = False,
) -> dict:
    """Run the full benchmark: submit pipeline + evaluate each entry."""
    from benchmark.core.pipeline_client import (
        evaluate_one,
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
    logger.info("Evaluating {} fused entries at {}", len(entries), base_url)

    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    semaphore = asyncio.Semaphore(concurrency)
    engine = build_async_engine()
    sf = async_session_factory(engine)
    await preflight_database_connection(sf)

    try:
        # Load MONDO hierarchy if available
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
        all_metrics = []

        async with httpx.AsyncClient(**client_kwargs) as client:
            async def eval_and_collect(entry: dict):
                m = await evaluate_one(
                    client,
                    base_url,
                    entry,
                    sf,
                    semaphore,
                    ground_truth_dir=GROUND_TRUTH_DIR,
                    mondo=mondo,
                    force_reextract=force_reextract,
                )
                all_metrics.append(m)
                icon = "✓" if m.pipeline_status == "completed" else "✗"
                tp = sum(1 for f in m.field_matches if f.matched)
                total = len(m.field_matches)
                std_str = f"std={m.standardization_accuracy:.0%}" if m.entity_matches else "std=-"
                logger.info("[{}] {} | {} | {}/{} fields | {} | {:.0f}s",
                            m.entry_id, icon, m.pipeline_status, tp, total, std_str, m.duration_s)
                return m

            tasks = [eval_and_collect(e) for e in entries]
            await asyncio.gather(*tasks)

        duration = time.time() - t0

        # Save per-entry metrics
        metrics_dir = GROUND_TRUTH_DIR.parent.parent / "reports" / "nar_fused75"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_list = []
        for m in all_metrics:
            metrics_list.append({
                "entry_id": m.entry_id,
                "gene_symbol": m.gene_symbol,
                "pipeline_status": m.pipeline_status,
                "evidence_count": m.evidence_count,
                "found_rate": m.found_rate,
                "grounding_rate": getattr(m, "grounding_rate", 0.0),
                "standardization_accuracy": m.standardization_accuracy,
                "track_consistency": m.track_consistency,
                "duration_s": m.duration_s,
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
                "error_message": m.error_message,
            })

        metrics_path = metrics_dir / "per_entry_metrics.json"
        metrics_path.write_text(json.dumps(metrics_list, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Per-entry metrics saved to {}", metrics_path)

        # Aggregate report
        completed = [m for m in all_metrics if m.pipeline_status in ("completed", "preprocessed")]
        total_entries = len(all_metrics)

        # Layer 1: Gene-Disease P/R/F1
        field_tp: dict[str, int] = {}
        field_fp: dict[str, int] = {}
        field_fn: dict[str, int] = {}
        for m in completed:
            for fm in m.field_matches:
                fid = fm.field_id
                if fid not in field_tp:
                    field_tp[fid] = 0
                    field_fp[fid] = 0
                    field_fn[fid] = 0
                if fm.matched:
                    field_tp[fid] += 1
                else:
                    field_fn[fid] += 1
                    if fm.extracted_value:
                        field_fp[fid] += 1

        layer1_by_field = {}
        for fid in field_tp:
            tp, fp, fn = field_tp[fid], field_fp[fid], field_fn[fid]
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
            layer1_by_field[fid] = {"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn}

        # Overall Layer 1
        total_tp = sum(field_tp.values())
        total_fp = sum(field_fp.values())
        total_fn = sum(field_fn.values())
        overall_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        overall_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) > 0 else 0.0

        # Layer 2: Variant Precision
        variant_tp = sum(1 for m in completed for fm in m.field_matches
                         if fm.field_id.startswith("C.") and fm.matched)
        variant_fp = sum(1 for m in completed for fm in m.field_matches
                         if fm.field_id.startswith("C.") and not fm.matched and fm.extracted_value)
        variant_precision = variant_tp / (variant_tp + variant_fp) if (variant_tp + variant_fp) > 0 else 0.0

        # Layer 3: Standardization
        entity_correct: dict[str, int] = {}
        entity_total: dict[str, int] = {}
        for m in completed:
            for etype, matched in m.entity_matches.items():
                entity_total.setdefault(etype, 0)
                entity_correct.setdefault(etype, 0)
                entity_total[etype] += 1
                if matched:
                    entity_correct[etype] += 1

        layer3 = {
            et: {
                "accuracy": entity_correct[et] / entity_total[et] if entity_total[et] > 0 else 0.0,
                "correct": entity_correct[et],
                "total": entity_total[et],
            }
            for et in entity_total
        }

        # Track consistency
        tc_values = [m.track_consistency for m in completed if m.track_consistency > 0]
        avg_tc = sum(tc_values) / len(tc_values) if tc_values else 0.0

        report = {
            "dataset": "clinvar_fused_75",
            "total_entries": total_entries,
            "evaluated_entries": len(completed),
            "failed_entries": total_entries - len(completed),
            "duration_s": round(duration, 1),
            "layer1_gene_disease": {
                "overall": {"precision": overall_p, "recall": overall_r, "f1": overall_f1},
                "by_field": layer1_by_field,
            },
            "layer2_variant": {
                "overall_precision": variant_precision,
                "tp": variant_tp,
                "fp": variant_fp,
            },
            "layer3_standardization": layer3,
            "track_consistency": avg_tc,
        }

        report_path = metrics_dir / "aggregate_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Aggregate report saved to {}", report_path)

        # Print summary
        print("\n" + "=" * 60)
        print("NAR Web Server Benchmark Results (Fused-75)")
        print("=" * 60)
        print(f"Entries: {len(completed)}/{total_entries}")
        print(f"Duration: {duration:.0f}s")
        print(f"\nLayer 1 - Gene-Disease (P/R/F1):")
        print(f"  Overall: P={overall_p:.1%} R={overall_r:.1%} F1={overall_f1:.1%}")
        for fid, fm in sorted(layer1_by_field.items()):
            print(f"  {fid}: P={fm['precision']:.1%} R={fm['recall']:.1%} F1={fm['f1']:.1%} "
                  f"(TP={fm['tp']} FP={fm['fp']} FN={fm['fn']})")
        print(f"\nLayer 2 - Variant Precision:")
        print(f"  Overall: {variant_precision:.1%} (TP={variant_tp} FP={variant_fp})")
        print(f"\nLayer 3 - Standardization:")
        for et, em in layer3.items():
            print(f"  {et}: {em['accuracy']:.1%} ({em['correct']}/{em['total']})")
        print(f"\nTrack Consistency (EN↔ZH): {avg_tc:.1%}")

        return report

    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="NAR Web Server benchmark runner (fused-75)")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="Process only N entries")
    parser.add_argument("--api-key", default=None, help="API key for authentication")
    parser.add_argument("--force-reextract", action="store_true", help="Re-run pipeline even if cached")
    parser.add_argument("--write", action="store_true", help="Write report to file")
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        base_url=args.base_url,
        concurrency=args.concurrency,
        api_key=args.api_key,
        limit=args.limit,
        force_reextract=args.force_reextract,
        write_report=args.write,
    ))


if __name__ == "__main__":
    main()
