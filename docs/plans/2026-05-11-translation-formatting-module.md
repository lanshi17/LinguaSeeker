# Translation & Formatting Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a modular, layered translation and formatting pipeline that normalizes upstream `ParseResult` documents (any language) into authoritative formatted-original + English-translation outputs with sentence-level bbox tracking.

**Architecture:** Six-module pipeline orchestrated by LangGraph. Format-first approach: normalize source markdown → detect language → multi-stage translation (terminology → structure → draft → polish → review) → validate. All LLM calls use the existing `TranslationConfig` (MT_*). File I/O delegated to `rust_io.files`. Token-budgeted segmentation (8192) applied to both formatting and translation stages.

**Tech Stack:** Python 3.12+, LangGraph, LangChain, LangSmith, loguru, pydantic, `rust_io.files`, `lingua-language-detector`

---

## Module Structure

```
backend/src/core/cross_lingual_process_and_extract_evidence/
├── __init__.py
├── contracts.py          # All data types (Pydantic models, dataclasses)
├── prompts.py            # LLM prompt templates (inline)
├── language_detector.py  # Language detection + skip logic
├── segmenter.py          # Token-budgeted text segmentation
├── formatter.py          # Source markdown normalization + bbox tracking
├── validator.py          # Translation quality validation + assessment
└── workflow.py           # LangGraph pipeline orchestration + public service
```

---

### Task 1: Data Contracts

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/__init__.py
# (empty)
```

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py
from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    BboxPoint,
    SentenceRegion,
    FormattedDocument,
    TranslationSegment,
    TranslationResult,
)


def test_bbox_point_creation():
    pt = BboxPoint(page=1, offset=100)
    assert pt.page == 1
    assert pt.offset == 100


def test_sentence_region_span():
    region = SentenceRegion(
        page=1,
        start_offset=0,
        end_offset=50,
        text="Hello world.",
    )
    assert region.span == 50


def test_formatted_document_from_pages():
    pages = [
        {"page_number": 1, "markdown": "First page content."},
        {"page_number": 2, "markdown": "Second page content."},
    ]
    doc = FormattedDocument.from_pages(pages, formatted_markdown="First page content.\n\nSecond page content.")
    assert doc.source_language == ""
    assert len(doc.sentences) == 0
    assert "First page" in doc.formatted_markdown


def test_translation_segment_defaults():
    seg = TranslationSegment(
        index=0,
        source_text="Original text.",
        translated_text="Translated text.",
    )
    assert seg.source_bbox is None
    assert seg.translated_bbox is None


def test_translation_result_fields():
    result = TranslationResult(
        formatted_original="原文",
        translated_english="English",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )
    assert result.formatted_original == "原文"
    assert result.translated_english == "English"
    assert result.source_language == "zh"
```

**Step 2: Run test to verify it fails**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/__init__.py
```

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py
"""Data contracts for translation and formatting pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Bbox tracking ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BboxPoint:
    """Position reference: page number + character offset within page."""

    page: int
    offset: int


@dataclass(frozen=True)
class SentenceRegion:
    """Sentence-level position tracking within a document."""

    page: int
    start_offset: int
    end_offset: int
    text: str

    @property
    def span(self) -> int:
        return self.end_offset - self.start_offset


# ── Formatting output ────────────────────────────────────────────────────


@dataclass
class FormattedDocument:
    """Output of the format/normalize stage.

    ``formatted_markdown`` is the authoritative source-language document.
    ``sentences`` tracks each sentence's origin for bbox mapping.
    """

    formatted_markdown: str
    sentences: List[SentenceRegion] = field(default_factory=list)
    source_language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_pages(
        cls,
        pages: List[Dict[str, Any]],
        formatted_markdown: str,
        source_language: str = "",
    ) -> FormattedDocument:
        """Build from upstream page dicts (``ParseResult.pages`` serialized)."""
        return cls(
            formatted_markdown=formatted_markdown,
            source_language=source_language,
            metadata={"page_count": len(pages)},
        )


# ── Translation output ───────────────────────────────────────────────────


@dataclass
class TranslationSegment:
    """One translated segment with its bbox mapping back to the formatted source."""

    index: int
    source_text: str
    translated_text: str
    source_bbox: Optional[SentenceRegion] = None
    translated_bbox: Optional[SentenceRegion] = None


@dataclass
class TranslationResult:
    """Final output of the full format → translate pipeline.

    ``formatted_original`` — the authoritative source-language document.
    ``translated_english`` — the authoritative English document.
    """

    formatted_original: str
    translated_english: str
    source_language: str
    terminology_map: Dict[str, str]
    translation_warnings: List[str]
    sentences: List[SentenceRegion]
    segments: List[TranslationSegment]
```

