"""Paired statistical tests for N=50 comparison and ablation experiment.

Implements the tests specified in the design doc:

- McNemar's test for entry-level success/failure
- Paired t-test plus Wilcoxon signed-rank sensitivity check for per-entry F1
- Clustered bootstrap by entry for field-level binary correctness
- 95% confidence intervals for all effect estimates

Usage::

    cd backend && uv run python -m benchmark.analysis.n50_comparison.paired_tests \
        --reference benchmark/data/reports/n50/c2_full_broad_<ts>.json \
        --comparison benchmark/data/reports/n50/c1_catalog_<ts>.json \
        --output benchmark/data/reports/n50/paired_tests.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats as sp_stats


def _load_report(path: Path) -> dict[str, Any]:
    """Load a condition report JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _per_entry_f1(report: dict[str, Any]) -> dict[str, float]:
    """Compute per-entry F1 from a condition report.

    Returns a dict mapping entry_id to F1 score.
    F1 per entry = 2*TP / (2*TP + FP + FN) where TP/FP/FN are field-level.
    """
    result: dict[str, float] = {}
    for pe in report.get("per_entry", []):
        entry_id = pe["entry_id"]
        matches = pe.get("field_matches", [])
        tp = sum(1 for f in matches if f.get("matched"))
        fp = sum(1 for f in matches if not f.get("matched") and f.get("extracted"))
        fn = sum(1 for f in matches if not f.get("matched") and not f.get("extracted"))
        denom = 2 * tp + fp + fn
        f1 = (2 * tp / denom) if denom > 0 else 0.0
        result[entry_id] = f1
    return result


def _per_entry_success(report: dict[str, Any]) -> dict[str, bool]:
    """Compute per-entry success/failure (completion + at least one TP)."""
    result: dict[str, bool] = {}
    for pe in report.get("per_entry", []):
        entry_id = pe["entry_id"]
        completed = pe.get("pipeline_status") == "completed"
        has_tp = any(f.get("matched") for f in pe.get("field_matches", []))
        result[entry_id] = completed and has_tp
    return result


def _per_field_correctness(report: dict[str, Any]) -> dict[str, dict[str, bool]]:
    """Compute per-entry per-field binary correctness.

    Returns dict[entry_id][field_id] = bool.
    """
    result: dict[str, dict[str, bool]] = {}
    for pe in report.get("per_entry", []):
        entry_id = pe["entry_id"]
        result[entry_id] = {}
        for f in pe.get("field_matches", []):
            result[entry_id][f["field_id"]] = f.get("matched", False)
    return result


def mcnemar_test(
    ref_success: dict[str, bool],
    cmp_success: dict[str, bool],
) -> dict[str, Any]:
    """McNemar's test for paired success/failure.

    Builds the 2x2 contingency table:
    - b = ref succeeds, cmp fails
    - c = ref fails, cmp succeeds

    Uses exact binomial test when b+c < 25, chi-square otherwise.
    """
    common_ids = set(ref_success.keys()) & set(cmp_success.keys())
    b = sum(1 for eid in common_ids if ref_success[eid] and not cmp_success[eid])
    c = sum(1 for eid in common_ids if not ref_success[eid] and cmp_success[eid])
    n = b + c

    if n == 0:
        return {
            "test": "mcnemar",
            "b": b, "c": c, "n_discordant": n,
            "statistic": 0.0, "p_value": 1.0,
            "method": "no_discordant_pairs",
        }

    if n < 25:
        # Exact binomial test
        p_value = float(sp_stats.binomtest(min(b, c), n, 0.5).pvalue)
        method = "exact_binomial"
        statistic = float(min(b, c))
    else:
        # Chi-square with continuity correction
        statistic = float((abs(b - c) - 1) ** 2 / n)
        p_value = float(sp_stats.chi2.sf(statistic, df=1))
        method = "chi_square_continuity"

    return {
        "test": "mcnemar",
        "b": b, "c": c, "n_discordant": n,
        "statistic": round(statistic, 4),
        "p_value": round(p_value, 6),
        "method": method,
    }


def paired_t_test(
    ref_f1: dict[str, float],
    cmp_f1: dict[str, float],
) -> dict[str, Any]:
    """Paired t-test for per-entry F1 differences."""
    common_ids = sorted(set(ref_f1.keys()) & set(cmp_f1.keys()))
    diffs = [ref_f1[eid] - cmp_f1[eid] for eid in common_ids]
    diffs_arr = np.array(diffs)

    if len(diffs) < 2:
        return {
            "test": "paired_t",
            "n_pairs": len(diffs),
            "mean_diff": 0.0, "std_diff": 0.0,
            "t_statistic": 0.0, "p_value": 1.0,
            "ci_95": [0.0, 0.0],
        }

    t_stat, p_value = sp_stats.ttest_rel(diffs_arr, np.zeros_like(diffs_arr))
    mean_diff = float(np.mean(diffs_arr))
    std_diff = float(np.std(diffs_arr, ddof=1))
    sem = std_diff / np.sqrt(len(diffs))
    ci_95 = [mean_diff - 1.96 * sem, mean_diff + 1.96 * sem]

    return {
        "test": "paired_t",
        "n_pairs": len(diffs),
        "mean_diff": round(mean_diff, 4),
        "std_diff": round(std_diff, 4),
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_value), 6),
        "ci_95": [round(ci_95[0], 4), round(ci_95[1], 4)],
    }


