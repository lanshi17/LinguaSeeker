# Cross-Lingual Module Refactor Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Break the 1640-line `translator.py` god object and 664-line `validator.py` into focused modules — separating LLM client management, prompt templates, validation logic, text normalization, and block operations into independent files.

**Architecture:** The `cross_lingual/translate/` package will be restructured from 5 files to a cleaner separation of concerns: `providers.py` for LLM client lifecycle, `prompts/` sub-package grouped by pipeline stage, `validator/` sub-package for validation + normalization + artifact stripping, and `blocks.py` for block-level operations extracted from the translator. The translator itself becomes a pure orchestration facade.

**Tech Stack:** Python, LangChain (ChatOpenAI), loguru, pytest

---

## Current Problems

| File | Lines | Problem |
|------|-------|---------|
| `translator.py` | 1640 | God object: LLM client, retry logic, terminology parsing, block merging, translation, post-processing, drift computation — all in one class |
| `validator.py` | 664 | Mixed concerns: validation, punctuation normalization, placeholder cleanup, OCR fix, redaction marking, artifact stripping |
| `prompts.py` | 279 | All prompt templates in one flat file (format, terminology, translate, review) |

## Target Structure

```
cross_lingual/translate/
├── __init__.py              # Re-exports public API
├── base.py                  # BaseTranslator ABC (unchanged)
├── language_detector.py     # Language detection (unchanged)
├── providers.py             # NEW: LLM client factory + retry logic
├── blocks.py                # NEW: Block merge/split/marker operations
├── postprocess.py           # NEW: Dedup, quality flagging, language check, block building
├── prompts/                 # NEW sub-package
│   ├── __init__.py          # Re-exports all prompt functions
│   ├── format.py            # get_prescan_prompt, get_format_prompt
│   ├── terminology.py       # get_terminology_prompt, get_system_prompt_generation_prompt
│   └── translate.py         # get_translate_prompt, get_full_document_translate_prompt, get_self_review_prompt
├── validator/               # NEW sub-package
│   ├── __init__.py          # Re-exports all validator functions
│   ├── core.py              # validate_translation_output, validate_segment, validate_image_references_preserved, summarize_validation_error
│   ├── normalize.py         # normalize_cjk_punctuation, normalize_placeholders, normalize_keywords_capitalization, fix_email_placeholder, fix_ocr_truncations, fix_word_boundary_redacted
│   ├── artifacts.py         # strip_prompt_artifacts, strip_inline_artifacts, strip_prompt_echo, strip_source_contamination, _is_terminology_echo
│   └── redacted.py          # mark_redacted_values + its regex patterns
└── translator.py            # Slimmed: orchestration only (~400 lines)
```

---

## Task 1: Extract LLM Client to `providers.py`

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/providers.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator.py

def test_providers_create_llm():
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.providers import create_llm
    llm = create_llm(model="test-model", api_key="test-key", base_url="http://localhost:8001/v1", temperature=0.0)
    assert llm is not None


def test_providers_create_json_llm():
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.providers import create_json_llm
    llm = create_json_llm(model="test-model", api_key="test-key", base_url="http://localhost:8001/v1", temperature=0.0)
    assert llm is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator.py::test_providers_create_llm -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.providers'`

**Step 3: Create `providers.py`**