**Step 4: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/__init__.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/__init__.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py
git commit -m "feat(cross-lingual): add data contracts for translation pipeline"
```

---

### Task 2: Prompt Templates

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py
from src.core.cross_lingual_process_and_extract_evidence.prompts import (
    get_terminology_prompt,
    get_structure_prompt,
    get_draft_prompt,
    get_polish_prompt,
    get_review_prompt,
    get_format_prompt,
)


def test_terminology_prompt_contains_source():
    prompt = get_terminology_prompt("Some source text about genes.")
    assert "genes" in prompt
    assert "TERMINOLOGY" in prompt.upper() or "terminology" in prompt.lower()


def test_structure_prompt_contains_source():
    prompt = get_structure_prompt("Some source text.")
    assert "Some source text" in prompt


def test_draft_prompt_contains_all_inputs():
    prompt = get_draft_prompt("segment", "term_map", "structure_plan")
    assert "segment" in prompt
    assert "term_map" in prompt
    assert "structure_plan" in prompt


def test_polish_prompt_contains_draft():
    prompt = get_polish_prompt("draft text", "terminology")
    assert "draft text" in prompt


def test_review_prompt_contains_both_texts():
    prompt = get_review_prompt("source", "translated")
    assert "source" in prompt
    assert "translated" in prompt


def test_format_prompt_contains_markdown():
    prompt = get_format_prompt("# Title\n\nSome content.")
    assert "Title" in prompt
    assert "content" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/prompts.py
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
```

**Step 4: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/prompts.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py
git commit -m "feat(cross-lingual): add LLM prompt templates for translation pipeline"
```

---

### Task 3: Language Detector

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/language_detector.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py`

**Prerequisite:** Add `lingua-language-detector` to project dependencies.

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv add lingua-language-detector
```

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py
import pytest
from src.core.cross_lingual_process_and_extract_evidence.language_detector import (
    detect_language,
    should_skip_translation,
)


def test_detect_english():
    lang = detect_language("The patient presented with a novel variant in the BRCA1 gene.")
    assert lang == "en"


def test_detect_chinese():
    lang = detect_language("该患者携带BRCA1基因的新变异。")
    assert lang == "zh"


def test_detect_japanese():
    lang = detect_language("患者はBRCA1遺伝子の新規変異を呈した。")
    assert lang == "ja"


def test_skip_translation_for_english():
    assert should_skip_translation("This is an English document about genetics.") is True


def test_no_skip_for_chinese():
    assert should_skip_translation("这是一份关于遗传学的中文文档。") is False


def test_skip_translation_for_empty():
    assert should_skip_translation("") is False
    assert should_skip_translation("   ") is False
```

**Step 2: Run test to verify it fails**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/language_detector.py
"""Language detection and translation skip logic."""
from __future__ import annotations

import re

from lingua import Language, LanguageDetectorBuilder

_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()

_CJK_RE = re.compile(r"[㐀-鿿぀-ヿ가-힯]")

_LANG_MAP = {
    Language.ENGLISH: "en",
    Language.CHINESE: "zh",
    Language.JAPANESE: "ja",
    Language.KOREAN: "ko",
    Language.FRENCH: "fr",
    Language.GERMAN: "de",
    Language.SPANISH: "es",
    Language.PORTUGUESE: "pt",
    Language.RUSSIAN: "ru",
    Language.ARABIC: "ar",
}


def detect_language(text: str, sample_size: int = 4000) -> str:
    """Detect the primary language of ``text``.

    Returns ISO 639-1 code (e.g. ``"en"``, ``"zh"``).
    Returns ``"unknown"`` if detection confidence is too low.
    """
    sample = str(text or "").strip()[:sample_size]
    if not sample:
        return "unknown"
    detected = _DETECTOR.detect_language_of(sample)
    if detected is None:
        return "unknown"
    return _LANG_MAP.get(detected, detected.iso_code_639_1.name.lower())


def should_skip_translation(text: str) -> bool:
    """Return ``True`` if the text is already English or empty."""
    sample = str(text or "").strip()
    if not sample:
        return False
    if _CJK_RE.search(sample):
        return False
    lang = detect_language(sample)
    return lang == "en"
```

**Step 4: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/language_detector.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py
git commit -m "feat(cross-lingual): add language detection with lingua"
```

---

### Task 4: Text Segmenter

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/segmenter.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py
from src.core.cross_lingual_process_and_extract_evidence.segmenter import (
    estimate_tokens,
    segment_text,
)


