"""Translation engine for biomedical documents."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Tuple

import httpx
import openai
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import SecretStr

from ...config_context import TranslationConfigContext
from ...contracts import (
    ContentBlock,
    FormattedDocument,
    SegmentDrift,
    TranslationResult,
    TranslationSegment,
)
from ..format.segmenter import estimate_tokens, segment_text
from .base import BaseTranslator
from .language_detector import _CJK_RE, detect_language
from .prompts import (
    get_system_prompt_generation_prompt,
    get_terminology_prompt,
    get_translate_prompt,
)
from .validator import (
    strip_prompt_artifacts,
    strip_source_contamination,
    summarize_validation_error,
    validate_image_references_preserved,
    validate_segment,
    validate_translation_output,
)


class MultiStageTranslator(BaseTranslator):
    """Translator with a 3-stage pipeline: terminology → translate → validate.

    Each segment is translated once with terminology and structure constraints
    built into the prompt. Failed segments are automatically retried.
    All LLM settings come from ``TranslationConfigContext``.
    """

    _MAX_SEGMENT_RETRIES: int = 3

    # Pre-compiled regex for _clean_terminology
    _TERM_HEADER_RE = re.compile(
        r"^(?:TERMINOLOGY_STAGE|FORMAT_STAGE|TRANSLATE_STAGE"
        r"|#\s*Terminology\s+Stage|#\s*Bilingual\s+Term\s+Pairs"
        r"|##\s*Bilingual\s+Term\s+Pairs|##\s*Preservation\s+Rules"
        r"|These bilingual term pairs|Bilingual Terminology Map"
        r"|You are a bilingual|Extract a concise"
        r"|\d+\.\s+\*\*[A-Z])",
        re.IGNORECASE,
    )
    _TERM_SUBSECTION_RE = re.compile(r"^(?:\d+\.\s+)?\*\*[A-Z].*\*\*\s*:?\s*$")
    _TERM_BULLET_PAIR_RE = re.compile(r"^[-*]\s+\*\*(.+?)\*\*\s*[→:→]\s*\*\*(.+?)\*\*")
    _TERM_LANG_SRC_RE = re.compile(
        r"^[-*]\s*(?:Japanese|Source|Chinese|Korean|Russian):\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    _TERM_LANG_TGT_RE = re.compile(
        r"^[-*]\s*(?:English|Target):\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    _TERM_SIMPLE_PAIR_RE = re.compile(r"^[-*]?\s*(.+?)\s*[→:→]\s*(.+)$")

    def __init__(self, ctx: TranslationConfigContext):
        self._ctx = ctx
        self._llm = ChatOpenAI(
            model=self._ctx.model,
            api_key=SecretStr(self._ctx.api_key),
            base_url=self._ctx.base_url,
            temperature=self._ctx.temperature,
        )

    @staticmethod
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
                    # Non-text items (image_url, etc.) are intentionally skipped
            return "\n".join(parts).strip()
        if isinstance(content, dict):
            text = content.get("text") or content.get("content") or ""
            return str(text).strip()
        return str(content).strip()

    # ── Helpers ─────────────────────────────────────────────────────────

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

    def _invoke_with_retry(
        self, prompt: str, stage: str, system_prompt: str = "",
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
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._llm.invoke(messages)
                return self._to_text(response.content)
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                delay = self._BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Stage {} attempt {}/{} failed: {}. Retrying in {:.0f}s",
                    stage, attempt, self._MAX_RETRIES, exc, delay,
                )
                if attempt < self._MAX_RETRIES:
                    time.sleep(delay)
        raise RuntimeError(f"Stage {stage} failed after {self._MAX_RETRIES} attempts") from last_exc

    @staticmethod
    def _parse_terminology(raw: str) -> Dict[str, str]:
        """Parse 'source: target' lines into a dict.

        Validates: both sides <=10 words, source side contains non-ASCII
        (since source language is non-English for translation).
        """
        result: Dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^(.+?):\s*(.+)$", line)
            if not match:
                continue
            source = match.group(1).strip()
            target = match.group(2).strip()
            # Skip lines that look like English notes/comments
            if len(source.split()) > 10 or len(target.split()) > 10:
                continue
            # Source side should contain non-ASCII (CJK/non-English term)
            if source.isascii():
                continue
            result[source] = target
        return result

    @classmethod
    def _clean_terminology(cls, raw: str) -> str:
        """Strip LLM echo artifacts and normalize terminology output.

        The terminology LLM returns structured markdown with headers,
        bullet points, and formatting. This strips artifacts and
        normalizes to simple ``source: target`` pairs.
        """
        if not raw:
            return raw

        lines = raw.splitlines()
        clean: list[str] = []
        pending_src: str | None = None  # buffered source term for lang-pair format

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Skip headers and stage markers
            if cls._TERM_HEADER_RE.match(stripped):
                continue

            # Skip sub-section headers (Preservation Rules, HGVS Notations, etc.)
            if cls._TERM_SUBSECTION_RE.match(stripped):
                pending_src = None
                continue

            # Skip "Keep as is" rules
            if "keep as is" in stripped.lower():
                pending_src = None
                continue

            # Try bullet pair: - **source** → **target**
            m = cls._TERM_BULLET_PAIR_RE.match(stripped)
            if m:
                clean.append(f"{m.group(1).strip()}: {m.group(2).strip()}")
                pending_src = None
                continue

            # Try Japanese/Source: X → buffer as source
            m = cls._TERM_LANG_SRC_RE.match(stripped)
            if m:
                pending_src = m.group(1).strip()
                continue

            # Try English/Target: X → pair with buffered source
            m = cls._TERM_LANG_TGT_RE.match(stripped)
            if m and pending_src:
                clean.append(f"{pending_src}: {m.group(1).strip()}")
                pending_src = None
                continue

            # Simple pair format (non-bold)
            m = cls._TERM_SIMPLE_PAIR_RE.match(stripped)
            if m and "**" not in m.group(1):
                src, tgt = m.group(1).strip(), m.group(2).strip()
                if len(src.split()) <= 10 and len(tgt.split()) <= 10:
                    clean.append(f"{src}: {tgt}")
                pending_src = None
                continue

            # Unknown line — reset pending
            pending_src = None

        return "\n".join(clean).strip()

    def _generate_system_prompt(self, formatted: FormattedDocument) -> str:
        """Use an LLM to generate an optimal translation system prompt.

        Analyzes the document sample and produces a tailored system message
        that will be reused for all segment translations of this document.
        """
        source_lang = formatted.source_language or "unknown"
        sample = formatted.formatted_markdown[:2000]
        meta_prompt = get_system_prompt_generation_prompt(sample, source_lang)

        logger.info("Generating dynamic system prompt for lang={}", source_lang)
        system_prompt = self._invoke_with_retry(meta_prompt, "system_prompt_gen")

        # Validate: generated prompt should be reasonable length
        if len(system_prompt) < 50:
            logger.warning("Generated system prompt too short ({} chars), using fallback", len(system_prompt))
            return (
                "You are a professional biomedical translation engine. "
                "Translate to English. Preserve markdown structure, image references, "
                "and biomedical literals exactly. Output only translated markdown."
            )

        logger.info("Generated system prompt ({} chars)", len(system_prompt))
        return system_prompt

    # ── Pipeline stages ──────────────────────────────────────────────────

    def extract_terminology(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: terminology")
        text = formatted.formatted_markdown
        overhead = estimate_tokens(get_terminology_prompt(""))
        segments = segment_text(text, max_tokens=6000, prompt_overhead_tokens=overhead)

        if len(segments) <= 1:
            raw = self._invoke_with_retry(
                get_terminology_prompt(text), "terminology",
            )
            return self._clean_terminology(raw)

        all_terms: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = get_terminology_prompt(segment)
            terms = self._invoke_with_retry(prompt, f"terminology/{idx}")
            all_terms.append(terms)
            logger.info("Terminology segment {}/{} done", idx, len(segments))

        # Merge: deduplicate by keeping unique source:target pairs
        merged = "\n".join(all_terms)
        seen: set[str] = set()
        unique_lines: list[str] = []
        for line in merged.splitlines():
            key = line.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique_lines.append(line.strip())
        return self._clean_terminology("\n".join(unique_lines))

    # Maximum input tokens for qwen-mt-flash
    _MODEL_MAX_TOKENS: int = 8192
    # Reserve ~half for output (translation ≈ source length)
    _INPUT_BUDGET: int = 4000
    # Context window per side (prev/next)
    _CONTEXT_CHARS: int = 150

    def translate_segments(
        self, formatted: FormattedDocument, terminology: str,
    ) -> Tuple[str, List[str], List[str]]:
        """Translate document segment by segment with per-segment validation.

        Each segment gets one translation attempt. If validation fails,
        the segment is retried up to ``_MAX_SEGMENT_RETRIES`` times.

        Returns:
            Tuple of (joined_translated_text, source_segments, translated_parts).
        """
        logger.info("Stage: translate")
        text = formatted.formatted_markdown

        # Generate a dynamic system prompt tailored to this document
        system_prompt = self._generate_system_prompt(formatted)

        # Calculate total overhead: system prompt + base template + context
        sys_tokens = estimate_tokens(system_prompt)
        base_template = get_translate_prompt("", "", "", "")
        base_tokens = estimate_tokens(base_template)
        ctx_sample = "x" * self._CONTEXT_CHARS * 2
        ctx_tokens = estimate_tokens(ctx_sample)

        # Budget for terminology = INPUT_BUDGET - sys - base - context
        available = self._INPUT_BUDGET - sys_tokens - base_tokens - ctx_tokens
        term_tokens = estimate_tokens(terminology)
        if term_tokens > max(available * 0.4, 500):
            # Truncate terminology to fit
            budget_chars = int(len(terminology) * (available * 0.4) / (term_tokens or 1) * 0.9)
            # Snap to nearest newline to avoid splitting mid-entry
            cut = terminology.rfind("\n", 0, max(budget_chars, 200))
            terminology = terminology[:max(cut, 200)]
            term_tokens = estimate_tokens(terminology)
            logger.warning("Truncated terminology to {} tokens", term_tokens)

        # Total overhead for segment_text budget
        overhead = sys_tokens + base_tokens + ctx_tokens + term_tokens
        max_segment_tokens = self._INPUT_BUDGET - overhead
        logger.info(
            "Token budget: sys={} + base={} + ctx={} + terms={} = overhead={}, segment_max={}",
            sys_tokens, base_tokens, ctx_tokens, term_tokens, overhead, max_segment_tokens,
        )

        segments = segment_text(text, max_tokens=max(2000, max_segment_tokens), prompt_overhead_tokens=overhead)

        translated_parts: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            # Provide neighboring context so the LLM can translate coherently
            prev_ctx = segments[idx - 2][-self._CONTEXT_CHARS:] if idx >= 2 else ""
            next_ctx = segments[idx][:self._CONTEXT_CHARS] if idx < len(segments) else ""
            translated = self._translate_one_segment(
                segment, terminology, idx, len(segments),
                prev_context=prev_ctx, next_context=next_ctx,
                system_prompt=system_prompt,
            )
            translated_parts.append(translated)
            logger.info("Translate segment {}/{} done", idx, len(segments))

        return "\n\n".join(translated_parts), segments, translated_parts

    def _translate_one_segment(
        self,
        source_segment: str,
        terminology: str,
        idx: int,
        total: int,
        prev_context: str = "",
        next_context: str = "",
        system_prompt: str = "",
    ) -> str:
        """Translate a single segment with validation and retry."""
        prompt = get_translate_prompt(
            source_segment, terminology,
            prev_context=prev_context, next_context=next_context,
        )
        stage = f"translate/{idx}"

        for attempt in range(1, self._MAX_SEGMENT_RETRIES + 1):
            translated = self._invoke_with_retry(prompt, stage, system_prompt)

            # Strip prompt artifacts echoed back by the LLM
            translated = strip_prompt_artifacts(translated)

            # Strip any source-language contamination from this segment
            translated = strip_source_contamination(
                translated, self._detect_source_lang(source_segment),
            )

            # Validate segment quality
            try:
                validate_segment(source_segment, translated)
                return translated
            except ValueError as exc:
                logger.warning(
                    "Segment {}/{} attempt {}/{} validation failed: {}",
                    idx, total, attempt, self._MAX_SEGMENT_RETRIES, exc,
                )
                if attempt == self._MAX_SEGMENT_RETRIES:
                    # Last attempt — accept whatever we have
                    logger.warning(
                        "Segment {}/{} max retries reached, accepting as-is", idx, total,
                    )
                    return translated

        return translated  # unreachable, but satisfies type checker

    @staticmethod
    def _trim_repetitive_content(text: str) -> str:
        """Remove repetitive heading blocks from LLM output.

        When the LLM enters a repetition loop, it generates the same section
        structure over and over. This function detects repeated heading patterns
        and keeps only the first occurrence plus any content before it.
        """
        paragraphs = re.split(r"\n\s*\n", text)
        seen_headings: list[str] = []
        clean_parts: list[str] = []
        repetition_start: int | None = None

        for idx, para in enumerate(paragraphs):
            stripped = para.strip()
            heading_match = re.match(r"^(#{1,6})\s+(.+)", stripped)
            if heading_match:
                heading_text = heading_match.group(2).strip().lower()
                if heading_text in seen_headings:
                    # Found repeated heading — mark where repetition starts
                    if repetition_start is None:
                        repetition_start = idx
                    continue
                seen_headings.append(heading_text)
            if repetition_start is not None:
                # Skip content after repetition started
                continue
            clean_parts.append(para)

        if repetition_start is None:
            return text

        result = "\n\n".join(clean_parts).strip()
        if len(result) < 100:
            # Safety: if trimming removed almost everything, keep original
            logger.warning("Repetition trim left <100 chars, keeping original")
            return text

        logger.info(
            "Trimmed repetitive content: {} -> {} chars ({} paragraphs removed)",
            len(text), len(result), len(paragraphs) - len(clean_parts),
        )
        return result

    @staticmethod
    def _detect_source_lang(text: str) -> str:
        """Quick heuristic to detect source language for contamination stripping."""
        cjk_count = len(_CJK_RE.findall(text[:500]))
        if cjk_count > 50:
            return detect_language(text) or "unknown"
        return "unknown"

    # ── Full pipeline ────────────────────────────────────────────────────

    def run_pipeline(self, formatted: FormattedDocument) -> Tuple[Dict[str, str], str, str, str, List[str], List[str], List[str]]:
        # ── Stage 1: Translate (terminology + segment translation) ────────
        terminology = self.extract_terminology(formatted)
        translated, source_segments, translated_parts = self.translate_segments(formatted, terminology)

        # ── Stage 2: Review (validate, clean, strip artifacts) ────────────
        warnings: list[str] = []
        translated = strip_prompt_artifacts(translated)
        translated = strip_source_contamination(translated, formatted.source_language or "unknown")

        # Guard: detect LLM repetition loops (translated >> source size)
        source_len = len(formatted.formatted_markdown) or 1
        if len(translated) > source_len * 5:
            unique_headings = set(re.findall(r"^#{1,6}\s+.+", translated, re.MULTILINE))
            if len(unique_headings) > 0 and len(translated) / len(unique_headings) > 500:
                logger.warning(
                    "Detected LLM repetition loop: {} chars ({}x source), {} unique headings. "
                    "Trimming to first occurrence of repeated content.",
                    len(translated), len(translated) // source_len, len(unique_headings),
                )
                warnings.append("repetition_loop")
                translated = self._trim_repetitive_content(translated)

        try:
            validate_translation_output(formatted.formatted_markdown, translated)
        except Exception as exc:
            warnings.append(summarize_validation_error(exc))
            logger.warning("Translation validation warning: {}", warnings[-1])

        # Validate image references preserved
        try:
            validate_image_references_preserved(formatted.formatted_markdown, translated)
        except ValueError as exc:
            warnings.append(f"image_refs: {exc}")
            logger.warning("Image reference warning: {}", exc)

        terminology_map = self._parse_terminology(terminology)
        # Return structure_plan="" for backward compatibility with BaseTranslator
        return terminology_map, "", "", translated, source_segments, translated_parts, warnings

    @staticmethod
    def _find_translated_text_for_block(
        block: ContentBlock,
        segments: List[TranslationSegment],
    ) -> str:
        """Find translated text for a text/title block using segment alignment.

        Searches segments whose source_text overlaps with the block's text,
        then concatenates their translations.
        """
        block_text = block.text.strip()
        if not block_text:
            return ""

        matching_parts: list[str] = []
        for seg in segments:
            src = seg.source_text.strip()
            if not src:
                continue
            # Check if segment source overlaps with block text
            # Use narrower search window to reduce false positives
            src_start = src[:max(len(block_text) * 2, 100)]
            if src in block_text or block_text in src_start:
                matching_parts.append(seg.translated_text)

        if matching_parts:
            return "\n\n".join(matching_parts)

        # Fallback: try to find a segment that starts with similar text
        block_start = block_text[:80]
        for seg in segments:
            if seg.source_text.strip()[:80] == block_start:
                return seg.translated_text

        # Last resort: return empty (block will have empty text)
        return ""

    @staticmethod
    def _build_translated_blocks(
        original_blocks: List[ContentBlock],
        segments: List[TranslationSegment],
    ) -> List[ContentBlock]:
        """Map translated text back to original block structure.

        For text/title blocks, uses segment alignment to find the translated
        content. For non-text blocks (image, table, etc.), copies the original
        block as-is.
        """
        translated_blocks: list[ContentBlock] = []
        for block in original_blocks:
            if block.type in ("text", "title"):
                new_text = MultiStageTranslator._find_translated_text_for_block(
                    block, segments,
                )
                new_block = ContentBlock(
                    type=block.type,
                    page_idx=block.page_idx,
                    bbox=block.bbox,
                    text=new_text,
                    text_level=block.text_level,
                )
            else:
                # Non-text blocks: copy as-is
                new_block = ContentBlock(
                    type=block.type,
                    page_idx=block.page_idx,
                    bbox=block.bbox,
                    text=block.text,
                    img_path=block.img_path,
                    content=block.content,
                    image_caption=list(block.image_caption),
                    image_footnote=list(block.image_footnote),
                    sub_type=block.sub_type,
                    table_body=block.table_body,
                    table_caption=list(block.table_caption),
                    table_footnote=list(block.table_footnote),
                    text_format=block.text_format,
                    code_body=block.code_body,
                    code_caption=list(block.code_caption),
                    code_sub_type=block.code_sub_type,
                    list_sub_type=block.list_sub_type,
                    list_items=list(block.list_items),
                    chart_caption=list(block.chart_caption),
                    chart_footnote=list(block.chart_footnote),
                )
            translated_blocks.append(new_block)
        return translated_blocks

    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        terminology_map, _structure_plan, _draft, translated, source_segments, translated_parts, warnings = (
            self.run_pipeline(formatted)
        )
        tr_segments: list[TranslationSegment] = []
        # Compute translated segment offsets by tracking cumulative position
        translated_offset = 0
        for idx, src_seg in enumerate(source_segments):
            src_bbox = None
            for sent in formatted.sentences:
                if sent.text.strip() in src_seg.strip() or src_seg.strip() in sent.text:
                    src_bbox = sent
                    break
            tr_text = translated_parts[idx] if idx < len(translated_parts) else ""
            tr_segments.append(TranslationSegment(
                index=idx, source_text=src_seg,
                translated_text=tr_text,
                source_bbox=src_bbox,
            ))
            translated_offset += len(tr_text) + 2  # +2 for "\n\n" joiner

        # Build translated blocks by mapping translation back to block structure
        translated_blocks = self._build_translated_blocks(
            formatted.original_blocks, tr_segments,
        )

        return TranslationResult(
            formatted_original=formatted.formatted_markdown,
            translated_english=translated,
            source_language=formatted.source_language or "unknown",
            terminology_map=terminology_map, translation_warnings=warnings,
            sentences=formatted.sentences, segments=tr_segments,
            original_blocks=formatted.original_blocks,
            translated_blocks=translated_blocks,
        )

    @staticmethod
    def compute_translation_drift(
        source_segments: List[str],
        translated_parts: List[str],
    ) -> List[SegmentDrift]:
        """Compute character drift between source and translated segments.

        For each segment pair, tracks the offset positions and length changes.
        """
        drifts: list[SegmentDrift] = []
        source_offset = 0
        translated_offset = 0

        for idx in range(max(len(source_segments), len(translated_parts))):
            src = source_segments[idx] if idx < len(source_segments) else ""
            tr = translated_parts[idx] if idx < len(translated_parts) else ""
            src_len = len(src)
            tr_len = len(tr)
            length_drift = tr_len - src_len

            drifts.append(
                SegmentDrift(
                    segment_index=idx,
                    source_start=source_offset,
                    source_end=source_offset + src_len,
                    translated_start=translated_offset,
                    translated_end=translated_offset + tr_len,
                    source_length=src_len,
                    translated_length=tr_len,
                    length_drift=length_drift,
                    source_text=src[:200],  # Truncate for JSON readability
                    translated_text=tr[:200],
                )
            )
            source_offset += src_len + 2  # +2 for "\n\n" joiner
            translated_offset += tr_len + 2

        return drifts
