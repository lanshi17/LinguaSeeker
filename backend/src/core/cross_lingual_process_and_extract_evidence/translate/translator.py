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

    # ── Individual stages ────────────────────────────────────────────────

    def extract_terminology(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: terminology")
        llm = self._llm
        response = llm.invoke(
            [HumanMessage(content=get_terminology_prompt(formatted.formatted_markdown))]
        )
        return self._to_text(response.content)

    def plan_structure(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: structure")
        llm = self._llm
        response = llm.invoke(
            [HumanMessage(content=get_structure_prompt(formatted.formatted_markdown))]
        )
        return self._to_text(response.content)

    def translate_segments(
        self, formatted: FormattedDocument, terminology: str, structure_plan: str,
    ) -> Tuple[str, List[str]]:
        logger.info("Stage: draft")
        llm = self._llm
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
        llm = self._llm
        response = llm.invoke([HumanMessage(content=get_polish_prompt(draft, terminology))])
        return self._to_text(response.content) or draft

    def review(self, source: str, translated: str) -> str:
        logger.info("Stage: review")
        if not translated:
            return ""
        llm = self._llm
        response = llm.invoke([HumanMessage(content=get_review_prompt(source, translated))])
        return self._to_text(response.content)

    # ── Full pipeline ────────────────────────────────────────────────────

    def _translate(self, formatted: FormattedDocument) -> Tuple[str, str, str, str, List[str], List[str]]:
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

        return terminology, structure_plan, draft, translated, source_segments, warnings

    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        terminology, structure_plan, draft, translated, source_segments, warnings = (
            self._translate(formatted)
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