def test_estimate_tokens_ascii():
    assert estimate_tokens("hello world") > 0


def test_estimate_tokens_cjk():
    assert estimate_tokens("你好世界") > 0


def test_segment_text_short():
    text = "Short sentence."
    segments = segment_text(text, max_tokens=8192)
    assert len(segments) == 1
    assert segments[0] == text


def test_segment_text_multiple_paragraphs():
    para1 = "First paragraph with enough content to be its own segment."
    para2 = "Second paragraph with enough content to be its own segment."
    text = f"{para1}\n\n{para2}"
    segments = segment_text(text, max_tokens=20)
    assert len(segments) >= 2


def test_segment_text_preserves_structure():
    text = "# Heading\n\nParagraph one.\n\nParagraph two."
    segments = segment_text(text, max_tokens=8192)
    assert len(segments) == 1
    assert "# Heading" in segments[0]
```

**Step 2: Run test to verify it fails**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/segmenter.py
"""Token-budgeted text segmentation for LLM context windows."""
from __future__ import annotations

import re
from typing import List, Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ASCII chars / 4, CJK chars count as 1 each."""
    if not text:
        return 0
    ascii_chars = sum(1 for ch in text if ch.isascii())
    non_ascii_chars = len(text) - ascii_chars
    return int(ascii_chars / 4 + non_ascii_chars)


def _split_paragraph(
    paragraph: str,
    max_tokens: int,
    max_chars: Optional[int] = None,
) -> List[str]:
    """Split one paragraph into chunks that fit within the token budget."""

    def fits(text: str) -> bool:
        if estimate_tokens(text) > max_tokens:
            return False
        if max_chars is not None and len(text) > max_chars:
            return False
        return True

    if fits(paragraph):
        return [paragraph]

    sentences = [s for s in re.split(r"(?<=[。！？.!?])\s+", paragraph.strip()) if s]
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if fits(candidate):
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if fits(sentence):
            current = sentence
            continue
        # Sentence too long — hard split
        chunk_size = max_chars if max_chars is not None else max_tokens * 4
        chunk_size = max(1, chunk_size)
        start = 0
        while start < len(sentence):
            end = min(len(sentence), start + chunk_size)
            chunks.append(sentence[start:end].strip())
            start = end

    if current:
        chunks.append(current)
    return chunks


def segment_text(
    text: str,
    max_tokens: int = 8192,
    prompt_overhead_tokens: int = 0,
) -> List[str]:
    """Segment ``text`` into chunks that fit within ``max_tokens``.

    Splits on paragraph boundaries first, then on sentences if needed.
    ``prompt_overhead_tokens`` reduces the effective budget per segment.
    """
    effective_max = max(1, max_tokens - prompt_overhead_tokens - 20)
    max_chars = effective_max * 4

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paragraph_units: List[str] = []
    for para in paragraphs:
        paragraph_units.extend(_split_paragraph(para, effective_max, max_chars))

    segments: List[str] = []
    current = ""
    for unit in paragraph_units:
        candidate = unit if not current else f"{current}\n\n{unit}"
        if estimate_tokens(candidate) <= effective_max and (
            max_chars is None or len(candidate) <= max_chars
        ):
            current = candidate
            continue
        if current:
            segments.append(current)
        current = unit

    if current:
        segments.append(current)
    return segments
```

