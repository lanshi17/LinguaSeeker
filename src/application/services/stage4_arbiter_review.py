"""
阶段四：仲裁评审与迭代优化

验收标准：
- {{arbiter_score}} ≥ 80 或已达最大迭代次数
- 每次迭代均有明确修改依据
- 溯源信息完整性与评分机制合规性是评分关键维度
"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Any

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.timer import Timer


class Stage4ArbiterReviewStep(IPipelineStep):
    """
    Pipeline step for evidence quality evaluation and iterative improvement.
    
    Key responsibilities:
    1. Score evidence quality (0-100)
    2. Identify quality issues and provide actionable feedback
    3. Support iterative improvement (max 3 rounds)
    4. Accept if score ≥ 80, else reject and mark as insufficient
    5. Track all iterations with clear rationales
    
    Input context:
    - {{ps3_evidence_result}}: Evidence JSON from Stage-3
    - {{translated_english_html}}: Source document path
    - {{bbox_metadata}}: Bbox records
    
    Output variables:
    - {{arbiter_score}}: Quality score (0-100)
    - {{arbiter_feedback}}: Structured feedback
    - {{iterations_performed}}: Number of iterations
    """

    def __init__(self, arbiter_llm_client=None, max_iterations: int = 3):
        """Initialize with optional arbiter LLM client."""
        self.arbiter_llm_client = arbiter_llm_client
        self.max_iterations = max_iterations
        self.logger = Logger.get_logger(__name__)

    @property
    def name(self) -> str:
        return "stage4_arbiter_review"

    @property
    def description(self) -> str:
        return "Stage-4: Arbiter quality review and iterative optimization"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate required context."""
        ps3_result = context.get("ps3_evidence_result")
        
        if not ps3_result:
            self.logger.error("Missing ps3_evidence_result in context")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute Stage-4 arbiter review."""
        try:
            ps3_result = context.get("ps3_evidence_result")
            translated_html_path = context.get("translated_english_html_path") or context.get("{{translated_english_html}}")
            bbox_metadata = context.get("bbox_metadata") or []
            out_dir = context.get("out_dir")
            
            self.logger.info("=" * 80)
            self.logger.info("STAGE-4: Arbiter Quality Review and Iterative Optimization")
            self.logger.info("=" * 80)
            
            # Initialize iteration tracking
            current_evidence = ps3_result
            iterations = []
            iteration_count = 0
            final_score = 0
            
            # Iterative review loop
            while iteration_count < self.max_iterations:
                iteration_count += 1
                self.logger.info(f"\n--- Iteration {iteration_count} ---")
                
                # Perform review
                with Timer(f'Arbiter review (iteration {iteration_count})', silent=False):
                    review_result = self._perform_review(
                        evidence=current_evidence,
                        bbox_metadata=bbox_metadata,
                        translated_html_path=translated_html_path
                    )
                
                score = review_result["score"]
                feedback = review_result["feedback"]
                issues = review_result["issues"]
                
                self.logger.info(f"Iteration {iteration_count} score: {score}/100")
                self.logger.info(f"Issues identified: {len(issues)}")
                
                # Track iteration
                iterations.append({
                    "iteration": iteration_count,
                    "score": score,
                    "issues": issues,
                    "feedback": feedback,
                })
                
                final_score = score
                
                # Check if acceptable
                if score >= 80:
                    self.logger.info(f"✓ Evidence accepted with score {score}")
                    break
                
                # If not acceptable and not last iteration, request improvements
                if iteration_count < self.max_iterations:
                    self.logger.info(f"Score {score} < 80, triggering improvement for iteration {iteration_count + 1}")
                    
                    # Request improvements (in production, call main LLM to revise evidence)
                    improvement_result = self._request_improvements(
                        evidence=current_evidence,
                        feedback=feedback,
                        iteration=iteration_count
                    )
                    
                    current_evidence = improvement_result.get("revised_evidence", current_evidence)
                else:
                    self.logger.info(f"Max iterations ({self.max_iterations}) reached")
                    break
            
            # Final result
            self.logger.info("\n" + "=" * 80)
            self.logger.info(f"FINAL RESULT: Score = {final_score}/100")
            self.logger.info(f"Total iterations: {iteration_count}")
            
            if final_score >= 80:
                self.logger.info("Status: ACCEPTED")
            else:
                self.logger.info("Status: INSUFFICIENT EVIDENCE (max iterations reached)")
                self.logger.info("Current best result is output for reference")
            
            # Persist final result
            final_result = {
                "arbiter_score": final_score,
                "iterations_performed": iteration_count,
                "max_iterations": self.max_iterations,
                "status": "ACCEPTED" if final_score >= 80 else "INSUFFICIENT_EVIDENCE",
                "final_evidence": current_evidence,
                "iteration_history": iterations,
            }
            
            result_path = Path(out_dir) / "stage4_arbiter_review.json"
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Arbiter review result saved to: {result_path}")
            
            # Store outputs in context
            context.update({
                "{{arbiter_score}}": final_score,
                "arbiter_score": final_score,
                "{{arbiter_feedback}}": iterations[-1]["feedback"] if iterations else "",
                "arbiter_feedback": iterations[-1]["feedback"] if iterations else "",
                "{{iterations_performed}}": iteration_count,
                "iterations_performed": iteration_count,
                "arbiter_review_result": final_result,
                "arbiter_review_result_path": str(result_path),
                "stage4_complete": True,
            })
            
            self.logger.info("Stage-4 execution completed")
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Stage-4 execution failed: {e}", exc_info=True)
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback: Preserve arbiter review results."""
        self.logger.info("Stage-4 rollback: preserving arbiter review results")
        pass

    def _perform_review(
        self,
        evidence: Dict[str, Any],
        bbox_metadata: List[Dict[str, Any]],
        translated_html_path: str
    ) -> Dict[str, Any]:
        """
        Perform evidence quality review.
        
        Scoring criteria:
        - Pathogenic mechanism clarity (0-20 points)
        - Experimental method adequacy (0-20 points)
        - Control and replicate design (0-20 points)
        - Source traceability (0-20 points)
        - Reasoning completeness (0-20 points)
        
        Returns:
            {
                "score": 0-100,
                "issues": [...],
                "feedback": str
            }
        """
        scores = {}
        issues = []
        
        # 1. Pathogenic mechanism clarity (0-20)
        if evidence.get("pathogenic_mechanism_clear"):
            scores["mechanism"] = 20
        else:
            scores["mechanism"] = 0
            issues.append("Pathogenic mechanism not clearly established")
        
        # 2. Experimental method adequacy (0-20)
        if evidence.get("experimental_method_applicable"):
            scores["method"] = 15
        else:
            scores["method"] = 0
            issues.append("Functional assay method not applicable")
        
        if evidence.get("method_reliability"):
            scores["method"] = min(20, scores["method"] + 5)
        else:
            issues.append("Method reliability not established")
        
        # 3. Control and replicate design (0-20)
        control_score = 0
        
        if evidence.get("control_setup_adequate"):
            control_score += 10
        else:
            issues.append("Control setup inadequate (missing positive/negative controls)")
        
        if evidence.get("replicate_count", 0) >= 3:
            control_score += 10
        elif evidence.get("replicate_count", 0) > 0:
            control_score += 5
            issues.append(f"Limited replicates ({evidence.get('replicate_count')})")
        else:
            issues.append("No replicate information found")
        
        scores["control"] = control_score
        
        # 4. Source traceability (0-20)
        traceability_score = 0
        
        p1_has_location = evidence.get("p1_source") and evidence.get("p1_source") != "not reported"
        p2_has_location = evidence.get("p2_source") and evidence.get("p2_source") != "not reported"
        
        if p1_has_location and p2_has_location:
            traceability_score = 20
        elif p1_has_location or p2_has_location:
            traceability_score = 10
            issues.append("Only partial P1/P2 source location available")
        else:
            traceability_score = 0
            issues.append("P1/P2 source locations not traceable")
        
        scores["traceability"] = traceability_score
        
        # 5. Reasoning completeness (0-20)
        reasoning = evidence.get("reasoning_summary", "")
        reasoning_score = 0
        
        required_keywords = ["mechanism", "control", "replicate", "method"]
        found_keywords = sum(1 for kw in required_keywords if kw.lower() in reasoning.lower())
        
        reasoning_score = (found_keywords / len(required_keywords)) * 20
        if not reasoning:
            issues.append("Reasoning summary is empty")
        
        scores["reasoning"] = reasoning_score
        
        # Calculate total
        total_score = sum(scores.values())
        
        # Build feedback
        feedback_parts = []
        for criterion, score in scores.items():
            feedback_parts.append(f"{criterion}: {score}/20")
        
        feedback = f"Review scores: {' | '.join(feedback_parts)}"
        if issues:
            feedback += f"\nIssues: {'; '.join(issues)}"
        
        return {
            "score": int(total_score),
            "scores": scores,
            "issues": issues,
            "feedback": feedback,
        }

    def _request_improvements(
        self,
        evidence: Dict[str, Any],
        feedback: str,
        iteration: int
    ) -> Dict[str, Any]:
        """
        Request improvements to evidence based on feedback.
        
        In production, this would call the main LLM (DeepSeek-V3) to revise evidence.
        For now, return placeholder response.
        """
        self.logger.info(f"Requesting improvements based on feedback from iteration {iteration}")
        
        # Placeholder: return same evidence
        # In production: call LLM with feedback and get revised evidence
        return {
            "revised_evidence": evidence,
            "revision_rationale": f"Improvements requested for iteration {iteration + 1}"
        }
