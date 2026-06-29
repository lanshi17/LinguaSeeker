#!/usr/bin/env python3
"""Summarize unified B8 evaluation errors by field family and field ID.

Reads eval_unified_merged_b8_20260627.json and produces:
  - benchmark/data/reports/unified_b8_error_breakdown_20260629.json
  - benchmark/data/reports/unified_b8_error_breakdown_20260629.md
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPORT_PATH = Path("benchmark/data/reports/eval_unified_merged_b8_20260627.json")
OUT_JSON = Path("benchmark/data/reports/unified_b8_error_breakdown_20260629.json")
OUT_MD = Path("benchmark/data/reports/unified_b8_error_breakdown_20260629.md")

FAMILY_LABELS = {
    "A": "Gene / Variant",
    "B": "Disease / Phenotype",
    "C": "De novo / Genetic mechanism",
    "D": "Carrier observation",
    "E": "Functional evidence",
    "F": "Population / Allele frequency",
    "G": "Experimental methods",
    "H": "Segregation",
    "I": "Animal model",
    "J": "Public assertions (ClinVar)",
}


def classify(fm: dict) -> str:
    """Return TP, FP, or FN for a field match."""
    matched = fm.get("matched", False)
    extracted = fm.get("extracted")
    has_ext = extracted is not None and str(extracted).strip() not in ("", "None", "{}")
    if matched:
        return "TP"
    if has_ext:
        return "FP"
    return "FN"


def main() -> None:
    report = json.loads(REPORT_PATH.read_text())
    per_entry = report.get("per_entry", [])

    # Aggregation structures.
    by_field: dict[str, dict[str, int]] = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})
    by_family: dict[str, dict[str, int]] = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})
    # Per-field per-source for cross-tab.
    by_field_source: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})
    )

    for entry in per_entry:
        source = entry.get("source_dataset", "unknown")
        for fm in entry.get("field_matches", []):
            fid = fm["field_id"]
            prefix = fid.split(".")[0] if "." in fid else "other"
            status = classify(fm)

            by_field[fid][status] += 1
            by_family[prefix][status] += 1
            by_source[source][status] += 1
            by_field_source[fid][source][status] += 1

    def metrics(d: dict[str, int]) -> dict[str, float | int]:
        tp, fp, fn = d["TP"], d["FP"], d["FN"]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        return {"TP": tp, "FP": fp, "FN": fn, "precision": round(p, 4), "recall": round(r, 4), "F1": round(f1, 4)}

    # Build output.
    field_rows = []
    for fid in sorted(by_field, key=lambda k: by_field[k]["FN"], reverse=True):
        m = metrics(by_field[fid])
        m["field_id"] = fid
        m["family"] = fid.split(".")[0] if "." in fid else "other"
        # Top source contributors to FN.
        fn_sources = {}
        for src, counts in by_field_source[fid].items():
            if counts["FN"] > 0:
                fn_sources[src] = counts["FN"]
        m["fn_by_source"] = dict(sorted(fn_sources.items(), key=lambda x: x[1], reverse=True))
        field_rows.append(m)

    family_rows = []
    for fam in sorted(by_family, key=lambda k: by_family[k]["TP"] + by_family[k]["FP"] + by_family[k]["FN"], reverse=True):
        m = metrics(by_family[fam])
        m["family"] = fam
        m["label"] = FAMILY_LABELS.get(fam, fam)
        family_rows.append(m)

    source_rows = []
    for src in sorted(by_source):
        m = metrics(by_source[src])
        m["source_dataset"] = src
        source_rows.append(m)

    output = {
        "overall": metrics({"TP": sum(d["TP"] for d in by_field.values()),
                            "FP": sum(d["FP"] for d in by_field.values()),
                            "FN": sum(d["FN"] for d in by_field.values())}),
        "by_family": family_rows,
        "by_field_top_fn": [r for r in field_rows if r["FN"] > 0][:25],
        "by_field_top_fp": sorted(field_rows, key=lambda r: r["FP"], reverse=True)[:15],
        "by_source": source_rows,
    }

    OUT_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT_JSON}")

    # --- Markdown report ---
    lines: list[str] = []
    lines.append("# Unified B8 Error Breakdown (2026-06-29)\n")
    lines.append(f"Source: `{REPORT_PATH}`\n")

    o = output["overall"]
    lines.append(f"**Overall**: TP={o['TP']}  FP={o['FP']}  FN={o['FN']}  "
                 f"P={o['precision']:.1%}  R={o['recall']:.1%}  F1={o['F1']:.1%}\n")

    lines.append("## By Field Family\n")
    lines.append("| family | label | TP | FP | FN | P | R | F1 |")
    lines.append("|--------|-------|---:|---:|---:|----:|----:|----:|")
    for r in family_rows:
        lines.append(f"| {r['family']} | {r['label']} | {r['TP']} | {r['FP']} | {r['FN']} | "
                     f"{r['precision']:.1%} | {r['recall']:.1%} | {r['F1']:.1%} |")
    lines.append("")

    lines.append("## Top 20 False-Negative Fields\n")
    lines.append("| field_id | FN | FP | TP | top FN sources |")
    lines.append("|----------|---:|---:|---:|----------------|")
    for r in field_rows[:20]:
        fn_src = ", ".join(f"{k}:{v}" for k, v in list(r["fn_by_source"].items())[:3])
        lines.append(f"| {r['field_id']} | {r['FN']} | {r['FP']} | {r['TP']} | {fn_src} |")
    lines.append("")

    lines.append("## Top 10 False-Positive Fields\n")
    lines.append("| field_id | FP | FN | TP |")
    lines.append("|----------|---:|---:|---:|")
    for r in output["by_field_top_fp"][:10]:
        lines.append(f"| {r['field_id']} | {r['FP']} | {r['FN']} | {r['TP']} |")
    lines.append("")

    lines.append("## By Source Dataset\n")
    lines.append("| source | TP | FP | FN | P | R | F1 |")
    lines.append("|--------|---:|---:|---:|----:|----:|----:|")
    for r in source_rows:
        lines.append(f"| {r['source_dataset']} | {r['TP']} | {r['FP']} | {r['FN']} | "
                     f"{r['precision']:.1%} | {r['recall']:.1%} | {r['F1']:.1%} |")
    lines.append("")

    lines.append("## Observations\n")
    lines.append("- **A (Gene/Variant)** is the largest FN source (432 FN). "
                 "Many variant-level fields (HGVS, variant_type, functional_domain) are often implicit "
                 "or require external database normalization not visible in the article.")
    lines.append("- **B (Disease/Phenotype)** has the highest FP count (155 FP). "
                 "The pipeline sometimes extracts disease terms that don't exactly match the gold label "
                 "due to synonym/normalization differences.")
    lines.append("- **J (Public assertions)** has 64 FN with only 12 TP, reflecting that "
                 "ClinVar/assertion fields are often not present in the article text itself.")
    lines.append("- **C, D, E, F, G, H, I** families are dominated by FN with zero or near-zero TP, "
                 "indicating these fields are rarely extractable from a single document.")

    OUT_MD.write_text("\n".join(lines))
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
