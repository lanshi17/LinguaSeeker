# Translation & Formatting Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** implemented
**Created:** 2026-05-11

**Goal:** Implement a modular, layered translation and formatting pipeline that normalizes upstream `ParseResult` documents (any language) into authoritative formatted-original + English-translation outputs with sentence-level bbox tracking.

**Architecture:** Pipeline orchestrated by LangGraph with five optimization principles applied:

| Dimension | Baseline | Optimized |
|---|---|---|
| **State contract** | Free-form `Dict[str, Any]` | Pydantic `PipelineState` with `Annotated` reducers — compile-time safety, self-documenting node I/O |
| **Feature internals** | Script-style functions | Interface/implementation split (ABC in `base.py`, concrete in module) — swappable, testable in isolation |
| **Decision logic** | Hardcoded `if-else` in orchestrator | Independent `Router` class — single-responsibility, easily extensible |
| **Observability** | Manual `logger.info` per node | LangSmith `@traceable` decorators + loguru structured logging — zero-boilerplate tracing |
| **Configuration** | Scattered `cfg.translation.*` access | Typed `TranslationConfigContext` dataclass — single injection point, no raw config leakage |

Format-first flow: normalize source markdown → detect language → route → multi-stage translation → validate. `workflow.py` is a pure orchestrator — zero business logic, only graph wiring and public API.

**Tech Stack:** Python 3.12+, LangGraph, LangChain, LangSmith (`@traceable`), loguru, pydantic, `rust_io.files`, `lingua-language-detector`

---

## Module Structure

```
backend/src/core/cross_lingual_process_and_extract_evidence/
├── __init__.py
├── contracts.py               # Pydantic PipelineState + all data types
├── config_context.py          # Typed TranslationConfigContext — single injection point
├── router.py                  # Independent LanguageRouter — decoupled from orchestrator
├── middleware.py              # LangSmith @traceable + loguru structured logging
├── workflow.py                # Pure orchestrator — graph wiring + public API (zero business logic)
│
├── format/                    # Formatting sub-package
│   ├── __init__.py
│   ├── base.py                # ABC: BaseFormatter interface
│   ├── formatter.py           # MarkdownFormatter implementation
│   └── segmenter.py           # Token-budgeted text segmentation (shared by format + translate)
│
└── translate/                 # Translation sub-package
    ├── __init__.py
    ├── base.py                # ABC: BaseTranslator interface
    ├── translator.py          # MultiStageTranslator implementation
    ├── prompts.py             # LLM prompt templates (inline)
    ├── language_detector.py   # Language detection + skip logic
    └── validator.py           # Translation quality validation + assessment
```

---

### Task 1: Data Contracts

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/config_context.py`
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
    PipelineState,
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


def test_pipeline_state_defaults():
    state = PipelineState(pages=[{"page_number": 1, "markdown": "test"}])
    assert state.source_language == ""
    assert state.needs_translation is True
    assert state.formatted is None
    assert state.translation_result is None


def test_pipeline_state_rejects_missing_pages():
    import pytest
    with pytest.raises(Exception):
        PipelineState()  # pages is required

**Step 2: Run test to verify it fails**

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py -v`
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


# ── Pipeline state (LangGraph) ─────────────────────────────────────────


class PipelineState(BaseModel):
    """Typed state for the LangGraph pipeline — replaces free-form dict.

    Each field is a discrete pipeline artifact. Nodes declare what they
    read/write via their function signatures.
    """

    model_config = {"arbitrary_types_allowed": True}

    pages: List[Dict[str, Any]]
    formatted: Optional[FormattedDocument] = None
    source_language: str = ""
    needs_translation: bool = True
    translation_result: Optional[TranslationResult] = None
```

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/config_context.py
"""Typed configuration context — single injection point for all LLM settings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TranslationConfigContext:
    """Subset of app config needed by translation/formatting modules.

    Built once from ``cfg.translation`` at service init, then injected
    into sub-modules. Prevents raw config leakage into deep code.
    """

    model: str
    api_key: str
    base_url: str
    temperature: float = 0.0

    @classmethod
    def from_config(cls, cfg: Any) -> TranslationConfigContext:
        """Build from the global config object (``cfg.translation``)."""
        return cls(
            model=cfg.translation.model,
            api_key=cfg.translation.api_key,
            base_url=cfg.translation.base_url,
            temperature=getattr(cfg.translation, "temperature", 0.0),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/__init__.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/config_context.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/__init__.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py
git commit -m "feat(cross-lingual): add data contracts, PipelineState, and config context"
```

