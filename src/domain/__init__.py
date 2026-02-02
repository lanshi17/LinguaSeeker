"""Domain layer - core business logic only.

Domain layer contains:
- Entities: Document, Evidence, PipelineState
- Value Objects: Language, OddsPath, EvidenceStrength, PS3 evaluation results
- Repositories: Abstract interfaces for data access
- Services: Abstract interfaces for business operations
- Interfaces: Protocol definitions

Technical implementations belong in infrastructure/implementations.
"""

from .entities import Document, Evidence, PipelineState
from .repositories import PDFRepository, RAGRepository
from .services import (
    ArbiterService,
    EvidenceExtractorService,
    LanguageDetectorService,
    PS3EvaluationService,
    TranslatorService,
)
from .value_objects import (
    EvidenceStrength,
    Language,
    OddsPath,
    PS3Step1Result,
    PS3Step2Result,
    PS3Step3Component,
    PS3Step3Result,
    PS3Step4Result,
    StepStatus,
)

__all__ = [
    "PipelineState",
    "Evidence",
    "Document",
    "Language",
    "OddsPath",
    "EvidenceStrength",
    "StepStatus",
    "PS3Step1Result",
    "PS3Step2Result",
    "PS3Step3Component",
    "PS3Step3Result",
    "PS3Step4Result",
    "PDFRepository",
    "RAGRepository",
    "LanguageDetectorService",
    "TranslatorService",
    "EvidenceExtractorService",
    "ArbiterService",
    "PS3EvaluationService",
]
