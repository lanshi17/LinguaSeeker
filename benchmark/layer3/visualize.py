"""Visualize Layer 3 evaluation reports.

Reads a JSON report from reports/ and generates:
- Per-field P/R/F1 bar chart
- Per-classification accuracy heatmap
- Per-MOI comparison chart
- Entity standardization accuracy chart
- Cross-lingual consistency chart
- HTML summary report
"""
from __future__ import annotations

import json
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def load_latest_report() -> dict:
    """Load the most recent evaluation report."""
    reports = sorted(REPORTS_DIR.glob("eval_*.json"), reverse=True)
    if not reports:
        raise FileNotFoundError(f"No reports found in {REPORTS_DIR}")
    latest = reports[0]
    print(f"Loading: {latest.name}")
    return json.loads(latest.read_text(encoding="utf-8"))


def plot_field_f1(report: dict, output_dir: Path) -> Path:
    """Per-field Precision/Recall/F1 bar chart."""
    import matplotlib.pyplot as plt
    import numpy as np

    by_field = report.get("aggregates", {}).get("by_field", {})
    if not by_field:
        return output_dir / "field_f1.png"

    fields = list(by_field.keys())
    precision = [by_field[f]["precision"] for f in fields]
    recall = [by_field[f]["recall"] for f in fields]
    f1 = [by_field[f]["f1"] for f in fields]

    x = np.arange(len(fields))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width, precision, width, label="Precision", color="#4C72B0")
    ax.bar(x, recall, width, label="Recall", color="#DD8452")
    ax.bar(x + width, f1, width, label="F1", color="#55A868")

    ax.set_xlabel("Field ID")
    ax.set_ylabel("Score")
    ax.set_title("Per-Field Precision / Recall / F1")
    ax.set_xticks(x)
    ax.set_xticklabels(fields, rotation=45, ha="right")
    ax.legend()
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = output_dir / "field_f1.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_classification_heatmap(report: dict, output_dir: Path) -> Path:
    """Per-classification accuracy heatmap."""
    import matplotlib.pyplot as plt
    import numpy as np

    by_cls = report.get("aggregates", {}).get("by_classification", {})
    if not by_cls:
        return output_dir / "classification_heatmap.png"

    classes = list(by_cls.keys())
    metrics = ["precision", "recall", "f1"]

    data = np.array([[by_cls[c][m] for m in metrics] for c in classes])

    fig, ax = plt.subplots(figsize=(8, max(4, len(classes) * 0.6)))
    im = ax.imshow(data, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels([m.capitalize() for m in metrics])
    ax.set_yticks(range(len(classes)))
    ax.set_yticklabels(classes)

    for i in range(len(classes)):
        for j in range(len(metrics)):
            ax.text(j, i, f"{data[i, j]:.0%}",
                    ha="center", va="center", color="black", fontsize=11)

    ax.set_title("Per-Classification Accuracy Heatmap")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    path = output_dir / "classification_heatmap.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_moi_comparison(report: dict, output_dir: Path) -> Path:
    """Per-MOI comparison chart with F1, standardization accuracy, and track consistency."""
    import matplotlib.pyplot as plt
    import numpy as np

    by_moi = report.get("aggregates", {}).get("by_moi", {})
    if not by_moi:
        return output_dir / "moi_comparison.png"

    mois = list(by_moi.keys())
    f1_vals = [by_moi[m]["f1"] for m in mois]
    std_vals = [by_moi[m].get("standardization_accuracy", 0) for m in mois]
    tc_vals = [by_moi[m].get("track_consistency", 0) for m in mois]

    x = np.arange(len(mois))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width, f1_vals, width, label="Field F1", color="#4C72B0")
    ax.bar(x, std_vals, width, label="Std Accuracy", color="#55A868")
    ax.bar(x + width, tc_vals, width, label="Track Consistency", color="#DD8452")

    ax.set_xlabel("MOI (Mode of Inheritance)")
    ax.set_ylabel("Score")
    ax.set_title("Per-MOI Evaluation Metrics")
    ax.set_xticks(x)
    ax.set_xticklabels(mois)
    ax.legend()
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3)

    # Add count annotations
    for i, m in enumerate(mois):
        count = by_moi[m]["count"]
        ax.annotate(f"n={count}", (x[i], -0.05), ha="center", fontsize=9)

    fig.tight_layout()
    path = output_dir / "moi_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_entity_standardization(report: dict, output_dir: Path) -> Path:
    """Entity standardization accuracy by entity type."""
    import matplotlib.pyplot as plt

    by_entity = report.get("aggregates", {}).get("by_entity_type", {})
    if not by_entity:
        return output_dir / "entity_standardization.png"

    types = list(by_entity.keys())
    accuracies = [by_entity[t] for t in types]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(types, accuracies, color=["#4C72B0", "#55A868", "#DD8452", "#C44E52"][:len(types)])

    ax.set_xlabel("Entity Type")
    ax.set_ylabel("Standardization Accuracy")
    ax.set_title("Entity Standardization Accuracy by Type")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3)

    for bar, val in zip(bars, accuracies):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.0%}", ha="center", fontsize=11)

    fig.tight_layout()
    path = output_dir / "entity_standardization.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_overall_summary(report: dict, output_dir: Path) -> Path:
    """Radar chart of overall metrics."""
    import matplotlib.pyplot as plt
    import numpy as np

    overall = report.get("aggregates", {}).get("overall", {})
    if not overall:
        return output_dir / "overall_summary.png"

    categories = ["Precision", "Recall", "F1", "Std Accuracy", "Track Consistency"]
    values = [
        overall.get("precision", 0),
        overall.get("recall", 0),
        overall.get("f1", 0),
        overall.get("entity_standardization_accuracy", 0),
        overall.get("cross_lingual_consistency", 0),
    ]

    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color="#4C72B0", alpha=0.25)
    ax.plot(angles, values, color="#4C72B0", linewidth=2)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 1)
    ax.set_title("Overall Evaluation Summary", pad=20)

    fig.tight_layout()
    path = output_dir / "overall_summary.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def generate_html_report(report: dict, output_dir: Path) -> Path:
    """Generate an HTML summary report with embedded charts."""
    import base64

    overall = report.get("aggregates", {}).get("overall", {})
    by_field = report.get("aggregates", {}).get("by_field", {})
    by_cls = report.get("aggregates", {}).get("by_classification", {})
    by_moi = report.get("aggregates", {}).get("by_moi", {})
    by_entity = report.get("aggregates", {}).get("by_entity_type", {})
    per_entry = report.get("per_entry", [])

    def img_to_base64(path: Path) -> str:
        if path.exists():
            data = path.read_bytes()
            return f"data:image/png;base64,{base64.b64encode(data).decode()}"
        return ""

    charts = {
        "overall": img_to_base64(output_dir / "overall_summary.png"),
        "field": img_to_base64(output_dir / "field_f1.png"),
        "classification": img_to_base64(output_dir / "classification_heatmap.png"),
        "moi": img_to_base64(output_dir / "moi_comparison.png"),
        "entity": img_to_base64(output_dir / "entity_standardization.png"),
    }

    # Build field table
    field_rows = ""
    for fid, m in sorted(by_field.items()):
        field_rows += f"""<tr>
            <td>{fid}</td>
            <td>{m['precision']:.1%}</td>
            <td>{m['recall']:.1%}</td>
            <td>{m['f1']:.1%}</td>
        </tr>"""

    # Build classification table
    cls_rows = ""
    for cls, m in sorted(by_cls.items()):
        cls_rows += f"""<tr>
            <td>{cls}</td>
            <td>{m['count']}</td>
            <td>{m['precision']:.1%}</td>
            <td>{m['recall']:.1%}</td>
            <td>{m['f1']:.1%}</td>
        </tr>"""

    # Build MOI table
    moi_rows = ""
    for moi, m in sorted(by_moi.items()):
        moi_rows += f"""<tr>
            <td>{moi}</td>
            <td>{m['count']}</td>
            <td>{m['f1']:.1%}</td>
            <td>{m.get('standardization_accuracy', 0):.1%}</td>
            <td>{m.get('track_consistency', 0):.1%}</td>
        </tr>"""

    # Build entity table
    entity_rows = ""
    for etype, acc in sorted(by_entity.items()):
        entity_rows += f"""<tr>
            <td>{etype}</td>
            <td>{acc:.1%}</td>
        </tr>"""

    # Build per-entry table (first 10)
    entry_rows = ""
    for e in per_entry[:20]:
        tp = sum(1 for f in e.get("field_matches", []) if f["matched"])
        total = len(e.get("field_matches", []))
        status_class = "success" if e["pipeline_status"] in ("awaiting_review", "completed") else "error"
        entry_rows += f"""<tr class="{status_class}">
            <td>{e['entry_id']}</td>
            <td>{e['gene_symbol']}</td>
            <td>{e['classification']}</td>
            <td>{e.get('moi', '-')}</td>
            <td>{e['pipeline_status']}</td>
            <td>{tp}/{total}</td>
            <td>{e.get('standardization_accuracy', 0):.0%}</td>
            <td>{e.get('track_consistency', 0):.0%}</td>
            <td>{e['duration_s']:.0f}s</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Layer 3 Evaluation Report — {report.get('evaluation_id', '')}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 1200px; margin: 0 auto; padding: 20px; color: #333; }}
  h1 {{ color: #1a1a1a; border-bottom: 2px solid #4C72B0; padding-bottom: 10px; }}
  h2 {{ color: #4C72B0; margin-top: 40px; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin: 20px 0; }}
  .metric-card {{ background: #f8f9fa; border-radius: 8px; padding: 16px; text-align: center; }}
  .metric-card .value {{ font-size: 2em; font-weight: bold; color: #4C72B0; }}
  .metric-card .label {{ font-size: 0.85em; color: #666; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
  th {{ background: #f0f2f5; font-weight: 600; }}
  tr.success {{ background: #f0fff0; }}
  tr.error {{ background: #fff0f0; }}
  .chart {{ max-width: 100%; margin: 20px auto; display: block; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
  .info {{ color: #666; font-size: 0.9em; }}
</style>
</head>
<body>

<h1>Layer 3 Evaluation Report</h1>
<p class="info">
  ID: {report.get('evaluation_id', '-')} |
  Entries: {report.get('total_entries', '-')} |
  Duration: {report.get('total_duration_s', 0):.0f}s |
  {report.get('timestamp', '-')}
</p>

<div class="metrics-grid">
  <div class="metric-card">
    <div class="value">{overall.get('precision', 0):.1%}</div>
    <div class="label">Precision</div>
  </div>
  <div class="metric-card">
    <div class="value">{overall.get('recall', 0):.1%}</div>
    <div class="label">Recall</div>
  </div>
  <div class="metric-card">
    <div class="value">{overall.get('f1', 0):.1%}</div>
    <div class="label">F1</div>
  </div>
  <div class="metric-card">
    <div class="value">{overall.get('entity_standardization_accuracy', 0):.1%}</div>
    <div class="label">Std Accuracy</div>
  </div>
  <div class="metric-card">
    <div class="value">{overall.get('cross_lingual_consistency', 0):.1%}</div>
    <div class="label">Track Consistency</div>
  </div>
</div>

<h2>Overall Summary</h2>
<img class="chart" src="{charts['overall']}" alt="Overall Summary">

<div class="chart-row">
  <div>
    <h2>Per-Field F1</h2>
    <img class="chart" src="{charts['field']}" alt="Per-Field F1">
  </div>
  <div>
    <h2>Classification Heatmap</h2>
    <img class="chart" src="{charts['classification']}" alt="Classification">
  </div>
</div>

<div class="chart-row">
  <div>
    <h2>MOI Comparison</h2>
    <img class="chart" src="{charts['moi']}" alt="MOI">
  </div>
  <div>
    <h2>Entity Standardization</h2>
    <img class="chart" src="{charts['entity']}" alt="Entity">
  </div>
</div>

<h2>Per-Field Breakdown</h2>
<table>
  <thead><tr><th>Field</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead>
  <tbody>{field_rows}</tbody>
</table>

<h2>Per-Classification</h2>
<table>
  <thead><tr><th>Classification</th><th>Count</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead>
  <tbody>{cls_rows}</tbody>
</table>

<h2>Per-MOI</h2>
<table>
  <thead><tr><th>MOI</th><th>Count</th><th>F1</th><th>Std Accuracy</th><th>Track Consistency</th></tr></thead>
  <tbody>{moi_rows}</tbody>
</table>

<h2>Entity Standardization</h2>
<table>
  <thead><tr><th>Entity Type</th><th>Accuracy</th></tr></thead>
  <tbody>{entity_rows}</tbody>
</table>

<h2>Per-Entry Details</h2>
<table>
  <thead>
    <tr>
      <th>Entry</th><th>Gene</th><th>Classification</th><th>MOI</th>
      <th>Status</th><th>Fields</th><th>Std Acc</th><th>Track Cons</th><th>Duration</th>
    </tr>
  </thead>
  <tbody>{entry_rows}</tbody>
</table>

</body>
</html>"""

    path = output_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    return path


def main():
    import matplotlib
    matplotlib.use("Agg")

    report = load_latest_report()
    output_dir = Path(report.get("config", {}).get("output_dir", REPORTS_DIR))

    print("Generating charts...")
    p1 = plot_overall_summary(report, output_dir)
    p2 = plot_field_f1(report, output_dir)
    p3 = plot_classification_heatmap(report, output_dir)
    p4 = plot_moi_comparison(report, output_dir)
    p5 = plot_entity_standardization(report, output_dir)
    print(f"  {p1.name}, {p2.name}, {p3.name}, {p4.name}, {p5.name}")

    print("Generating HTML report...")
    html_path = generate_html_report(report, output_dir)
    print(f"  {html_path}")


if __name__ == "__main__":
    main()
