"""Public interfaces and API."""

from .pipeline_step import IPipelineStep, IPipelineContext, IResultAccumulator
from src.infrastructure.utils.config import AppConfig
from src.infrastructure.embeddings.embedding_provider import EmbeddingProvider
from src.infrastructure.llm import (
    ArbiterServiceImpl,
    EvidenceExtractorServiceImpl,
    LanguageDetectorServiceImpl,
    TranslatorServiceImpl,
)
from src.infrastructure.llm.llm_provider import LLMProvider
from src.infrastructure.repositories import PDFRepositoryImpl, RAGRepositoryImpl
# NOTE: Avoid importing application.services at module load to prevent circular
# imports during test collection. Import inside functions when needed.
from src.application.dto import ProcessPDFRequest, ProcessPDFResponse


def run_pipeline_refactored(pdf_path: str, out_dir: str = "outputs") -> dict:
    """Main entry point using refactored step-based pipeline architecture.
    
    This is the new recommended approach with better separation of concerns.

    Args:
        pdf_path: Path to input PDF
        out_dir: Output directory for results

    Returns:
        Dictionary with processing results
    """
    # Lazy import to avoid circular import during test discovery
    from src.application.services import PipelineFactory

    # Load configuration
    cfg = AppConfig.from_env()

    # Initialize providers
    llm_provider = LLMProvider(cfg)
    embedding_provider = EmbeddingProvider(cfg)

    # Initialize repositories
    pdf_repo = PDFRepositoryImpl(
        ocr_config=cfg.llm,
        use_mineru=True,
    )
    rag_repo = RAGRepositoryImpl(
        embedding_provider.get_embeddings(),
        rerank_config=cfg.rerank if cfg.rerank.enabled else None
    )

    # Initialize domain services
    lang_detector = LanguageDetectorServiceImpl(pdf_repo)
    translator = TranslatorServiceImpl(llm_provider.get_primary_llm())
    evidence_extractor = EvidenceExtractorServiceImpl(llm_provider.get_primary_llm())
    arbiter = ArbiterServiceImpl(llm_provider.get_arbiter_llm())

    # Create refactored orchestrator using factory
    processor = PipelineFactory.create_processor_with_defaults(
        cfg,
        pdf_repo,
        rag_repo,
        lang_detector,
        translator,
        evidence_extractor,
        arbiter,
    )

    # Execute pipeline
    request = ProcessPDFRequest(pdf_path, out_dir)
    response = processor.process_pdf(request)

    return response.to_dict()


def run_pipeline(pdf_path: str, out_dir: str = "outputs") -> dict:
    """Legacy entry point retained for backward compatibility.

    Internally proxies to the refactored step-based pipeline.
    """
    return run_pipeline_refactored(pdf_path=pdf_path, out_dir=out_dir)


__all__ = [
    "run_pipeline",
    "run_pipeline_refactored",
    "ProcessPDFRequest",
    "ProcessPDFResponse",
    "IPipelineStep",
    "IPipelineContext",
    "IResultAccumulator",
]
