"""Prompt templates for the translation and self-review stages."""
from __future__ import annotations


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

    parts.append(
        "[RULES]\n"
        "- Translate LITERALLY. Do not add, infer, or summarize.\n"
        "- Preserve evidence strength exactly: 提示→suggestive of, "
        "支持→supportive of, 考虑→consistent with, 明确→confirmed.\n"
        "- Use 'variant' for 变异. Use 'mutation' only when source says 突变.\n"
        "- Use 'suspected' not 'suspicious' for 疑似/可疑.\n"
        "- Use 'family screening' for 家系筛查 (not 'pedigree screening').\n"
        "- 包括X在内 → 'including X' (spell out the noun, never 'including that').\n"
        "- Chinese title pattern 'X病N例' → 'A case of X' (e.g. '法布雷病1例' → "
        "'A case of Fabry disease'). Follow medical English conventions.\n"
        "- Author names: space-separated pinyin with given name before surname, "
        "or abbreviated format (e.g. '杜涓' → 'Du Juan', not 'Dujuan'). "
        "Separate multiple authors with commas.\n"
        "- Preserve ALL [REDACTED] markers exactly as-is. These mark "
        "redacted/missing values (ages, dates, lab results). "
        "Embed them naturally in the English sentence (e.g. "
        "'aged [REDACTED] years', 'In [REDACTED], the onset...'). "
        "Do NOT remove, translate, or replace them with 'blank'/'unknown'.\n"
        "- Do not add clinical conclusions, phenotype summaries, or ACMG language.\n"
        "- Do not summarize or aggregate clinical findings across sentences.\n"
        "- Preserve product names, vector names, strain designations, catalog "
        "numbers, and accession IDs EXACTLY as written in the source, even if "
        "they appear to contain typos. Do NOT silently 'correct' them "
        "(e.g. 'pET156' stays 'pET156', not 'pET15b'; "
        "'CondonPlus' stays 'CondonPlus', not 'CodonPlus').\n"
    )

    parts.append(f"[TRANSLATE THIS SEGMENT]\n{markdown_segment}")
    if "«BLK»" in markdown_segment:
        parts.append(
            "\n[IMPORTANT: Preserve all «BLK» markers exactly as-is in your "
            "translation. Do not translate, remove, or modify them.]"
        )
    return "\n".join(parts)


def get_full_document_translate_prompt(
    marked_source: str,
    terminology: str,
) -> str:
    """Build the prompt for translating a full document in one call.

    The source text contains ``[BLOCK_N]`` markers that delimit each
    content block. The LLM must preserve these markers exactly.
    """
    parts: list[str] = []

    if terminology:
        parts.append(f"[TERMINOLOGY]\n{terminology}\n")

    parts.append(
        "[RULES]\n"
        "- Translate the entire document from source language to English.\n"
        "- Preserve ALL [BLOCK_N] markers exactly as they appear. "
        "Do NOT translate, remove, renumber, or modify them.\n"
        "- Translate LITERALLY. Do not add, infer, or summarize.\n"
        "- Preserve evidence strength exactly: 提示→suggestive of, "
        "支持→supportive of, 考虑→consistent with, 明确→confirmed.\n"
        "- Use 'variant' for 变异. Use 'mutation' only when source says 突变.\n"
        "- Use 'suspected' not 'suspicious' for 疑似/可疑.\n"
        "- Use 'family screening' for 家系筛查 (not 'pedigree screening').\n"
        "- 包括X在内 → 'including X' (spell out the noun, never 'including that').\n"
        "- Title pattern 'X病N例' → 'A case of X' (medical English convention).\n"
        "- Author names: space-separated pinyin, comma-separated "
        "(e.g. '杜涓' → 'Du Juan', not 'Dujuan').\n"
        "- Preserve ALL [REDACTED] markers exactly as-is. These mark "
        "redacted/missing values (ages, dates, lab results). "
        "Embed them naturally in the English sentence (e.g. "
        "'aged [REDACTED] years', 'In [REDACTED], the onset...'). "
        "Do NOT remove, translate, or replace them with 'blank'/'unknown'.\n"
        "- Do not add clinical conclusions, phenotype summaries, or ACMG language.\n"
        "- Preserve product names, vector names, strain designations, catalog "
        "numbers, and accession IDs EXACTLY as written in the source, even if "
        "they appear to contain typos. Do NOT silently 'correct' them "
        "(e.g. 'pET156' stays 'pET156', not 'pET15b'; "
        "'CondonPlus' stays 'CondonPlus', not 'CodonPlus').\n"
        "- Output ONLY the translated document with [BLOCK_N] markers.\n"
    )

    parts.append(f"[DOCUMENT]\n{marked_source}")
    return "\n".join(parts)


def get_self_review_prompt(source_text: str, translated_text: str) -> str:
    """Build a prompt for post-translation quality review and correction.

    The review is generic — it checks for common quality patterns rather
    than overfitting to specific document issues.
    """
    return (
        "You are a bilingual medical editor reviewing an English translation "
        "of a biomedical document. Compare the source and translation below.\n\n"
        "Fix these quality issues if found:\n"
        "1. Untranslated source-language text left in the translation.\n"
        "2. Placeholder artifacts: bare '年月日', '[year]', '(month)', 'blank', "
        "'year month day', etc. — remove them entirely. "
        "IMPORTANT: Do NOT remove [REDACTED] markers — these are intentional "
        "placeholders for redacted/missing values that must be preserved.\n"
        "3. Redundant section prefixes the LLM added (e.g. 'Paper Abstract'). "
        "'Keywords:' as a label is acceptable.\n"
        "4. Title should follow medical English conventions "
        "(e.g. 'A case of X', not 'X 1 case').\n"
        "5. Author names should be properly spaced "
        "(e.g. 'Du Juan', not 'Dujuan').\n"
        "6. Evidence strength terms must be preserved exactly: "
        "'suggestive of', 'supportive of', 'consistent with'.\n"
        "7. 'suspected' not 'suspicious' for medical uncertainty.\n"
        "8. 'family screening' not 'pedigree screening'.\n"
        "9. Fix dangling modifiers (e.g. 'Due to X, resulting in Y' → "
        "'Due to X, Y occurs' or 'A variant in X results in Y').\n"
        "10. Keyword lists should use lowercase for common terms "
        "(e.g. 'Fabry disease; genetic disease' not 'Fabry disease; Genetic disease').\n"
        "11. Fix 'Email: :' or 'Email:' with missing address → 'Email: [unavailable]'.\n"
        "12. Do NOT add content, inference, or clinical conclusions.\n"
        "    Only fix formatting and terminology issues.\n"
        "13. Product names, vector names, strain designations, and catalog numbers\n"
        "    must match the source EXACTLY. If the translation changed 'pET156' to\n"
        "    'pET15b' or 'CondonPlus' to 'CodonPlus', revert to the source form.\n"
        "    Do NOT silently 'correct' apparent typos in identifiers.\n\n"
        "Output ONLY the corrected English translation. "
        "No explanations, no preamble, no diff.\n\n"
        f"[SOURCE]\n{source_text}\n\n"
        f"[TRANSLATION]\n{translated_text}"
    )
