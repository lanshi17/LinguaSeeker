"""Three-way comparison: B0-naive vs B7-expanded vs SYSTEM.

Generates per-dataset, per-difficulty, and per-field metrics for all three
systems, plus SYSTEM vs B7-expanded statistical significance.

Usage:
    python -m benchmark.analysis.diagnostics.three_way_comparison [--write]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from benchmark.analysis.diagnostics.statistical_significance import (
    _classify_field,
    _f1,
    _precision,
    _recall,
    bootstrap_ci_paired_delta,
    compute_per_entry_outcomes,
    paired_permutation_test,
)

REPORTS_DIR = Path("benchmark/data/reports")


def _load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_entries(report: dict[str, Any]) -> list[dict[str, Any]]:
    strategies = report.get("strategies", [])
    if isinstance(strategies, list) and strategies:
        return strategies[0].get("per_entry", [])
    return report.get("per_entry", [])


def _entries_by_id(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(e["entry_id"]): e for e in entries if isinstance(e, dict) and e.get("entry_id")}


def _outcomes_for(
    entries: dict[str, dict[str, Any]],
    entry_ids: list[str],
    category: str | None = None,
) -> list[tuple[str, Any]]:
    """Return (entry_id, PerEntryOutcome) pairs."""
    results = []
    for eid in entry_ids:
        entry = entries[eid]
        matches = entry.get("field_matches", [])
        if category:
            matches = [m for m in matches if _classify_field(m.get("field_id", "")) == category]
        results.append((eid, compute_per_entry_outcomes(matches)))
    return results


def _f1_array(outcomes: list[tuple[str, Any]]) -> np.ndarray:
    return np.array([_f1(o.tp, o.fp, o.fn) for _, o in outcomes])


def _per_field_metrics(
    entries: dict[str, dict[str, Any]],
    entry_ids: list[str],
) -> dict[str, dict[str, float]]:
    """Compute per-field TP/FP/FN/F1 for a set of entries."""
    field_stats: dict[str, dict[str, int]] = {}
    for eid in entry_ids:
        entry = entries[eid]
        for m in entry.get("field_matches", []):
            fid = m.get("field_id", "")
            if not fid:
                continue
            if fid not in field_stats:
                field_stats[fid] = {"tp": 0, "fp": 0, "fn": 0}
            if m.get("matched"):
                field_stats[fid]["tp"] += 1
            elif m.get("match_type") == "missing":
                field_stats[fid]["fn"] += 1
            else:
                field_stats[fid]["fp"] += 1
                field_stats[fid]["fn"] += 1
    result: dict[str, dict[str, float]] = {}
    for fid, stats in sorted(field_stats.items()):
        tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
        result[fid] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(_precision(tp, fp), 4),
            "recall": round(_recall(tp, fn), 4),
            "f1": round(_f1(tp, fp, fn), 4),
            "support": tp + fn,
            "category": _classify_field(fid),
        }
    return result


def compute_three_way(
    sys_report: dict[str, Any],
    b0_report: dict[str, Any],
    b7_report: dict[str, Any],
    n_bootstrap: int = 5000,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute three-way comparison metrics."""
    sys_entries = _entries_by_id(_extract_entries(sys_report))
    b0_entries = _entries_by_id(_extract_entries(b0_report))
    b7_entries = _entries_by_id(_extract_entries(b7_report))

    common_ids = sorted(set(sys_entries) & set(b0_entries) & set(b7_entries))
    rett_ids = [i for i in common_ids if i.startswith("rett")]
    park_ids = [i for i in common_ids if i.startswith("parkinson")]

    def _group_stats(
        label: str,
        entry_ids: list[str],
        category: str | None = None,
    ) -> dict[str, Any]:
        sys_out = _outcomes_for(sys_entries, entry_ids, category)
        b0_out = _outcomes_for(b0_entries, entry_ids, category)
        b7_out = _outcomes_for(b7_entries, entry_ids, category)

        sys_tp = sum(o.tp for _, o in sys_out)
        sys_fp = sum(o.fp for _, o in sys_out)
        sys_fn = sum(o.fn for _, o in sys_out)
        b0_tp = sum(o.tp for _, o in b0_out)
        b0_fp = sum(o.fp for _, o in b0_out)
        b0_fn = sum(o.fn for _, o in b0_out)
        b7_tp = sum(o.tp for _, o in b7_out)
        b7_fp = sum(o.fp for _, o in b7_out)
        b7_fn = sum(o.fn for _, o in b7_out)

        sys_f1_arr = _f1_array(sys_out)
        b0_f1_arr = _f1_array(b0_out)
        b7_f1_arr = _f1_array(b7_out)

        # SYSTEM vs B7 significance
        seed_offset = hash(label) % (2**31)
        delta_ci = bootstrap_ci_paired_delta(
            sys_f1_arr, b7_f1_arr,
            n_bootstrap=n_bootstrap,
            rng=np.random.default_rng(seed + seed_offset),
        )
        perm = paired_permutation_test(
            sys_f1_arr, b7_f1_arr,
            n_permutations=n_bootstrap,
            rng=np.random.default_rng(seed + seed_offset + 1),
        )

        return {
            "label": label,
            "n_entries": len(entry_ids),
            "system": {
                "precision": round(_precision(sys_tp, sys_fp), 4),
                "recall": round(_recall(sys_tp, sys_fn), 4),
                "f1": round(_f1(sys_tp, sys_fp, sys_fn), 4),
                "per_entry_mean_f1": round(float(sys_f1_arr.mean()), 4),
            },
            "b0_naive": {
                "precision": round(_precision(b0_tp, b0_fp), 4),
                "recall": round(_recall(b0_tp, b0_fn), 4),
                "f1": round(_f1(b0_tp, b0_fp, b0_fn), 4),
                "per_entry_mean_f1": round(float(b0_f1_arr.mean()), 4),
            },
            "b7_expanded": {
                "precision": round(_precision(b7_tp, b7_fp), 4),
                "recall": round(_recall(b7_tp, b7_fn), 4),
                "f1": round(_f1(b7_tp, b7_fp, b7_fn), 4),
                "per_entry_mean_f1": round(float(b7_f1_arr.mean()), 4),
            },
            "delta_system_vs_b7": {
                "f1": round(_f1(sys_tp, sys_fp, sys_fn) - _f1(b7_tp, b7_fp, b7_fn), 4),
                "per_entry_mean_f1": round(float((sys_f1_arr - b7_f1_arr).mean()), 4),
                "bootstrap_ci_95": [round(delta_ci[0], 4), round(delta_ci[1], 4)],
                "p_value": round(perm.p_value, 4),
                "significant_at_0_05": perm.significant_at_0_05,
                "significant_at_0_01": perm.significant_at_0_01,
            },
            "delta_system_vs_b0": {
                "f1": round(_f1(sys_tp, sys_fp, sys_fn) - _f1(b0_tp, b0_fp, b0_fn), 4),
                "per_entry_mean_f1": round(float((sys_f1_arr - b0_f1_arr).mean()), 4),
            },
        }

    # Overall, per-dataset, per-difficulty
    groups: list[dict[str, Any]] = []
    groups.append(_group_stats("merged_73", common_ids))
    groups.append(_group_stats("rett_53", rett_ids))
    groups.append(_group_stats("parkinson_20", park_ids))
    for cat in ("simple_explicit", "medium_contextual", "complex_evidence"):
        groups.append(_group_stats(f"merged_{cat}", common_ids, category=cat))

    # Per-field metrics for all three systems
    per_field_sys = _per_field_metrics(sys_entries, common_ids)
    per_field_b0 = _per_field_metrics(b0_entries, common_ids)
    per_field_b7 = _per_field_metrics(b7_entries, common_ids)

    all_field_ids = sorted(set(per_field_sys) | set(per_field_b0) | set(per_field_b7))
    per_field_rows = []
    for fid in all_field_ids:
        s = per_field_sys.get(fid, {"f1": 0.0, "support": 0, "category": _classify_field(fid)})
        b0 = per_field_b0.get(fid, {"f1": 0.0, "support": 0, "category": _classify_field(fid)})
        b7 = per_field_b7.get(fid, {"f1": 0.0, "support": 0, "category": _classify_field(fid)})
        per_field_rows.append({
            "field_id": fid,
            "category": s.get("category", _classify_field(fid)),
            "support": s.get("support", 0),
            "system_f1": s.get("f1", 0.0),
            "b0_naive_f1": b0.get("f1", 0.0),
            "b7_expanded_f1": b7.get("f1", 0.0),
            "delta_system_vs_b7": round(s.get("f1", 0.0) - b7.get("f1", 0.0), 4),
            "delta_system_vs_b0": round(s.get("f1", 0.0) - b0.get("f1", 0.0), 4),
        })

    # Identify fields where B7 closes the gap vs B0
    fields_b7_closes_gap = [
        r for r in per_field_rows
        if r["b7_expanded_f1"] > r["b0_naive_f1"] + 0.01
    ]
    fields_system_still_wins = [
        r for r in per_field_rows
        if r["system_f1"] > r["b7_expanded_f1"] + 0.01
    ]

    return {
        "report_id": f"three_way_comparison_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_bootstrap": n_bootstrap,
        "seed": seed,
        "n_entries": len(common_ids),
        "datasets": ["rett", "parkinson"],
        "comparisons": groups,
        "per_field": per_field_rows,
        "fields_b7_closes_gap": fields_b7_closes_gap,
        "fields_system_still_wins": fields_system_still_wins,
    }


