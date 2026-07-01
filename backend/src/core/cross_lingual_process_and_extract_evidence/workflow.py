"""Pure orchestrator — graph wiring + public service API. Zero business logic."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from loguru import logger

from .config_context import TranslationConfigContext
from .contracts import CrossLingualOutput, PipelineState, TranslationResult
from .persistence import DocumentPersistenceService
from .cross_lingual.format.formatter import MarkdownFormatter
from .cross_lingual.translate.language_detector import detect_language
from src.utils.observability import traced_node
from .router import LanguageRouter
from .cross_lingual.translate.translator import MultiStageTranslator, TranslationError


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
        # Create LLM for formatter (redaction detection + OCR repair)
        from src.utils.llm_adapter import create_llm_client

        formatter_llm = create_llm_client(
            model=self._ctx.model,
            base_url=self._ctx.base_url,
            api_keys=self._ctx.api_keys,
            max_tokens=self._ctx.max_tokens,
            temperature=self._ctx.temperature,
            timeout=self._ctx.timeout,
        )
        self._formatter = MarkdownFormatter(llm=formatter_llm)
        self._translator = MultiStageTranslator(ctx=self._ctx)
        self._router = LanguageRouter()
        self._persistence = DocumentPersistenceService()
        self._graph = self._build_graph()

    # ── Pipeline nodes (thin delegates) ─────────────────────────────────

    @traced_node("format")
    def _node_format(self, state: PipelineState) -> PipelineState:
        formatted = self._formatter.format(state.pages, content_blocks=state.content_blocks)
        state.formatted = formatted
        return state

    @traced_node("detect_language")
    def _node_detect_language(self, state: PipelineState) -> PipelineState:
        text = state.formatted.formatted_markdown if state.formatted else ""
        lang = state.source_language or detect_language(text)
        state.source_language = lang
        # Propagate to FormattedDocument so translator can read it
        if state.formatted:
            state.formatted.source_language = lang
        state.needs_translation = self._router.route(state) == "translate"
        logger.info("lang={}, needs_translation={}", lang, state.needs_translation)
        return state

    @traced_node("translate")
    async def _node_translate(self, state: PipelineState) -> PipelineState:
        try:
            result = await self._translator.translate_to_result(state.formatted)
        except TranslationError:
            raise  # Let critical failures propagate — do not persist garbage
        state.translation_result = result
        return state

    @traced_node("skip_translate")
    def _node_skip_translate(self, state: PipelineState) -> PipelineState:
        logger.info("Document is already English, skipping translation")
        text = state.formatted.formatted_markdown if state.formatted else ""
        blocks = state.formatted.original_blocks if state.formatted else []
        state.translation_result = TranslationResult(
            formatted_original=text,
            translated_english=text,
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=state.formatted.sentences if state.formatted else [],
            segments=[],
            original_blocks=blocks,
            translated_blocks=blocks,
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

    async def run(
        self,
        pages: List[Dict[str, Any]],
        content_blocks: List[Dict[str, Any]] | None = None,
    ) -> TranslationResult:
        logger.info("Starting translation pipeline for {} pages", len(pages))

        initial_state = PipelineState(pages=pages, content_blocks=content_blocks or [])
        graph = self._graph

        final_state = await graph.ainvoke(initial_state)

        if isinstance(final_state, dict):
            final_state = PipelineState(**final_state)

        result = final_state.translation_result
        if result is None:
            raise RuntimeError("Pipeline produced no translation result")

        logger.info(
            "Pipeline complete: {} sentences, {} segments, lang={}",
            len(result.sentences),
            len(result.segments),
            result.source_language,
        )
        return result

    def run_sync(
        self,
        pages: List[Dict[str, Any]],
        content_blocks: List[Dict[str, Any]] | None = None,
    ) -> TranslationResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(pages, content_blocks=content_blocks))
        raise RuntimeError("run_sync() cannot be called from within a running event loop. Use run() instead.")

    def save(
        self,
        result: TranslationResult,
        output_dir: str,
        doc_id: str,
        image_paths: list[str] | None = None,
    ) -> CrossLingualOutput:
        """Persist result to local storage and return downstream output contract.

        Args:
            result: TranslationResult from run().
            output_dir: Root output directory.
            doc_id: Unique document identifier.
            image_paths: Optional source image paths to copy.

        Returns:
            CrossLingualOutput for downstream consumers.
        """
        saved = self._persistence.save(result, output_dir, doc_id, image_paths)
        return self._persistence.to_output(result, saved)
