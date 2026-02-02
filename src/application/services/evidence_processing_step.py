"""Evidence Processing step - handles evidence extraction and quality scoring."""

import json
from pathlib import Path
from typing import Optional

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.domain.repositories import RAGRepository
from src.domain.services import (
    EvidenceExtractorService,
    ArbiterService,
)
from src.infrastructure.implementations import P1P2SearchEngine
from src.infrastructure.utils.logger import Logger


class EvidenceProcessingStep(IPipelineStep):
    """Pipeline step responsible for evidence extraction and scoring.
    
    Responsibilities:
    - Retrieve PS3 guidance from knowledge base
    - Extract evidence from translated content
    - Iteratively improve evidence via arbiter feedback
    - Score evidence quality
    - Manage P1/P2 secondary search
    
    Input context keys:
    - english_markdown: Translated content
    - out_dir: Output directory
    - bbox_metadata: Optional bbox metadata
    
    Output context keys:
    - evidence: Extracted evidence object
    - arbiter_score: Quality score (0-100)
    - arbiter_feedback: Structured feedback
    - iterations_performed: Number of iterations
    - evidence_json_path: Path to saved evidence
    """

    def __init__(
        self,
        rag_repo: RAGRepository,
        evidence_extractor: EvidenceExtractorService,
        arbiter: ArbiterService,
        max_iterations: int = 3,
    ):
        """Initialize evidence processing step.
        
        Args:
            rag_repo: RAG repository for KB retrieval
            evidence_extractor: Evidence extraction service
            arbiter: Evidence quality arbiter service
            max_iterations: Maximum refinement iterations
        """
        self.rag_repo = rag_repo
        self.evidence_extractor = evidence_extractor
        self.arbiter = arbiter
        self.max_iterations = max_iterations
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        """Get step name."""
        return "evidence_processing"

    @property
    def description(self) -> str:
        """Get step description."""
        return "Extract and iteratively refine PS3 evidence with quality scoring"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate prerequisites for evidence processing.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if prerequisites met
        """
        if not context.has("english_markdown"):
            self.logger.error("Missing english_markdown in context")
            return False
        
        if not context.has("out_dir"):
            self.logger.error("Missing out_dir in context")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute evidence processing step.
        
        Args:
            context: Pipeline context
            
        Raises:
            RuntimeError: If execution fails
        """
        try:
            english_markdown = context.get("english_markdown")
            out_dir = context.get("out_dir")
            pdf_path = context.get("pdf_path", "")
            bbox_metadata = context.get("bbox_metadata", [])
            
            self.logger.info("Starting evidence processing...")
            
            # 1. Build KB index and retrieve PS3 guidance
            kb_context = self._retrieve_kb_context()
            
            # 2. Iteratively extract and refine evidence
            evidence, arbiter_feedback, iteration_count = self._extract_with_refinement(
                english_markdown,
                kb_context,
                pdf_path,
                bbox_metadata
            )
            
            # 3. Persist evidence JSON
            evidence_json_path = None
            if evidence:
                evidence_json_path = self._persist_evidence(evidence, out_dir, pdf_path)
            
            # 4. Update context
            context.update({
                "evidence": evidence,
                "arbiter_score": arbiter_feedback.overall_score if arbiter_feedback else 0,
                "arbiter_feedback": arbiter_feedback.to_dict() if arbiter_feedback else {},
                "iterations_performed": iteration_count,
                "evidence_json_path": evidence_json_path,
                "kb_context": kb_context,
            })
            
            self.logger.info(
                f"Evidence processing complete: score={context.get('arbiter_score'):.1f}, "
                f"iterations={iteration_count}"
            )
            
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Evidence processing failed: {e}")
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback evidence processing step.
        
        Args:
            context: Pipeline context
        """
        evidence_json_path = context.get("evidence_json_path")
        if evidence_json_path and Path(evidence_json_path).exists():
            try:
                Path(evidence_json_path).unlink()
                self.logger.info(f"Rolled back: {evidence_json_path}")
            except Exception as e:
                self.logger.warning(f"Rollback cleanup failed: {e}")
        
        context.remove("evidence")
        context.remove("arbiter_score")
        context.remove("arbiter_feedback")
        context.remove("iterations_performed")

    def _retrieve_kb_context(self) -> Optional[str]:
        """Retrieve PS3 guidance from knowledge base.
        
        Returns:
            KB context for evidence extraction, or None if unavailable
        """
        try:
            self.logger.info("Retrieving PS3 context from knowledge base...")
            
            # Build KB index from local files
            kb_files = ["KnowledgeRetrievalBase/acmg_guide.pdf"]
            kb_files_exist = [f for f in kb_files if Path(f).exists()]
            
            if kb_files_exist:
                self.rag_repo.build_knowledge_base_index(kb_files_exist)
            
            # Retrieve guidance with similarity threshold
            context, max_similarity = self.rag_repo.retrieve_from_knowledge_base(
                "PS3 functional evidence SVI four-step framework OddsPath",
                k=4,
                similarity_threshold=0.65,
            )
            
            # Fallback if similarity too low
            if max_similarity < 0.65:
                self.logger.warning(
                    f"KB similarity low ({max_similarity:.3f}); triggering fallback"
                )
                if kb_files_exist:
                    self.rag_repo.fallback_load_and_vectorize(kb_files_exist[0])
                    context, _ = self.rag_repo.retrieve_from_knowledge_base(
                        "PS3 functional evidence SVI four-step framework OddsPath",
                        k=4,
                        similarity_threshold=0.0,
                    )
            
            return context
            
        except Exception as e:
            self.logger.warning(f"KB retrieval failed: {e}")
            return None

    def _extract_with_refinement(
        self,
        english_markdown: str,
        kb_context: Optional[str],
        pdf_path: str,
        bbox_metadata: list,
    ) -> tuple:
        """Iteratively extract and refine evidence.
        
        Args:
            english_markdown: Translated content
            kb_context: Knowledge base context
            pdf_path: Original PDF path
            bbox_metadata: BBox metadata
            
        Returns:
            Tuple of (evidence, arbiter_feedback, iteration_count)
        """
        evidence = None
        arbiter_feedback = None
        iteration = 0
        
        while iteration < self.max_iterations:
            self.logger.info(f"Evidence extraction iteration {iteration + 1}...")
            
            # Prepare feedback from previous iteration
            feedback_prompt = ""
            if arbiter_feedback and arbiter_feedback.key_issues:
                feedback_prompt = (
                    f"\n\nPrevious iteration feedback:\n"
                    f"Key issues: {'; '.join(arbiter_feedback.key_issues[:3])}\n"
                    f"Recommendations: {'; '.join(arbiter_feedback.recommendations[:3])}"
                )
            
            # Extract evidence
            evidence = self.evidence_extractor.extract_evidence(
                english_markdown,
                kb_context or [],
                feedback=feedback_prompt
            )
            
            # Trigger secondary search if P1/P2 data not found
            if (evidence.p1_source_location == "not reported" or
                evidence.p2_source_location == "not reported"):
                self.logger.info("P1/P2 data not found; triggering secondary search...")
                p1_candidates, p2_candidates = P1P2SearchEngine.search_for_p1p2_locations(
                    english_markdown,
                    bbox_metadata
                )
                
                if p1_candidates or p2_candidates:
                    evidence._p1_candidates = p1_candidates
                    evidence._p2_candidates = p2_candidates
            
            # Score evidence
            arbiter_feedback = self.arbiter.score_evidence(evidence, kb_context)
            evidence.arbiter_score = arbiter_feedback.overall_score
            
            iteration += 1
            
            self.logger.info(
                f"Iteration {iteration}: Score={arbiter_feedback.overall_score:.1f}, "
                f"Issues={len(arbiter_feedback.key_issues)}"
            )
            
            # Check if score acceptable or no iteration needed
            if (arbiter_feedback.overall_score >= 80 or
                not arbiter_feedback.should_iterate):
                break
        
        return evidence, arbiter_feedback, iteration

    @staticmethod
    def _persist_evidence(evidence, out_dir: str, pdf_path: str) -> Optional[str]:
        """Persist evidence to JSON file.
        
        Args:
            evidence: Evidence object
            out_dir: Output directory
            pdf_path: Original PDF path
            
        Returns:
            Path to saved evidence file
        """
        try:
            pdf_stem = Path(pdf_path).stem if pdf_path else "evidence"
            evidence_json_path = Path(out_dir) / f"{pdf_stem}_evidence.json"

            # Write native evidence schema
            evidence_json_path.write_text(
                json.dumps(evidence.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # Also write Stage-2 required schema
            stage2_path = Path(out_dir) / f"{pdf_stem}_ps3_stage2.json"
            stage2_payload = EvidenceProcessingStep._build_stage2_payload(evidence)
            stage2_path.write_text(
                json.dumps(stage2_payload, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            return str(evidence_json_path)
        except Exception as e:
            Logger.get_logger(__name__).warning(f"Evidence persistence failed: {e}")
            return None

    @staticmethod
    def _build_stage2_payload(evidence) -> dict:
        """Build Stage-2 JSON output per spec."""
        # Map OddsPath to evidence level per provided table
        odds_val = evidence.odds_path_value if getattr(evidence, "odds_path_computable", True) else None
        level = EvidenceProcessingStep._map_odds_to_level(odds_val)

        # p1/p2 coordinates default
        p1_field = "not reported"
        p2_field = "not reported"
        # If candidates exist from secondary search, take the first as hint
        if hasattr(evidence, "_p1_candidates") and evidence._p1_candidates:
            c = evidence._p1_candidates[0]
            p1_field = {"page": c.get("page"), "bbox": c.get("bbox")}
        if hasattr(evidence, "_p2_candidates") and evidence._p2_candidates:
            c = evidence._p2_candidates[0]
            p2_field = {"page": c.get("page"), "bbox": c.get("bbox")}

        return {
            "ps3_evidence_level": level,
            "odds_path_value": odds_val if odds_val is not None else None,
            "p1_source": p1_field,
            "p2_source": p2_field,
            "reasoning_summary": (evidence.rationale or "")[:500],
        }

    @staticmethod
    def _map_odds_to_level(odds_val: Optional[float]) -> str:
        """Map OddsPath to PS3/BS3 levels per the specified intervals."""
        if odds_val is None:
            # Without OddsPath, allow supporting if criteria met
            return "PS3_supporting"
        v = odds_val
        if v < 0.017:
            return "BS3"
        if 0.017 <= v < 0.05:
            return "BS3_moderate"
        if 0.05 <= v < 0.33:
            return "BS3_supporting"
        if 0.33 <= v < 3.0:
            return "none"
        if 3.0 <= v < 20.0:
            return "PS3_supporting"
        if 20.0 <= v < 60.0:
            return "PS3_moderate"
        return "PS3"