def wilcoxon_test(
    ref_f1: dict[str, float],
    cmp_f1: dict[str, float],
) -> dict[str, Any]:
    """Wilcoxon signed-rank test as a sensitivity check."""
    common_ids = sorted(set(ref_f1.keys()) & set(cmp_f1.keys()))
    diffs = [ref_f1[eid] - cmp_f1[eid] for eid in common_ids]
    nonzero_diffs = [d for d in diffs if d != 0]

    if len(nonzero_diffs) < 1:
        return {
            "test": "wilcoxon",
            "n_nonzero": 0,
            "statistic": 0.0, "p_value": 1.0,
        }

    try:
        stat, p_value = sp_stats.wilcoxon(
            np.array(diffs),
            zero_method="wilcox",
            alternative="two-sided",
        )
    except ValueError:
        return {
            "test": "wilcoxon",
            "n_nonzero": len(nonzero_diffs),
            "statistic": 0.0, "p_value": 1.0,
        }

    return {
        "test": "wilcoxon",
        "n_nonzero": len(nonzero_diffs),
        "statistic": round(float(stat), 4),
        "p_value": round(float(p_value), 6),
    }


def clustered_bootstrap(
    ref_fields: dict[str, dict[str, bool]],
    cmp_fields: dict[str, dict[str, bool]],
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    """Clustered bootstrap by entry for field-level binary correctness.

    Resamples entries (clusters) with replacement, then computes the
    difference in accuracy across all fields within the resampled entries.
    Returns the 95% CI for the accuracy difference.
    """
    rng = np.random.default_rng(seed)
    common_ids = sorted(set(ref_fields.keys()) & set(cmp_fields.keys()))
    n_entries = len(common_ids)

    if n_entries == 0:
        return {
            "test": "clustered_bootstrap",
            "n_entries": 0,
            "mean_diff": 0.0,
            "ci_95": [0.0, 0.0],
            "n_bootstrap": n_bootstrap,
        }

    # Precompute per-entry accuracy
    ref_accs = []
    cmp_accs = []
    for eid in common_ids:
        ref_vals = list(ref_fields[eid].values())
        cmp_vals = list(cmp_fields[eid].values())
        ref_accs.append(np.mean(ref_vals) if ref_vals else 0.0)
        cmp_accs.append(np.mean(cmp_vals) if cmp_vals else 0.0)

    ref_accs = np.array(ref_accs)
    cmp_accs = np.array(cmp_accs)

    boot_diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n_entries, size=n_entries)
        boot_diffs[i] = np.mean(ref_accs[idx]) - np.mean(cmp_accs[idx])

    ci_95 = [float(np.percentile(boot_diffs, 2.5)), float(np.percentile(boot_diffs, 97.5))]
    mean_diff = float(np.mean(boot_diffs))

    return {
        "test": "clustered_bootstrap",
        "n_entries": n_entries,
        "mean_diff": round(mean_diff, 4),
        "ci_95": [round(ci_95[0], 4), round(ci_95[1], 4)],
        "n_bootstrap": n_bootstrap,
    }


def run_all_paired_tests(
    ref_report: dict[str, Any],
    cmp_report: dict[str, Any],
) -> dict[str, Any]:
    """Run all paired tests between a reference and comparison condition."""
    ref_f1 = _per_entry_f1(ref_report)
    cmp_f1 = _per_entry_f1(cmp_report)
    ref_success = _per_entry_success(ref_report)
    cmp_success = _per_entry_success(cmp_report)
    ref_fields = _per_field_correctness(ref_report)
    cmp_fields = _per_field_correctness(cmp_report)

    return {
        "reference": ref_report.get("config", {}).get("condition_id", "unknown"),
        "comparison": cmp_report.get("config", {}).get("condition_id", "unknown"),
        "mcnemar": mcnemar_test(ref_success, cmp_success),
        "paired_t": paired_t_test(ref_f1, cmp_f1),
        "wilcoxon": wilcoxon_test(ref_f1, cmp_f1),
        "clustered_bootstrap": clustered_bootstrap(ref_fields, cmp_fields),
        "practical_effect": {
            "mean_f1_diff": paired_t_test(ref_f1, cmp_f1)["mean_diff"],
            "ci_95_f1_diff": paired_t_test(ref_f1, cmp_f1)["ci_95"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paired statistical tests for N=50 comparison",
    )
    parser.add_argument("--reference", type=Path, required=True, help="Reference condition report")
    parser.add_argument("--comparison", type=Path, required=True, help="Comparison condition report")
    parser.add_argument("--output", type=Path, default=None, help="Output file")
    args = parser.parse_args()

    ref = _load_report(args.reference)
    cmp = _load_report(args.comparison)
    results = run_all_paired_tests(ref, cmp)

    output_path = args.output or args.comparison.parent / f"paired_{results['reference']}_vs_{results['comparison']}.json"
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Paired tests written to: {output_path}")
    for test_name, test_result in results.items():
        if isinstance(test_result, dict) and "p_value" in test_result:
            print(f"  {test_name}: p={test_result['p_value']}")


if __name__ == "__main__":
    main()
