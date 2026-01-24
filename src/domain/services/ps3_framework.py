"""PS3 four-step SVI evaluation framework."""

from enum import Enum
from typing import Dict, List, Optional


class StepStatus(str, Enum):
    """Status for each PS3 evaluation step."""
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_APPLICABLE = "na"


class PS3Step1Result:
    """Result of Step 1: Disease mechanism clarity."""
    
    def __init__(self, status: StepStatus, reasoning: str):
        self.status = status
        self.reasoning = reasoning
        self.should_continue = status != StepStatus.FAIL


class PS3Step2Result:
    """Result of Step 2: Functional assay method suitability."""
    
    def __init__(self, status: StepStatus, reasoning: str):
        self.status = status
        self.reasoning = reasoning
        self.should_continue = status != StepStatus.FAIL


class PS3Step3Component:
    """Individual component evaluation in Step 3."""
    
    def __init__(self, name: str, status: StepStatus, score: float, max_score: float, detail: str):
        self.name = name
        self.status = status
        self.score = score
        self.max_score = max_score
        self.detail = detail


class PS3Step3Result:
    """Result of Step 3: Experimental validity (4 components)."""
    
    def __init__(self):
        self.controls: Optional[PS3Step3Component] = None
        self.replicates: Optional[PS3Step3Component] = None
        self.method_reliability: Optional[PS3Step3Component] = None
        self.positive_controls: Optional[PS3Step3Component] = None
        
    def get_total_score(self) -> float:
        total = 0
        for component in [self.controls, self.replicates, self.method_reliability, self.positive_controls]:
            if component:
                total += component.score
        return total
    
    def get_max_score(self) -> float:
        return 50  # Total max for Step 3
    
    def overall_status(self) -> StepStatus:
        """Determine overall status based on component results."""
        if any(c and c.status == StepStatus.FAIL for c in [self.controls, self.replicates, self.method_reliability]):
            return StepStatus.FAIL
        if any(c and c.status == StepStatus.NOT_APPLICABLE for c in [self.method_reliability]):
            return StepStatus.NOT_APPLICABLE
        if all(c and c.status == StepStatus.PASS for c in [self.controls, self.replicates, self.method_reliability]):
            return StepStatus.PASS
        return StepStatus.PARTIAL


class PS3Step4Result:
    """Result of Step 4: Variant-specific application and OddsPath."""
    
    def __init__(
        self,
        odds_path_computable: bool,
        odds_path_valid: bool,
        mapping_correct: bool,
        score: float,
        reasoning: str,
    ):
        self.odds_path_computable = odds_path_computable
        self.odds_path_valid = odds_path_valid
        self.mapping_correct = mapping_correct
        self.score = score
        self.reasoning = reasoning


