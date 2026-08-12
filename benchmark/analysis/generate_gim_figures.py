#!/usr/bin/env python3
"""Generate GIM paper figures from multilingual contribution report.

Figures:
  F1: Paired bar chart — per-entry EN-only vs Combined evidence items
  F2: Field-level benefit heatmap — which ACMG fields gain from Chinese track
  F3: Evidence gain distribution (histogram/box)
  F4: By-field count of evidence items (grouped)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPORT = Path(__file__).resolve().parents[2] / "benchmark" / "data" / "reports" / "nar_ablation" / "multilingual_contribution_report.json"
OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "nar-web-server" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Color palette (NAR-style, white bg, blue family)
EN_COLOR = "#4C72B0"     # blue
ZH_COLOR = "#DD8452"     # orange
COMBINED_COLOR = "#55A868"  # green
GAIN_COLOR = "#C44E52"   # red


def load_report() -> dict:
    with open(REPORT) as f:
        return json.load(f)


def fig1_paired_bar(report: dict) -> None:
    """F1: Per-entry paired bar chart EN vs Combined."""
    entries = report["per_entry"]
    entries.sort(key=lambda e: e["entry_id"])

    entry_ids = [e["entry_id"] for e in entries]
    en_vals = [e["en_found_items"] for e in entries]
    combined_vals = [e["combined_unique_items"] for e in entries]
    gains = [e["multilingual_gain"] for e in entries]

    valid = [e for e in entries if e["en_found_items"] > 0]
    avg_en = np.mean([e["en_found_items"] for e in valid])
    avg_combo = np.mean([e["combined_unique_items"] for e in valid])
    gain_pct = report["aggregate"]["multilingual_gain_pct"]

    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=300)
    x = np.arange(len(entry_ids))
    width = 0.38

    bars_en = ax.bar(x - width / 2, en_vals, width, label="English-only", color=EN_COLOR, edgecolor="black", linewidth=0.4)
    bars_combo = ax.bar(x + width / 2, combined_vals, width, label="Multilingual (EN+ZH)", color=COMBINED_COLOR, edgecolor="black", linewidth=0.4)

    # Highlight entries with gain
    for i, g in enumerate(gains):
        if g > 0:
            ax.plot([x[i], x[i]], [en_vals[i], combined_vals[i]], color=GAIN_COLOR, linewidth=0.8, zorder=5)
            ax.text(x[i] + width - 0.03, combined_vals[i] + 0.3, f"+{g}", fontsize=6, ha="right", color=GAIN_COLOR, fontweight="bold")

    # Avg lines
    ax.axhline(avg_en, color=EN_COLOR, linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(avg_combo, color=COMBINED_COLOR, linestyle="--", linewidth=1, alpha=0.6)

    ax.set_xticks(x)
    ax.set_xticklabels(entry_ids, rotation=90, fontsize=7)
    ax.set_ylabel("Evidence items (found)", fontsize=11)
    ax.set_title(
        f"Evidence extraction: English-only vs Multilingual track\n"
        f"Mean: {avg_en:.1f} → {avg_combo:.1f} items/entry (+{gain_pct:.1f}%)",
        fontsize=12, fontweight="bold",
    )
    ax.legend(loc="upper right", fontsize=9, frameon=True)
    ax.set_ylim(0, max(combined_vals) * 1.15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out = OUT_DIR / "F1_paired_evidence_comparison.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def fig2_field_heatmap(report: dict) -> None:
    """F2: Field-level benefit heatmap."""
    entries = report["per_entry"]
    entries.sort(key=lambda e: e["entry_id"])

    # All field types that appeared
    all_fields = set()
    for e in entries:
        all_fields.update(e["zh_only_field_ids"])
    all_fields = sorted(all_fields)

    # Build matrix: rows=entries, cols=fields, value=1 if ZH-only found
    matrix = np.zeros((len(entries), len(all_fields)))
    for i, e in enumerate(entries):
        for f in e["zh_only_field_ids"]:
            if f in all_fields:
                matrix[i, all_fields.index(f)] = 1

    if len(all_fields) == 0:
        print("No ZH-only fields; skipping heatmap")
        return

    fig, ax = plt.subplots(figsize=(9, len(entries) * 0.35 + 2), dpi=300)
    im = ax.imshow(matrix, cmap="Oranges", aspect="auto", interpolation="nearest")

    ax.set_xticks(range(len(all_fields)))
    ax.set_xticklabels(all_fields, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(entries)))
    ax.set_yticklabels([e["entry_id"] for e in entries], fontsize=7)

    # Annotate values
    for i in range(len(entries)):
        for j in range(len(all_fields)):
            if matrix[i, j] > 0:
                ax.text(j, i, "✓", ha="center", va="center", fontsize=7, color="black")

    ax.set_xlabel("Field type", fontsize=11)
    ax.set_ylabel("Entry", fontsize=11)
    ax.set_title(
        "Fields with evidence found ONLY in Chinese translation track (✓)\n"
        f"{report['aggregate']['entries_with_zh_only_fields']}/{report['valid_entries']} entries benefited",
        fontsize=11, fontweight="bold",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    out = OUT_DIR / "F2_field_level_zh_benefit_heatmap.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def fig3_gain_distribution(report: dict) -> None:
    """F3: Distribution of evidence gain per entry."""
    entries = report["per_entry"]
    gains = [e["multilingual_gain"] for e in entries if e["en_found_items"] > 0]

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)

    # Histogram
    bins = np.arange(min(gains) - 0.5, max(gains) + 1.5, 1)
    n, b, patches = ax.hist(gains, bins=bins, color=COMBINED_COLOR, edgecolor="black", linewidth=0.5, alpha=0.8)
    for count, p in zip(n, patches):
        if p.get_x() <= 0 < p.get_x() + p.get_width():
            p.set_facecolor(EN_COLOR)
            p.set_alpha(0.7)

    ax.axvline(0, color=GAIN_COLOR, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Multilingual evidence gain (items/entry)", fontsize=11)
    ax.set_ylabel("Number of entries", fontsize=11)
    ax.set_title(
        "Distribution of evidence gain from multilingual processing\n"
        "Positive = multilingual found more evidence than English-only",
        fontsize=11, fontweight="bold",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    ax.set_xticks(np.arange(min(gains), max(gains) + 1, 2))

    fig.tight_layout()
    out = OUT_DIR / "F3_evidence_gain_distribution.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def fig4_field_count_grouped(report: dict) -> None:
    """F4: Total evidence count by field category (EN vs ZH)."""
    entries = report["per_entry"]

    # Load run_ids from dual_track_metrics
    dtm = REPORT.with_name("dual_track_metrics.json")
    run_by_entry = {}
    if dtm.exists():
        with open(dtm) as f:
            for m in json.load(f):
                run_by_entry[m["entry_id"]] = m.get("run_id")

    # Collect per-field counts from extraction results
    from collections import defaultdict
    en_by_field = defaultdict(int)
    zh_by_field = defaultdict(int)

    # Pipeline run outputs live in the external data project; override via PIPELINE_DATA_DIR.
    base = Path(os.environ.get("PIPELINE_DATA_DIR", "/data/yangzs/Projects/01_ACMG_Lingua/data/pipeline"))
    for e in entries:
        run_id = run_by_entry.get(e["entry_id"])
        path = base / run_id / "phase_2" / "extraction_result.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        for track, counter in [("original_result", en_by_field), ("translated_result", zh_by_field)]:
            for item in data.get(track, {}).get("evidence_items", []):
                if item.get("status") == "found":
                    fid = item.get("field_id", "")
                    cat = fid.split(".")[0] if "." in fid else fid
                    counter[cat] += 1

    cats = sorted(set(en_by_field.keys()) | set(zh_by_field.keys()))
    if not cats:
        return

    en_vals = [en_by_field.get(c, 0) for c in cats]
    zh_vals = [zh_by_field.get(c, 0) for c in cats]

    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    x = np.arange(len(cats))
    width = 0.38

    ax.bar(x - width / 2, en_vals, width, label="English track", color=EN_COLOR, edgecolor="black", linewidth=0.4)
    ax.bar(x + width / 2, zh_vals, width, label="Chinese track", color=ZH_COLOR, edgecolor="black", linewidth=0.4)

    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=10)
    ax.set_ylabel("Evidence items (found)", fontsize=11)
    ax.set_xlabel("ACMG evidence category", fontsize=11)
    ax.set_title("Evidence items by ACMG category (English vs Chinese track)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out = OUT_DIR / "F4_evidence_by_category.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def main() -> None:
    report = load_report()
    print(f"Loaded report: {REPORT}")
    print(f"Valid entries: {report['valid_entries']}/{report['total_entries']}")
    print(f"Multilingual gain: {report['aggregate']['multilingual_gain_items']} items/entry "
          f"({report['aggregate']['multilingual_gain_pct']}%)")
    print()
    fig1_paired_bar(report)
    fig2_field_heatmap(report)
    fig3_gain_distribution(report)
    fig4_field_count_grouped(report)
    print("\nAll figures generated in:", OUT_DIR)


if __name__ == "__main__":
    main()