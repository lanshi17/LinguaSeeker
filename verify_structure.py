"""Quick syntax and import verification."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def verify_imports():
    """Verify all module imports work correctly."""
    errors = []

    try:
        from domain.value_objects import Language, OddsPath, EvidenceStrength
        print("✓ Value objects imported")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Value objects: {e}")

    try:
        from domain.entities import PipelineState, Evidence, Document
        print("✓ Entities imported")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Entities: {e}")

    try:
        from domain.repositories import PDFRepository, RAGRepository
        print("✓ Repositories imported")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Repositories: {e}")

    try:
        from domain.services import (
            LanguageDetectorService,
            TranslatorService,
            EvidenceExtractorService,
            ArbiterService,
        )
        print("✓ Domain services imported")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Domain services: {e}")

    try:
        from infrastructure.repositories import PDFRepositoryImpl, RAGRepositoryImpl
        print("✓ Repository implementations imported")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Repository impl: {e}")

    try:
        from infrastructure.llm import (
            LanguageDetectorServiceImpl,
            TranslatorServiceImpl,
            EvidenceExtractorServiceImpl,
            ArbiterServiceImpl,
        )
        print("✓ LLM service implementations imported")
    except Exception as e:  # noqa: BLE001
        errors.append(f"LLM impl: {e}")

    try:
        from application.services import (
            RefactoredPipelineOrchestrator,
            PipelineFactory,
            PipelineProcessor,
        )
        print("✓ Application layer imported (refactored)")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Application layer (refactored): {e}")

    try:
        from application.pipeline_runner import run_pipeline, run_pipeline_refactored
        print("✓ Public API imported (application.pipeline_runner)")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Public API: {e}")

    if errors:
        print("\n❌ Import errors found:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("\n✅ All imports successful!")
    return True


def verify_ddd_structure():
    """Verify DDD structure integrity."""
    print("\n--- DDD Structure Verification ---")

    checks = [
        ("src/domain/__init__.py", "Domain layer exports"),
        ("src/infrastructure/__init__.py", "Infrastructure layer exports"),
        ("src/application/__init__.py", "Application layer exports"),
        ("src/domain/interfaces/__init__.py", "Interface layer exports"),
    ]

    all_ok = True
    for file_path, desc in checks:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            print(f"✓ {desc}")
        else:
            print(f"✗ {desc} - {file_path} not found")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    success = verify_imports() and verify_ddd_structure()
    sys.exit(0 if success else 1)
