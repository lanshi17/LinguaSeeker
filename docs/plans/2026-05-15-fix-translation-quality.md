# Fix Translation Quality: Image References & Structure Preservation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two translation quality bugs: (1) image references `![](images/xxx.jpg)` being stripped during translation, (2) outline structure diverging from original.

**Architecture:** Modify prompts in `prompts.py` to explicitly preserve image references and original heading structure. Add post-translation validation to detect image reference loss.

**Tech Stack:** Python, LLM prompt engineering

---

## Problem Analysis

### Bug 1: Image References Lost

**Evidence:**
```bash
# Original has 3 image references
grep -c "!\[\]" output/zh/GLA基因c.92C_A突变法布雷病家系1例/original.md
# Output: 3

# Translated has 0
grep -c "!\[\]" output/zh/GLA基因c.92C_A突变法布雷病家系1例/translated.md
# Output: 0
```

**Root cause:** `get_draft_prompt()` and `get_polish_prompt()` don't mention preserving image references. The LLM treats `![](images/xxx.jpg)` as content that can be omitted or rewritten.

### Bug 2: Outline Structure Divergence

**Evidence:**
```bash
# Original: only top-level headings
grep "^#" original.md
# # GLA基因c.92C>A突变法布雷病家系1例
# # 参 考 文 献
# # 《中华内科杂志》第十一届编辑委员会名单

# Translated: rich hierarchy added
grep "^#" translated.md
# # A Case of Fabry Disease...
# ## Abstract
# ## Keywords
# ## I. Case Presentation
# ### 1.1 Patient Information
# ... (many more)
```

**Root cause:** `get_structure_prompt()` says "Re-express only the logical structure needed for clear English rendering. Restore omitted subjects when necessary, split long clauses, make logical connectors explicit." This instructs the LLM to **add** structure that wasn't in the original.

---

## Task 1: Fix Image Reference Preservation in Draft Prompt

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py:49-66`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompt_image_preservation.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompt_image_preservation.py
"""Tests for image reference preservation in translation prompts."""
import re

from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
    get_draft_prompt,
    get_polish_prompt,
)


def test_draft_prompt_mentions_image_preservation():
    """Draft prompt should instruct LLM to preserve image references."""
    prompt = get_draft_prompt("test content", "terms", "structure")
    assert "image" in prompt.lower() or "![image]" in prompt or "![]" in prompt


def test_polish_prompt_mentions_image_preservation():
    """Polish prompt should instruct LLM to preserve image references."""
    prompt = get_polish_prompt("test content", "terms")
    assert "image" in prompt.lower() or "![image]" in prompt or "![]" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompt_image_preservation.py -v`
Expected: FAIL

**Step 3: Update `get_draft_prompt` to preserve image references**

```python
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
        "CRITICAL: Preserve ALL image references exactly as-is (e.g., "
        "![](images/xxx.jpg)). Do not remove, rewrite, or translate them.\n\n"
        f"TERMINOLOGY MAP:\n{terminology}\n\n"
        f"STRUCTURE PLAN:\n{structure_plan}\n\n"
        f"MARKDOWN SEGMENT:\n{markdown_segment}"
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompt_image_preservation.py::test_draft_prompt_mentions_image_preservation -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py
git add backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompt_image_preservation.py
git commit -m "fix: preserve image references in draft translation prompt"
```

---

## Task 2: Fix Image Reference Preservation in Polish Prompt

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py:69-79`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompt_image_preservation.py`

**Step 1: Update `get_polish_prompt` to preserve image references**

```python
def get_polish_prompt(draft: str, terminology: str) -> str:
    """Generate prompt for polishing the translated draft."""
    return (
        "POLISH_STAGE\n"
        "You are polishing biomedical English prose. Improve fluency for "
        "academic English while preserving markdown layout and scientific meaning. "
        "Do not alter biomedical literals or terminology mappings, and avoid "
        "obvious stock AI phrasing.\n\n"
        "CRITICAL: Preserve ALL image references exactly as-is (e.g., "
        "![](images/xxx.jpg)). Do not remove, rewrite, or translate them.\n\n"
        f"TERMINOLOGY MAP:\n{terminology}\n\n"
        f"DRAFT MARKDOWN:\n{draft}"
    )
```

**Step 2: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompt_image_preservation.py::test_polish_prompt_mentions_image_preservation -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py
git commit -m "fix: preserve image references in polish translation prompt"
```

---

## Task 3: Fix Structure Preservation in Structure Prompt

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py:35-47`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompt_structure_preservation.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompt_structure_preservation.py
"""Tests for structure preservation in translation prompts."""
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
    get_structure_prompt,
)


