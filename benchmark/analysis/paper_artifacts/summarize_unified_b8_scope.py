#!/usr/bin/env python3
"""Summarize scope sensitivity for the unified 150-entry evaluation.

The script derives paper-ready scope rows from the frozen merged benchmark
report and checks that the all-field row exactly matches the report-level
overall counts.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

REPORT_PATH = Path("benchmark/data/reports/eval_unified_merged_b8_20260627.json")
OUT_JSON = Path("benchmark/data/reports/unified_b8_scope_sensitivity_20260629.json")
OUT_MD = Path("benchmark/data/reports/unified_b8_scope_sensitivity_20260629.md")

FAMILY_LABELS = {
    "A": "Gene / Variant",
    "B": "Disease / Phenotype",
    "C": "De novo / Mechanism",
    "D": "Allele frequency / Carrier observation",
    "E": "Conservation / Computational evidence",
    "F": "Functional evidence",
    "G": "Experimental methods",
    "H": "Contradiction / Alternative cause",
    "I": "Gene function / Model evidence",
    "J": "Public assertions",
}


@dataclass(frozen=True)
class CountRow:
    """Paper-facing count and metric row."""

    label: str
    included_families: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    interpretation: str


def has_extracted_value(field_match: object) -> bool:
    """Return whether a field match has a non-empty extracted value."""
    if not isinstance(field_match, dict):
        return False
    extracted = field_match.get("extracted")
    return extracted is not None and str(extracted).strip() not in ("", "None", "{}")


def compute_metrics(label: str, included_families: list[str], counts_by_family: dict[str, dict[str, int]], interpretation: str) -> CountRow:
    """Compute TP/FP/FN and P/R/F1 for a family subset."""
    tp = sum(counts_by_family[family]["TP"] for family in included_families)
    fp = sum(counts_by_family[family]["FP"] for family in included_families)
    fn = sum(counts_by_family[family]["FN"] for family in included_families)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return CountRow(
        label=label,
        included_families="+".join(included_families),
        tp=tp,
        fp=fp,
        fn=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        interpretation=interpretation,
    )


def main() -> None:
    report = json.loads(REPORT_PATH.read_text())
    per_entry = report["per_entry"]
    counts_by_family: dict[str, dict[str, int]] = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})

    for entry in per_entry:
        for field_match in entry.get("field_matches", []):
            family = str(field_match["field_id"]).split(".", maxsplit=1)[0]
            extra_count = len(field_match.get("extra_found_values") or [])
            if field_match.get("matched"):
                counts_by_family[family]["TP"] += 1
                counts_by_family[family]["FP"] += extra_count
            elif has_extracted_value(field_match):
                counts_by_family[family]["FP"] += 1 + extra_count
            else:
                counts_by_family[family]["FN"] += 1

    families = sorted(counts_by_family)
    rows = [
        compute_metrics(
            "All eligible fields",
            families,
            counts_by_family,
            "Primary 150-entry production benchmark.",
        ),
        compute_metrics(
            "Covered field families",
            [family for family in families if counts_by_family[family]["TP"] > 0],
            counts_by_family,
            "Excludes D--I families with zero true positives in this run.",
        ),
        compute_metrics(
            "Core article-local families",
            ["A", "B", "J"],
            counts_by_family,
            "Gene/variant, disease/phenotype, and public assertion fields.",
        ),
        compute_metrics(
            "Gene and phenotype fields",
            ["A", "B"],
            counts_by_family,
            "Most directly article-local gene/variant and phenotype evidence.",
        ),
    ]

    overall = report["aggregates"]["overall"]
    all_row = rows[0]
    expected = (
        overall["true_positives"],
        overall["false_positives"],
        overall["false_negatives"],
    )
    actual = (all_row.tp, all_row.fp, all_row.fn)
    if actual != expected:
        raise RuntimeError(f"Derived overall counts {actual} do not match report counts {expected}.")

    output = {
        "source_report": str(REPORT_PATH),
        "family_counts": {
            family: {"label": FAMILY_LABELS.get(family, family), **counts}
            for family, counts in sorted(counts_by_family.items())
        },
        "scope_rows": [asdict(row) for row in rows],
    }
    OUT_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    lines = [
        "# Unified B8 Scope Sensitivity (2026-06-29)",
        "",
        f"Source: `{REPORT_PATH}`",
        "",
        "## Scope Rows",
        "",
        "| scope | families | TP | FP | FN | precision | recall | F1 | interpretation |",
        "|-------|----------|---:|---:|---:|----------:|-------:|---:|----------------|",
    ]
    for row in rows:
        lines.append(
            f"| {row.label} | {row.included_families} | {row.tp} | {row.fp} | {row.fn} | "
            f"{row.precision:.3f} | {row.recall:.3f} | {row.f1:.3f} | {row.interpretation} |"
        )
    lines.extend(
        [
            "",
            "## Family Counts",
            "",
            "| family | label | TP | FP | FN |",
            "|--------|-------|---:|---:|---:|",
        ]
    )
    for family, counts in sorted(counts_by_family.items()):
        lines.append(
            f"| {family} | {FAMILY_LABELS.get(family, family)} | "
            f"{counts['TP']} | {counts['FP']} | {counts['FN']} |"
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines))
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
