"""Pipeline runner wiring the refactored DDD pipeline to real implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from src.application.dto import ProcessPDFRequest, ProcessPDFResponse
from src.application.services import PipelineFactory
from src.infrastructure.llm import (
    ArbiterServiceImpl,
    EvidenceExtractorServiceImpl,
    LanguageDetectorServiceImpl,
    LLMProvider,
    TranslatorServiceImpl,
)
from src.infrastructure.repositories import PDFRepositoryImpl, RAGRepositoryImpl
from src.infrastructure.utils.config import AppConfig
from src.infrastructure.utils.logger import Logger


logger = Logger.get_logger(__name__)


def _require_file(pdf_path: str) -> None:
    """Fail fast with a friendly error if the PDF is missing."""

    if not pdf_path:
        raise FileNotFoundError("pdf_path is required")

    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"Input PDF not found: {pdf_path}")


def _build_orchestrator(cfg: AppConfig):
    """Create a fully-wired pipeline orchestrator with concrete implementations."""

    # LLM providers (primary + arbiter)
    llm_provider = LLMProvider(cfg)

    # Repositories / services
    pdf_repo = PDFRepositoryImpl(cfg.llm)

    # Embeddings for vector store / RAG
    embeddings = _build_embeddings(cfg)
    rag_repo = RAGRepositoryImpl(
        embeddings=embeddings,
        rerank_config=cfg.rerank,
    )

    lang_detector = LanguageDetectorServiceImpl(pdf_repo)
    translator = TranslatorServiceImpl(llm_provider.get_primary_llm())
    evidence_extractor = EvidenceExtractorServiceImpl(llm_provider.get_primary_llm())
    arbiter = ArbiterServiceImpl(llm_provider.get_arbiter_llm())

    # Build orchestrator with ordered steps
    orchestrator = PipelineFactory.create_orchestrator(
        cfg=cfg,
        pdf_repo=pdf_repo,
        rag_repo=rag_repo,
        lang_detector=lang_detector,
        translator=translator,
        evidence_extractor=evidence_extractor,
        arbiter=arbiter,
        max_iterations=cfg.max_reasoning_iterations,
    )

    return orchestrator


def _build_embeddings(cfg: AppConfig):
    """Instantiate embeddings client from config with sensible defaults."""

    # Import locally to keep optional dependency surface minimal at import time
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=cfg.embedding.model_name,
        openai_api_key=cfg.embedding.api_key,
        base_url=cfg.embedding.base_url,
        dimensions=cfg.embedding.dimension,
    )


def build_pipeline(cfg: Optional[AppConfig] = None):
    """Build and return the configured pipeline orchestrator.

    Args:
        cfg: Optional application config (falls back to env)
    """

    cfg = cfg or AppConfig.from_env()
    return _build_orchestrator(cfg)


def run_pipeline(pdf_path: str, out_dir: str = "outputs", cfg: Optional[AppConfig] = None) -> Dict[str, Any]:
    """Backward-compatible entrypoint calling the refactored pipeline."""

    return run_pipeline_refactored(pdf_path=pdf_path, out_dir=out_dir, cfg=cfg)


def run_pipeline_refactored(
    pdf_path: str,
    out_dir: str = "outputs",
    cfg: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """Run the refactored pipeline end-to-end.

    Args:
        pdf_path: Path to input PDF
        out_dir: Output directory
        cfg: Optional pre-loaded config

    Returns:
        Dictionary-compatible result payload for CLI/API consumers
    """

    _require_file(pdf_path)

    cfg = cfg or AppConfig.from_env()
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    orchestrator = _build_orchestrator(cfg)

    # Execute pipeline
    response: ProcessPDFResponse = orchestrator.process_pdf(
        ProcessPDFRequest(pdf_path=pdf_path, out_dir=out_dir)
    )

    # Return dict for compatibility (CLI & FastAPI facade expect mapping)
    if hasattr(response, "to_dict"):
        return response.to_dict()

    # Fallback: best-effort mapping
    return {
        "detected_language": getattr(response, "detected_language", "unknown"),
        "arbiter_score": getattr(response, "arbiter_score", 0.0),
        "evidence": getattr(response, "evidence", {}),
        "output_html": getattr(response, "output_html", ""),
        "evidence_json_path": getattr(response, "evidence_json_path", None),
        "final_structured_path": getattr(response, "final_structured_path", None),
        "bbox_metadata_path": getattr(response, "bbox_metadata_path", None),
        "html_report_path": getattr(response, "html_report_path", None),
    }
