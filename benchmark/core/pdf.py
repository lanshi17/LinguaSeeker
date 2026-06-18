"""PDF rendering helpers used by the layer-3 evaluator and dataset tools.

Carved out of ``benchmark.layer3.evaluate`` during the 2026-06-18
framework refactor. Behavior is byte-identical with the original.
"""
from __future__ import annotations

__all__ = ["sanitize_for_pdf", "markdown_to_pdf_bytes"]


def sanitize_for_pdf(text: str) -> str:
    """Remove characters that can't be encoded in latin-1."""
    # Replace common Unicode chars with ASCII equivalents
    replacements = {
        "—": "-",
        "–": "-",
        "−": "-",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "―": "-",
        "－": "-",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Encode to latin-1, replacing unknown chars
    return text.encode("latin-1", errors="replace").decode("latin-1")


# Legacy private alias for the old ``benchmark.layer3.evaluate._sanitize_for_pdf``
# import path used by a couple of dataset-curation modules. New code MUST use
# ``sanitize_for_pdf``.
_sanitize_for_pdf = sanitize_for_pdf


def markdown_to_pdf_bytes(md_text: str, title: str = "") -> bytes:
    """Convert markdown text to PDF bytes using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=10)

    if title:
        pdf.set_font("Helvetica", "B", 14)
        pdf.multi_cell(0, 8, sanitize_for_pdf(title[:200]))
        pdf.ln(5)
        pdf.set_font("Helvetica", size=10)

    lines = md_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        # Truncate very long lines
        if len(line) > 2000:
            line = line[:2000] + "..."
        text = sanitize_for_pdf(line)
        if not text.strip():
            continue
        try:
            if line.startswith("## "):
                pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 6, text[3:] if len(text) > 3 else text)
                pdf.set_font("Helvetica", size=10)
            elif line.startswith("# "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, text[2:] if len(text) > 2 else text)
                pdf.set_font("Helvetica", size=10)
            else:
                pdf.multi_cell(0, 5, text)
        except Exception:
            # Skip problematic lines
            continue

    return bytes(pdf.output())
