"""PS3 evaluation domain service interface."""

from abc import ABC, abstractmethod
from typing import Optional

from ..value_objects.ps3_evaluation import PS3Step1Result, PS3Step2Result, PS3Step3Result, PS3Step4Result


class PS3EvaluationService(ABC):
    """Domain service for PS3 four-step evidence evaluation framework.
    
    This service defines the core business logic for PS3 classification:
    - Step 1: Validate disease mechanism clarity
    - Step 2: Validate functional assay method suitability
    - Step 3: Evaluate experimental validity (controls, replicates, etc.)
    - Step 4: Apply evidence to variant and compute OddsPath
    """

    @abstractmethod
    def evaluate_step1_disease_mechanism(
        self, has_mechanism: bool, mechanism_detail: str
    ) -> PS3Step1Result:
        """Evaluate Step 1: Disease mechanism clarity.
        
        Args:
            has_mechanism: Whether disease mechanism is documented
            mechanism_detail: Description of mechanism
            
        Returns:
            PS3Step1Result with evaluation status and reasoning
        """

    @abstractmethod
    def evaluate_step2_method_suitability(
        self, is_suitable: bool, method_detail: str
    ) -> PS3Step2Result:
        """Evaluate Step 2: Functional assay method suitability.
        
        Args:
            is_suitable: Whether method is suitable for testing mechanism
            method_detail: Description of method
            
        Returns:
            PS3Step2Result with evaluation status and reasoning
        """

    @abstractmethod
    def evaluate_step3_experimental_validity(
        self,
        has_controls: bool,
        has_replicates: bool,
        is_method_reliable: Optional[bool],
        has_positive_controls: bool,
    ) -> PS3Step3Result:
        """Evaluate Step 3: Experimental validity (4 components).
        
        Args:
            has_controls: Both normal and abnormal controls present
            has_replicates: Biological or technical replicates used
            is_method_reliable: Historically validated method
            has_positive_controls: Positive controls documented
            
        Returns:
            PS3Step3Result with component scores and overall status
        """

    @abstractmethod
    def evaluate_step4_variant_application(
        self,
        control_variants_count: int,
        odds_path_value: Optional[float],
        mapping_correct: bool,
    ) -> PS3Step4Result:
        """Evaluate Step 4: Variant-specific application and OddsPath.
        
        Args:
            control_variants_count: Number of control variants tested
            odds_path_value: Computed OddsPath value
            mapping_correct: Whether variant is correctly mapped
            
        Returns:
            PS3Step4Result with application validity assessment
        """

    @abstractmethod
    def evaluate_evidence(
        self,
        has_disease_mechanism: bool,
        disease_mechanism_detail: str,
        method_suitable: bool,
        method_detail: str,
        has_controls: bool,
        has_replicates: bool,
        method_reliable: Optional[bool],
        has_positive_controls: bool,
        control_variants_count: int,
        odds_path_value: Optional[float] = None,
    ) -> dict:
        """Complete PS3 four-step evaluation.
        
        Returns dictionary with all step results and conclusion.
        """
