"""Core business logic for evidence extraction.

Re-exports public types from focused sub-modules for convenience.
New code should prefer importing directly from the specific sub-module.
"""

from .evidence_chain import EvidenceChainBuilder
from .grouping import GroupAssigner, make_group_id, normalize_group_token
from .normalization import (
    EvidenceItemNormalizer,
    FieldValueNormalizer,
    RawSourceNormalizer,
)
from .quality import IntraTrackConflictChecker, QualityValidator, TargetEntityGuard
from .source_grounding import SourceGrounder, _fuzzy_ellipsis_match
from .special_evidence import SpecialEvidenceValidator

__all__ = [
    "EvidenceChainBuilder",
    "GroupAssigner",
    "IntraTrackConflictChecker",
    "QualityValidator",
    "RawSourceNormalizer",
    "SourceGrounder",
    "SpecialEvidenceValidator",
    "TargetEntityGuard",
    "EvidenceItemNormalizer",
    "FieldValueNormalizer",
    "make_group_id",
    "normalize_group_token",
    "_fuzzy_ellipsis_match",
]