**Step 4: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/segmenter.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py
git commit -m "feat(cross-lingual): add token-budgeted text segmenter"
```

---

### Task 5: Formatter

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/formatter.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py
from src.core.cross_lingual_process_and_extract_evidence.formatter import (
    extract_sentences,
    build_page_offset_map,
    format_markdown,
)
from src.core.cross_lingual_process_and_extract_evidence.contracts import FormattedDocument


def test_extract_sentences_basic():
    text = "First sentence. Second sentence."
    sentences = extract_sentences(text)
    assert len(sentences) == 2
    assert sentences[0].text == "First sentence."
    assert sentences[1].text == "Second sentence."


def test_extract_sentences_with_page_map():
    text = "Hello world. Goodbye world."
    page_map = {0: 1, 13: 1}  # char offset -> page number
    sentences = extract_sentences(text, page_map)
    assert all(s.page == 1 for s in sentences)


def test_build_page_offset_map():
    pages = [
        {"page_number": 1, "markdown": "Page one content."},
        {"page_number": 2, "markdown": "Page two content."},
    ]
    offset_map = build_page_offset_map(pages)
    assert 0 in offset_map
    assert offset_map[0] == 1


def test_format_markdown_returns_formatted_document():
    pages = [
        {"page_number": 1, "markdown": "Some content about genes."},
    ]
    result = format_markdown(pages)
    assert isinstance(result, FormattedDocument)
    assert result.formatted_markdown != ""
    assert result.metadata["page_count"] == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/formatter.py
"""Source document formatting and normalization with bbox tracking."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from .contracts import FormattedDocument, SentenceRegion
from .segmenter import estimate_tokens, segment_text


def build_page_offset_map(pages: List[Dict[str, Any]]) -> Dict[int, int]:
    """Build a mapping from character offset to page number.

    Returns a dict where keys are character offsets in the concatenated
    markdown and values are the corresponding page numbers.
    """
    offset_map: Dict[int, int] = {}
    offset = 0
    for page in pages:
        page_number = page.get("page_number", 0)
        offset_map[offset] = page_number
        markdown = page.get("markdown", "")
        offset += len(markdown) + 2  # +2 for "\n\n" joiner
    return offset_map


def _resolve_page(offset: int, page_map: Dict[int, int]) -> int:
    """Resolve character offset to page number via the offset map."""
    if not page_map:
        return 0
    best_page = 0
    best_offset = -1
    for map_offset, page_num in page_map.items():
        if map_offset <= offset and map_offset > best_offset:
            best_offset = map_offset
            best_page = page_num
    return best_page


def extract_sentences(
    text: str,
    page_offset_map: Optional[Dict[int, int]] = None,
) -> List[SentenceRegion]:
    """Split text into sentences and track their positions.

    Uses sentence-ending punctuation as delimiters. Each sentence
    records its page number (via ``page_offset_map``) and character
    offsets within ``text``.
    """
    if not text.strip():
        return []

    sentences: List[SentenceRegion] = []
    # Split on sentence boundaries (CJK + Western punctuation)
    pattern = re.compile(r"(?<=[。！？.!?])\s*")
    current_offset = 0

    for part in pattern.split(text):
        part = part.strip()
        if not part:
            current_offset += len(part) + 1
            continue

        # Find the actual offset of this part in the original text
        idx = text.find(part, current_offset)
        if idx == -1:
            idx = current_offset

        page = _resolve_page(idx, page_offset_map) if page_offset_map else 0
        sentences.append(
            SentenceRegion(
                page=page,
                start_offset=idx,
                end_offset=idx + len(part),
                text=part,
            )
        )
        current_offset = idx + len(part)

    return sentences


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive blank lines and strip trailing whitespace."""
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fix_markdown_headings(text: str) -> str:
    """Ensure markdown headings have proper spacing."""
    text = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", text, flags=re.MULTILINE)
    return text


def format_markdown(
    pages: List[Dict[str, Any]],
    raw_markdown: str = "",
) -> FormattedDocument:
    """Normalize and format the source document.

    Joins per-page markdown, cleans OCR artifacts, normalizes structure,
    and tracks sentence-level positions for bbox mapping.
    """
    if not raw_markdown:
        raw_markdown = "\n\n".join(
            p.get("markdown", "") for p in pages
        )

    # Basic normalization
    formatted = _normalize_whitespace(raw_markdown)
    formatted = _fix_markdown_headings(formatted)

    # Build bbox tracking
    page_offset_map = build_page_offset_map(pages)
    sentences = extract_sentences(formatted, page_offset_map)

    logger.info(
        "Formatted document: {} chars, {} sentences, {} pages",
        len(formatted),
        len(sentences),
        len(pages),
    )

    return FormattedDocument(
        formatted_markdown=formatted,
        sentences=sentences,
        metadata={"page_count": len(pages)},
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/formatter.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py
git commit -m "feat(cross-lingual): add markdown formatter with bbox tracking"
```

---

### Task 6: Translation Validator

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/validator.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator.py
import pytest
from src.core.cross_lingual_process_and_extract_evidence.validator import (
    validate_translation_output,
    summarize_validation_error,
)


def test_validate_empty_translation():
    with pytest.raises(ValueError, match="empty"):
        validate_translation_output("source text", "")


def test_validate_cjk_heavy_output():
    cjk_text = "这是一段中文文本，超过百分之十的CJK字符。" * 5
    with pytest.raises(ValueError, match="non_english"):
        validate_translation_output("source", cjk_text)


def test_validate_unchanged_text():
    source = "This text should not be identical to the translation output."
    with pytest.raises(ValueError, match="unchanged"):
        validate_translation_output(source, source)


