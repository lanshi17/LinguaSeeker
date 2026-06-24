"""Field profiles for evaluation-scoped extraction.

A field profile restricts which catalog fields are sent to the LLM during
extraction.  This reduces prompt size and attention dilution by excluding
fields that are not scored in the evaluation and not needed for evidence
chain assembly.

Profiles are **opt-in**.  The default production behavior extracts all
non-curation catalog fields (143 fields).  Named profiles such as
``DATASET_D_FIELDS`` must be explicitly requested — typically by a
benchmark runner or evaluation config — so that field-budgeted extraction
is never a hidden default.
"""
from __future__ import annotations

from enum import Enum

from .catalog import CATALOG_GROUPS, EvidenceFieldSpec
from .channel_contracts import (
    DocumentChannelClassification,
    compute_channel_eligibility,
)


class ExtractionProfile(str, Enum):
    """Named extraction profiles.

    ``NONE`` is the production default: extract all non-curation fields.
    ``DATASET_D_PUBLICATION`` restricts to the 20 fields scored or needed
    for the merged_73 BIBM evaluation.
    """

    NONE = "none"
    DATASET_D_PUBLICATION = "dataset_d_publication"


# Fields scored in the merged_73 SYSTEM evaluation.
_SCORED_FIELDS: frozenset[str] = frozenset({
    "A.gene_symbol",
    "B.disease_diagnosis",
    "A.gene_disease_relationship",
    "A.variant_hgvs_c",
    "A.variant_hgvs_p",
    "A.variant_type",
    "A.functional_domain_or_hotspot",
    "B.sex",
    "B.age_of_onset",
    "B.mode_of_inheritance_reported",
    "B.clinical_phenotypes",
    "B.hpo_terms",
    "C.de_novo_status",
})

# Identity fields needed for evidence chain assembly but not directly scored.
# These support group_assignment, role_routing, and chain_assembly stages.
_IDENTITY_FIELDS: frozenset[str] = frozenset({
    "A.variant_hgvs_g",        # genomic variant for chain identity
    "A.transcript_id",         # transcript for variant context
    "B.proband_status",        # case identity
    "B.case_count",            # PS4 support
    "B.consanguinity",         # PM3 support
    "C.inheritance_source",    # de novo context
    "D.allele_frequency",      # BA1/BS1 support
})

# Combined profile for dataset D evaluation.
DATASET_D_FIELDS: frozenset[str] = _SCORED_FIELDS | _IDENTITY_FIELDS

# Lookup from enum value to the actual frozenset.
_PROFILE_FIELDS: dict[str, frozenset[str] | None] = {
    ExtractionProfile.NONE: None,
    ExtractionProfile.DATASET_D_PUBLICATION: DATASET_D_FIELDS,
}


def resolve_profile_fields(
    profile: ExtractionProfile | str | None,
) -> frozenset[str] | None:
    """Resolve a profile name to its field set.

    Returns ``None`` for the default (no restriction) profile.
    Raises ``ValueError`` for unknown profile names.
    """
    if profile is None or profile == ExtractionProfile.NONE:
        return None
    key = profile if isinstance(profile, str) else profile.value
    fields = _PROFILE_FIELDS.get(key)
    if fields is None and key not in _PROFILE_FIELDS:
        valid = ", ".join(sorted(_PROFILE_FIELDS))
        raise ValueError(f"Unknown extraction profile {key!r}. Valid: {valid}")
    return fields


def build_profiled_catalog(
    profile_fields: frozenset[str],
) -> dict[str, tuple[EvidenceFieldSpec, ...]]:
    """Return catalog groups filtered to ``profile_fields``.

    The ``curation`` group is always excluded (it is cross-paper GDV metadata,
    not for single-document LLM extraction).
    """
    result: dict[str, tuple[EvidenceFieldSpec, ...]] = {}
    for group_name, specs in CATALOG_GROUPS.items():
        if group_name == "curation":
            continue
        filtered = tuple(s for s in specs if s.field_id in profile_fields)
        if filtered:
            result[group_name] = filtered
    return result


def resolve_channel_profile_fields(
    classification: DocumentChannelClassification,
) -> frozenset[str]:
    """Resolve the catalog fields permitted by a channel classification.

    Delegates to :func:`compute_channel_eligibility` so the channel→field
    matrix has a single source of truth.  Category K (cross-paper curation)
    is always excluded.  ``UNKNOWN`` yields all single-paper fields (143);
    bare ``MIXED`` yields the union of all three concrete channels (143).

    This is the extraction-workflow-facing bridge to the channel contracts:
    callers (e.g. ``CatalogExtractionStage``) consume the returned
    ``frozenset`` without importing ``channel_contracts`` directly.
    """
    return compute_channel_eligibility(classification).allowed_field_ids


def intersect_profile_fields(
    base_profile_fields: frozenset[str] | None,
    channel_fields: frozenset[str] | None,
) -> frozenset[str] | None:
    """Intersect a named profile with a channel field set.

    ``None`` means "no restriction" (permissive):

    - ``None ∩ channel_fields`` → ``channel_fields``
    - ``base_profile_fields ∩ None`` → ``base_profile_fields``
    - ``None ∩ None`` → ``None`` (fully permissive — all non-curation fields)
    - both present → set intersection
    """
    if base_profile_fields is None:
        return channel_fields
    if channel_fields is None:
        return base_profile_fields
    return base_profile_fields & channel_fields
