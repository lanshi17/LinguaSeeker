"""Generate PDFs from source markdown files for fused benchmark entries.

Supports CJK text (zh/ja/ko) using Noto Sans CJK font.
English-only articles use Helvetica (latin-1 safe).

Output structure matches Dataset 1:
  benchmark/pipeline/input/ground_truth/{lang}/case_report/{entry_id}.pdf

Usage:
    PYTHONPATH=. uv run python -m benchmark.datasets.clinvar_fused.generate_pdfs
    PYTHONPATH=. uv run python -m benchmark.datasets.clinvar_fused.generate_pdfs --limit 5
    PYTHONPATH=. uv run python -m benchmark.datasets.clinvar_fused.generate_pdfs --langs en zh
"""
from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

GROUND_TRUTH_DIR = Path(__file__).resolve().parent.parent.parent.parent / "benchmark" / "data" / "ground_truth" / "clinvar_fused"
PIPELINE_INPUT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "pipeline" / "input" / "ground_truth"
)

LANGUAGES = {
    "en": {"source_file": "source.md", "font": None},
    "zh": {"source_file": "source_zh.md", "font": "NotoSansCJKsc"},
    "ja": {"source_file": "source_ja.md", "font": "NotoSansCJKjp"},
    "ko": {"source_file": "source_ko.md", "font": "NotoSansCJKkr"},
}

# CJK font paths
_CJK_FONTS = {
    "NotoSansCJKsc": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "NotoSansCJKjp": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "NotoSansCJKkr": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "NotoSansCJKBold": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
}


def _is_cjk_lang(lang: str) -> bool:
    return lang in ("zh", "ja", "ko")


def markdown_to_pdf_cjk(md_text: str, title: str = "", lang: str = "en") -> bytes:
    """Convert markdown to PDF with CJK font support."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Use Noto Sans CJK for ALL languages (handles Unicode chars in EN articles too)
    # Falls back to Helvetica only if font file is missing
    if _is_cjk_lang(lang):
        font_name = LANGUAGES[lang]["font"]
    else:
        font_name = "NotoSansCJKsc"  # CJK font also handles Latin chars
    font_path = _CJK_FONTS.get(font_name, "")
    bold_path = _CJK_FONTS.get("NotoSansCJKBold", "")
    if font_path and Path(font_path).exists():
        pdf.add_font(font_name, "", font_path, uni=True)
        if bold_path and Path(bold_path).exists():
            pdf.add_font(font_name, "B", bold_path, uni=True)
        _heading_font = font_name
        _body_font = font_name
    else:
        _heading_font = "Helvetica"
        _body_font = "Helvetica"
    pdf.set_font(_body_font, size=10)

    pdf.add_page()

    if title:
        pdf.set_font(_heading_font, "B", 14)
        pdf.multi_cell(0, 8, title[:300])
        pdf.ln(5)
        pdf.set_font(_body_font, size=10)

    lines = md_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        if len(line) > 3000:
            line = line[:3000] + "..."
        if not line:
            continue
        try:
            if line.startswith("### "):
                pdf.set_font(_heading_font, "B", 10)
                pdf.multi_cell(0, 6, line[4:])
                pdf.set_font(_body_font, size=10)
            elif line.startswith("## "):
                pdf.set_font(_heading_font, "B", 11)
                pdf.multi_cell(0, 7, line[3:])
                pdf.set_font(_body_font, size=10)
            elif line.startswith("# "):
                pdf.set_font(_heading_font, "B", 13)
                pdf.multi_cell(0, 8, line[2:])
                pdf.set_font(_body_font, size=10)
            else:
                pdf.set_font(_body_font, size=10)
                pdf.multi_cell(0, 5, line)
        except Exception:
            continue

    return bytes(pdf.output())


def generate_pdfs(
    target_langs: list[str] | None = None,
    limit: int | None = None,
    entry_ids: list[str] | None = None,
    force: bool = False,
) -> None:
    """Generate PDFs for all fused benchmark entries and languages."""
    langs = target_langs or list(LANGUAGES.keys())

    selection_path = GROUND_TRUTH_DIR / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))
    if entry_ids:
        entries = [e for e in entries if e["entry_id"] in set(entry_ids)]
    if limit:
        entries = entries[:limit]

    total = 0
    generated = 0
    skipped = 0

    for entry in entries:
        entry_id = entry["entry_id"]
        title = entry.get("source_title", "") or entry.get("clingen", {}).get("gene_symbol", "")

        for lang in langs:
            if lang not in LANGUAGES:
                logger.warning("Unknown language: {}", lang)
                continue

            source_file = LANGUAGES[lang]["source_file"]
            source_path = GROUND_TRUTH_DIR / entry_id / source_file
            output_dir = PIPELINE_INPUT_DIR / lang / "case_report"
            output_path = output_dir / f"{entry_id}.pdf"
            total += 1

            if not source_path.exists():
                logger.debug("[{}] {} source not found: {}", entry_id, lang, source_file)
                skipped += 1
                continue

            if output_path.exists() and not force:
                logger.debug("[{}] {} PDF already exists", entry_id, lang)
                skipped += 1
                continue

            md_text = source_path.read_text(encoding="utf-8")
            if len(md_text) < 100:
                logger.warning("[{}] {} source too small", entry_id, lang)
                skipped += 1
                continue

            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                pdf_bytes = markdown_to_pdf_cjk(md_text, title=title, lang=lang)
                output_path.write_bytes(pdf_bytes)
                generated += 1
                logger.info("[{}] {} PDF generated ({:.0f} KB)", entry_id, lang, len(pdf_bytes) / 1024)
            except Exception as e:
                logger.error("[{}] {} PDF generation failed: {}", entry_id, lang, e)
                skipped += 1

    logger.info("Done. Generated: {}, Skipped: {}, Total: {}", generated, skipped, total)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate PDFs for fused benchmark")
    parser.add_argument("--langs", nargs="+", default=None, help="Languages (en zh ja ko)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--entries", nargs="+", default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDFs")
    args = parser.parse_args()

    generate_pdfs(
        target_langs=args.langs,
        limit=args.limit,
        entry_ids=args.entries,
        force=args.force,
    )
