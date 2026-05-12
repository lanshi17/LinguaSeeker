"""Pure orchestrator — graph wiring + public service API. Zero business logic."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from loguru import logger

from .config_context import TranslationConfigContext
from .contracts import FormattedDocument, PipelineState, TranslationResult
from .format.formatter import MarkdownFormatter
from .translate.language_detector import detect_language
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
