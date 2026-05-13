"""Multi-stage translation engine for biomedical documents."""
from __future__ import annotations

import re
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
from .validator import summarize_validation_error, validate_translation_output


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

    _MAX_RETRIES: int = 2
    _TRANSIENT_EXCEPTIONS = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    def _invoke_with_retry(self, prompt: str, stage: str) -> str:
        """Call LLM with retry on transient failures only."""
        last_exc: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._llm.invoke([HumanMessage(content=prompt)])
                return self._to_text(response.content)
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning(
                    "Stage {} attempt {}/{} failed: {}", stage, attempt, self._MAX_RETRIES, exc,
                )
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
        return self._invoke_with_retry(
            get_terminology_prompt(formatted.formatted_markdown), "terminology",
        )

    def plan_structure(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: structure")
        return self._invoke_with_retry(
            get_structure_prompt(formatted.formatted_markdown), "structure",
        )

    def translate_segments(
        self, formatted: FormattedDocument, terminology: str, structure_plan: str,
    ) -> Tuple[str, List[str]]:
        logger.info("Stage: draft")
        text = formatted.formatted_markdown
        overhead = estimate_tokens(get_draft_prompt("", terminology, structure_plan))
        segments = segment_text(text, max_tokens=8192, prompt_overhead_tokens=overhead)

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
        return self._invoke_with_retry(get_polish_prompt(draft, terminology), "polish") or draft

    def review(self, source: str, translated: str) -> str:
        logger.info("Stage: review")
        if not translated:
            return ""
        return self._invoke_with_retry(get_review_prompt(source, translated), "review")

    # ── Full pipeline ────────────────────────────────────────────────────

    def run_pipeline(self, formatted: FormattedDocument) -> Tuple[str, Dict[str, str], str, str, List[str], List[str]]:
        terminology = self.extract_terminology(formatted)
        structure_plan = self.plan_structure(formatted)
        draft, source_segments = self.translate_segments(formatted, terminology, structure_plan)
        polished = self.polish(draft, terminology)
        review_notes = self.review(formatted.formatted_markdown, polished)
        logger.info("Review notes: {}", review_notes)

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
