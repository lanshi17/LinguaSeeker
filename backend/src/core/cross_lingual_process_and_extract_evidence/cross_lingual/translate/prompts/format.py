"""Prompt templates for the document formatting/normalization stage."""

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
        "Do NOT insert [REDACTED] for OCR truncations (Task 3) or intentional blanks.\n"
        "CRITICAL: NEVER insert [REDACTED] inside an existing word. "
        "e.g., 'References' must stay 'References', NOT 'Re[REDACTED]ferences'.\n\n"
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
