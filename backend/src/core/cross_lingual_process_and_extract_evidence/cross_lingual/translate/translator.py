"""Multi-stage translation engine for biomedical documents."""
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
from .prompts import (
    get_draft_prompt,
    get_polish_prompt,
    get_review_prompt,
    get_structure_prompt,
    get_terminology_prompt,
)
from .validator import strip_source_contamination, summarize_validation_error, validate_image_references_preserved, validate_translation_output


class MultiStageTranslator(BaseTranslator):
    """Concrete translator implementing the BaseTranslator interface.

    Runs: terminology → structure → draft → polish → review → validate.
    All LLM settings come from ``TranslationConfigContext`` (injected, not raw config).
    """

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

        Validates: both sides ≤10 words, source side contains non-ASCII
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

    # ── Individual stages ────────────────────────────────────────────────

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

    def plan_structure(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: structure")
        text = formatted.formatted_markdown
        overhead = estimate_tokens(get_structure_prompt(""))
        segments = segment_text(text, max_tokens=6000, prompt_overhead_tokens=overhead)

        if len(segments) <= 1:
            return self._invoke_with_retry(
                get_structure_prompt(text), "structure",
            )

        plans: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = get_structure_prompt(segment)
            plan = self._invoke_with_retry(prompt, f"structure/{idx}")
            plans.append(plan)
            logger.info("Structure segment {}/{} done", idx, len(segments))

        # Merge: concatenate structure plans
        merged = "\n\n".join(plans)

        # Final consolidation pass if merged result is still within limits
        consolidation_overhead = estimate_tokens(
            "CONSOLIDATE_STRUCTURE\nMerge the following structure plans into one coherent plan:\n\n"
        )
        if estimate_tokens(merged) < (6000 - consolidation_overhead - 100):
            consolidation_prompt = (
                "CONSOLIDATE_STRUCTURE\n"
                "Merge the following structure plans into one coherent plan:\n\n"
                f"{merged}"
            )
            return self._invoke_with_retry(consolidation_prompt, "structure/consolidate")

        return merged

    def translate_segments(
        self, formatted: FormattedDocument, terminology: str, structure_plan: str,
    ) -> Tuple[str, List[str]]:
        logger.info("Stage: draft")
        text = formatted.formatted_markdown

        # Ensure terminology + structure_plan leave room for segment content
        # Total budget is 8192 tokens; reserve 3000 for actual content segment
        max_overhead = 5000
        base_prompt_tokens = estimate_tokens(get_draft_prompt("", "", ""))
        overhead = estimate_tokens(get_draft_prompt("", terminology, structure_plan))
        if overhead > max_overhead:
            # Aggressively truncate: keep only what fits in budget
            budget = max_overhead - base_prompt_tokens
            term_tokens = estimate_tokens(terminology)
            struct_tokens = estimate_tokens(structure_plan)
            total = term_tokens + struct_tokens or 1
            # Split budget proportionally
            term_budget = max(100, int(budget * term_tokens / total))
            struct_budget = max(100, int(budget * struct_tokens / total))
            # Truncate by character ratio with safety margin
            if term_tokens > 0:
                ratio = min(1.0, term_budget / term_tokens * 0.9)  # 10% safety margin
                terminology = terminology[:int(len(terminology) * ratio)]
            if struct_tokens > 0:
                ratio = min(1.0, struct_budget / struct_tokens * 0.9)
                structure_plan = structure_plan[:int(len(structure_plan) * ratio)]
            overhead = estimate_tokens(get_draft_prompt("", terminology, structure_plan))
            logger.warning(
                "Truncated terminology/structure_plan to fit token budget (overhead={})", overhead,
            )

        segments = segment_text(text, max_tokens=6000, prompt_overhead_tokens=overhead)

        translated_parts: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = get_draft_prompt(segment, terminology, structure_plan)
            translated_parts.append(self._invoke_with_retry(prompt, f"draft/{idx}"))
            logger.info("Draft segment {}/{} done", idx, len(segments))

        return "\n\n".join(translated_parts), segments

    def polish(self, draft: str, terminology: str) -> str:
        logger.info("Stage: polish")
        if not draft:
            return ""

        # Ensure terminology leaves room for draft segment content
        max_overhead = 5000
        base_prompt_tokens = estimate_tokens(get_polish_prompt("", ""))
        overhead = estimate_tokens(get_polish_prompt("", terminology))
        if overhead > max_overhead:
            budget = max_overhead - base_prompt_tokens
            term_tokens = estimate_tokens(terminology) or 1
            ratio = min(1.0, budget / term_tokens * 0.9)  # 10% safety margin
            terminology = terminology[:int(len(terminology) * ratio)]
            overhead = estimate_tokens(get_polish_prompt("", terminology))
            logger.warning("Truncated terminology to fit token budget (overhead={})", overhead)

        segments = segment_text(draft, max_tokens=6000, prompt_overhead_tokens=overhead)

        if len(segments) <= 1:
            return self._invoke_with_retry(get_polish_prompt(draft, terminology), "polish") or draft

        polished_parts: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = get_polish_prompt(segment, terminology)
            polished = self._invoke_with_retry(prompt, f"polish/{idx}")
            polished_parts.append(polished or segment)
            logger.info("Polish segment {}/{} done", idx, len(segments))

        return "\n\n".join(polished_parts)

    def review(self, source: str, translated: str) -> str:
        logger.info("Stage: review")
        if not translated:
            return ""

        # Review needs both source and translated, so budget is split
        overhead = estimate_tokens(get_review_prompt("", ""))
        max_per_part = (6000 - overhead) // 2

        source_segments = segment_text(source, max_tokens=max_per_part)
        translated_segments = segment_text(translated, max_tokens=max_per_part)

        # If either needs segmentation, review segment-by-segment
        if len(source_segments) <= 1 and len(translated_segments) <= 1:
            return self._invoke_with_retry(
                get_review_prompt(source, translated), "review",
            )

        # Align segments (use zip, review shorter set)
        max_pairs = max(len(source_segments), len(translated_segments))
        reviews: list[str] = []
        for idx in range(max_pairs):
            src = source_segments[idx] if idx < len(source_segments) else ""
            tgt = translated_segments[idx] if idx < len(translated_segments) else ""
            if not src or not tgt:
                continue
            prompt = get_review_prompt(src, tgt)
            review = self._invoke_with_retry(prompt, f"review/{idx + 1}")
            reviews.append(review)
            logger.info("Review segment {}/{} done", idx + 1, max_pairs)

        return "\n\n".join(reviews)

    # ── Full pipeline ────────────────────────────────────────────────────

    def run_pipeline(self, formatted: FormattedDocument) -> Tuple[str, Dict[str, str], str, str, List[str], List[str]]:
        terminology = self.extract_terminology(formatted)
        structure_plan = self.plan_structure(formatted)
        draft, source_segments = self.translate_segments(formatted, terminology, structure_plan)
        polished = self.polish(draft, terminology)
        review_notes = self.review(formatted.formatted_markdown, polished)
        logger.info("Review notes: {}", review_notes)

        warnings: list[str] = []
        translated = strip_source_contamination(polished, formatted.source_language or "unknown")

        # Guard: detect LLM repetition loops (translated >> source size)
        source_len = len(formatted.formatted_markdown) or 1
        if len(translated) > source_len * 5:
            unique_headings = set(re.findall(r"^#{1,6}\s+.+", translated, re.MULTILINE))
            if len(unique_headings) > 0 and len(translated) / len(unique_headings) > 500:
                # Many repeated headings with little content between them
                logger.warning(
                    "Detected LLM repetition loop: {} chars ({}x source), {} unique headings. "
                    "Falling back to draft.",
                    len(translated), len(translated) // source_len, len(unique_headings),
                )
                warnings.append("repetition_loop_fallback")
                translated = strip_source_contamination(draft, formatted.source_language or "unknown")

        try:
            validate_translation_output(formatted.formatted_markdown, translated)
        except Exception as exc:
            warnings.append(summarize_validation_error(exc))
            logger.warning("Translation validation warning: {}", warnings[-1])
            if translated != draft:
                try:
                    stripped_draft = strip_source_contamination(draft, formatted.source_language or "unknown")
                    validate_translation_output(formatted.formatted_markdown, stripped_draft)
                    translated = stripped_draft
                    warnings.append("fell_back_to_draft")
                except Exception:
                    pass

        # Validate image references preserved
        try:
            validate_image_references_preserved(formatted.formatted_markdown, translated)
        except ValueError as exc:
            warnings.append(f"image_refs: {exc}")
            logger.warning("Image reference warning: {}", exc)

        terminology_map = self._parse_terminology(terminology)
        return terminology_map, structure_plan, draft, translated, source_segments, warnings

    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        terminology_map, structure_plan, draft, translated, source_segments, warnings = (
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
