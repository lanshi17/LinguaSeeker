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
from ...contracts import FormattedDocument, TranslationResult, TranslationSegment
from ..format.segmenter import estimate_tokens, segment_text
from .base import BaseTranslator
from .prompts import get_terminology_prompt, get_translate_prompt
from .validator import (
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

    # ── Helpers ─────────────────────────────────────────────────────────

    _MAX_RETRIES: int = 5
    _BACKOFF_BASE: float = 30.0  # seconds
    _TRANSIENT_EXCEPTIONS = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    def _invoke_with_retry(self, prompt: str, stage: str) -> str:
        """Call LLM with exponential backoff on transient failures."""
        last_exc: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._llm.invoke([HumanMessage(content=prompt)])
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

    # ── Pipeline stages ──────────────────────────────────────────────────

    def extract_terminology(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: terminology")
        text = formatted.formatted_markdown
        overhead = estimate_tokens(get_terminology_prompt(""))
        segments = segment_text(text, max_tokens=6000, prompt_overhead_tokens=overhead)

        if len(segments) <= 1:
            return self._invoke_with_retry(
                get_terminology_prompt(text), "terminology",
            )

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
        return "\n".join(unique_lines)

    def translate_segments(
        self, formatted: FormattedDocument, terminology: str,
    ) -> Tuple[str, List[str]]:
        """Translate document segment by segment with per-segment validation.

        Each segment gets one translation attempt. If validation fails,
        the segment is retried up to ``_MAX_SEGMENT_RETRIES`` times.
        """
        logger.info("Stage: translate")
        text = formatted.formatted_markdown

        # Calculate token budget for prompt overhead
        max_overhead = 5000
        base_prompt_tokens = estimate_tokens(get_translate_prompt("", ""))
        overhead = estimate_tokens(get_translate_prompt("", terminology))
        if overhead > max_overhead:
            budget = max_overhead - base_prompt_tokens
            term_tokens = estimate_tokens(terminology) or 1
            ratio = min(1.0, budget / term_tokens * 0.9)
            terminology = terminology[:int(len(terminology) * ratio)]
            overhead = estimate_tokens(get_translate_prompt("", terminology))
            logger.warning(
                "Truncated terminology to fit token budget (overhead={})", overhead,
            )

        segments = segment_text(text, max_tokens=6000, prompt_overhead_tokens=overhead)

        translated_parts: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            translated = self._translate_one_segment(segment, terminology, idx, len(segments))
            translated_parts.append(translated)
            logger.info("Translate segment {}/{} done", idx, len(segments))

        return "\n\n".join(translated_parts), segments

    def _translate_one_segment(
        self, source_segment: str, terminology: str, idx: int, total: int,
    ) -> str:
        """Translate a single segment with validation and retry."""
        prompt = get_translate_prompt(source_segment, terminology)
        stage = f"translate/{idx}"

        for attempt in range(1, self._MAX_SEGMENT_RETRIES + 1):
            translated = self._invoke_with_retry(prompt, stage)

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
        from .language_detector import _CJK_RE
        cjk_count = len(_CJK_RE.findall(text[:500]))
        if cjk_count > 50:
            # Could be zh or ja — let the detector figure it out
            from .language_detector import detect_language
            return detect_language(text) or "unknown"
        return "unknown"

    # ── Full pipeline ────────────────────────────────────────────────────

    def run_pipeline(self, formatted: FormattedDocument) -> Tuple[str, Dict[str, str], str, str, List[str], List[str]]:
        # Stage 1: Extract terminology
        terminology = self.extract_terminology(formatted)

        # Stage 2: Translate with built-in constraints
        translated, source_segments = self.translate_segments(formatted, terminology)

        # Stage 3: Validate and clean
        warnings: list[str] = []
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
        return terminology_map, "", "", translated, source_segments, warnings

    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        terminology_map, _structure_plan, _draft, translated, source_segments, warnings = (
            self.run_pipeline(formatted)
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
            terminology_map=terminology_map, translation_warnings=warnings,
            sentences=formatted.sentences, segments=tr_segments,
        )
