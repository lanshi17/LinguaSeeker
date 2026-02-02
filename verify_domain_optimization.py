#!/usr/bin/env python
"""Domain layer optimization verification script."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_domain_imports():
    """Test that domain layer imports work correctly."""
    print("\n=== Testing Domain Layer Imports ===")
    
    try:
        from src.domain import (
            Document,
            Evidence,
            PipelineState,
            Language,
            OddsPath,
            EvidenceStrength,
            StepStatus,
            PS3Step1Result,
            PS3Step2Result,
            PS3Step3Component,
            PS3Step3Result,
            PS3Step4Result,
            PDFRepository,
            RAGRepository,
            LanguageDetectorService,
            TranslatorService,
            EvidenceExtractorService,
            ArbiterService,
            PS3EvaluationService,
        )
        print("✓ All domain exports available")
        return True
    except ImportError as e:
        print(f"✗ Domain import failed: {e}")
        return False


def test_infrastructure_implementations():
    """Test that infrastructure implementations are accessible."""
    print("\n=== Testing Infrastructure Implementations ===")
    
    try:
        from src.infrastructure.implementations import (
            FigureTableDetector,
            P1P2SearchEngine,
        )
        print("✓ Infrastructure implementations available")
        return True
    except ImportError as e:
        print(f"✗ Infrastructure import failed: {e}")
        return False


def test_application_layer():
    """Test that application layer imports work after refactoring."""
    print("\n=== Testing Application Layer ===")
    
    try:
        from src.application.services.evidence_processing_step import (
            EvidenceProcessingStep,
        )
        from src.application.services.pdf_processing_step import PDFProcessingStep
        from src.application.services.translation_step import TranslationStep
        print("✓ Application layer imports correct")
        return True
    except ImportError as e:
        print(f"✗ Application layer import failed: {e}")
        return False


def test_value_objects():
    """Test that PS3 value objects are properly defined."""
    print("\n=== Testing Value Objects ===")
    
    try:
        from src.domain.value_objects.ps3_evaluation import (
            StepStatus,
            PS3Step1Result,
            PS3Step2Result,
            PS3Step3Component,
            PS3Step3Result,
            PS3Step4Result,
        )
        
        # Test creating instances
        step1 = PS3Step1Result(StepStatus.PASS, "Test reasoning")
        step2 = PS3Step2Result(StepStatus.FAIL, "Test reasoning")
        step3 = PS3Step3Result()
        step4 = PS3Step4Result(
            odds_path_computable=True,
            odds_path_valid=True,
            mapping_correct=True,
            score=10.0,
            reasoning="Test",
        )
        
        assert step1.status == StepStatus.PASS
        assert step2.status == StepStatus.FAIL
        assert step3.get_max_score() == 50
        assert step4.odds_path_computable is True
        
        print("✓ Value objects work correctly")
        return True
    except Exception as e:
        print(f"✗ Value objects test failed: {e}")
        return False


def test_service_interfaces():
    """Test that service interfaces are properly defined."""
    print("\n=== Testing Service Interfaces ===")
    
    try:
        from src.domain.services import (
            PS3EvaluationService,
            EvidenceExtractorService,
            ArbiterService,
            LanguageDetectorService,
            TranslatorService,
        )
        from abc import ABC
        
        # Verify all are abstract base classes
        assert issubclass(PS3EvaluationService, ABC)
        assert issubclass(EvidenceExtractorService, ABC)
        assert issubclass(ArbiterService, ABC)
        
        print("✓ All service interfaces are properly abstract")
        return True
    except Exception as e:
        print(f"✗ Service interfaces test failed: {e}")
        return False


def main():
    """Run all verification tests."""
    print("╔═════════════════════════════════════════════════════════════╗")
    print("║   Domain Layer Optimization Verification                  ║")
    print("╚═════════════════════════════════════════════════════════════╝")
    
    results = [
        test_domain_imports(),
        test_infrastructure_implementations(),
        test_application_layer(),
        test_value_objects(),
        test_service_interfaces(),
    ]
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("✓ All verification tests PASSED!")
        print("\nDomain layer optimization is complete and working correctly.")
        return 0
    else:
        print("✗ Some tests FAILED - review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