---

### Task 2: Prompt Templates

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/translate/__init__.py` (empty)
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/translate/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py
from src.core.cross_lingual_process_and_extract_evidence.translate.prompts import (
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/translate/prompts.py
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/translate/__init__.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/translate/prompts.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_prompts.py
git commit -m "feat(cross-lingual): add LLM prompt templates in translate sub-package"
```

---

### Task 3: Language Detector

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/translate/language_detector.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py`

**Prerequisite:** Add `lingua-language-detector` to project dependencies.

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv add lingua-language-detector
```

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py
import pytest
from src.core.cross_lingual_process_and_extract_evidence.translate.language_detector import (
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/translate/language_detector.py
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/translate/language_detector.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_language_detector.py
git commit -m "feat(cross-lingual): add language detection with lingua"
```

---

### Task 4: Text Segmenter

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/format/__init__.py` (empty)
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/format/segmenter.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py
from src.core.cross_lingual_process_and_extract_evidence.format.segmenter import (
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/format/segmenter.py
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/format/__init__.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/format/segmenter.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_segmenter.py
git commit -m "feat(cross-lingual): add token-budgeted text segmenter in format sub-package"
```

---

### Task 5: Formatter

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/format/formatter.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py
from src.core.cross_lingual_process_and_extract_evidence.format.formatter import (
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/format/base.py
"""Interface for document formatters — Clean Architecture boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..contracts import FormattedDocument


class BaseFormatter(ABC):
    """Abstract formatter interface. Swappable for testing or alternative strategies."""

    @abstractmethod
    def format(self, pages: List[Dict[str, Any]]) -> FormattedDocument:
        ...
```

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/format/formatter.py
"""Source document formatting and normalization with bbox tracking."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from ..contracts import FormattedDocument, SentenceRegion
from .base import BaseFormatter
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


class MarkdownFormatter(BaseFormatter):
    """Concrete formatter implementing the BaseFormatter interface."""

    def format(self, pages: List[Dict[str, Any]]) -> FormattedDocument:
        return format_markdown(pages)
```

**Step 4: Run test to verify it passes**

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/format/formatter.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_formatter.py
git commit -m "feat(cross-lingual): add markdown formatter with bbox tracking"
```

---

### Task 6: Translation Validator

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/translate/validator.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator.py
import pytest
from src.core.cross_lingual_process_and_extract_evidence.translate.validator import (
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_validator.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/translate/validator.py
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_validator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/translate/validator.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_validator.py
git commit -m "feat(cross-lingual): add translation quality validator"
```

---

### Task 7: Multi-Stage Translation Engine (with BaseTranslator ABC)

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/translate/base.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/translate/translator.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator.py`

Translation engine with interface/implementation split. `MultiStageTranslator` implements `BaseTranslator` ABC. All LLM settings injected via `TranslationConfigContext`.

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator.py
import pytest
from unittest.mock import MagicMock, patch

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    FormattedDocument,
    TranslationSegment,
)
from src.core.cross_lingual_process_and_extract_evidence.config_context import TranslationConfigContext
from src.core.cross_lingual_process_and_extract_evidence.translate.translator import MultiStageTranslator


@pytest.fixture
def mock_ctx():
    return TranslationConfigContext(
        model="test-model",
        api_key="test-key",
        base_url="http://localhost:8001/v1",
    )


@pytest.fixture
def formatted_doc():
    return FormattedDocument(
        formatted_markdown="The patient carries a novel BRCA1 variant.",
        source_language="en",
    )


def test_translator_init(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    assert t._ctx == mock_ctx


def test_translator_build_llm(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    llm = t._build_llm()
    assert llm is not None


def test_to_text_none():
    assert MultiStageTranslator._to_text(None) == ""


def test_to_text_string():
    assert MultiStageTranslator._to_text(" hello ") == "hello"


def test_to_text_list():
    content = [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
    assert "hello" in MultiStageTranslator._to_text(content)
```

**Step 2: Run test to verify it fails**

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/translate/base.py
"""Interface for translators — Clean Architecture boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

from ..contracts import FormattedDocument, TranslationResult


class BaseTranslator(ABC):
    """Abstract translator interface.

    Implementations translate a ``FormattedDocument`` into a ``TranslationResult``.
    Swappable for testing or alternative translation strategies (e.g. NMT vs LLM).
    """

    @abstractmethod
    def translate(self, formatted: FormattedDocument) -> Tuple[str, str, str, str, List[str], List[str]]:
        """Run the full translation pipeline.

        Returns (terminology, structure_plan, draft, translated, source_segments, warnings).
        """
        ...

    @abstractmethod
    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        """Run the full pipeline and return a ``TranslationResult``."""
        ...
```

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/translate/translator.py
"""Multi-stage translation engine for biomedical documents."""
from __future__ import annotations

from typing import Any, List, Tuple

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import SecretStr

from ..config_context import TranslationConfigContext
from ..contracts import FormattedDocument, TranslationResult, TranslationSegment
from ..format.segmenter import estimate_tokens, segment_text
from .base import BaseTranslator
from .prompts import (
    get_draft_prompt,
    get_polish_prompt,
    get_review_prompt,
    get_structure_prompt,
    get_terminology_prompt,
)
from .validator import summarize_validation_error, validate_translation_output


class MultiStageTranslator(BaseTranslator):
    """Concrete translator implementing the BaseTranslator interface.

    Runs: terminology → structure → draft → polish → review → validate.
    All LLM settings come from ``TranslationConfigContext`` (injected, not raw config).
    """

    def __init__(self, ctx: TranslationConfigContext):
        self._ctx = ctx

    def _build_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self._ctx.model,
            api_key=SecretStr(self._ctx.api_key),
            base_url=self._ctx.base_url,
            temperature=self._ctx.temperature,
        )

    @staticmethod
    def _to_text(content: Any) -> str:
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

    # ── Individual stages ────────────────────────────────────────────────

    def extract_terminology(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: terminology")
        llm = self._build_llm()
        response = llm.invoke(
            [HumanMessage(content=get_terminology_prompt(formatted.formatted_markdown))]
        )
        return self._to_text(response.content)

    def plan_structure(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: structure")
        llm = self._build_llm()
        response = llm.invoke(
            [HumanMessage(content=get_structure_prompt(formatted.formatted_markdown))]
        )
        return self._to_text(response.content)

    def translate_segments(
        self, formatted: FormattedDocument, terminology: str, structure_plan: str,
    ) -> Tuple[str, List[str]]:
        logger.info("Stage: draft")
        llm = self._build_llm()
        text = formatted.formatted_markdown
        overhead = estimate_tokens(get_draft_prompt("", terminology, structure_plan))
        segments = segment_text(text, max_tokens=8192, prompt_overhead_tokens=overhead)

        translated_parts: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = get_draft_prompt(segment, terminology, structure_plan)
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                translated_parts.append(self._to_text(response.content))
                logger.info("Draft segment {}/{} done", idx, len(segments))
            except Exception as e:
                logger.error("Draft segment {}/{} failed: {}", idx, len(segments), e)
                raise RuntimeError(f"Translation segment {idx} failed") from e

        return "\n\n".join(translated_parts), segments

    def polish(self, draft: str, terminology: str) -> str:
        logger.info("Stage: polish")
        if not draft:
            return ""
        llm = self._build_llm()
        response = llm.invoke([HumanMessage(content=get_polish_prompt(draft, terminology))])
        return self._to_text(response.content) or draft

    def review(self, source: str, translated: str) -> str:
        logger.info("Stage: review")
        if not translated:
            return ""
        llm = self._build_llm()
        response = llm.invoke([HumanMessage(content=get_review_prompt(source, translated))])
        return self._to_text(response.content)

    # ── Full pipeline ────────────────────────────────────────────────────

    def translate(self, formatted: FormattedDocument) -> Tuple[str, str, str, str, List[str], List[str]]:
        terminology = self.extract_terminology(formatted)
        structure_plan = self.plan_structure(formatted)
        draft, source_segments = self.translate_segments(formatted, terminology, structure_plan)
        polished = self.polish(draft, terminology)
        self.review(formatted.formatted_markdown, polished)

        warnings: list[str] = []
        translated = polished
        try:
            validate_translation_output(formatted.formatted_markdown, translated)
        except Exception as exc:
            warnings.append(summarize_validation_error(exc))
            logger.warning("Translation validation warning: {}", warnings[-1])
            if translated != draft:
                try:
                    validate_translation_output(formatted.formatted_markdown, draft)
                    translated = draft
                    warnings.append("fell_back_to_draft")
                except Exception:
                    pass

        return terminology, structure_plan, draft, translated, source_segments, warnings

    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        terminology, structure_plan, draft, translated, source_segments, warnings = (
            self.translate(formatted)
        )
        translated_sentences = translated.split("\n\n") if translated else []
        tr_segments: list[TranslationSegment] = []
        for idx, src_seg in enumerate(source_segments):
            src_bbox = None
            for sent in formatted.sentences:
                if sent.text.strip() in src_seg.strip() or src_seg.strip() in sent.text:
                    src_bbox = sent
                    break
            tr_segments.append(TranslationSegment(
                index=idx, source_text=src_seg,
                translated_text=translated_sentences[idx] if idx < len(translated_sentences) else "",
                source_bbox=src_bbox,
            ))
        return TranslationResult(
            formatted_original=formatted.formatted_markdown,
            translated_english=translated,
            source_language=formatted.source_language or "unknown",
            terminology_map={}, translation_warnings=warnings,
            sentences=formatted.sentences, segments=tr_segments,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_translator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/translate/base.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/translate/translator.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_translator.py
git commit -m "feat(cross-lingual): add BaseTranslator ABC + MultiStageTranslator implementation"
```

---

### Task 8: Router + Middleware (Observability & Decision Logic)

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/router.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/middleware.py`

**Step 1: Write the implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/router.py
"""Independent routing logic — decoupled from orchestrator."""
from __future__ import annotations

from typing import Literal

from .contracts import PipelineState
from .translate.language_detector import should_skip_translation


class LanguageRouter:
    """Decides whether a document needs translation.

    Single-responsibility: routing logic lives here, not in workflow.py.
    """

    @staticmethod
    def route(state: PipelineState) -> Literal["translate", "skip_translate"]:
        if state.needs_translation and not should_skip_translation(
            state.formatted.formatted_markdown if state.formatted else ""
        ):
            return "translate"
        return "skip_translate"
```

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/middleware.py
"""Observability interceptors — LangSmith tracing + structured logging."""
from __future__ import annotations

import functools
from typing import Any, Callable

from langsmith import traceable
from loguru import logger


def traced_node(name: str) -> Callable:
    """Decorator that adds LangSmith tracing + loguru logging to a pipeline node."""
    def decorator(fn: Callable) -> Callable:
        @traceable(name=name, run_type="chain")
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Node [{}] start", name)
            try:
                result = fn(*args, **kwargs)
                logger.info("Node [{}] done", name)
                return result
            except Exception as e:
                logger.error("Node [{}] failed: {}", name, e)
                raise
        return wrapper
    return decorator
```

**Step 2: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/router.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/middleware.py
git commit -m "feat(cross-lingual): add LanguageRouter and traced_node middleware"
```

---

### Task 9: LangGraph Workflow & Public Service (Pure Orchestrator)

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py`

Pure orchestrator — zero business logic. Delegates formatting to `MarkdownFormatter`, translation to `MultiStageTranslator`, routing to `LanguageRouter`, observability to `traced_node`. Uses typed `PipelineState` and `TranslationConfigContext`.

**Step 1: Write the failing test**

```python
# backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py
import pytest
from unittest.mock import MagicMock, patch

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    FormattedDocument,
    PipelineState,
    TranslationResult,
)
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001/v1"
    cfg.translation.model = "test-model"
    cfg.translation.temperature = 0.0
    return cfg


@pytest.fixture
def sample_pages():
    return [
        {"page_number": 1, "markdown": "The patient carries a novel BRCA1 variant."},
    ]


def test_service_init(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._ctx.model == "test-model"


def test_service_has_formatter(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._formatter is not None


def test_service_has_translator(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._translator is not None


def test_service_has_router(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._router is not None
```

**Step 2: Run test to verify it fails**

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py
"""Pure orchestrator — graph wiring + public service API. Zero business logic."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from loguru import logger

from .config_context import TranslationConfigContext
from .contracts import FormattedDocument, PipelineState, TranslationResult
from .format.formatter import MarkdownFormatter
from .language_detector import detect_language
from .middleware import traced_node
from .router import LanguageRouter
from .translate.translator import MultiStageTranslator


class TranslationService:
    """Public API for the translation and formatting pipeline.

    Usage::

        from src.core.config import get_config
        from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService

        cfg = get_config()
        service = TranslationService(cfg=cfg)
        result = await service.run(parse_result_pages)
    """

    def __init__(self, cfg: Any):
        self._ctx = TranslationConfigContext.from_config(cfg)
        self._formatter = MarkdownFormatter()
        self._translator = MultiStageTranslator(ctx=self._ctx)
        self._router = LanguageRouter()

    # ── Pipeline nodes (thin delegates) ─────────────────────────────────

    @traced_node("format")
    def _node_format(self, state: PipelineState) -> PipelineState:
        formatted = self._formatter.format(state.pages)
        state.formatted = formatted
        state.source_language = formatted.source_language or detect_language(
            formatted.formatted_markdown
        )
        return state

    @traced_node("detect_language")
    def _node_detect_language(self, state: PipelineState) -> PipelineState:
        text = state.formatted.formatted_markdown if state.formatted else ""
        lang = state.source_language or detect_language(text)
        state.source_language = lang
        state.needs_translation = self._router.route(state) == "translate"
        logger.info("lang={}, needs_translation={}", lang, state.needs_translation)
        return state

    @traced_node("translate")
    def _node_translate(self, state: PipelineState) -> PipelineState:
        result = self._translator.translate_to_result(state.formatted)
        state.translation_result = result
        return state

    @traced_node("skip_translate")
    def _node_skip_translate(self, state: PipelineState) -> PipelineState:
        logger.info("Document is already English, skipping translation")
        text = state.formatted.formatted_markdown if state.formatted else ""
        state.translation_result = TranslationResult(
            formatted_original=text,
            translated_english=text,
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=state.formatted.sentences if state.formatted else [],
            segments=[],
        )
        return state

    # ── Build graph ──────────────────────────────────────────────────────

    def _build_graph(self) -> Any:
        graph = StateGraph(PipelineState)

        graph.add_node("format", self._node_format)
        graph.add_node("detect_language", self._node_detect_language)
        graph.add_node("translate", self._node_translate)
        graph.add_node("skip_translate", self._node_skip_translate)

        graph.set_entry_point("format")
        graph.add_edge("format", "detect_language")
        graph.add_conditional_edges(
            "detect_language",
            lambda s: "translate" if s.needs_translation else "skip_translate",
            {"translate": "translate", "skip_translate": "skip_translate"},
        )
        graph.add_edge("translate", END)
        graph.add_edge("skip_translate", END)

        return graph.compile()

    # ── Public API ───────────────────────────────────────────────────────

    async def run(self, pages: List[Dict[str, Any]]) -> TranslationResult:
        logger.info("Starting translation pipeline for {} pages", len(pages))

        initial_state = PipelineState(pages=pages)
        graph = self._build_graph()

        try:
            loop = asyncio.get_running_loop()
            final_state = await loop.run_in_executor(
                None, graph.invoke, initial_state
            )
        except RuntimeError:
            final_state = graph.invoke(initial_state)

        if not isinstance(final_state, PipelineState):
            raise RuntimeError("Pipeline returned unexpected state type")

        result = final_state.translation_result
        if result is None:
            raise RuntimeError("Pipeline produced no translation result")

        logger.info(
            "Pipeline complete: {} sentences, {} segments, lang={}",
            len(result.sentences), len(result.segments), result.source_language,
        )
        return result

    def run_sync(self, pages: List[Dict[str, Any]]) -> TranslationResult:
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py \
       backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py
git commit -m "feat(cross-lingual): add pure orchestrator with PipelineState, Router, Middleware"

---

### Task 10: Integration Test with Mocked LLM

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


@patch("src.core.cross_lingual_process_and_extract_evidence.translate.translator.ChatOpenAI")
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


@patch("src.core.cross_lingual_process_and_extract_evidence.translate.translator.ChatOpenAI")
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

Run: `cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/test_integration.py
git commit -m "test(cross-lingual): add integration test with mocked LLM"
```

---

### Task 11: Ruff Lint Pass

**Step 1: Run Ruff**

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua/backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/ tests/core/cross_lingual_process_and_extract_evidence/
```

**Step 2: Fix any lint errors**

**Step 3: Commit**

```bash
git add -u
git commit -m "style(cross-lingual): fix ruff lint issues"
```

---

### Task 12: Progress & Doc Update

**Step 1: Update progress.txt**

```bash
echo "[2026-05-11] [cross-lingual translation+formatting module] [implemented]" >> /data/yangzs/Projects/01_ACMG_Lingua/progress.txt
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
- [ ] Module importable: `cd backend && uv run python -c "from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService; from src.core.cross_lingual_process_and_extract_evidence.translate.translator import MultiStageTranslator; print('OK')"`
- [ ] No dict returns: all return types are named dataclasses/pydantic models
- [ ] Bbox tracking: `SentenceRegion` populated for formatted sentences
- [ ] Language skip: English documents bypass translation entirely
- [ ] Token segmentation: long documents split into ≤8192-token segments
