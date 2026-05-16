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


def get_system_prompt_generation_prompt(
    markdown_sample: str,
    source_language: str,
) -> str:
    """Build a meta-prompt that asks an LLM to generate the optimal
    translation system prompt for the given document.

    The generated prompt will be used as the system message for all
    segment translations of this document.
    """
    return (
        "You are a prompt engineering expert. Given a sample of a biomedical "
        "document, generate an optimal SYSTEM PROMPT for a translation LLM.\n\n"
        "The system prompt must:\n"
        "1. Define the role (biomedical translation engine, source→English).\n"
        "2. List rules for preserving markdown structure, image references, "
        "and biomedical literals (HGVS, gene symbols, protein names, "
        "accession IDs, DOI/PMID, drug dosages, lab values).\n"
        "3. Include rules specific to the document's source language "
        f"({source_language}).\n"
        "4. Include rules specific to the document's domain and structure "
        "(e.g. if it has tables, images, dosage data, genetic notation).\n"
        "5. Be concise — under 500 words. No examples, no fluff.\n"
        "6. Output ONLY the system prompt text. No wrapper, no explanation.\n\n"
        f"SOURCE LANGUAGE: {source_language}\n"
        f"DOCUMENT SAMPLE (first ~2000 chars):\n{markdown_sample[:2000]}"
    )


def get_translate_prompt(
    markdown_segment: str,
    terminology: str,
    prev_context: str = "",
    next_context: str = "",
) -> str:
    """Build the human message for translating one segment.

    The system prompt (rules, role) is injected separately via SystemMessage.
    This function only assembles the content payload: context, terminology,
    and the segment itself.
    """
    parts: list[str] = []

    if prev_context:
        parts.append(f"[PRECEDING CONTEXT — for reference only, do NOT translate]\n{prev_context}\n")
    if next_context:
        parts.append(f"[FOLLOWING CONTEXT — for reference only, do NOT translate]\n{next_context}\n")

    if terminology:
        parts.append(f"[TERMINOLOGY]\n{terminology}\n")

    parts.append(f"[TRANSLATE THIS SEGMENT]\n{markdown_segment}")
    return "\n".join(parts)