```python
"""LLM client factory and retry logic for translation pipeline."""
from __future__ import annotations

import time
from typing import Any

import httpx
import openai
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import SecretStr

_MAX_RETRIES: int = 3
_BACKOFF_BASE: float = 30.0  # seconds
_TRANSIENT_EXCEPTIONS = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


def create_llm(
    model: str,
    api_key: str,
    base_url: str,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """Create a standard ChatOpenAI instance."""
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=temperature,
    )


def create_json_llm(
    model: str,
    api_key: str,
    base_url: str,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance with JSON response format."""
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=temperature,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _to_text(content: Any) -> str:
    """Extract plain text from LLM response content.

    Handles str, list of content blocks, and single content block dicts.
    Falls back to str() for unknown types.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") in ("text", None):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text))
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        return str(text).strip()
    return str(content).strip()


def invoke_with_retry(
    llm: ChatOpenAI,
    prompt: str,
    stage: str,
    system_prompt: str = "",
) -> str:
    """Call LLM with exponential backoff on transient failures.

    Note: qwen-mt-flash only supports user/assistant roles, so
    the system prompt is prepended to the human message.
    """
    if system_prompt:
        content = (
            f"[SYSTEM INSTRUCTIONS — DO NOT output these. Follow them silently.]\n"
            f"{system_prompt}\n"
            f"[END SYSTEM INSTRUCTIONS]\n\n"
            f"{prompt}"
        )
    else:
        content = prompt
    messages = [HumanMessage(content=content)]

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = llm.invoke(messages)
            return _to_text(response.content)
        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            delay = _BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "Stage {} attempt {}/{} failed: {}. Retrying in {:.0f}s",
                stage, attempt, _MAX_RETRIES, exc, delay,
            )
            if attempt < _MAX_RETRIES:
                time.sleep(delay)
    raise RuntimeError(f"Stage {stage} failed after {_MAX_RETRIES} attempts") from last_exc


def invoke_json_with_retry(
    llm: ChatOpenAI,
    prompt: str,
    stage: str,
    system_prompt: str = "",
) -> str:
    """Call LLM with JSON mode and exponential backoff on transient failures.

    Returns the raw JSON string from the LLM response.
    """
    if system_prompt:
        content = (
            f"[SYSTEM INSTRUCTIONS — DO NOT output these. Follow them silently.]\n"
            f"{system_prompt}\n"
            f"[END SYSTEM INSTRUCTIONS]\n\n"
            f"{prompt}"
        )
    else:
        content = prompt
    messages = [HumanMessage(content=content)]

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = llm.invoke(messages)
            return _to_text(response.content)
        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            delay = _BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "JSON stage {} attempt {}/{} failed: {}. Retrying in {:.0f}s",
                stage, attempt, _MAX_RETRIES, exc, delay,
            )
            if attempt < _MAX_RETRIES:
                time.sleep(delay)
    raise RuntimeError(f"JSON stage {stage} failed after {_MAX_RETRIES} attempts") from last_exc
```

**Step 4: Update `translator.py` to use `providers.py`**

Replace the `__init__` and helper methods in `MultiStageTranslator`:

```python
# In translator.py, update imports:
from .providers import (
    create_llm,
    create_json_llm,
    invoke_with_retry,
    invoke_json_with_retry,
    _to_text,
)

# In MultiStageTranslator.__init__:
def __init__(self, ctx: TranslationConfigContext):
    self._ctx = ctx
    self._llm = create_llm(ctx.model, ctx.api_key, ctx.base_url, ctx.temperature)
    self._json_llm = create_json_llm(ctx.model, ctx.api_key, ctx.base_url, ctx.temperature)

# Remove from MultiStageTranslator:
# - _to_text static method
# - _MAX_RETRIES, _BACKOFF_BASE, _TRANSIENT_EXCEPTIONS class vars
# - _invoke_with_retry method
# - _invoke_json_with_retry method

# Update all internal calls:
# self._invoke_with_retry(...) → invoke_with_retry(self._llm, ...)
# self._invoke_json_with_retry(...) → invoke_json_with_retry(self._json_llm, ...)
# self._to_text(...) → _to_text(...)
```

**Step 5: Run tests to verify**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/providers.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator.py
git commit -m "refactor(translate): extract LLM client factory and retry logic to providers.py"
```

---

## Task 2: Split `prompts.py` into stage-specific files

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts/__init__.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts/format.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts/terminology.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts/translate.py`
- Delete: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py`

**Step 1: Create the prompts sub-package**

First, rename old file:
```bash
mv backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py \
   backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts_old.py
mkdir backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts
```

**Step 2: Create `prompts/format.py`**

```python
"""Prompt templates for the document formatting/normalization stage."""
from __future__ import annotations


def get_prescan_prompt(source_text: str) -> str:
    """Build a prompt for LLM to identify and mark missing/redacted values."""
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
    """Generate prompt for the formatting/normalization stage."""
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
```

**Step 3: Create `prompts/terminology.py`**

```python
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
```

**Step 4: Create `prompts/translate.py`**

```python
"""Prompt templates for the translation and self-review stages."""
from __future__ import annotations


