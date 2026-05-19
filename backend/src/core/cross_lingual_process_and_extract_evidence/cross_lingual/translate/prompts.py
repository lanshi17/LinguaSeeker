"""LLM prompt templates for the translation pipeline."""
from __future__ import annotations


def get_prescan_prompt(source_text: str) -> str:
    """Build a prompt for LLM to identify and mark missing/redacted values.

    The LLM scans the source text and inserts [REDACTED] markers where
    it detects blank, missing, or redacted values (ages, dates, lab
    results, dosages, quantities, etc.). This is more robust than
    regex pattern matching for diverse OCR artifacts.
    """
    return (
        "You are a biomedical document analyst. Scan the following text "
        "and identify ALL missing, blank, or redacted values.\n\n"
        "Common patterns to look for:\n"
        "- Missing age: '患者男性， 岁' (space before 岁)\n"
        "- Missing year/date: ' 年' at line start, '于 年', '年 月'\n"
        "- Missing quantity: '纳入了 例', '在 个'\n"
        "- Missing lab values: '尿蛋白 ，' (space before punctuation)\n"
        "- Missing dosage: '环孢素 ' (space before comma)\n"
        "- Empty brackets: '（ ）'\n"
        "- Any other suspicious whitespace where a value should be\n\n"
        "For each missing value found, insert [REDACTED] in place of the "
        "whitespace/blank. Keep all other text exactly as-is.\n\n"
        "Output ONLY the text with [REDACTED] markers inserted. "
        "Do not translate, summarize, or modify any content.\n\n"
        f"SOURCE TEXT:\n{source_text}"
    )


def get_format_prompt(markdown_content: str) -> str:
    """Generate prompt for the formatting/normalization stage.

    This stage also detects and marks missing/redacted values with
    [REDACTED] markers, and repairs common OCR truncations.
    """
    return (
        "FORMAT_STAGE\n"
        "You are a biomedical document normalizer. Clean and restructure the "
        "following markdown document:\n\n"
        "## Task 1: Structure normalization\n"
        "- Remove OCR artifacts and normalize whitespace\n"
        "- Organize into clear academic sections (Title, Abstract, Introduction, "
        "Methods, Results, Discussion, References) when applicable\n"
        "- Fix broken markdown headings, lists, and tables\n"
        "- Preserve all scientific content, data, and terminology exactly\n"
        "- Preserve language — do NOT translate\n"
        "- Ensure each sentence is on its own line (one sentence per line)\n\n"
        "## Task 2: Mark missing/redacted values\n"
        "Insert [REDACTED] ONLY where a numeric/date/quantity value is clearly missing:\n"
        "- Missing age: '患者男性， 岁' → '患者男性，[REDACTED] 岁'\n"
        "- Missing year/date: ' 年以水肿' → '[REDACTED] 年以水肿'\n"
        "- Missing quantity: '纳入了 例' → '纳入了 [REDACTED] 例'\n"
        "- Missing lab values: '尿蛋白 ，' → '尿蛋白 [REDACTED]，'\n"
        "- Missing dosage: '环孢素 ，' → '环孢素 [REDACTED]，'\n"
        "- Empty brackets: '（ ）' → '（[REDACTED]）'\n"
        "Do NOT insert [REDACTED] for OCR truncations (Task 3) or intentional blanks.\n\n"
        "## Task 3: Repair OCR truncations (do NOT use [REDACTED] here)\n"
        "When medical terms are partially missing due to OCR, restore them:\n"
        "- '长 间期' → '长 R-R 间期' (restore 'R-R')\n"
        "- '查腹部 示' → '查腹部 CT/B超 示' (restore imaging method)\n"
        "- '查头颅 示' → '查头颅 CT/MRI 示' (restore imaging method)\n"
        "- '查头颅 未见' → '查头颅 CT/MRI 未见' (restore imaging method)\n"
        "- '心脏 超' → '心脏超声' (restore '声')\n"
        "These are OCR truncations where part of a medical term is missing. "
        "Use context to infer the missing term. Do NOT mark these as [REDACTED].\n\n"
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
        "    Only fix formatting and terminology issues.\n\n"
        "Output ONLY the corrected English translation. "
        "No explanations, no preamble, no diff.\n\n"
        f"[SOURCE]\n{source_text}\n\n"
        f"[TRANSLATION]\n{translated_text}"
    )
