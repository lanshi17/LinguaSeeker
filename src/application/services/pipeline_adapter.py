"""Backward compatibility adapter for refactored pipeline."""

from src.infrastructure.utils.config import AppConfig
from src.domain.repositories import PDFRepository, RAGRepository
from src.domain.services import (
    ArbiterService,
    EvidenceExtractorService,
    LanguageDetectorService,
    TranslatorService,
)
from src.application.dto import ProcessPDFRequest, ProcessPDFResponse

# Import pipeline components directly to avoid circular imports
from .refactored_pipeline_orchestrator import RefactoredPipelineOrchestrator
from .pdf_processing_step import PDFProcessingStep
from .mineru_processing_step import MinerUProcessingStep
from .translation_step import TranslationStep
from .evidence_processing_step import EvidenceProcessingStep
from .highlighting_step import HighlightingStep

# report_generation_step is optional; tests and minimal builds may omit it.
try:
    from .report_generation_step import ReportGenerationStep
except ModuleNotFoundError:  # pragma: no cover - not critical for unit tests
    class ReportGenerationStep:
        """Fallback no-op step when report generation module is absent."""

        @property
        def name(self):
            return "report_generation"

        @property
        def description(self):
            return "Report generation (stub)"

        def validate_prerequisites(self, context):
            return True

        def execute(self, context):
            # No-op placeholder
            context.mark_step_complete(self.name)

        def rollback(self, context):
            pass


class PipelineFactory:
    """Factory for creating configured pipeline orchestrator.
    
    Simplifies creation of refactored pipeline with all steps.
    Provides easy upgrade path from old to new architecture.
    """

    @staticmethod
    def create_orchestrator(
        cfg: AppConfig,
        pdf_repo: PDFRepository,
        rag_repo: RAGRepository,
        lang_detector: LanguageDetectorService,
        translator: TranslatorService,
        evidence_extractor: EvidenceExtractorService,
        arbiter: ArbiterService,
        max_iterations: int = 3,
    ) -> RefactoredPipelineOrchestrator:
        """Create fully configured pipeline orchestrator.
        
        Args:
            cfg: Application configuration
            pdf_repo: PDF repository
            rag_repo: RAG repository
            lang_detector: Language detection service
            translator: Translation service
            evidence_extractor: Evidence extraction service
            arbiter: Evidence quality arbiter
            max_iterations: Max refinement iterations
            
        Returns:
            Configured RefactoredPipelineOrchestrator
        """
        # Create pipeline steps in execution order
        steps = [
            # Stage-1: Use MinerU SDK to generate structured HTML
            MinerUProcessingStep(pdf_repo),
            TranslationStep(translator),
            EvidenceProcessingStep(
                rag_repo,
                evidence_extractor,
                arbiter,
                max_iterations=max_iterations
            ),
            HighlightingStep(),
            ReportGenerationStep(),
        ]
        
        # Create orchestrator with steps
        orchestrator = RefactoredPipelineOrchestrator(steps)
        
        return orchestrator

    @staticmethod
    def create_processor_with_defaults(
        cfg: AppConfig,
        pdf_repo: PDFRepository,
        rag_repo: RAGRepository,
        lang_detector: LanguageDetectorService,
        translator: TranslatorService,
        evidence_extractor: EvidenceExtractorService,
        arbiter: ArbiterService,
    ) -> 'PipelineProcessor':
        """Create a processor with default settings.
        
        Args:
            cfg: Application configuration
            pdf_repo: PDF repository
            rag_repo: RAG repository
            lang_detector: Language detection service
            translator: Translation service
            evidence_extractor: Evidence extraction service
            arbiter: Evidence quality arbiter
            
        Returns:
            PipelineProcessor instance
        """
        orchestrator = PipelineFactory.create_orchestrator(
            cfg, pdf_repo, rag_repo, lang_detector, translator,
            evidence_extractor, arbiter,
            max_iterations=cfg.max_reasoning_iterations
        )
        
        return PipelineProcessor(orchestrator)


class PipelineProcessor:
    """High-level processor wrapping refactored orchestrator.
    
    Provides convenient interface for processing PDFs while
    maintaining backward compatibility with existing code.
    """

    def __init__(self, orchestrator: RefactoredPipelineOrchestrator):
        """Initialize processor.
        
        Args:
            orchestrator: Refactored pipeline orchestrator
        """
        self.orchestrator = orchestrator

    def process_pdf(self, request: ProcessPDFRequest) -> ProcessPDFResponse:
        """Process PDF through pipeline.
        
        Args:
            request: PDF processing request
            
        Returns:
            Processing result
        """
        return self.orchestrator.process_pdf(request)

    def get_execution_summary(self) -> dict:
        """Get execution summary with timing info.
        
        Returns:
            Execution summary
        """
        return self.orchestrator.get_execution_summary()

    def get_accumulated_results(self) -> dict:
        """Get all accumulated results from steps.
        
        Returns:
            Accumulated results by step
        """
        return self.orchestrator.get_accumulated_results()

    def get_step_results(self, step_name: str) -> dict:
        """Get results from specific step.
        
        Args:
            step_name: Name of step
            
        Returns:
            Step results
        """
        results = self.get_accumulated_results()
        return results.get(step_name, {})