def get_translate_prompt(
    markdown_segment: str,
    terminology: str,
    prev_context: str = "",
    next_context: str = "",
) -> str:
    """Build the human message for translating one segment."""
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
    """Build the prompt for translating a full document in one call."""
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
    """Build a prompt for post-translation quality review and correction."""
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
```

**Step 5: Create `prompts/__init__.py`**

```python
"""LLM prompt templates for the translation pipeline.

Re-exports all prompt functions for backward compatibility.
"""
from .format import get_format_prompt, get_prescan_prompt
from .terminology import get_system_prompt_generation_prompt, get_terminology_prompt
from .translate import (
    get_full_document_translate_prompt,
    get_self_review_prompt,
    get_translate_prompt,
)

__all__ = [
    "get_format_prompt",
    "get_full_document_translate_prompt",
    "get_prescan_prompt",
    "get_self_review_prompt",
    "get_system_prompt_generation_prompt",
    "get_terminology_prompt",
    "get_translate_prompt",
]
```

**Step 6: Delete old prompts file and run tests**

```bash
rm backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts_old.py
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py -v
```

Expected: ALL PASS — imports still work via `from .prompts import ...` because `__init__.py` re-exports everything.

**Step 7: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts/
git rm backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts_old.py 2>/dev/null; true
git commit -m "refactor(translate): split prompts.py into stage-specific files under prompts/"
```

---

## Task 3: Split `validator.py` into focused modules

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/__init__.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/core.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/normalize.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/artifacts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/redacted.py`
- Delete: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator.py`

**Step 1: Create `validator/redacted.py`**

Contains `mark_redacted_values` and its regex patterns (moved from validator.py lines 588-629).

```python
"""Redacted value detection and marking for OCR-processed documents."""
from __future__ import annotations

import re


# Minimal patterns for obvious structural artifacts (empty brackets only).
_REDACTED_PATTERNS = [
    (re.compile(r"（\s+）"), "（[REDACTED]）"),
    (re.compile(r"\(\s+\)"), "([REDACTED])"),
]

# Generic CJK-gap detection: catches whitespace between CJK characters
# followed by common value indicators (units, counters, punctuation).
_CJK_GAP_PATTERNS = [
    (re.compile(r"([一-鿿])\s+([例个次名岁天月年期])"), r"\1 [REDACTED] \2"),
    (re.compile(r"([一-鿿])\s+([，。；：、])"), r"\1 [REDACTED]\2"),
    (re.compile(r"([一-鿿])\s+([一-鿿])(?=[，。；：、\s])"), r"\1 [REDACTED] \2"),
]


def mark_redacted_values(text: str) -> str:
    """Insert [REDACTED] markers where OCR values are missing.

    Uses a two-pass approach:
    1. LLM formatter (primary) - handles complex patterns in get_format_prompt
    2. Regex safety net (this function) - catches remaining CJK gaps
    """
    if not text:
        return text
    for pattern, replacement in _REDACTED_PATTERNS:
        text = pattern.sub(replacement, text)
    for pattern, replacement in _CJK_GAP_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\[REDACTED\]\s*\[REDACTED\]", "[REDACTED]", text)
    return text
```

**Step 2: Create `validator/artifacts.py`**

Contains all `strip_*` functions and `_is_terminology_echo` (moved from validator.py lines 193-365).

```python
"""Artifact stripping for LLM translation output."""
from __future__ import annotations

import re

from lingua import Language
from loguru import logger

from ..language_detector import _CJK_RE, _DETECTOR


def strip_source_contamination(translated: str, source_language: str = "unknown") -> str:
    """Strip source-language text from LLM translation output."""
    # [full implementation from validator.py lines 59-151]
    ...


def strip_prompt_artifacts(text: str) -> str:
    """Remove prompt instructions that the LLM echoed back."""
    # [full implementation from validator.py lines 241-265]
    ...


def strip_inline_artifacts(text: str) -> str:
    """Remove inline prompt injection markers and block delimiters."""
    # [full implementation from validator.py lines 268-280]
    ...


def strip_prompt_echo(text: str) -> str:
    """Strip LLM prompt echo by finding the last prompt marker."""
    # [full implementation from validator.py lines 305-342]
    ...


def _is_terminology_echo(text: str) -> bool:
    """Detect when the LLM echoed back the terminology map."""
    # [full implementation from validator.py lines 348-364]
    ...
```

