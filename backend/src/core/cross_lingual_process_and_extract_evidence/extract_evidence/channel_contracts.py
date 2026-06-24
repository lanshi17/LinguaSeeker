"""Document evidence channel contracts.

A *channel* is the document-type lens through which evidence is extracted.
The LLM first classifies a document into one or more channels
(:class:`DocumentEvidenceChannel`); extraction then restricts the 166-field
catalog to the intersection with fields that are extractable from the
detected channel(s).

Channels map to catalog categories (see :data:`_CHANNEL_CATEGORIES`):

- ``case_report``      -- individual case / phenotype / segregation evidence.
- ``functional_study`` -- functional, computational, and experimental evidence.
- ``cohort_study``     -- population-frequency and case-control evidence.

Variant identity (A), contradiction (H), and authority (J) categories are
common to every channel: a variant must be anchored regardless of study
type, contradictory evidence can arise in any design, and external
authority assertions may be referenced by any paper. Category K
(gene-disease validity curation) is cross-paper only and therefore never
single-paper extractable, so it is excluded from every channel.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from .catalog import EVIDENCE_FIELD_SPECS

if TYPE_CHECKING:
    from .contracts import DocumentEvidenceMap


class DocumentEvidenceChannel(str, Enum):
    """Document-type evidence channel.

    The first three values are *concrete* channels that map to a fixed set
    of catalog categories. ``MIXED`` flags a hybrid paper spanning more than
    one concrete channel; ``UNKNOWN`` marks a document whose channel could
    not be determined (extraction falls back to all single-paper fields).
    """

    CASE_REPORT = "case_report"
    FUNCTIONAL_STUDY = "functional_study"
    COHORT_STUDY = "cohort_study"
    MIXED = "mixed"
    UNKNOWN = "unknown"


_CONCRETE_CHANNELS: frozenset[DocumentEvidenceChannel] = frozenset(
    {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
        DocumentEvidenceChannel.COHORT_STUDY,
    }
)

# Catalog categories extractable per concrete channel.
# A (variant identity), H (contradiction), J (authority) are common to all;
# K (curation) is cross-paper only and intentionally absent from every set.
_CHANNEL_CATEGORIES: dict[DocumentEvidenceChannel, frozenset[str]] = {
    DocumentEvidenceChannel.CASE_REPORT: frozenset({"A", "B", "C", "H", "J"}),
    DocumentEvidenceChannel.FUNCTIONAL_STUDY: frozenset({"A", "E", "F", "I", "H", "J"}),
    DocumentEvidenceChannel.COHORT_STUDY: frozenset({"A", "D", "G", "H", "J"}),
}

_CURATION_CATEGORY = "K"


def channel_categories(channel: DocumentEvidenceChannel) -> frozenset[str]:
    """Return the catalog categories extractable for ``channel``.

    ``MIXED`` resolves to the union of all concrete channels; ``UNKNOWN``
    resolves to every single-paper category (A-J, i.e. all except K) so that
    an undetectable type does not silently drop extractable fields.
    """
    if channel in _CHANNEL_CATEGORIES:
        return _CHANNEL_CATEGORIES[channel]
    if channel is DocumentEvidenceChannel.MIXED:
        union: set[str] = set()
        for concrete in _CONCRETE_CHANNELS:
            union |= _CHANNEL_CATEGORIES[concrete]
        return frozenset(union)
    # UNKNOWN -- every single-paper (non-curation) category.
    return frozenset(
        spec.category_id
        for spec in EVIDENCE_FIELD_SPECS
        if spec.category_id != _CURATION_CATEGORY
    )


class FieldEligibilityReason(BaseModel):
    """Per-field explanation of channel eligibility."""

    field_id: str
    eligible: bool
    category_id: str
    channels: list[DocumentEvidenceChannel] = Field(default_factory=list)
    reason: str


class ChannelFieldEligibility(BaseModel):
    """Catalog fields permitted for extraction under a channel classification.

    ``allowed_field_ids`` is the intersection of the 166-field catalog with
    the fields extractable from the effective channels. It excludes category
    K (cross-paper curation) by construction. ``reasons`` provides a
    per-field audit trail; ``allowed`` and ``excluded`` partition the full
    catalog.
    """

    channels: list[DocumentEvidenceChannel]
    allowed_field_ids: frozenset[str]
    excluded_field_ids: frozenset[str] = Field(default_factory=frozenset)
    reasons: list[FieldEligibilityReason] = Field(default_factory=list)


class DocumentChannelClassification(BaseModel):
    """LLM classification of a document into evidence channel(s).

    Attributes:
        selected_channels: one or more detected channels. Concrete channels
            always win over ``UNKNOWN``; a bare ``MIXED`` (with no concrete
            channels) expands to all three concrete channels.
        confidence: classifier confidence in ``[0.0, 1.0]``.
        rationale: free-text justification for the channel selection.
        supporting_block_ids: document block ids that support the selection.
    """

    selected_channels: list[DocumentEvidenceChannel] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    supporting_block_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_channels(self) -> DocumentChannelClassification:
        # Deduplicate while preserving first-seen order.
        seen: set[DocumentEvidenceChannel] = set()
        deduped: list[DocumentEvidenceChannel] = []
        for channel in self.selected_channels:
            if channel not in seen:
                seen.add(channel)
                deduped.append(channel)
        # UNKNOWN is mutually exclusive with concrete detections: if the LLM
        # also detected a concrete channel, trust the concrete signal.
        concrete_present = any(channel in _CONCRETE_CHANNELS for channel in deduped)
        if DocumentEvidenceChannel.UNKNOWN in deduped and concrete_present:
            deduped = [
                channel
                for channel in deduped
                if channel is not DocumentEvidenceChannel.UNKNOWN
            ]
        self.selected_channels = deduped
        return self

    @property
    def effective_channels(self) -> list[DocumentEvidenceChannel]:
        """Concrete channels driving field eligibility.

        - Concrete channels present are returned as-is (precise selection
          always wins over the ``MIXED`` shorthand).
        - A bare ``MIXED`` (no concrete channels) expands to all three.
        - ``UNKNOWN`` yields an empty list; callers treat this as the
          permissive fallback (all single-paper fields).
        """
        concrete = [ch for ch in self.selected_channels if ch in _CONCRETE_CHANNELS]
        if concrete:
            return concrete
        if DocumentEvidenceChannel.MIXED in self.selected_channels:
            return list(_CONCRETE_CHANNELS)
        return []


def compute_channel_eligibility(
    classification: DocumentChannelClassification,
) -> ChannelFieldEligibility:
    """Compute the catalog field set permitted by a channel classification.

    The result intersects the 166-field catalog with the fields extractable
    from the classification's effective channels. Category K (cross-paper
    curation) is always excluded.

    **Permissive fallback**: when the effective channels are empty (i.e. the
    classification is ``UNKNOWN``), every single-paper (non-curation) field
    is permitted — 143 fields — so an undetectable document type never
    silently drops extractable fields.
    """
    effective = classification.effective_channels
    cats_by_channel = {ch: channel_categories(ch) for ch in effective}

    if effective:
        category_union: set[str] = set()
        for cats in cats_by_channel.values():
            category_union |= cats
    else:
        # UNKNOWN / no concrete channels: permissive — all single-paper
        # (non-curation) categories, so an undetectable document type never
        # silently drops extractable fields.
        category_union = set(channel_categories(DocumentEvidenceChannel.UNKNOWN))

    allowed: list[str] = []
    excluded: list[str] = []
    reasons: list[FieldEligibilityReason] = []

    for spec in EVIDENCE_FIELD_SPECS:
        if spec.category_id == _CURATION_CATEGORY:
            excluded.append(spec.field_id)
            reasons.append(
                FieldEligibilityReason(
                    field_id=spec.field_id,
                    eligible=False,
                    category_id=spec.category_id,
                    channels=[],
                    reason="curation: cross-paper only, not single-paper extractable",
                )
            )
            continue
        covering = [
            ch for ch in effective if spec.category_id in cats_by_channel[ch]
        ]
        if spec.category_id in category_union:
            allowed.append(spec.field_id)
            if covering:
                ch_names = ", ".join(ch.value for ch in covering)
                reason = f"category {spec.category_id} covered by channel(s): {ch_names}"
            else:
                reason = f"category {spec.category_id} covered (unknown permissive fallback)"
            reasons.append(
                FieldEligibilityReason(
                    field_id=spec.field_id,
                    eligible=True,
                    category_id=spec.category_id,
                    channels=covering,
                    reason=reason,
                )
            )
        else:
            excluded.append(spec.field_id)
            reasons.append(
                FieldEligibilityReason(
                    field_id=spec.field_id,
                    eligible=False,
                    category_id=spec.category_id,
                    channels=[],
                    reason=f"category {spec.category_id} not covered by detected channels",
                )
            )

    reported = effective if effective else [DocumentEvidenceChannel.UNKNOWN]
    return ChannelFieldEligibility(
        channels=reported,
        allowed_field_ids=frozenset(allowed),
        excluded_field_ids=frozenset(excluded),
        reasons=reasons,
    )


@dataclass(frozen=True)
class RelevanceScanResult:
    """Bundle the relevance scan produces: evidence map + channel classification.

    The relevance scan LLM call returns a single JSON object carrying both
    the document evidence map (relevance, terms, structure) and the document
    channel classification.  This dataclass pairs them so the stage can
    return both without changing the existing ``DocumentEvidenceMap`` type.
    """

    evidence_map: DocumentEvidenceMap
    channel_classification: DocumentChannelClassification


def merge_channel_classifications(
    classifications: list[DocumentChannelClassification],
) -> DocumentChannelClassification:
    """Merge chunk-level channel classifications into one document-level result.

    Strategy: prefer the highest-confidence concrete-channel classification.
    If no chunk produced concrete channels, fall back to the highest-confidence
    non-UNKNOWN result.  If all chunks are UNKNOWN, return UNKNOWN.  Channel
    lists from the winning chunk are unioned across all chunks that share the
    winning strategy (concrete vs. permissive), so a multi-chunk document that
    shows functional evidence in chunk 1 and case evidence in chunk 2 keeps
    both channels.
    """
    if not classifications:
        return DocumentChannelClassification(
            selected_channels=[DocumentEvidenceChannel.UNKNOWN],
            confidence=0.0,
            rationale="No relevance scan chunks produced a classification.",
            supporting_block_ids=[],
        )
    if len(classifications) == 1:
        return classifications[0]

    _CONCRETE = {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
        DocumentEvidenceChannel.COHORT_STUDY,
    }

    def _concrete_present(c: DocumentChannelClassification) -> bool:
        return bool(_CONCRETE.intersection(c.selected_channels))

    concrete_chunks = [c for c in classifications if _concrete_present(c)]
    if concrete_chunks:
        winner = max(concrete_chunks, key=lambda c: c.confidence)
        unioned: list[DocumentEvidenceChannel] = []
        seen: set[DocumentEvidenceChannel] = set()
        for c in concrete_chunks:
            for ch in c.selected_channels:
                if ch not in seen:
                    seen.add(ch)
                    unioned.append(ch)
        return DocumentChannelClassification(
            selected_channels=unioned,
            confidence=winner.confidence,
            rationale=winner.rationale,
            supporting_block_ids=winner.supporting_block_ids,
        )

    # No concrete channels in any chunk — pick highest confidence.
    winner = max(classifications, key=lambda c: c.confidence)
    return winner


_CHANNEL_VALUE_MAP: dict[str, DocumentEvidenceChannel] = {
    ch.value: ch for ch in DocumentEvidenceChannel
}


def parse_channel_classification(
    selected_channels: list[str] | None,
    confidence: float | None = None,
    rationale: str | None = None,
    supporting_block_ids: list[str] | None = None,
) -> DocumentChannelClassification:
    """Parse raw LLM channel strings into a :class:`DocumentChannelClassification`.

    Unknown/invalid channel strings are silently dropped.  If no valid channel
    remains, the result falls back to ``UNKNOWN`` with confidence 0.0 and a
    standard rationale, so downstream extraction remains permissive (all
    non-curation fields) rather than silently empty.
    """
    parsed: list[DocumentEvidenceChannel] = []
    if selected_channels:
        for raw in selected_channels:
            key = raw.strip().casefold() if isinstance(raw, str) else ""
            ch = _CHANNEL_VALUE_MAP.get(key)
            if ch is not None and ch not in parsed:
                parsed.append(ch)

    if not parsed:
        return DocumentChannelClassification(
            selected_channels=[DocumentEvidenceChannel.UNKNOWN],
            confidence=0.0,
            rationale="Channel classification unavailable from relevance scan.",
            supporting_block_ids=[],
        )

    clamped_conf = max(0.0, min(1.0, float(confidence))) if confidence is not None else 0.0
    return DocumentChannelClassification(
        selected_channels=parsed,
        confidence=clamped_conf,
        rationale=rationale or "",
        supporting_block_ids=supporting_block_ids or [],
    )
