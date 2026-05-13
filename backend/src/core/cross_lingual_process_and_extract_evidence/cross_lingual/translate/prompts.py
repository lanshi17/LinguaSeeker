"""LLM prompt templates for the translation and formatting pipeline."""
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


def get_structure_prompt(markdown_content: str) -> str:
    """Generate prompt for the structure planning stage."""
    return (
        "STRUCTURE_STAGE\n"
        "You are a structure planner for non-English biomedical markdown. "
        "Do not translate terminology. Re-express only the logical structure "
        "needed for clear English rendering. Restore omitted subjects when "
        "necessary, split long clauses, make logical connectors explicit, "
        "and preserve markdown-aware structure such as headings, bullet lists, "
        "and tables.\n\n"
        f"SOURCE DOCUMENT:\n{markdown_content}"
    )


def get_draft_prompt(
    markdown_segment: str,
    terminology: str,
    structure_plan: str,
) -> str:
    """Generate prompt for translating one segment."""
    return (
        "DRAFT_STAGE\n"
        "You are a faithful biomedical translation engine. Translate this "
        "markdown segment into English while preserving markdown structure. "
        "Obey the terminology map and the structure plan. Preserve HGVS, gene "
        "symbols, protein names, accession IDs, DOI/PMID strings, and other "
        "biomedical literals exactly. Do not omit uncertain content; if ambiguity "
        "remains, keep it explicit rather than rewriting it away.\n\n"
        f"TERMINOLOGY MAP:\n{terminology}\n\n"
        f"STRUCTURE PLAN:\n{structure_plan}\n\n"
        f"MARKDOWN SEGMENT:\n{markdown_segment}"
    )


def get_polish_prompt(draft: str, terminology: str) -> str:
    """Generate prompt for polishing the translated draft."""
    return (
        "POLISH_STAGE\n"
        "You are polishing biomedical English prose. Improve fluency for "
        "academic English while preserving markdown layout and scientific meaning. "
        "Do not alter biomedical literals or terminology mappings, and avoid "
        "obvious stock AI phrasing.\n\n"
        f"TERMINOLOGY MAP:\n{terminology}\n\n"
        f"DRAFT MARKDOWN:\n{draft}"
    )


def get_review_prompt(source_markdown: str, translated_markdown: str) -> str:
    """Generate prompt for reviewing translation quality."""
    return (
        "REVIEW_STAGE\n"
        "Review the translated biomedical markdown against the source. Identify "
        "unresolved ambiguity, dropped content, terminology drift, or logic gaps. "
        "Return a short review result only.\n\n"
        f"SOURCE DOCUMENT:\n{source_markdown}\n\n"
        f"TRANSLATED DOCUMENT:\n{translated_markdown}"
    )
