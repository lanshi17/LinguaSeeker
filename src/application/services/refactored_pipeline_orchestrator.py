"""Refactored pipeline orchestrator - coordinates processing steps."""

from typing import List, Optional
from pathlib import Path

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.application.services.pipeline_context import PipelineContext
from src.application.services.result_accumulator import ResultAccumulator
from src.application.dto import ProcessPDFRequest, ProcessPDFResponse
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.timer import Timer, print_timer_stats


class RefactoredPipelineOrchestrator:
    """Refactored orchestrator using step-based architecture.
    
    Coordinates pipeline steps with clean separation of concerns:
    - Each step handles a single responsibility
    - Steps communicate via context and accumulators
    - Easy to test, extend, and modify individual steps
    - Clear error handling and rollback support
    """

    def __init__(self, steps: List[IPipelineStep]):
        """Initialize orchestrator with pipeline steps.
        
        Args:
            steps: List of pipeline steps in execution order
        """
        self.steps = steps
        self.logger = Logger.get_logger(__name__)
        self.context: Optional[PipelineContext] = None
        self.accumulator: Optional[ResultAccumulator] = None

    def process_pdf(self, request: ProcessPDFRequest) -> ProcessPDFResponse:
        """Process PDF through configured pipeline steps.
        
        Args:
            request: PDF processing request
            
        Returns:
            Processing result
            
        Raises:
            RuntimeError: If pipeline execution fails
        """
        # Initialize execution context
        self.context = PipelineContext()
        self.accumulator = ResultAccumulator()
        
        # Setup initial context
        self.context.update({
            "pdf_path": request.pdf_path,
            "out_dir": request.out_dir,
        })
        
        # Execute pipeline steps
        try:
            with Timer('完整管线处理', silent=False):
                for step in self.steps:
                    self._execute_step(step)
            
            # Build final response
            return self._build_response()
            
        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {e}")
            self._rollback_steps()
            raise

    def _execute_step(self, step: IPipelineStep) -> None:
        """Execute a single pipeline step with error handling.
        
        Args:
            step: Step to execute
            
        Raises:
            RuntimeError: If step execution fails
        """
        self.logger.info(f"Executing step: {step.name} - {step.description}")
        
        try:
            # Validate prerequisites
            if not step.validate_prerequisites(self.context):
                raise RuntimeError(
                    f"Step {step.name} prerequisites not met"
                )
            
            # Record start time
            self.context.record_step_start(step.name)
            
            # Execute step with timing
            with Timer(f'【{step.name}】', silent=False):
                step.execute(self.context)
            
            # Accumulate results
            step_results = self._extract_step_results(step)
            self.accumulator.accumulate(step.name, step_results)
            
            # Log completion
            duration = self.context.get_step_duration(step.name)
            self.logger.info(
                f"Step {step.name} completed successfully in {duration:.2f}s"
            )
            
        except Exception as e:
            self.logger.error(f"Step {step.name} failed: {e}")
            self.context.record_error(step.name, str(e))
            raise

    def _extract_step_results(self, step: IPipelineStep) -> dict:
        """Extract results from context after step execution.
        
        Args:
            step: Executed step
            
        Returns:
            Dictionary of extracted results
        """
        # Common output keys for major steps
        step_output_keys = {
            "pdf_processing": [
                "detected_language",
                "raw_text",
                "bbox_metadata",
                "page_count",
                "bbox_metadata_path",
            ],
            "translation": [
                "english_markdown",
                "glossary_terms",
            ],
            "evidence_processing": [
                "evidence",
                "arbiter_score",
                "arbiter_feedback",
                "iterations_performed",
                "evidence_json_path",
                "kb_context",
            ],
            "highlighting": [
                "highlighted_markdown",
                "document",
            ],
            "report_generation": [
                "final_payload",
                "final_structured_path",
                "html_report_path",
                "figures_list",
                "tables_list",
            ],
        }
        
        # Extract relevant keys for this step
        output_keys = step_output_keys.get(step.name, [])
        results = {}
        
        for key in output_keys:
            if self.context.has(key):
                # Only include non-context-internal values
                value = self.context.get(key)
                if not key.startswith("_"):
                    results[key] = value
        
        return results

    def _rollback_steps(self) -> None:
        """Rollback all executed steps in reverse order."""
        self.logger.warning("Rolling back pipeline execution...")
        
        completed_steps = self.context.get_completed_steps()
        
        # Rollback in reverse order
        for step in reversed(self.steps):
            if step.name in completed_steps:
                try:
                    self.logger.info(f"Rolling back step: {step.name}")
                    step.rollback(self.context)
                except Exception as e:
                    self.logger.warning(
                        f"Rollback of {step.name} failed: {e}"
                    )

    def _build_response(self) -> ProcessPDFResponse:
        """Build response from accumulated results.
        
        Returns:
            ProcessPDFResponse with processing results
        """
        # Get final payload
        final_payload = self.accumulator.build_final_payload()
        
        # Extract top-level values
        detected_language = self.context.get("detected_language")
        arbiter_score = self.context.get("arbiter_score", 0.0)

        # Normalize detected_language to string
        if hasattr(detected_language, "value"):
            detected_lang_value = detected_language.value
        else:
            detected_lang_value = detected_language or "unknown"
        
        # Build response
        response = ProcessPDFResponse(
            detected_language=detected_lang_value,
            arbiter_score=arbiter_score,
            evidence=final_payload.get("stages", {}).get("evidence_processing", {}),
            output_html=self.context.get("html_report_path", ""),
            evidence_json_path=self.context.get("evidence_json_path"),
            final_structured_path=final_payload.get("final_structured_path"),
            bbox_metadata_path=self.context.get("bbox_metadata_path"),
            html_report_path=final_payload.get("html_report_path"),
        )
        
        return response

    def get_execution_summary(self) -> dict:
        """Get summary of pipeline execution.
        
        Returns:
            Execution summary including timing and errors
        """
        if not self.context:
            return {"status": "not_executed"}
        
        return self.context.get_execution_summary()

    def get_accumulated_results(self) -> dict:
        """Get all accumulated results from all steps.
        
        Returns:
            Accumulated results organized by step
        """
        if not self.accumulator:
            return {}
        
        return self.accumulator.get_accumulated()
