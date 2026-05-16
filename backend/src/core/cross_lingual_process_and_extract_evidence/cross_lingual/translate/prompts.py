"""LLM prompt templates for the translation pipeline."""
from __future__ import annotations


def get_format_prompt(markdown_content: str) -> str:
    """Generate prompt for the formatting/normalization stage."""
    return (
        "FORMAT_STAGE\n"
        "You are a biomedical document normalizer. Clean and restructure the "
        "following markdown document:\n"
        "- Remove OCR artifacts and normalize whitespace\n"
        "- Organize into clear academic sections (Title, Abstract, Introduction, "
        "Methods, Results, Discussion, References) when applicable\n"
        "- Fix broken markdown headings, lists, and tables\n"
        "- Preserve all scientific content, data, and terminology exactly\n"
        "- Preserve language — do NOT translate\n"
        "- Ensure each sentence is on its own line (one sentence per line)\n\n"
        f"SOURCE MARKDOWN:\n{markdown_content}"
    )


def get_terminology_prompt(markdown_content: str) -> str:
    """Generate prompt for the terminology extraction stage."""
    return (
        "TERMINOLOGY_STAGE\n"
        "You are a bilingual biomedical terminology planner. "
        "Extract a concise terminology map from the source document. "
        "Return only bilingual term pairs or preservation rules. "
        "Do not translate the full document. Preserve HGVS, gene symbols, "
        "protein names, accession IDs, and DOI/PMID strings exactly when appropriate.\n\n"
        f"SOURCE DOCUMENT:\n{markdown_content}"
    )


def get_translate_prompt(
    markdown_segment: str,
    terminology: str,
) -> str:
    """Generate prompt for translating one segment.

    Combines terminology enforcement, structure preservation, and image
    reference preservation into a single prompt. The LLM translates once
    — no separate draft/polish/review stages.
    """
    return (
        "TRANSLATE_STAGE\n"
        "You are a faithful biomedical translation engine. Translate the "
        "following markdown segment into English.\n\n"
        "CRITICAL RULES:\n"
        "1. Preserve ALL markdown structure exactly — do NOT add, remove, or "
        "rearrange headings (# ## ### etc.), bullet lists, tables, or horizontal rules.\n"
        "2. Preserve ALL image references exactly as-is (e.g., "
        "![](images/xxx.jpg)). Do not remove, rewrite, or translate them.\n"
        "3. Preserve ALL biomedical literals exactly: HGVS notation, gene symbols, "
        "protein names, accession IDs, DOI/PMID strings, drug dosages, lab values.\n"
        "4. Use the terminology map below for standard terms. If a term appears "
        "in the map, use the mapped translation consistently.\n"
        "5. Translate faithfully — do not omit content, do not add new content, "
        "do not summarize or expand. If ambiguity exists, keep it explicit.\n"
        "6. Output ONLY the translated markdown. Do NOT append the original text, "
        "explanations, or meta-commentary.\n\n"
        f"TERMINOLOGY MAP:\n{terminology}\n\n"
        f"MARKDOWN SEGMENT:\n{markdown_segment}"
    )
