"""Render main-benchmark baseline comparison figures from a matrix JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Mapping, cast

from benchmark.core.paths import PAPER_REPORTS_ROOT


METRICS = ("precision", "recall", "f1")
COLORS = {
    "precision": "#2F6F9F",
    "recall": "#7A4EAB",
    "f1": "#2E8B57",
}


def write_prf1_figure(
    *,
    matrix_path: Path,
    output_dir: Path = PAPER_REPORTS_ROOT / "main_benchmark_baseline_matrix",
) -> Path:
    """Write a grouped Precision/Recall/F1 SVG for complete matrix rows."""
    matrix = _load_json_object(matrix_path)
    rows = [
        row
        for row in _row_mappings(matrix)
        if str(row.get("coverage_status") or "") == "complete" and _int(row.get("error_entries")) == 0
    ]
    if not rows:
        raise ValueError("No complete, zero-error rows found for figure rendering")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"fig_main_benchmark_prf1_{time.strftime('%Y%m%d_%H%M%S')}.svg"
    output_path.write_text(_render_svg(rows), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for main-benchmark figure rendering."""
    parser = argparse.ArgumentParser(description="Render main-benchmark baseline P/R/F1 figure.")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=PAPER_REPORTS_ROOT / "main_benchmark_baseline_matrix")
    args = parser.parse_args(argv)

    output_path = write_prf1_figure(matrix_path=args.matrix, output_dir=args.output_dir)
    print(f"SVG: {output_path}")


def _render_svg(rows: list[Mapping[str, Any]]) -> str:
    width = 900
    height = 520
    left = 82
    right = 34
    top = 58
    bottom = 112
    plot_width = width - left - right
    plot_height = height - top - bottom
    group_width = plot_width / len(rows)
    bar_width = min(48.0, group_width / 5)
    chart_bottom = top + plot_height

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        ".title{font:700 22px Arial,sans-serif;fill:#1f2933}",
        ".label{font:13px Arial,sans-serif;fill:#2d3748}",
        ".tick{font:12px Arial,sans-serif;fill:#4a5568}",
        ".note{font:12px Arial,sans-serif;fill:#52616b}",
        "</style>",
        '<rect width="900" height="520" fill="#ffffff"/>',
        '<text class="title" x="82" y="34">Main Benchmark: LinguaSeeker vs Full GPT-5 Baselines</text>',
        '<text class="note" x="82" y="54">All rows use N=150, the same schema, gold set, and normalization rules.</text>',
    ]
    for index in range(6):
        value = index / 5
        y = chart_bottom - (value * plot_height)
        elements.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        elements.append(f'<text class="tick" x="{left - 12}" y="{y + 4:.1f}" text-anchor="end">{value:.1f}</text>')
    elements.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{chart_bottom}" stroke="#9aa5b1"/>')
    elements.append(f'<line x1="{left}" y1="{chart_bottom}" x2="{width - right}" y2="{chart_bottom}" stroke="#9aa5b1"/>')

    for row_index, row in enumerate(rows):
        group_center = left + group_width * row_index + group_width / 2
        for metric_index, metric in enumerate(METRICS):
            value = _float(row.get(metric))
            bar_height = value * plot_height
            x = group_center + (metric_index - 1) * (bar_width + 8) - bar_width / 2
            y = chart_bottom - bar_height
            elements.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" '
                f'rx="3" fill="{COLORS[metric]}"/>'
            )
            elements.append(
                f'<text class="tick" x="{x + bar_width / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle">{value:.3f}</text>'
            )
        label = _method_label(row)
        elements.append(
            f'<text class="label" x="{group_center:.1f}" y="{chart_bottom + 28}" text-anchor="middle">{_escape(label)}</text>'
        )
        elements.append(
            f'<text class="note" x="{group_center:.1f}" y="{chart_bottom + 47}" text-anchor="middle">N={_int(row.get("total_entries"))}</text>'
        )

    legend_x = width - 330
    legend_y = 78
    for index, metric in enumerate(METRICS):
        x = legend_x + index * 108
        elements.append(f'<rect x="{x}" y="{legend_y}" width="16" height="16" rx="3" fill="{COLORS[metric]}"/>')
        elements.append(f'<text class="label" x="{x + 23}" y="{legend_y + 13}">{metric.title()}</text>')
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def _method_label(row: Mapping[str, Any]) -> str:
    method_id = str(row.get("method_id") or "")
    prompt_mode = str(row.get("prompt_mode") or "")
    if method_id == "LinguaSeeker":
        return "LinguaSeeker"
    if method_id == "B0":
        return "GPT-5 prompt-only"
    if method_id == "B1":
        return "GPT-5 translate-extract"
    if method_id == "B2":
        return "GPT-5 original-only"
    return prompt_mode or method_id


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _row_mappings(matrix: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = matrix.get("rows")
    if not isinstance(rows, list):
        return []
    return [cast(Mapping[str, Any], row) for row in rows if isinstance(row, Mapping)]


def _int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    main()
