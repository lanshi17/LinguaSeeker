"""Summarize unified B8 benchmark reports into a paper-ready markdown document.

Usage:
    cd backend
    uv run python -m benchmark.analysis.paper_artifacts.summarize_unified_b8_report \
        --reports ../benchmark/data/reports/eval_unified_*.json \
        --output ../benchmark/data/reports/unified_b8_paper_summary_20260627.md
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def _fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%" if pct else f"{v:.4f}"


def _load_report(path: Path) -> dict:
    return json.loads(path.read_text())


def _pick_latest(reports: list[dict]) -> dict:
    """Pick the report with the most per_entry items (most complete)."""
    return max(reports, key=lambda r: len(r.get("per_entry", [])))


def build_summary(report: dict) -> str:
    cfg = report.get("config", {})
    agg = report.get("aggregates", {})
    overall = agg.get("overall", {})
    by_src = agg.get("by_source_dataset", {})
    per = report.get("per_entry", [])
    te = agg.get("timeout_and_errors", [])

    total = report.get("total_entries", len(per))
    completed = sum(1 for e in per if e.get("pipeline_status") == "completed")
    failed = sum(1 for e in per if e.get("pipeline_status") != "completed")
    duration = report.get("total_duration_s", 0)

    lines: list[str] = []
    w = lines.append

    w("# Unified B8 Benchmark Summary")
    w("")
    w("## Experiment Setup")
    w("")
    w(f"- **Dataset**: {cfg.get('dataset', 'unified')}")
    w(f"- **Extraction mode**: {cfg.get('extraction_mode', 'b8')} (business default)")
    w(f"- **Extraction profile**: {cfg.get('extraction_profile', 'none')}")
    w(f"- **Force re-extraction**: yes (--no-preprocessed)")
    w(f"- **Concurrency**: {cfg.get('concurrency', 1)}")
    w(f"- **Base URL**: {cfg.get('base_url', 'N/A')}")
    w(f"- **Total entries**: {total}")
    w(f"- **Completed**: {completed}")
    w(f"- **Failed/Timeout**: {failed}")
    w(f"- **Total duration**: {duration:.0f}s ({duration / 60:.1f}min)")
    w(f"- **Report timestamp**: {report.get('timestamp', 'N/A')}")
    w("")

    # ── Overall metrics table ──
    w("## Overall Metrics")
    w("")
    w("| Metric | Value |")
    w("|--------|-------|")
    w(f"| Precision | {_fmt(overall.get('precision'), True)} |")
    w(f"| Recall | {_fmt(overall.get('recall'), True)} |")
    w(f"| F1 | {_fmt(overall.get('f1'), True)} |")
    w(f"| True Positives | {overall.get('true_positives', '—')} |")
    w(f"| False Positives | {overall.get('false_positives', '—')} |")
    w(f"| False Negatives | {overall.get('false_negatives', '—')} |")
    w(f"| Over-extractions | {overall.get('over_extractions', '—')} |")
    w(f"| Entity Std. Accuracy | {_fmt(overall.get('entity_standardization_accuracy'), True)} |")
    w(f"| Cross-lingual Consistency | {_fmt(overall.get('cross_lingual_consistency'), True)} |")
    w("")

    # ── By source dataset table ──
    w("## By Source Dataset")
    w("")
    w("| Dataset | N | TP | FP | FN | Precision | Recall | F1 |")
    w("|---------|---|----|----|-----|-----------|--------|----|")
    for src in sorted(by_src.keys()):
        m = by_src[src]
        n = m.get("count", "?")
        w(f"| {src} | {n} | {m.get('true_positives', '—')} | {m.get('false_positives', '—')} | {m.get('false_negatives', '—')} | {_fmt(m.get('precision'), True)} | {_fmt(m.get('recall'), True)} | {_fmt(m.get('f1'), True)} |")
    w("")

    # ── Failure / timeout table ──
    w("## Failures and Timeouts")
    w("")
    if te:
        w("| Entry ID | Status | Error |")
        w("|----------|--------|-------|")
        for item in te:
            eid = item.get("entry_id", "?")
            st = item.get("status", "?")
            err = (item.get("error", "") or "")[:120]
            w(f"| {eid} | {st} | {err} |")
    else:
        failed_entries = [e for e in per if e.get("pipeline_status") != "completed"]
        if failed_entries:
            w("| Entry ID | Gene | Source | Status | Duration (s) | Error |")
            w("|----------|------|--------|--------|-------------|-------|")
            for e in failed_entries:
                w(f"| {e.get('entry_id', '?')} | {e.get('gene_symbol', '?')} | {e.get('source_dataset', '?')} | {e.get('pipeline_status', '?')} | {e.get('duration_s', '—'):.0f} | {(e.get('error_message') or '')[:100]} |")
        else:
            w("No failures or timeouts recorded.")
    w("")

    # ── Per-entry summary stats ──
    w("## Per-Entry Statistics")
    w("")
    durations = [e["duration_s"] for e in per if e.get("duration_s") is not None]
    if durations:
        avg_dur = sum(durations) / len(durations)
        min_dur = min(durations)
        max_dur = max(durations)
        w(f"- Average duration: {avg_dur:.0f}s ({avg_dur / 60:.1f}min)")
        w(f"- Min duration: {min_dur:.0f}s")
        w(f"- Max duration: {max_dur:.0f}s ({max_dur / 60:.1f}min)")
    w(f"- Entries with evidence: {sum(1 for e in per if (e.get('evidence_count') or 0) > 0)}/{len(per)}")
    found_rates = [e["found_rate"] for e in per if e.get("found_rate") is not None]
    if found_rates:
        w(f"- Average found_rate: {sum(found_rates) / len(found_rates):.2%}")
    w("")

    # ── Paper-ready prose draft ──
    w("## Results Text Draft")
    w("")
    w("On the unified dataset (150 entries spanning ClinGen, ClinVar-Fused, Rett, and ")
    w("Parkinson sources), the B8 business pipeline achieved an overall precision of ")
    w(f"{overall.get('precision', 0) * 100:.1f}%, recall of {overall.get('recall', 0) * 100:.1f}%, ")
    w(f"and F1 score of {overall.get('f1', 0) * 100:.1f}%. ")
    if by_src:
        best_src = max(by_src.items(), key=lambda x: x[1].get("f1", 0))
        w(f"The best-performing source dataset was {best_src[0]} (F1 = {best_src[1].get('f1', 0) * 100:.1f}%), ")
        worst_src = min(by_src.items(), key=lambda x: x[1].get("f1", 0))
        w(f"while {worst_src[0]} proved most challenging (F1 = {worst_src[1].get('f1', 0) * 100:.1f}%). ")
    w(f"Out of {total} entries, {completed} completed successfully and {failed} failed or timed out. ")
    w(f"Total evaluation time was {duration / 60:.0f} minutes at concurrency {cfg.get('concurrency', 1)}.")
    w("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", nargs="+", required=True, help="Glob patterns for report JSON files")
    parser.add_argument("--output", type=Path, required=True, help="Output markdown path")
    args = parser.parse_args()

    # Resolve globs
    paths: list[Path] = []
    for pattern in args.reports:
        paths.extend(Path(p) for p in glob.glob(pattern))
    if not paths:
        print("No report files found.")
        return

    reports = [_load_report(p) for p in sorted(paths)]
    # Use the most complete report
    report = _pick_latest(reports)
    print(f"Using report: {len(report.get('per_entry', []))} entries")

    md = build_summary(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md)
    print(f"Summary written to {args.output}")


if __name__ == "__main__":
    main()