**Step 3: Create `validator/normalize.py`**

Contains all `normalize_*`, `fix_*` functions (moved from validator.py lines 391-663).

```python
"""Text normalization and OCR artifact repair."""
from __future__ import annotations

import re

from loguru import logger


# [CJK_PUNCT_MAP, CJK_PUNCT_TABLE, normalize_cjk_punctuation from lines 392-423]
# [PLACEHOLDER_PATTERNS, normalize_placeholders from lines 427-466]
# [EMAIL patterns, fix_email_placeholder from lines 469-488]
# [OCR truncation patterns, fix_ocr_truncations from lines 492-525]
# [REDACTED word boundary patterns, fix_word_boundary_redacted from lines 528-577]
# [KEYWORDS_RE, normalize_keywords_capitalization from lines 580-663]
```

**Step 4: Create `validator/core.py`**

Contains `validate_translation_output`, `validate_segment`, `validate_image_references_preserved`, `summarize_validation_error` (moved from validator.py lines 13-56, 154-190, 370-388).

```python
"""Translation quality validation."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from lingua import Language
from loguru import logger

from ..language_detector import _CJK_RE, _DETECTOR


def validate_translation_output(source_text: str, translated_text: str) -> None:
    """Validate translated output quality."""
    # [full implementation from validator.py lines 13-48]
    ...


def summarize_validation_error(exc: Exception) -> str:
    """Extract a concise error summary from a validation exception."""
    # [full implementation from validator.py lines 51-56]
    ...


def validate_segment(source: str, translated: str) -> None:
    """Validate a single translated segment."""
    # [full implementation from validator.py lines 154-190]
    ...


_IMAGE_REF_RE = re.compile(r"!\[.*?\]\((.*?)\)")


def validate_image_references_preserved(source: str, translated: str) -> None:
    """Validate that all image references from source are preserved."""
    # [full implementation from validator.py lines 370-388]
    ...
```

**Step 5: Create `validator/__init__.py`**

```python
"""Translation quality validation and post-processing.

Re-exports all functions for backward compatibility.
"""
from .artifacts import (
    _is_terminology_echo,
    strip_inline_artifacts,
    strip_prompt_artifacts,
    strip_prompt_echo,
    strip_source_contamination,
)
from .core import (
    summarize_validation_error,
    validate_image_references_preserved,
    validate_segment,
    validate_translation_output,
)
from .normalize import (
    fix_email_placeholder,
    fix_ocr_truncations,
    fix_word_boundary_redacted,
    normalize_cjk_punctuation,
    normalize_keywords_capitalization,
    normalize_placeholders,
)
from .redacted import mark_redacted_values

# Re-export _IMAGE_REF_RE for backward compatibility (used in translator.py)
from .core import _IMAGE_REF_RE

__all__ = [
    "_IMAGE_REF_RE",
    "_is_terminology_echo",
    "fix_email_placeholder",
    "fix_ocr_truncations",
    "fix_word_boundary_redacted",
    "mark_redacted_values",
    "normalize_cjk_punctuation",
    "normalize_keywords_capitalization",
    "normalize_placeholders",
    "strip_inline_artifacts",
    "strip_prompt_artifacts",
    "strip_prompt_echo",
    "strip_source_contamination",
    "summarize_validation_error",
    "validate_image_references_preserved",
    "validate_segment",
    "validate_translation_output",
]
```

**Step 6: Delete old validator file and run tests**

```bash
rm backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator.py
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_validator.py -v
```

Expected: ALL PASS

**Step 7: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/
git rm backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator.py 2>/dev/null; true
git commit -m "refactor(translate): split validator.py into core/normalize/artifacts/redacted modules"
```

---

## Task 4: Extract block operations to `blocks.py`

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/blocks.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py`

