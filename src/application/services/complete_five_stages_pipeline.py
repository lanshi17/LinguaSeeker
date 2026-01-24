"""
完整的5阶段结构化PDF处理管道

集成所有阶段：
1. MinerU HTML提取（原文，无翻译）
2. HTML翻译为英文
3. RAG检索与PS3证据提取
4. 仲裁评审与迭代优化
5. 结果结构化与文档高亮

所有输出变量保留 {{...}} 占位符格式。
"""

from typing import List, Optional
from pathlib import Path

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.application.services.pipeline_context import PipelineContext
from src.application.services.result_accumulator import ResultAccumulator
from src.application.dto import ProcessPDFRequest, ProcessPDFResponse
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.timer import Timer, print_timer_stats

# Import all Stage classes
from src.application.services.stage1_mineru_html_extraction import Stage1MinerUHTMLExtractionStep
from src.application.services.stage2_html_translation import Stage2HTMLTranslationStep
from src.application.services.stage3_rag_and_ps3_extraction import Stage3RAGAndPS3ExtractionStep
from src.application.services.stage4_arbiter_review import Stage4ArbiterReviewStep
from src.application.services.stage5_result_structuring_and_highlighting import Stage5ResultStructuringAndHighlightingStep


class CompleteFiveStagesPipelineOrchestrator:
    """
    完整的5阶段PDF处理管道编排器。
    
    处理流程：
    1. Stage-1: MinerU PDF→HTML（原文，禁用翻译）
       输出：{{original_structured_html}}, {{detected_language}}, {{bbox_metadata}}
    
    2. Stage-2: 翻译HTML为英文
       输入：{{original_structured_html}}, {{detected_language}}
       输出：{{translated_english_html}}
    
    3. Stage-3: RAG检索与PS3证据提取
       输入：{{translated_english_html}}, {{bbox_metadata}}
       输出：{{ps3_evidence_result}}
    
    4. Stage-4: 仲裁评审（最多3轮迭代）
       输入：{{ps3_evidence_result}}
       输出：{{arbiter_score}}, {{iterations_performed}}
    
    5. Stage-5: 结果结构化与文档高亮
       输入：所有前期输出
       输出：{{final_evidence_json}}, {{final_annotated_doc}}, {{dual_language_view}}
    
    验收标准：
    - 所有占位符变量保留 {{...}} 格式
    - 各阶段输出文件本地持久化
    - 最终JSON包含所有必需字段
    - 高亮HTML与bbox坐标对应
    """

    def __init__(
        self,
        pdf_repository,
        rag_repository,
        mt_llm_client=None,
        arbiter_llm_client=None,
    ):
        """Initialize pipeline with repositories and LLM clients."""
        self.pdf_repo = pdf_repository
        self.rag_repo = rag_repository
        self.mt_llm_client = mt_llm_client
        self.arbiter_llm_client = arbiter_llm_client
        self.logger = Logger.get_logger(__name__)
        self.context: Optional[PipelineContext] = None
        self.accumulator: Optional[ResultAccumulator] = None

    def build_pipeline_steps(self) -> List[IPipelineStep]:
        """Build complete 5-stage pipeline."""
        steps = [
            Stage1MinerUHTMLExtractionStep(pdf_repo=self.pdf_repo),
            Stage2HTMLTranslationStep(mt_llm_client=self.mt_llm_client),
            Stage3RAGAndPS3ExtractionStep(rag_repo=self.rag_repo),
            Stage4ArbiterReviewStep(
                arbiter_llm_client=self.arbiter_llm_client,
                max_iterations=3
            ),
            Stage5ResultStructuringAndHighlightingStep(),
        ]
        return steps

    def process_pdf(self, request: ProcessPDFRequest) -> ProcessPDFResponse:
        """
        Execute complete 5-stage PDF processing pipeline.
        
        Args:
            request: ProcessPDFRequest with pdf_path and out_dir
        
        Returns:
            ProcessPDFResponse with results
        """
        # Initialize execution context
        self.context = PipelineContext()
        self.accumulator = ResultAccumulator()
        
        # Setup initial context
        self.context.update({
            "pdf_path": request.pdf_path,
            "out_dir": request.out_dir,
        })
        
        # Build pipeline steps
        steps = self.build_pipeline_steps()
        
        self.logger.info("=" * 80)
        self.logger.info("STARTING 5-STAGE PDF PROCESSING PIPELINE")
        self.logger.info("=" * 80)
        self.logger.info(f"Input PDF: {request.pdf_path}")
        self.logger.info(f"Output directory: {request.out_dir}")
        self.logger.info(f"Total stages: {len(steps)}")
        for i, step in enumerate(steps, 1):
            self.logger.info(f"  {i}. {step.description}")
        
        # Execute pipeline steps
        try:
            with Timer('Complete 5-stage pipeline execution', silent=False):
                for step in steps:
                    self.logger.info(f"\n{'=' * 80}")
                    self.logger.info(f"Executing: {step.description}")
                    self.logger.info(f"{'=' * 80}")
                    
                    # Validate prerequisites
                    if not step.validate_prerequisites(self.context):
                        raise RuntimeError(f"Step '{step.name}' validation failed")
                    
                    # Execute step
                    step.execute(self.context)
                    
                    # Check for errors
                    if self.context.has_errors(step.name):
                        error_msg = self.context.get_error(step.name)
                        raise RuntimeError(f"Step '{step.name}' failed: {error_msg}")
            
            # Build response from context
            response = self._build_response(self.context)
            
            self.logger.info("\n" + "=" * 80)
            self.logger.info("PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
            self.logger.info("=" * 80)
            self.logger.info(f"Output directory: {request.out_dir}")
            self.logger.info("\nGenerated files:")
            self.logger.info(f"  - Original HTML: {{{{original_structured_html}}}}")
            self.logger.info(f"  - Translated HTML: {{{{translated_english_html}}}}")
            self.logger.info(f"  - Evidence JSON: {{{{ps3_evidence_result}}}}")
            self.logger.info(f"  - Arbiter score: {{{{arbiter_score}}}}")
            self.logger.info(f"  - Final JSON: {{{{final_evidence_json}}}}")
            self.logger.info(f"  - Annotated HTML: {{{{final_annotated_doc}}}}")
            self.logger.info(f"  - Dual-language view: {{{{dual_language_view}}}}")
            
            print_timer_stats()
            
            return response
            
        except Exception as e:
            self.logger.error(f"Pipeline execution failed at step: {e}", exc_info=True)
            return ProcessPDFResponse(
                success=False,
                error_message=str(e),
                output_dir=request.out_dir
            )

    def _build_response(self, context: IPipelineContext) -> ProcessPDFResponse:
        """Build response from execution context."""
        return ProcessPDFResponse(
            success=True,
            output_dir=context.get("out_dir"),
            results={
                # Stage 1 outputs
                "original_structured_html": context.get("{{original_structured_html}}", "{{original_structured_html}}"),
                "detected_language": context.get("{{detected_language}}", "{{detected_language}}"),
                "bbox_metadata_path": context.get("{{bbox_metadata_path}}", "{{bbox_metadata_path}}"),
                
                # Stage 2 outputs
                "translated_english_html": context.get("{{translated_english_html}}", "{{translated_english_html}}"),
                
                # Stage 3 outputs
                "ps3_evidence_result": context.get("{{ps3_evidence_result}}", {}),
                
                # Stage 4 outputs
                "arbiter_score": context.get("{{arbiter_score}}", 0),
                "iterations_performed": context.get("{{iterations_performed}}", 0),
                
                # Stage 5 outputs
                "final_evidence_json": context.get("{{final_evidence_json}}", {}),
                "final_annotated_doc": context.get("{{final_annotated_doc}}", "{{final_annotated_doc}}"),
                "dual_language_view": context.get("{{dual_language_view}}", "{{dual_language_view}}"),
            }
        )