def test_validate_good_translation():
    source = "该患者携带BRCA1基因的新变异，导致蛋白质功能丧失。"
    translated = "The patient carries a novel variant in the BRCA1 gene, resulting in loss of protein function."
    # Should not raise
    validate_translation_output(source, translated)


def test_summarize_validation_error():
    exc = ValueError("translation_validation_failed: empty")
    summary = summarize_validation_error(exc)
    assert "empty" in summary


def test_summarize_unknown_error():
    exc = ValueError("something else")
    summary = summarize_validation_error(exc)
    assert "something else" in summary
```

**Step 2: Run test to verify it fails**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_validator.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/validator.py
"""Translation quality validation and assessment."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from lingua import Language, LanguageDetectorBuilder

_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()
_CJK_RE = re.compile(r"[㐀-鿿぀-ヿ가-힯]")


def validate_translation_output(source_text: str, translated_text: str) -> None:
    """Validate translated output quality.

    Raises ``ValueError`` with a ``translation_validation_failed:`` prefix
    if any check fails.
    """
    source = str(source_text or "").strip()
    translated = str(translated_text or "").strip()

    if not translated:
        raise ValueError("translation_validation_failed: empty")

    # Check CJK ratio — if >10% CJK, likely not translated
    cjk_count = len(_CJK_RE.findall(translated))
    if cjk_count and len(translated) > 0 and cjk_count / len(translated) > 0.10:
        raise ValueError("translation_validation_failed: non_english_output")

    # Check if translation is essentially unchanged from source
    ratio = SequenceMatcher(None, source.lower(), translated.lower()).ratio()
    if source and ratio >= 0.85:
        raise ValueError("translation_validation_failed: unchanged")

    # Check detected language of output
    detected = _DETECTOR.detect_language_of(translated[:4000])
    if detected is not None and detected != Language.ENGLISH:
        raise ValueError("translation_validation_failed: non_english_output")


def summarize_validation_error(exc: Exception) -> str:
    """Extract a concise error summary from a validation exception."""
    message = str(exc or "").strip()
    if message.startswith("translation_validation_failed:"):
        return message
    return f"translation_validation_failed: {message or 'unknown'}"
```

**Step 4: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_validator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/validator.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator.py
git commit -m "feat(cross-lingual): add translation quality validator"
```

---

### Task 7: LangGraph Workflow & Public Service

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py`

This is the orchestration layer — the LangGraph pipeline and the public `TranslationService` API.

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    FormattedDocument,
    TranslationResult,
)
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService


@pytest.fixture
def mock_config():
    """Minimal mock config for TranslationService."""
    cfg = MagicMock()
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001/v1"
    cfg.translation.model = "test-model"
    return cfg


@pytest.fixture
def sample_pages():
    return [
        {"page_number": 1, "markdown": "The patient carries a novel BRCA1 variant."},
    ]