def test_structure_prompt_preserves_original_headings():
    """Structure prompt should instruct LLM to preserve original heading hierarchy."""
    prompt = get_structure_prompt("test content")
    # Should mention preserving original structure, not adding new structure
    assert "preserve" in prompt.lower() or "original" in prompt.lower()
    # Should NOT encourage adding headings
    assert "add headings" not in prompt.lower()
    assert "create sections" not in prompt.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompt_structure_preservation.py -v`
Expected: FAIL

**Step 3: Update `get_structure_prompt` to preserve original structure**

```python
def get_structure_prompt(markdown_content: str) -> str:
    """Generate prompt for the structure planning stage."""
    return (
        "STRUCTURE_STAGE\n"
        "You are a structure planner for non-English biomedical markdown. "
        "Analyze the document structure and create a plan for clear English rendering.\n\n"
        "CRITICAL RULES:\n"
        "- PRESERVE the original heading hierarchy exactly (# ## ### etc.)\n"
        "- Do NOT add new headings or sections that don't exist in the source\n"
        "- Do NOT reorganize or restructure the document\n"
        "- Only plan sentence-level improvements: restore omitted subjects, "
        "split long clauses, make logical connectors explicit\n"
        "- Preserve markdown structure such as bullet lists and tables\n\n"
        f"SOURCE DOCUMENT:\n{markdown_content}"
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompt_structure_preservation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts.py
git add backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompt_structure_preservation.py
git commit -m "fix: preserve original heading hierarchy in structure planning prompt"
```

---

## Task 4: Add Post-Translation Image Reference Validation

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator_image_check.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator_image_check.py
"""Tests for image reference validation in translated output."""
import pytest

from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator import (
    validate_image_references_preserved,
)


def test_validate_image_references_all_preserved():
    """Should pass when all image references are preserved."""
    source = "Text\n![](images/a.jpg)\nMore text\n![](images/b.jpg)"
    translated = "Translated text\n![](images/a.jpg)\nMore translated text\n![](images/b.jpg)"
    # Should not raise
    validate_image_references_preserved(source, translated)


def test_validate_image_references_some_missing():
    """Should raise when image references are missing in translation."""
    source = "Text\n![](images/a.jpg)\nMore text\n![](images/b.jpg)"
    translated = "Translated text\nMore translated text"
    with pytest.raises(ValueError, match="image"):
        validate_image_references_preserved(source, translated)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_validator_image_check.py -v`
Expected: FAIL (function doesn't exist)

**Step 3: Add validation function to `validator.py`**

```python
import re


def validate_image_references_preserved(source: str, translated: str) -> None:
    """Validate that all image references from source are preserved in translation.

    Args:
        source: Original markdown text.
        translated: Translated markdown text.

    Raises:
        ValueError: If image references are missing from translation.
    """
    image_pattern = re.compile(r"!\[.*?\]\((.*?)\)")
    source_images = set(image_pattern.findall(source))
    translated_images = set(image_pattern.findall(translated))

    missing = source_images - translated_images
    if missing:
        raise ValueError(
            f"Image references missing from translation: {missing}. "
            f"Source has {len(source_images)} images, translated has {len(translated_images)}."
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_validator_image_check.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator.py
git add backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator_image_check.py
git commit -m "feat: add image reference preservation validation"
```

---

## Task 5: Integrate Image Validation into Pipeline

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py:286-310`

**Step 1: Add import and validation call in `run_pipeline`**

```python
from .validator import summarize_validation_error, validate_translation_output, validate_image_references_preserved

# In run_pipeline method, after validation:
try:
    validate_image_references_preserved(formatted.formatted_markdown, translated)
except ValueError as exc:
    warnings.append(f"image_refs: {exc}")
    logger.warning("Image reference warning: {}", exc)
```

**Step 2: Run existing tests to verify no regression**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator_segmentation.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "feat: integrate image reference validation into translation pipeline"
```

---

## Task 6: End-to-End Test

**Files:**
- Script: `scripts/parse_and_translate.py`

**Step 1: Clear previous output**

```bash
rm -rf backend/output/*
```

**Step 2: Run the full pipeline**

```bash
cd backend && uv run python ../scripts/parse_and_translate.py 2>&1
```

**Step 3: Verify image references preserved**

```bash
# Check Chinese PDF with images
grep -c "!\[\]" output/zh/GLA基因c.92C_A突变法布雷病家系1例/original.md
grep -c "!\[\]" output/zh/GLA基因c.92C_A突变法布雷病家系1例/translated.md
# Both should show same count
```

**Step 4: Verify structure preserved**

```bash
# Compare heading hierarchy
grep "^#" output/zh/GLA基因c.92C_A突变法布雷病家系1例/original.md
grep "^#" output/zh/GLA基因c.92C_A突变法布雷病家系1例/translated.md
# Should have same hierarchy (translated versions of same headings)
```

**Step 5: Commit**

```bash
git commit -m "test: verify image references and structure preservation end-to-end"
```

---

## Verification Checklist

- [ ] Image references preserved: `grep -c "!\[\]"` matches between original.md and translated.md
- [ ] Heading hierarchy preserved: `grep "^#"` shows same structure (translated)
- [ ] All unit tests pass: `uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v`
- [ ] Translation quality improved (manual review)