def _format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Three-Way Comparison: B0-naive vs B7-expanded vs SYSTEM",
        "",
        f"Generated: {result['timestamp']}",
        f"N entries: {result['n_entries']}",
        f"Bootstrap iterations: {result['n_bootstrap']}",
        "",
        "## 1. Overall Merged (N=73)",
        "",
    ]

    merged = next(c for c in result["comparisons"] if c["label"] == "merged_73")
    lines += _format_comparison_table([merged])

    lines += ["", "## 2. Per-Dataset", ""]
    per_ds = [c for c in result["comparisons"] if c["label"] in ("rett_53", "parkinson_20")]
    lines += _format_comparison_table(per_ds)

    lines += ["", "## 3. Per-Difficulty (Merged)", ""]
    per_diff = [c for c in result["comparisons"] if c["label"].startswith("merged_") and c["label"] != "merged_73"]
    lines += _format_comparison_table(per_diff)

    # Per-field table
    lines += ["", "## 4. Per-Field Comparison", ""]
    lines += [
        "| Field | Category | Support | SYS F1 | B0 F1 | B7 F1 | Δ(SYS-B7) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(result["per_field"], key=lambda x: -x.get("support", 0)):
        lines.append(
            f"| {r['field_id']} | {r['category']} | {r['support']} | "
            f"{r['system_f1']:.4f} | {r['b0_naive_f1']:.4f} | {r['b7_expanded_f1']:.4f} | "
            f"{r['delta_system_vs_b7']:+.4f} |"
        )

    # Fields where B7 closes gap
    lines += ["", "## 5. Fields Where B7-expanded Closes Gap vs B0-naive", ""]
    if result["fields_b7_closes_gap"]:
        for r in result["fields_b7_closes_gap"]:
            lines.append(
                f"- **{r['field_id']}** ({r['category']}): "
                f"B0={r['b0_naive_f1']:.4f} → B7={r['b7_expanded_f1']:.4f} "
                f"(+{r['b7_expanded_f1'] - r['b0_naive_f1']:.4f})"
            )
    else:
        lines.append("(none)")

    # Fields where SYSTEM still wins
    lines += ["", "## 6. Fields Where SYSTEM Still Wins vs B7-expanded", ""]
    if result["fields_system_still_wins"]:
        for r in result["fields_system_still_wins"]:
            lines.append(
                f"- **{r['field_id']}** ({r['category']}): "
                f"SYSTEM={r['system_f1']:.4f} vs B7={r['b7_expanded_f1']:.4f} "
                f"(Δ={r['delta_system_vs_b7']:+.4f})"
            )
    else:
        lines.append("(none)")

    # Significance summary
    lines += ["", "## 7. SYSTEM vs B7-expanded Statistical Significance", ""]
    lines += [
        "| Group | ΔF1 (mean) | 95% CI | p-value | Sig |",
        "|---|---|---|---|---|",
    ]
    for c in result["comparisons"]:
        d = c["delta_system_vs_b7"]
        ci = d["bootstrap_ci_95"]
        sig = "✓" if d["significant_at_0_05"] else "✗"
        lines.append(
            f"| {c['label']} | {d['per_entry_mean_f1']:+.4f} | "
            f"[{ci[0]:+.4f}, {ci[1]:+.4f}] | {d['p_value']:.4f} | {sig} |"
        )

    # Paper interpretation
    lines += ["", "## 8. Paper-Ready Interpretation", ""]
    merged_d = merged["delta_system_vs_b7"]
    if merged_d["significant_at_0_05"] and merged_d["per_entry_mean_f1"] > 0:
        lines += [
            "SYSTEM significantly outperforms B7-expanded (stronger single-prompt baseline).",
            "",
            f"The multi-agent pipeline achieves a mean per-entry F1 of {merged['system']['per_entry_mean_f1']:.4f} "
            f"compared to {merged['b7_expanded']['per_entry_mean_f1']:.4f} for the expanded single-prompt baseline, "
            f"a statistically significant improvement (ΔF1={merged_d['per_entry_mean_f1']:+.4f}, "
            f"paired permutation p={merged_d['p_value']:.4f}, "
            f"95% bootstrap CI [{merged_d['bootstrap_ci_95'][0]:+.4f}, {merged_d['bootstrap_ci_95'][1]:+.4f}]).",
            "",
            "This demonstrates that the pipeline advantage persists even when the single-prompt baseline "
            "is explicitly instructed to extract medium and complex fields, ruling out prompt design "
            "unfairness as an alternative explanation.",
        ]
    elif merged_d["per_entry_mean_f1"] > 0 and not merged_d["significant_at_0_05"]:
        lines += [
            "SYSTEM has higher F1 than B7-expanded, but the difference is NOT statistically significant.",
            "",
            f"ΔF1={merged_d['per_entry_mean_f1']:+.4f}, p={merged_d['p_value']:.4f}.",
            "",
            "The expanded prompt recovers much of the medium-field advantage. SYSTEM's remaining edge "
            "is concentrated on complex evidence fields where source-grounding and dual-track reconcile "
            "provide value that a single prompt cannot replicate.",
        ]
    else:
        lines += [
            "SYSTEM does NOT outperform B7-expanded on overall F1.",
            "",
            f"ΔF1={merged_d['per_entry_mean_f1']:+.4f}, p={merged_d['p_value']:.4f}.",
            "",
            "The expanded single-prompt baseline matches or exceeds the pipeline. Paper framing should "
            "shift to emphasize auditability, cross-lingual robustness, and source grounding as the "
            "pipeline's differentiators rather than aggregate F1.",
        ]

    return "\n".join(lines)


def _format_comparison_table(comparisons: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Group | N | SYS F1 | B0 F1 | B7 F1 | Δ(SYS-B7) | Δ(SYS-B0) | p(SYS-B7) | Sig |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in comparisons:
        d7 = c["delta_system_vs_b7"]
        d0 = c["delta_system_vs_b0"]
        sig = "✓" if d7["significant_at_0_05"] else "✗"
        lines.append(
            f"| {c['label']} | {c['n_entries']} | "
            f"{c['system']['f1']:.4f} | {c['b0_naive']['f1']:.4f} | {c['b7_expanded']['f1']:.4f} | "
            f"{d7['per_entry_mean_f1']:+.4f} | {d0['per_entry_mean_f1']:+.4f} | "
            f"{d7['p_value']:.4f} | {sig} |"
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Three-way comparison: B0-naive vs B7-expanded vs SYSTEM")
    parser.add_argument("--system-report", type=Path, default=None)
    parser.add_argument("--b0-report", type=Path, default=None)
    parser.add_argument("--b7-report", type=Path, default=None)
    parser.add_argument("--n-bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    sys_path = args.system_report or max(REPORTS_DIR.glob("eval_merged_final_*.json"), key=lambda p: p.stat().st_mtime)
    b0_path = args.b0_report or max(REPORTS_DIR.glob("baseline_b0_merged_*.json"), key=lambda p: p.stat().st_mtime)
    b7_path = args.b7_report or max(REPORTS_DIR.glob("baseline_b7_*.json"), key=lambda p: p.stat().st_mtime)

    sys_report = _load_report(sys_path)
    b0_report = _load_report(b0_path)
    b7_report = _load_report(b7_path)

    result = compute_three_way(sys_report, b0_report, b7_report, n_bootstrap=args.n_bootstrap, seed=args.seed)

    # Print summary
    print(f"{'Group':<30} {'SYS':>6} {'B0':>6} {'B7':>6} {'Δ(S-B7)':>8} {'p':>8} {'Sig':>5}")
    print("-" * 80)
    for c in result["comparisons"]:
        d = c["delta_system_vs_b7"]
        sig = "✓" if d["significant_at_0_05"] else "✗"
        print(
            f"{c['label']:<30} "
            f"{c['system']['f1']:>6.4f} "
            f"{c['b0_naive']['f1']:>6.4f} "
            f"{c['b7_expanded']['f1']:>6.4f} "
            f"{d['per_entry_mean_f1']:>+8.4f} "
            f"{d['p_value']:>8.4f} {sig:>5}"
        )

    if args.write:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        json_path = REPORTS_DIR / f"three_way_comparison_{timestamp}.json"
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {json_path}")

        md_path = REPORTS_DIR / f"three_way_comparison_{timestamp}.md"
        md_path.write_text(_format_markdown(result), encoding="utf-8")
        print(f"MD: {md_path}")


if __name__ == "__main__":
    main()