def test_service_init(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._cfg == mock_config


def test_service_build_llm(mock_config):
    service = TranslationService(cfg=mock_config)
    llm = service._build_llm()
    assert llm is not None
```

**Step 2: Run test to verify it fails**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py
"""LangGraph pipeline orchestration and public translation service."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from loguru import logger
from pydantic import SecretStr

from .contracts import (
    FormattedDocument,
    SentenceRegion,
    TranslationResult,
    TranslationSegment,
)
from .formatter import format_markdown
from .language_detector import detect_language, should_skip_translation
from .prompts import (
    get_draft_prompt,
    get_format_prompt,
    get_polish_prompt,
    get_review_prompt,
    get_structure_prompt,
    get_terminology_prompt,
)
from .segmenter import estimate_tokens, segment_text
from .validator import summarize_validation_error, validate_translation_output


# ── Type aliases ─────────────────────────────────────────────────────────

PipelineState = Dict[str, Any]


# ── Service ──────────────────────────────────────────────────────────────


class TranslationService:
    """Public API for the translation and formatting pipeline.

    Usage::

        from src.core.config import get_config
        from src.core.cross_lingual_process_and_extract_evidence.workflow import (
            TranslationService,
        )

        cfg = get_config()
        service = TranslationService(cfg=cfg)
        result = await service.run(parse_result_pages)
    """

    def __init__(self, cfg: Any):
        self._cfg = cfg

    def _build_llm(self) -> ChatOpenAI:
        """Build a ChatOpenAI client from TranslationConfig (MT_*)."""
        return ChatOpenAI(
            model=self._cfg.translation.model,
            api_key=SecretStr(self._cfg.translation.api_key),
            base_url=self._cfg.translation.base_url,
            temperature=0.0,
        )

    @staticmethod
    def _to_text(content: Any) -> str:
        """Normalize LangChain message content to plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts).strip()
        if isinstance(content, dict):
            if content.get("type") == "text":
                return str(content.get("text", "")).strip()
            return str(content.get("text", content.get("content", ""))).strip()
        return str(content).strip()

    # ── Pipeline nodes ───────────────────────────────────────────────────

    def _node_format(self, state: PipelineState) -> PipelineState:
        """Stage 1: Normalize and format the source document."""
        logger.info("Stage: format")
        pages = state["pages"]
        formatted = format_markdown(pages)
        state["formatted"] = formatted
        state["source_language"] = formatted.source_language or detect_language(
            formatted.formatted_markdown
        )
        return state

    def _node_detect_language(self, state: PipelineState) -> PipelineState:
        """Stage 2: Detect language and decide if translation is needed."""
        logger.info("Stage: detect_language")
        text = state["formatted"].formatted_markdown
        lang = state.get("source_language") or detect_language(text)
        state["source_language"] = lang
        state["needs_translation"] = not should_skip_translation(text)
        logger.info("Detected language: {}, needs_translation: {}", lang, state["needs_translation"])
        return state

    def _node_terminology(self, state: PipelineState) -> PipelineState:
        """Stage 3a: Extract bilingual terminology map."""
        logger.info("Stage: terminology")
        llm = self._build_llm()
        text = state["formatted"].formatted_markdown
        response = llm.invoke([HumanMessage(content=get_terminology_prompt(text))])
        state["terminology"] = self._to_text(response.content)
        return state

    def _node_structure(self, state: PipelineState) -> PipelineState:
        """Stage 3b: Plan document structure for English rendering."""
        logger.info("Stage: structure")
        llm = self._build_llm()
        text = state["formatted"].formatted_markdown
        response = llm.invoke([HumanMessage(content=get_structure_prompt(text))])
        state["structure_plan"] = self._to_text(response.content)
        return state

    def _node_draft(self, state: PipelineState) -> PipelineState:
        """Stage 3c: Translate each segment with terminology + structure guidance."""
        logger.info("Stage: draft")
        llm = self._build_llm()
        text = state["formatted"].formatted_markdown
        terminology = state.get("terminology", "")
        structure_plan = state.get("structure_plan", "")

        # Calculate prompt overhead
        overhead = estimate_tokens(get_draft_prompt("", terminology, structure_plan))
        segments = segment_text(text, max_tokens=8192, prompt_overhead_tokens=overhead)

        translated_segments: List[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = get_draft_prompt(segment, terminology, structure_plan)
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                content = self._to_text(response.content)
                translated_segments.append(content)
                logger.info("Draft segment {}/{} done", idx, len(segments))
            except Exception as e:
                logger.error("Draft segment {}/{} failed: {}", idx, len(segments), e)
                raise RuntimeError(f"Translation segment {idx} failed") from e

        state["draft"] = "\n\n".join(translated_segments)
        state["segments"] = segments
        return state

    def _node_polish(self, state: PipelineState) -> PipelineState:
        """Stage 3d: Polish the draft for academic English fluency."""
        logger.info("Stage: polish")
        draft = state.get("draft", "")
        if not draft:
            state["polished"] = ""
            return state

        llm = self._build_llm()
        terminology = state.get("terminology", "")
        response = llm.invoke(
            [HumanMessage(content=get_polish_prompt(draft, terminology))]
        )
        polished = self._to_text(response.content)
        state["polished"] = polished or draft
        return state

    def _node_review(self, state: PipelineState) -> PipelineState:
        """Stage 3e: Review translation against source for gaps."""
        logger.info("Stage: review")
        source = state["formatted"].formatted_markdown
        translated = state.get("polished") or state.get("draft", "")
        if not translated:
            state["review"] = ""
            return state

        llm = self._build_llm()
        response = llm.invoke(
            [HumanMessage(content=get_review_prompt(source, translated))]
        )
        state["review"] = self._to_text(response.content)
        return state

    def _node_validate(self, state: PipelineState) -> PipelineState:
        """Stage 4: Validate translation quality."""
        logger.info("Stage: validate")
        source = state["formatted"].formatted_markdown
        translated = state.get("polished") or state.get("draft", "")
        warnings: List[str] = list(state.get("warnings", []))

        try:
            validate_translation_output(source, translated)
        except Exception as exc:
            warnings.append(summarize_validation_error(exc))
            logger.warning("Translation validation warning: {}", warnings[-1])
            # Fallback to draft if polish failed validation
            if translated != state.get("draft", ""):
                try:
                    validate_translation_output(source, state.get("draft", ""))
                    translated = state["draft"]
                    warnings.append("fell_back_to_draft")
                except Exception:
                    pass

        state["final_translated"] = translated
        state["warnings"] = warnings
        return state

    # ── Routing ──────────────────────────────────────────────────────────

    @staticmethod
    def _route_after_detect(state: PipelineState) -> str:
        if state.get("needs_translation", True):
            return "terminology"
        return "skip_translate"

    def _node_skip_translate(self, state: PipelineState) -> PipelineState:
        """No-op node for English documents — no translation needed."""
        logger.info("Document is already English, skipping translation")
        text = state["formatted"].formatted_markdown
        state["terminology"] = ""
        state["structure_plan"] = ""
        state["draft"] = text
        state["polished"] = text
        state["review"] = ""
        state["final_translated"] = text
        state["warnings"] = []
        state["segments"] = []
        return state

    # ── Build graph ──────────────────────────────────────────────────────

    def _build_graph(self) -> Any:
        """Construct the LangGraph pipeline."""
        graph = StateGraph(dict)

        graph.add_node("format", self._node_format)
        graph.add_node("detect_language", self._node_detect_language)
        graph.add_node("terminology", self._node_terminology)
        graph.add_node("structure", self._node_structure)
        graph.add_node("draft", self._node_draft)
        graph.add_node("polish", self._node_polish)
        graph.add_node("review", self._node_review)
        graph.add_node("validate", self._node_validate)
        graph.add_node("skip_translate", self._node_skip_translate)

        graph.set_entry_point("format")
        graph.add_edge("format", "detect_language")
        graph.add_conditional_edges(
            "detect_language",
            self._route_after_detect,
            {
                "terminology": "terminology",
                "skip_translate": "skip_translate",
            },
        )
        graph.add_edge("terminology", "structure")
        graph.add_edge("structure", "draft")
        graph.add_edge("draft", "polish")
        graph.add_edge("polish", "review")
        graph.add_edge("review", "validate")
        graph.add_edge("validate", END)
        graph.add_edge("skip_translate", END)

        return graph.compile()

    # ── Public API ───────────────────────────────────────────────────────

    async def run(
        self,
        pages: List[Dict[str, Any]],
    ) -> TranslationResult:
        """Run the full format → translate pipeline.

        Args:
            pages: List of page dicts from ``ParseResult.pages``.
                   Each must have ``page_number`` and ``markdown`` keys.

        Returns:
            ``TranslationResult`` with formatted original, English translation,
            terminology map, bbox mappings, and metadata.
        """
        logger.info("Starting translation pipeline for {} pages", len(pages))

        initial_state: PipelineState = {
            "pages": pages,
            "formatted": None,
            "source_language": "",
            "needs_translation": True,
            "terminology": "",
            "structure_plan": "",
            "draft": "",
            "polished": "",
            "review": "",
            "final_translated": "",
            "warnings": [],
            "segments": [],
        }

        graph = self._build_graph()

        # LangGraph invoke (sync) — wrap in executor for async context
        try:
            loop = asyncio.get_running_loop()
            final_state = await loop.run_in_executor(
                None, graph.invoke, initial_state
            )
        except RuntimeError:
            final_state = graph.invoke(initial_state)

        if not isinstance(final_state, dict):
            raise RuntimeError("Pipeline returned non-dict state")

        formatted: FormattedDocument = final_state["formatted"]

        # Build translation segments with bbox mapping
        source_segments = final_state.get("segments", [])
        translated_text = final_state.get("final_translated", "")
        translated_sentences = translated_text.split("\n\n") if translated_text else []

        tr_segments: List[TranslationSegment] = []
        for idx, src_seg in enumerate(source_segments):
            src_bbox = None
            # Find matching sentence in formatted sentences
            for sent in formatted.sentences:
                if sent.text.strip() in src_seg.strip() or src_seg.strip() in sent.text:
                    src_bbox = sent
                    break

            tr_segments.append(
                TranslationSegment(
                    index=idx,
                    source_text=src_seg,
                    translated_text=translated_sentences[idx] if idx < len(translated_sentences) else "",
                    source_bbox=src_bbox,
                )
            )

        result = TranslationResult(
            formatted_original=formatted.formatted_markdown,
            translated_english=translated_text,
            source_language=final_state.get("source_language", "unknown"),
            terminology_map={},  # TODO: parse terminology string into map
            translation_warnings=final_state.get("warnings", []),
            sentences=formatted.sentences,
            segments=tr_segments,
        )

        logger.info(
            "Translation pipeline complete: {} sentences, {} segments, lang={}",
            len(result.sentences),
            len(result.segments),
            result.source_language,
        )

        return result


    def run_sync(
        self,
        pages: List[Dict[str, Any]],
    ) -> TranslationResult:
        """Synchronous wrapper for ``run()``."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(pages))
        raise RuntimeError(
            "run_sync() cannot be called from within a running event loop. "
            "Use run() instead."
        )
```

**Step 4: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py
git commit -m "feat(cross-lingual): add LangGraph pipeline and TranslationService"
```

---

### Task 8: Integration Test with Mocked LLM

**Files:**
- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_integration.py`

**Step 1: Write the integration test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_integration.py
"""Integration test for the full translation pipeline with mocked LLM."""
from unittest.mock import MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationResult,
)
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService


@pytest.fixture
def mock_cfg():
    cfg = MagicMock()
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001/v1"
    cfg.translation.model = "test-model"
    return cfg


@pytest.fixture
def chinese_pages():
    return [
        {
            "page_number": 1,
            "markdown": "该患者携带BRCA1基因的新变异。该变异导致蛋白质功能丧失。",
        },
    ]


@pytest.fixture
def english_pages():
    return [
        {
            "page_number": 1,
            "markdown": "The patient carries a novel BRCA1 variant. This variant results in loss of protein function.",
        },
    ]


def _mock_llm_response(text: str):
    """Create a mock LLM response."""
    response = MagicMock()
    response.content = text
    return response


@patch("src.core.cross_lingual_process_and_extract_evidence.workflow.ChatOpenAI")
def test_full_pipeline_chinese(mock_chat_cls, mock_cfg, chinese_pages):
    """Full pipeline: Chinese → English with all stages."""
    mock_llm = MagicMock()
    mock_chat_cls.return_value = mock_llm

    # Mock each LLM call in order
    mock_llm.invoke.side_effect = [
        _mock_llm_response("基因:gene\n变异:variant"),          # terminology
        _mock_llm_response("Section 1: Patient variant info"),  # structure
        _mock_llm_response("The patient carries a novel BRCA1 gene variant. This variant leads to loss of protein function."),  # draft
        _mock_llm_response("The patient carries a novel BRCA1 gene variant. This variant leads to loss of protein function."),  # polish
        _mock_llm_response("Translation accurate, no gaps found."),  # review
    ]

    service = TranslationService(cfg=mock_cfg)
    result = service.run_sync(chinese_pages)

    assert isinstance(result, TranslationResult)
    assert result.source_language != "en"
    assert len(result.translated_english) > 0
    assert result.translated_english != result.formatted_original
    assert len(result.sentences) > 0