**Step 1: Create `blocks.py`**

Extract from `translator.py`: `_BLOCK_SEP`, `_BLOCK_MARKER_RE`, `_is_predominantly_english`, `_SHORT_KW_CJK_RE`, `_is_short_keyword`, `_KW_MERGE_SEP`, `_merge_short_keywords`, `_split_merged_keywords`, `_join_blocks_with_markers`, `_split_by_markers`.

```python
"""Block-level merge, split, and marker operations for translation."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from loguru import logger

from ...contracts import ContentBlock
from .validator.redacted import mark_redacted_values
from .language_detector import _CJK_RE

_BLOCK_SEP = "\n\n«BLK»\n\n"
_BLOCK_MARKER_RE = re.compile(r"\[BLOCK_(\d+)\]")
_SHORT_KW_CJK_RE = re.compile(r"[一-鿿]")
_KW_MERGE_SEP = "；"


def is_predominantly_english(text: str) -> bool:
    """Check if text is predominantly English (low CJK ratio)."""
    cjk_count = len(_CJK_RE.findall(text))
    total = len(text.strip()) or 1
    return cjk_count / total < 0.05


def is_short_keyword(text: str) -> bool:
    """Check if text is a short isolated keyword (1-4 CJK chars)."""
    stripped = text.strip()
    if not stripped:
        return False
    cjk_chars = _SHORT_KW_CJK_RE.findall(stripped)
    return 1 <= len(cjk_chars) <= 4 and len(stripped) <= 10


def merge_short_keywords(
    non_empty: list[tuple[int, ContentBlock]],
) -> Tuple[
    list[tuple[int, ContentBlock]],
    Dict[int, int],
]:
    """Merge adjacent short keyword blocks into single blocks."""
    # [full implementation from translator.py lines 469-530]
    ...


def split_merged_keywords(
    translated_parts: list[str],
    merge_map: Dict[int, int],
) -> list[str]:
    """Split merged keyword blocks back into individual translations."""
    # [full implementation from translator.py lines 532-579]
    ...


def join_blocks_with_markers(
    non_empty: list[tuple[int, ContentBlock]],
) -> Tuple[str, list[int], list[str], Dict[int, str]]:
    """Join text/title blocks into one string with [BLOCK_N] markers."""
    # [full implementation from translator.py lines 582-631]
    ...


def split_by_markers(marked_text: str, n_expected: int) -> list[str]:
    """Split LLM output on [BLOCK_N] markers."""
    # [full implementation from translator.py lines 634-665]
    ...
```

**Step 2: Update `translator.py` to import from `blocks.py`**

```python
# Replace class-level references:
from .blocks import (
    _BLOCK_SEP,
    _BLOCK_MARKER_RE,
    is_predominantly_english,
    is_short_keyword,
    merge_short_keywords,
    split_merged_keywords,
    join_blocks_with_markers,
    split_by_markers,
)

# Update _translate_blocks to use module-level functions:
# self._merge_short_keywords(...) → merge_short_keywords(...)
# self._join_blocks_with_markers(...) → join_blocks_with_markers(...)
# etc.
```

**Step 3: Run tests**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator.py tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/blocks.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "refactor(translate): extract block merge/split/marker operations to blocks.py"
```

---

## Task 5: Extract post-processing to `postprocess.py`

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/postprocess.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py`

**Step 1: Create `postprocess.py`**

Extract from `translator.py`: `_trim_repetitive_content`, `_check_block_language`, `_deduplicate_bilingual_blocks`, `_flag_quality_issues`, `_build_translated_blocks`, `_fallback_block_text`, `compute_translation_drift`.

