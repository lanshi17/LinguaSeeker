#!/usr/bin/env python3
"""Generate GIM paper Figure 1: Lingua Seeker four-phase system architecture.

Pure matplotlib block diagram, consistent with generate_gim_figures.py palette.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "gim" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EN_COLOR = "#4C72B0"
ZH_COLOR = "#DD8452"
COMBINED_COLOR = "#55A868"
GAIN_COLOR = "#C44E52"
GRAY = "#555555"


def phase_box(ax, x, y, w, h, title, lines, facecolor):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=1.4, edgecolor="#222222", facecolor=facecolor, alpha=0.92,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h - 0.13, title, ha="center", va="top",
            fontsize=10.5, fontweight="bold", color="#111111")
    body = "\n".join(lines)
    ax.text(x + w / 2, y + 0.14, body, ha="center", va="bottom",
            fontsize=8.0, color="#222222", linespacing=1.45)


def arrow(ax, x1, y1, x2, y2, label=None):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                        mutation_scale=16, linewidth=1.6, color="#333333")
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2, y1 + 0.06, label, ha="center", va="bottom",
                fontsize=7.5, color=GRAY, style="italic")


def main() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 5.2), dpi=300)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.4)
    ax.axis("off")

    fig.text(0.5, 0.965, "Lingua Seeker: four-phase multi-agent evidence pipeline",
             ha="center", fontsize=13, fontweight="bold")

    # ---- Phase boxes (top row) ----
    phase_box(ax, 0.25, 3.15, 2.7, 1.9, "Phase 1",
              ["Literature acquisition", "& digitization",
               "15+ providers (Crossref,\nPubMed, OpenAlex, EuropePMC,\nPMC, DOAJ, J-STAGE,\nUnpaywall, web scrapers)",
               "MinerU PDF parsing"],
              "#DDEBFA")  # light blue
    phase_box(ax, 3.35, 3.15, 2.7, 1.9, "Phase 2",
              ["Cross-lingual evidence", "extraction",
               "Dual track: English +", "Chinese translation",
               "Rust PyO3 HTTP I/O"],
              "#FDF0E0")  # light orange
    phase_box(ax, 6.45, 3.15, 2.7, 1.9, "Phase 3",
              ["Entity standardization", "& knowledge alignment",
               "HGNC / OMIM / HPO / ClinVar",
               "exact + bge-m3 vector", "matching (pgvector)"],
              "#E2F4E4")  # light green
    phase_box(ax, 9.55, 3.15, 2.2, 1.9, "Phase 4",
              ["Expert-in-the-loop", "review & feedback",
               "Bilingual visualization", "of extracted evidence"],
              "#FBE3E4")  # light red

    arrow(ax, 2.95, 4.10, 3.35, 4.10)
    arrow(ax, 6.05, 4.10, 6.45, 4.10)
    arrow(ax, 9.15, 4.10, 9.55, 4.10)

    # ---- Ablation inset (bottom) ----
    ax.text(0.35, 2.72, "Controlled ablation (30 ClinGen/ClinVar entries, paired):",
            fontsize=9.5, fontweight="bold", color="#111111")

    # Mode A box
    box_a = FancyBboxPatch((0.25, 0.55), 3.2, 1.8, boxstyle="round,pad=0.02,rounding_size=0.04",
                           linewidth=1.4, edgecolor="#222222", facecolor=EN_COLOR, alpha=0.9)
    ax.add_patch(box_a)
    ax.text(1.85, 2.05, "Mode A — English-only", ha="center", va="top",
            fontsize=9.5, fontweight="bold", color="white")
    ax.text(1.85, 0.75, "Evidence extraction from the\nEnglish article only\n"
                        "Field match vs gold standard:\n3.57 / 8 fields", ha="center", va="bottom",
            fontsize=8, color="white", linespacing=1.5)

    # Mode B box
    box_b = FancyBboxPatch((4.2, 0.55), 3.6, 1.8, boxstyle="round,pad=0.02,rounding_size=0.04",
                           linewidth=1.4, edgecolor="#222222", facecolor=COMBINED_COLOR, alpha=0.9)
    ax.add_patch(box_b)
    ax.text(6.0, 2.05, "Mode B — Dual-track (EN + ZH)", ha="center", va="top",
            fontsize=9.5, fontweight="bold", color="white")
    ax.text(6.0, 0.75, "Parallel extraction from English\nand Chinese versions, merged\n"
                      "Field match: 3.57 / 8 fields\nZH-only items: +3.62/entry (+22.8%)",
            ha="center", va="bottom", fontsize=8, color="white", linespacing=1.5)

    arrow(ax, 3.45, 1.45, 4.2, 1.45)

    # Outcome annotation
    ax.text(8.5, 1.45, "Outcomes:\n1. Evidence-item yield (ZH-only items)\n2. Field-level match vs 8-field gold standard\n3. Final-output evidence items",
            ha="left", va="center", fontsize=8, color="#222222", linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#FAFAFA", edgecolor="#999999", linewidth=0.8))

    # ZH track indicator below phase 2
    ax.text(4.7, 3.02, "ZH track", ha="center", va="top", fontsize=7.5,
            color=ZH_COLOR, fontweight="bold", rotation=0)

    out = OUT_DIR / "F1_architecture.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