@patch("src.core.cross_lingual_process_and_extract_evidence.workflow.ChatOpenAI")
def test_pipeline_skip_english(mock_chat_cls, mock_cfg, english_pages):
    """Pipeline should skip translation for English documents."""
    mock_llm = MagicMock()
    mock_chat_cls.return_value = mock_llm

    service = TranslationService(cfg=mock_cfg)
    result = service.run_sync(english_pages)

    assert isinstance(result, TranslationResult)
    assert result.source_language == "en"
    assert result.formatted_original == result.translated_english
    assert len(result.segments) == 0
```

**Step 2: Run test to verify it passes**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/test_integration.py
git commit -m "test(cross-lingual): add integration test with mocked LLM"
```

---

### Task 9: Ruff Lint Pass

**Step 1: Run Ruff**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/ tests/core/cross_lingual_process_and_extract_evidence/
```

**Step 2: Fix any lint errors**

**Step 3: Commit**

```bash
git add -u
git commit -m "style(cross-lingual): fix ruff lint issues"
```

---

### Task 10: Progress & Doc Update

**Step 1: Update progress.txt**

```bash
echo "[2026-05-11] [cross-lingual translation+formatting module] [implemented]" >> /data/[redacted-user]/Projects/01_ACMG_Lingua/progress.txt
```

**Step 2: Commit**

```bash
git add progress.txt
git commit -m "docs: record translation module progress"
```

---

## Verification Checklist

After all tasks are complete, verify:

- [ ] All tests pass: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v`
- [ ] Ruff clean: `cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/`
- [ ] Module importable: `cd backend && uv run python -c "from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService; print('OK')"`
- [ ] No dict returns: all return types are named dataclasses/pydantic models
- [ ] Bbox tracking: `SentenceRegion` populated for formatted sentences
- [ ] Language skip: English documents bypass translation entirely
- [ ] Token segmentation: long documents split into ≤8192-token segments
