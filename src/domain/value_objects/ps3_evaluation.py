"""PS3 evaluation value objects."""

from enum import Enum
from typing import Optional


class StepStatus(str, Enum):
    """Status for each PS3 evaluation step."""
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_APPLICABLE = "na"


class PS3Step1Result:
    """Result of Step 1: Disease mechanism clarity (value object)."""
    
    def __init__(self, status: StepStatus, reasoning: str):
        self.status = status
        self.reasoning = reasoning
        self.should_continue = status != StepStatus.FAIL


class PS3Step2Result:
    """Result of Step 2: Functional assay method suitability (value object)."""
    
    def __init__(self, status: StepStatus, reasoning: str):
        self.status = status
        self.reasoning = reasoning
        self.should_continue = status != StepStatus.FAIL


class PS3Step3Component:
    """Individual component evaluation in Step 3 (value object)."""
    
    def __init__(self, name: str, status: StepStatus, score: float, max_score: float, detail: str):
        self.name = name
        self.status = status
        self.score = score
        self.max_score = max_score
        self.detail = detail


class PS3Step3Result:
    """Result of Step 3: Experimental validity (4 components) (value object)."""
    
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
    """Result of Step 4: Variant-specific application and OddsPath (value object)."""
    
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