```python
"""Post-processing: dedup, quality flagging, language check, block building."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from loguru import logger

from ...contracts import (
    ContentBlock,
    SegmentDrift,
    TranslationSegment,
)
from .language_detector import _CJK_RE
from .validator.normalize import (
    fix_email_placeholder,
    fix_ocr_truncations,
    fix_word_boundary_redacted,
    normalize_cjk_punctuation,
    normalize_placeholders,
)
from .validator.artifacts import strip_inline_artifacts

# Pre-compiled patterns
_DOI_RE = re.compile(
    r"(?:DOI|doi)\s*[:\s：]*\d+\.\d+/"
    r"|https?://doi\.org/"
    r"|https?://dx\.doi\.org/"
)
_TRUNCATED_REF_RE = re.compile(
    r"(?:by et al\.)"
    r"|(?:In \d{1,2},\s*et al\.)"
    r"|(?:^|\.\s+)et al\.\s*\[\d+\]"
)
_TRUNCATED_YEAR_RE = re.compile(r"\bIn (\d{2}),\s")
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")
_HIRAGANA_KATAKANA_RE = re.compile(r"[ぁ-んァ-ヶ]")
_HANGUL_RE = re.compile(r"[가-힯]")

_UNTRANSLATED_BLOCK_RATIO = 0.40
_BLOCK_SOURCE_LANG_THRESHOLD = 0.15
_DEDUP_SIMILARITY_THRESHOLD = 0.75


def trim_repetitive_content(text: str) -> str:
    """Remove repetitive heading blocks from LLM output."""
    # [full implementation from translator.py lines 954-1023]
    ...


def check_block_language(
    blocks: list[ContentBlock],
    source_language: str,
) -> None:
    """Check translated blocks for remaining source-language text.

    Raises TranslationError if >40% of text/title blocks are still in source lang.
    """
    # [full implementation from translator.py lines 1383-1443]
    ...


def deduplicate_bilingual_blocks(
    blocks: list[ContentBlock],
) -> list[ContentBlock]:
    """Remove duplicate blocks from bilingual documents."""
    # [full implementation from translator.py lines 1449-1503]
    ...


def flag_quality_issues(blocks: list[ContentBlock]) -> int:
    """Flag blocks that need manual review due to quality issues."""
    # [full implementation from translator.py lines 1505-1543]
    ...


def build_translated_blocks(
    original_blocks: List[ContentBlock],
    segments: List[TranslationSegment],
    translated_text: str,
    text_block_indices: list[int] | None = None,
    aux_translations: dict[int, dict[str, Any]] | None = None,
) -> List[ContentBlock]:
    """Map translated text back to original block structure."""
    # [full implementation from translator.py lines 1177-1335]
    # Uses _BLOCK_SEP, _DOI_RE from blocks.py / this module
    ...


def fallback_block_text(
    block: ContentBlock,
    segments: List[TranslationSegment],
) -> str:
    """Fallback: find translated text via segment matching."""
    # [full implementation from translator.py lines 1337-1353]
    ...


def compute_translation_drift(
    source_segments: List[str],
    translated_parts: List[str],
) -> List[SegmentDrift]:
    """Compute character drift between source and translated segments."""
    # [full implementation from translator.py lines 1602-1639]
    ...
```

**Step 2: Update `translator.py` to import from `postprocess.py`**

```python
from .postprocess import (
    build_translated_blocks,
    check_block_language,
    compute_translation_drift,
    deduplicate_bilingual_blocks,
    flag_quality_issues,
    trim_repetitive_content,
)

# In run_pipeline():
# self._trim_repetitive_content(translated) → trim_repetitive_content(translated)
# self._check_block_language(...) → check_block_language(...)
# self._deduplicate_bilingual_blocks(...) → deduplicate_bilingual_blocks(...)
# self._flag_quality_issues(...) → flag_quality_issues(...)

# In translate_to_result():
# self._build_translated_blocks(...) → build_translated_blocks(...)
# MultiStageTranslator.compute_translation_drift(...) → compute_translation_drift(...)
```

**Step 3: Run full test suite**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/postprocess.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "refactor(translate): extract post-processing (dedup, quality, block building) to postprocess.py"
```

---

## Task 6: Clean up `translator.py` — final slim version

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py`

**Step 1: Verify translator.py is now slim**

