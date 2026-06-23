"""Update BIBM result package with B7-expanded baseline results.

Reads the existing result package, B7-expanded report, and three-way
comparison, then generates an updated package with stronger baseline analysis.

Usage:
    python -m benchmark.analysis.paper_artifacts.update_result_package_with_expanded_baseline [--write]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

REPORTS_DIR = Path("benchmark/data/reports")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest(pattern: str) -> Path:
    candidates = list(REPORTS_DIR.glob(pattern))
    if not candidates:
        raise FileNotFoundError(f"No {pattern} reports found")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def update_package(
    existing_package: dict[str, Any],
    three_way: dict[str, Any],
) -> dict[str, Any]:
    """Update the result package with B7-expanded baseline data."""
    pkg = dict(existing_package)

    merged = next(c for c in three_way["comparisons"] if c["label"] == "merged_73")
    rett = next(c for c in three_way["comparisons"] if c["label"] == "rett_53")
    park = next(c for c in three_way["comparisons"] if c["label"] == "parkinson_20")

    d7 = merged["delta_system_vs_b7"]
    d7_rett = rett["delta_system_vs_b7"]
    d7_park = park["delta_system_vs_b7"]

    # Update source reports
    pkg["source_reports"] = {
        **pkg.get("source_reports", {}),
        "three_way_comparison": str(_latest("three_way_comparison_*.json")),
        "b7_expanded_baseline": str(_latest("baseline_b7_*.json")),
    }

    # Add section 3b: stronger baseline comparison
    pkg["section_3b_stronger_baseline_comparison"] = {
        "description": "SYSTEM vs B0-naive vs B7-expanded (stronger single-prompt baseline)",
        "b7_expanded_metadata": {
            "model_baseline_id": "B7_GPT5_EXPANDED_PROMPT",
            "model_baseline_name": "GPT-5 expanded single-prompt evidence extraction",
            "model": "gpt-5-2025-08-07",
            "provider_family": "openai",
            "prompt_fields": "simple + medium + complex (17 fields)",
            "constraints": "single-pass, no pipeline modules, no dual-track reconcile, no source-grounding repair",
        },
        "merged_73": {
            "system": merged["system"],
            "b0_naive": merged["b0_naive"],
            "b7_expanded": merged["b7_expanded"],
            "delta_system_vs_b7": d7,
            "delta_system_vs_b0": merged["delta_system_vs_b0"],
        },
        "per_dataset": {
            "rett": {
                "system_f1": rett["system"]["f1"],
                "b7_f1": rett["b7_expanded"]["f1"],
                "delta": d7_rett["per_entry_mean_f1"],
                "p_value": d7_rett["p_value"],
                "significant": d7_rett["significant_at_0_05"],
            },
            "parkinson": {
                "system_f1": park["system"]["f1"],
                "b7_f1": park["b7_expanded"]["f1"],
                "delta": d7_park["per_entry_mean_f1"],
                "p_value": d7_park["p_value"],
                "significant": d7_park["significant_at_0_05"],
            },
        },
        "per_difficulty": {
            c["label"].replace("merged_", ""): {
                "system_f1": c["system"]["f1"],
                "b0_f1": c["b0_naive"]["f1"],
                "b7_f1": c["b7_expanded"]["f1"],
                "delta_system_vs_b7": c["delta_system_vs_b7"]["per_entry_mean_f1"],
                "p_value": c["delta_system_vs_b7"]["p_value"],
            }
            for c in three_way["comparisons"]
            if c["label"].startswith("merged_") and c["label"] != "merged_73"
        },
        "fields_where_b7_closes_gap": three_way["fields_b7_closes_gap"],
        "fields_where_system_still_wins": three_way["fields_system_still_wins"],
    }

    # Update claims based on B7-expanded results
    pkg["section_9_claims_supported"] = _update_claims_supported(pkg, d7, merged)
    pkg["section_10_claims_to_avoid"] = _update_claims_to_avoid(pkg, d7, merged)

    # Update readiness
    pkg["section_13_bibm_readiness"] = _update_readiness(pkg, d7, merged)

    # Update package metadata
    pkg["package_id"] = f"bibm_main_paper_result_package_{time.strftime('%Y%m%d_%H%M%S')}"
    pkg["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    pkg["expanded_baseline_note"] = (
        "B7-expanded baseline added as rebuttal-ready supplementary experiment. "
        "This stronger single-prompt baseline explicitly requests all simple, medium, and complex fields, "
        "addressing the reviewer risk that SYSTEM's advantage was due to B0's weak prompt."
    )

    return pkg


def _update_claims_supported(
    pkg: dict[str, Any],
    d7: dict[str, Any],
    merged: dict[str, Any],
) -> list[str]:
    claims = list(pkg.get("section_9_claims_supported", []))

    if d7["significant_at_0_05"] and d7["per_entry_mean_f1"] > 0:
        claims.append(
            f"SYSTEM significantly outperforms B7-expanded (stronger single-prompt baseline) on merged 73 entries "
            f"(ΔF1={d7['per_entry_mean_f1']:+.4f}, p={d7['p_value']:.4f}, "
            f"95% CI [{d7['bootstrap_ci_95'][0]:+.4f}, {d7['bootstrap_ci_95'][1]:+.4f}]). "
            f"This rules out prompt design unfairness as an alternative explanation."
        )
    elif d7["per_entry_mean_f1"] > 0:
        claims.append(
            f"SYSTEM has higher F1 than B7-expanded but the difference is not statistically significant "
            f"(ΔF1={d7['per_entry_mean_f1']:+.4f}, p={d7['p_value']:.4f}). "
            f"The expanded prompt partially closes the gap on medium fields."
        )

    return claims


def _update_claims_to_avoid(
    pkg: dict[str, Any],
    d7: dict[str, Any],
    merged: dict[str, Any],
) -> list[str]:
    claims = list(pkg.get("section_10_claims_to_avoid", []))

    if not d7["significant_at_0_05"]:
        claims.append(
            "Do not claim SYSTEM significantly outperforms the stronger B7-expanded baseline. "
            "The expanded prompt closes much of the medium-field gap."
        )
    if d7["per_entry_mean_f1"] <= 0:
        claims.append(
            "Do not claim SYSTEM outperforms B7-expanded on aggregate F1. "
            "Shift framing to auditability, cross-lingual robustness, and source grounding."
        )

    return claims


def _update_readiness(
    pkg: dict[str, Any],
    d7: dict[str, Any],
    merged: dict[str, Any],
) -> dict[str, Any]:
    readiness = dict(pkg.get("section_13_bibm_readiness", {}))

    if d7["significant_at_0_05"] and d7["per_entry_mean_f1"] > 0:
        readiness["ready_for_main_submission"] = "ready"
        readiness["confidence_level"] = "high"
        readiness["strongest_selling_point"] = (
            f"SYSTEM significantly outperforms both B0-naive and B7-expanded (stronger single-prompt baseline). "
            f"B7-expanded ΔF1={d7['per_entry_mean_f1']:+.4f}, p={d7['p_value']:.4f}. "
            f"Pipeline advantage persists under stronger prompt, ruling out prompt design unfairness."
        )
        readiness["biggest_reviewer_risk"] = (
            "Remaining risk: B7-expanded may still be improved with better prompt engineering, "
            "few-shot examples, or chain-of-thought. The auditability and cross-lingual robustness "
            "claims require additional supporting experiments."
        )
    elif d7["per_entry_mean_f1"] > 0 and not d7["significant_at_0_05"]:
        readiness["ready_for_main_submission"] = "borderline"
        readiness["confidence_level"] = "moderate"
        readiness["strongest_selling_point"] = (
            f"SYSTEM has higher F1 than B7-expanded (ΔF1={d7['per_entry_mean_f1']:+.4f}) but not significant. "
            f"Pipeline advantage is concentrated on complex evidence fields where source-grounding matters."
        )
        readiness["biggest_reviewer_risk"] = (
            "B7-expanded prompt closes much of the medium-field gap. SYSTEM's advantage may not survive "
            "a more sophisticated prompt with few-shot examples or chain-of-thought reasoning."
        )
    else:
        readiness["ready_for_main_submission"] = "borderline"
        readiness["confidence_level"] = "low"
        readiness["strongest_selling_point"] = (
            "Pipeline provides structured audit trails, source grounding, and cross-lingual robustness "
            "that single-prompt baselines cannot match, even when aggregate F1 is comparable."
        )
        readiness["biggest_reviewer_risk"] = (
            "B7-expanded matches or exceeds SYSTEM on aggregate F1. Paper must shift emphasis from "
            "F1 improvement to methodology benefits (auditability, cross-lingual, source grounding)."
        )

    readiness["expanded_baseline_mitigation"] = (
        "B7-expanded baseline explicitly requests all simple, medium, and complex fields in a single prompt, "
        "addressing the reviewer risk that SYSTEM's advantage was due to B0's weak prompt. "
        f"Result: ΔF1={d7['per_entry_mean_f1']:+.4f}, p={d7['p_value']:.4f}."
    )

    return readiness


def main() -> None:
    parser = argparse.ArgumentParser(description="Update result package with B7-expanded baseline")
    parser.add_argument("--package", type=Path, default=None)
    parser.add_argument("--three-way", type=Path, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    pkg_path = args.package or _latest("bibm_main_paper_result_package_*.json")
    three_way_path = args.three_way or _latest("three_way_comparison_*.json")

    pkg = _load_json(pkg_path)
    three_way = _load_json(three_way_path)

    updated = update_package(pkg, three_way)

    # Print summary
    d7 = next(c for c in three_way["comparisons"] if c["label"] == "merged_73")["delta_system_vs_b7"]
    print(f"SYSTEM vs B7-expanded: ΔF1={d7['per_entry_mean_f1']:+.4f}, p={d7['p_value']:.4f}")
    print(f"Ready: {updated['section_13_bibm_readiness']['ready_for_main_submission']}")
    print(f"Confidence: {updated['section_13_bibm_readiness']['confidence_level']}")

    if args.write:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        json_path = REPORTS_DIR / f"bibm_main_paper_result_package_{timestamp}.json"
        json_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {json_path}")

        md_path = REPORTS_DIR / f"bibm_main_paper_result_package_{timestamp}.md"
        md_path.write_text(_format_markdown(updated, three_way), encoding="utf-8")
        print(f"MD: {md_path}")


def _format_markdown(pkg: dict[str, Any], three_way: dict[str, Any]) -> str:
    merged = next(c for c in three_way["comparisons"] if c["label"] == "merged_73")
    d7 = merged["delta_system_vs_b7"]
    d0 = merged["delta_system_vs_b0"]

    lines = [
        "# BIBM Main Paper Result Package (Updated with B7-expanded baseline)",
        "",
        f"Generated: {pkg['timestamp']}",
        "",
        "## 1. Three-Way Baseline Comparison (Merged 73 entries)",
        "",
        "| System | P | R | F1 | per-entry mean F1 |",
        "|---|---|---|---|---|",
        f"| SYSTEM | {merged['system']['precision']:.4f} | {merged['system']['recall']:.4f} | {merged['system']['f1']:.4f} | {merged['system']['per_entry_mean_f1']:.4f} |",
        f"| B0-naive | {merged['b0_naive']['precision']:.4f} | {merged['b0_naive']['recall']:.4f} | {merged['b0_naive']['f1']:.4f} | {merged['b0_naive']['per_entry_mean_f1']:.4f} |",
        f"| B7-expanded | {merged['b7_expanded']['precision']:.4f} | {merged['b7_expanded']['recall']:.4f} | {merged['b7_expanded']['f1']:.4f} | {merged['b7_expanded']['per_entry_mean_f1']:.4f} |",
        "",
        f"**SYSTEM vs B0-naive**: ΔF1={d0['per_entry_mean_f1']:+.4f}",
        f"**SYSTEM vs B7-expanded**: ΔF1={d7['per_entry_mean_f1']:+.4f}, p={d7['p_value']:.4f}, "
        f"95% CI [{d7['bootstrap_ci_95'][0]:+.4f}, {d7['bootstrap_ci_95'][1]:+.4f}]",
        f"**Significant at α=0.05**: {'Yes' if d7['significant_at_0_05'] else 'No'}",
        "",
        "## 2. Per-Dataset (SYSTEM vs B7-expanded)",
        "",
        "| Dataset | SYSTEM F1 | B7 F1 | ΔF1 | p-value | Sig |",
        "|---|---|---|---|---|---|",
    ]

    for c in three_way["comparisons"]:
        if c["label"] not in ("rett_53", "parkinson_20"):
            continue
        d = c["delta_system_vs_b7"]
        sig = "✓" if d["significant_at_0_05"] else "✗"
        lines.append(
            f"| {c['label']} | {c['system']['f1']:.4f} | {c['b7_expanded']['f1']:.4f} | "
            f"{d['per_entry_mean_f1']:+.4f} | {d['p_value']:.4f} | {sig} |"
        )

    lines += [
        "",
        "## 3. Per-Difficulty (SYSTEM vs B7-expanded)",
        "",
        "| Category | SYS F1 | B0 F1 | B7 F1 | Δ(SYS-B7) | p |",
        "|---|---|---|---|---|---|",
    ]

    for c in three_way["comparisons"]:
        if not c["label"].startswith("merged_") or c["label"] == "merged_73":
            continue
        cat = c["label"].replace("merged_", "")
        d = c["delta_system_vs_b7"]
        lines.append(
            f"| {cat} | {c['system']['f1']:.4f} | {c['b0_naive']['f1']:.4f} | "
            f"{c['b7_expanded']['f1']:.4f} | {d['per_entry_mean_f1']:+.4f} | {d['p_value']:.4f} |"
        )

    # Fields where B7 closes gap
    lines += ["", "## 4. Fields Where B7-expanded Closes Gap vs B0-naive", ""]
    gap_fields = three_way.get("fields_b7_closes_gap", [])
    if gap_fields:
        for r in gap_fields[:10]:
            lines.append(
                f"- **{r['field_id']}** ({r['category']}): "
                f"B0={r['b0_naive_f1']:.4f} → B7={r['b7_expanded_f1']:.4f}"
            )
    else:
        lines.append("(none)")

    # Fields where SYSTEM still wins
    lines += ["", "## 5. Fields Where SYSTEM Still Wins vs B7-expanded", ""]
    win_fields = three_way.get("fields_system_still_wins", [])
    if win_fields:
        for r in win_fields[:10]:
            lines.append(
                f"- **{r['field_id']}** ({r['category']}): "
                f"SYS={r['system_f1']:.4f} vs B7={r['b7_expanded_f1']:.4f} (Δ={r['delta_system_vs_b7']:+.4f})"
            )
    else:
        lines.append("(none)")

    # Claims
    lines += ["", "## 6. Updated Claims", ""]
    lines.append("### Strongest Claims")
    for claim in pkg.get("section_9_claims_supported", []):
        lines.append(f"- {claim}")
    lines.append("")
    lines.append("### Claims to Avoid")
    for claim in pkg.get("section_10_claims_to_avoid", []):
        lines.append(f"- {claim}")

    # Readiness
    readiness = pkg.get("section_13_bibm_readiness", {})
    lines += [
        "",
        "## 7. BIBM Readiness",
        "",
        f"- **Ready for main submission**: {readiness.get('ready_for_main_submission', 'unknown')}",
        f"- **Confidence**: {readiness.get('confidence_level', 'unknown')}",
        f"- **Strongest selling point**: {readiness.get('strongest_selling_point', '')}",
        f"- **Biggest reviewer risk**: {readiness.get('biggest_reviewer_risk', '')}",
        f"- **Expanded baseline mitigation**: {readiness.get('expanded_baseline_mitigation', '')}",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    main()
