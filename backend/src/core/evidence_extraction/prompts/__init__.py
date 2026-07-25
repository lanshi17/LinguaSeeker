"""Prompt builders for evidence extraction stages.

Re-exports all prompt builder functions for backward compatibility.
Import directly from specific sub-modules for better dependency tracking.
"""

from .blocks import (
    block_context_ref,
    block_readable_text,
    build_block_prompt_text,
    format_block_prompt_entry,
    map_block_type,
)
from .catalog import (
    get_catalog_extraction_prompt,
)
from .context import (
    get_clinical_context_prompt,
    get_core_identity_retry_prompt,
)
from .evidence_map import (
    disease_boundary_guidance,
    expanded_field_coverage_guidance,
    get_channel_strategy_guidance,
    get_evidence_map_prompt,
    relationship_decision_guidance,
)
from .special import (
    get_source_ambiguity_review_prompt,
    get_special_evidence_prompt,
)

__all__ = [
    "block_context_ref",
    "block_readable_text",
    "build_block_prompt_text",
    "disease_boundary_guidance",
    "expanded_field_coverage_guidance",
    "format_block_prompt_entry",
    "get_catalog_extraction_prompt",
    "get_channel_strategy_guidance",
    "get_clinical_context_prompt",
    "get_core_identity_retry_prompt",
    "get_evidence_map_prompt",
    "get_source_ambiguity_review_prompt",
    "get_special_evidence_prompt",
    "map_block_type",
    "relationship_decision_guidance",
]