class PS3EvaluationFramework:
    """PS3 SVI four-step evaluation framework."""
    
    @staticmethod
    def evaluate_evidence(
        has_disease_mechanism: bool,
        disease_mechanism_detail: str,
        method_suitable: bool,
        method_detail: str,
        has_controls: bool,
        has_replicates: bool,
        method_reliable: bool,
        has_positive_controls: bool,
        control_variants_count: int,
        odds_path_value: Optional[float] = None,
        odds_path_computable: bool = False,
    ) -> Dict:
        """Evaluate evidence against PS3 four-step framework."""
        
        result = {}
        
        # Step 1: Disease Mechanism
        step1 = PS3Step1Result(
            status=StepStatus.PASS if has_disease_mechanism else StepStatus.FAIL,
            reasoning=disease_mechanism_detail,
        )
        result["step_1"] = {
            "status": step1.status.value,
            "reasoning": step1.reasoning,
        }
        
        if not step1.should_continue:
            result["conclusion"] = "PS3/BS3 not applicable: Disease mechanism unclear"
            return result
        
        # Step 2: Method Suitability
        step2 = PS3Step2Result(
            status=StepStatus.PASS if method_suitable else StepStatus.FAIL,
            reasoning=method_detail,
        )
        result["step_2"] = {
            "status": step2.status.value,
            "reasoning": step2.reasoning,
        }
        
        if not step2.should_continue:
            result["conclusion"] = "PS3/BS3 not applicable: Functional assay method not suitable"
            return result
        
        # Step 3: Experimental Validity
        step3 = PS3Step3Result()
        
        # 3a: Controls
        if has_controls:
            step3.controls = PS3Step3Component(
                "controls",
                StepStatus.PASS,
                15,
                15,
                "Both normal/wild-type and abnormal/pathogenic controls present"
            )
        else:
            step3.controls = PS3Step3Component(
                "controls",
                StepStatus.FAIL,
                0,
                15,
                "Adequate controls not documented"
            )
        
        # 3b: Replicates
        if has_replicates:
            step3.replicates = PS3Step3Component(
                "replicates",
                StepStatus.PASS,
                10,
                10,
                "Biological or technical replicates used"
            )
        else:
            step3.replicates = PS3Step3Component(
                "replicates",
                StepStatus.FAIL,
                0,
                10,
                "No replicates documented"
            )
        
        # 3c: Method Reliability
        if method_reliable:
            step3.method_reliability = PS3Step3Component(
                "method_reliability",
                StepStatus.PASS,
                15,
                15,
                "Historically validated or certified kit method"
            )
        elif method_reliable is None:  # Not specified
            step3.method_reliability = PS3Step3Component(
                "method_reliability",
                StepStatus.NOT_APPLICABLE,
                0,
                15,
                "Method reliability cannot be determined; PS3/BS3 not applicable"
            )
        else:
            step3.method_reliability = PS3Step3Component(
                "method_reliability",
                StepStatus.FAIL,
                0,
                15,
                "Method reliability not established"
            )
        
        # 3d: Positive Controls (known P/LP or B/LB variants)
        if has_positive_controls:
            step3.positive_controls = PS3Step3Component(
                "positive_controls",
                StepStatus.PASS,
                10,
                10,
                f"Known pathogenic/benign variants used as controls (n={control_variants_count})"
            )
        else:
            step3.positive_controls = PS3Step3Component(
                "positive_controls",
                StepStatus.FAIL,
                0,
                10,
                "No known P/LP or B/LB variants used as controls"
            )
        
        result["step_3"] = {
            "components": {
                "controls": {
                    "status": step3.controls.status.value,
                    "score": step3.controls.score,
                    "detail": step3.controls.detail,
                },
                "replicates": {
                    "status": step3.replicates.status.value,
                    "score": step3.replicates.score,
                    "detail": step3.replicates.detail,
                },
                "method_reliability": {
                    "status": step3.method_reliability.status.value,
                    "score": step3.method_reliability.score,
                    "detail": step3.method_reliability.detail,
                },
                "positive_controls": {
                    "status": step3.positive_controls.status.value,
                    "score": step3.positive_controls.score,
                    "detail": step3.positive_controls.detail,
                },
            },
            "total_score": step3.get_total_score(),
            "max_score": step3.get_max_score(),
            "overall_status": step3.overall_status().value,
        }
        
        # Check if method reliability failure stops everything
        if step3.method_reliability.status == StepStatus.NOT_APPLICABLE:
            result["conclusion"] = "PS3/BS3 not applicable: Method reliability not established"
            return result
        
        # Step 4: OddsPath Validity and Application
        step4_score = 0
        step4_reasoning = ""
        mapping_correct = False
        
        if odds_path_computable and odds_path_value is not None:
            # Validate odds path is reasonable
            if 0 < odds_path_value < float('inf'):
                step4_score = 20
                mapping_correct = True
                step4_reasoning = f"OddsPath {odds_path_value:.3f} computable and valid"
            else:
                step4_score = 0
                step4_reasoning = f"OddsPath {odds_path_value} out of valid range"
        else:
            step4_score = 10  # Partial credit if not computable but satisfies ③
            step4_reasoning = "OddsPath not computable but controls/replicates sufficient for PS3_supporting"
        
        result["step_4"] = {
            "odds_path_computable": odds_path_computable,
            "odds_path_value": odds_path_value,
            "mapping_correct": mapping_correct,
            "score": step4_score,
            "reasoning": step4_reasoning,
        }
        
        # Final conclusion
        result["conclusion"] = "Evidence evaluated through all steps"
        
        return result