After Tasks 1-5, `translator.py` should contain only:
- `TranslationError` exception
- `MultiStageTranslator` class with:
  - `__init__` (uses `providers.py`)
  - `_generate_system_prompt` (uses `prompts/`)
  - `extract_terminology` (uses `providers.py`)
  - `_extract_terminology_json_pairs` (uses `providers.py`)
  - `_parse_terminology` (static, stays — terminology parsing is translator-specific)
  - `_clean_terminology` (static, stays)
  - `_translate_blocks` (orchestrates blocks.py + providers.py)
  - `translate_segments` (orchestrates)
  - `_translate_one_segment` (orchestrates)
  - `_self_review` (orchestrates)
  - `_translate_auxiliary_blocks` (orchestrates)
  - `run_pipeline` (main entry)
  - `translate_to_result` (main entry)

Target: ~500-600 lines (down from 1640).

**Step 2: Verify all tests pass**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v`
Expected: ALL PASS

**Step 3: Run ruff check**

Run: `cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/`
Expected: No errors

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "refactor(translate): slim translator.py to pure orchestration (~500 lines)"
```

---

## Task 7: Update `__init__.py` and run full regression

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/__init__.py`

**Step 1: Update `__init__.py` with new module exports**

```python
"""Translation pipeline: language detection, multi-stage LLM translation, validation."""
from .blocks import (
    _BLOCK_SEP,
    is_short_keyword,
    merge_short_keywords,
    split_merged_keywords,
)
from .language_detector import detect_language, should_skip_translation
from .postprocess import (
    build_translated_blocks,
    compute_translation_drift,
    deduplicate_bilingual_blocks,
)
from .providers import create_llm, create_json_llm, invoke_with_retry
from .translator import MultiStageTranslator, TranslationError
from .validator import (
    mark_redacted_values,
    normalize_cjk_punctuation,
    normalize_placeholders,
    strip_prompt_artifacts,
    validate_segment,
    validate_translation_output,
)
```

**Step 2: Run full test suite**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v`
Expected: ALL PASS

**Step 3: Run ruff check on entire module**

Run: `cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/`
Expected: No errors

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/__init__.py
git commit -m "refactor(translate): update __init__.py with new module exports"
```

---

## Task 8: Update README.md

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/README.md`

**Step 1: Update the architecture diagram and module listing**

Update the `translate/` section of the README to reflect the new structure:

```
translate/
├── __init__.py          # Re-exports public API
├── base.py              # BaseTranslator ABC
├── language_detector.py # Language detection via lingua
├── providers.py         # LLM client factory + retry logic
├── blocks.py            # Block merge/split/marker operations
├── postprocess.py       # Dedup, quality flagging, language check, block building
├── prompts/             # Stage-specific prompt templates
│   ├── __init__.py
│   ├── format.py        # Formatting/normalization prompts
│   ├── terminology.py   # Terminology extraction prompts
│   └── translate.py     # Translation + self-review prompts
├── validator/           # Validation and post-processing
│   ├── __init__.py
│   ├── core.py          # Validation functions
│   ├── normalize.py     # Text normalization (punctuation, placeholders, OCR fix)
│   ├── artifacts.py     # Prompt artifact stripping
│   └── redacted.py      # Redacted value marking
└── translator.py        # MultiStageTranslator orchestration (~500 lines)
```

**Step 2: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/README.md
git commit -m "docs: update cross_lingual README with new translate/ module structure"
```

---

## Verification Checklist

After all tasks:

1. `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v` — ALL PASS
2. `cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/` — No errors
3. `translator.py` is ~500 lines (down from 1640)
4. `validator.py` is split into 4 focused modules
5. `prompts.py` is split into 3 stage-specific files
6. All external imports still work (backward compatible via `__init__.py` re-exports)
7. `workflow.py`, `persistence.py`, `router.py` — no changes needed (they import from translator/validator which re-export)

## Import Impact Analysis

| Caller | Old import | New import (if needed) |
|--------|-----------|----------------------|
| `workflow.py` | `from .cross_lingual.translate.translator import MultiStageTranslator, TranslationError` | No change |
| `persistence.py` | `from .cross_lingual.translate.translator import MultiStageTranslator` | No change |
| `router.py` | `from .cross_lingual.translate.language_detector import should_skip_translation` | No change |
| `formatter.py` | `from ..translate.prompts import get_format_prompt` | No change (re-exported) |
| All test files | Various imports from translator/validator/prompts | No change (re-exported) |
