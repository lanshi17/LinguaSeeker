"""Prompt templates for terminology extraction and system prompt generation."""

from __future__ import annotations


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
        "1. Define the role: faithful literal translation engine, source→English.\n"
        "2. List rules for preserving markdown structure, image references, "
        "and biomedical literals (HGVS, gene symbols, protein names, "
        "accession IDs, DOI/PMID, drug dosages, lab values).\n"
        "3. Include rules specific to the document's source language "
        f"({source_language}).\n"
        "4. Include rules specific to the document's domain and structure "
        "(e.g. if it has tables, images, dosage data, genetic notation).\n"
        "5. If the source contains «BLK» paragraph separators, preserve them "
        "exactly in the translation — do not translate, remove, or modify them.\n"
        "6. Be concise — under 500 words. No examples, no fluff.\n"
        "7. Output ONLY the system prompt text. No wrapper, no explanation.\n\n"
        "CRITICAL CONSTRAINTS (must be included in the generated prompt):\n"
        "- Translate LITERALLY. Do NOT upgrade or downgrade evidence strength.\n"
        "  '提示' → 'suggestive of', NOT 'confirming'. "
        " '支持' → 'supportive of', NOT 'confirming'. "
        " '考虑' → 'consistent with', NOT 'diagnosed as'.\n"
        "- Do NOT add medical inference, clinical summarization, or phenotype "
        "abstraction. Translate sentence-by-sentence, not idea-by-idea.\n"
        "- Do NOT infer missing values. Preserve ALL [REDACTED] markers exactly "
        "as-is — these mark redacted/missing values (ages, dates, lab results). "
        "Embed them naturally in the English sentence.\n"
        "- Use 'variant' for 变异 by default. Use 'mutation' ONLY when the source "
        "explicitly writes 突变.\n"
        "- Do NOT add ACMG/ClinGen classification language.\n"
        "- Do NOT summarize, aggregate, or restructure clinical findings.\n\n"
        f"SOURCE LANGUAGE: {source_language}\n"
        f"DOCUMENT SAMPLE (first ~2000 chars):\n{markdown_sample[:2000]}"
    )
