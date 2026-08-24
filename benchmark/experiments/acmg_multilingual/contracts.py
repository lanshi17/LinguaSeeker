"""Strongly typed contracts for the ACMG multilingual code-recovery study.

The experiment deliberately separates a source-language comparison from a
clinical code adjudication. Pipeline field labels and ``assigned_acmg_codes``
are not accepted as formal ACMG decisions by these contracts.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ExperimentArm = Literal["english_pivot", "native_only", "dual_track"]
SourceArtifactTrack = Literal["original", "translated"]
TranslationReviewStatus = Literal["pending", "machine_translated", "human_reviewed", "model_reviewed", "rejected"]
ExperimentEntryStatus = Literal["candidate", "needs_translation_review", "ready", "excluded"]
CriterionFamily = Literal["PS2_PM6", "PM3", "PP1_BS4", "PS3_BS3", "PS4"]
FormalCriterion = Literal["PS2", "PM6", "PM3", "PP1", "BS4", "PS3", "BS3", "PS4"]
CriterionOutcome = Literal["qualified", "not_qualified", "not_assessed"]
ParentageStatus = Literal["confirmed", "not_confirmed", "not_reported", "not_applicable"]
EvidenceEligibility = Literal["eligible", "not_eligible"]
CriterionStrength = Literal["very_strong", "strong", "moderate", "supporting", "stand_alone", "not_applicable"]

ACMG_MULTILINGUAL_ARMS: tuple[ExperimentArm, ...] = (
    "english_pivot",
    "native_only",
    "dual_track",
)

REVIEWED_TRANSLATION_STATUSES: frozenset[TranslationReviewStatus] = frozenset(
    {"human_reviewed", "model_reviewed"}
)

_HASH_CHARS = frozenset("0123456789abcdef")
_SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_OPAQUE_PACKET_ID = re.compile(r"^packet-[0-9a-f]{32}$")
_CRITERION_FAMILY_BY_CODE: dict[FormalCriterion, CriterionFamily] = {
    "PS2": "PS2_PM6",
    "PM6": "PS2_PM6",
    "PM3": "PM3",
    "PP1": "PP1_BS4",
    "BS4": "PP1_BS4",
    "PS3": "PS3_BS3",
    "BS3": "PS3_BS3",
    "PS4": "PS4",
}


def _validate_opaque_packet_id(review_packet_id: str) -> None:
    """Reject semantic or caller-selected packet identifiers that can reveal an arm."""
    if not _OPAQUE_PACKET_ID.fullmatch(review_packet_id):
        raise ValueError("review_packet_id must use the generated packet-<32 lowercase hex> format")


def _normalize_reviewer_id(reviewer_id: str, *, field_name: str) -> str:
    """Normalize a clinician identifier while preventing allocation-label leakage."""
    normalized_reviewer_id = reviewer_id.strip()
    if not normalized_reviewer_id:
        raise ValueError(f"{field_name} must not be blank")
    normalized_casefolded = normalized_reviewer_id.casefold()
    if any(arm in normalized_casefolded for arm in ACMG_MULTILINGUAL_ARMS):
        raise ValueError(f"{field_name} must not contain an experimental arm label")
    return normalized_reviewer_id


def _is_english_language_tag(language: str) -> bool:
    """Recognize English labels and BCP-47-style English regional variants."""
    primary_subtag = language.strip().replace("_", "-").split("-", maxsplit=1)[0].casefold()
    return primary_subtag in {"en", "eng", "english"}


class SourceArtifact(BaseModel):
    """A content-addressed document stored below a caller-provided source root."""

    model_config = ConfigDict(frozen=True)

    relative_path: Path
    sha256: str = Field(min_length=64, max_length=64)
    language: str = Field(min_length=2, max_length=16)

    @model_validator(mode="after")
    def validate_relative_path_and_hash(self) -> SourceArtifact:
        """Reject absolute/traversal paths and malformed content hashes."""
        if self.relative_path.is_absolute() or ".." in self.relative_path.parts:
            raise ValueError("relative_path must stay below the configured source root")
        if any(character not in _HASH_CHARS for character in self.sha256):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        normalized_language = self.language.strip()
        if not normalized_language:
            raise ValueError("language must not be blank")
        object.__setattr__(self, "language", normalized_language)
        return self


class ReviewPacketEvidenceArtifact(BaseModel):
    """A neutral, content-addressed model-output file supplied to one reviewer."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    relative_path: Path
    sha256: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_packet_evidence_artifact(self) -> ReviewPacketEvidenceArtifact:
        """Keep reviewer evidence inside its opaque packet directory."""
        if not _SAFE_CASE_ID.fullmatch(self.case_id):
            raise ValueError("case_id must be a safe path component")
        if self.relative_path.is_absolute() or ".." in self.relative_path.parts:
            raise ValueError("relative_path must stay below the reviewer packet root")
        if any(character not in _HASH_CHARS for character in self.sha256):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        return self


class ReviewPanel(BaseModel):
    """The two independent reviewers and separate clinician who signs adjudications."""

    model_config = ConfigDict(frozen=True)

    reviewer_ids: tuple[str, str]
    adjudicator_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review_panel(self) -> ReviewPanel:
        """Require exactly two distinct reviewers and an independent adjudicator."""
        reviewer_ids = tuple(
            _normalize_reviewer_id(reviewer_id, field_name="reviewer_ids")
            for reviewer_id in self.reviewer_ids
        )
        adjudicator_id = _normalize_reviewer_id(self.adjudicator_id, field_name="adjudicator_id")
        if len({reviewer_id.casefold() for reviewer_id in reviewer_ids}) != len(reviewer_ids):
            raise ValueError("reviewer_ids must contain two distinct reviewer identifiers")
        if adjudicator_id.casefold() in {reviewer_id.casefold() for reviewer_id in reviewer_ids}:
            raise ValueError("adjudicator_id must differ from both independent reviewer_ids")
        object.__setattr__(self, "reviewer_ids", reviewer_ids)
        object.__setattr__(self, "adjudicator_id", adjudicator_id)
        return self


class TranslationReview(BaseModel):
    """Review state for the content-equivalent English full-text document."""

    model_config = ConfigDict(frozen=True)

    status: TranslationReviewStatus
    english_fulltext: SourceArtifact | None = None
    alignment_relative_path: Path | None = None
    alignment_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    reviewer_ids: tuple[str, ...] = ()
    reviewed_on: date | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate_review_evidence(self) -> TranslationReview:
        """Require a reviewed translation and alignment map before a run is eligible."""
        if self.alignment_relative_path is not None and (
            self.alignment_relative_path.is_absolute() or ".." in self.alignment_relative_path.parts
        ):
            raise ValueError("alignment_relative_path must stay below the configured source root")
        if self.alignment_sha256 is not None and any(character not in _HASH_CHARS for character in self.alignment_sha256):
            raise ValueError("alignment_sha256 must be a lowercase SHA-256 digest")
        reviewer_ids = tuple(
            _normalize_reviewer_id(reviewer_id, field_name="reviewer_ids")
            for reviewer_id in self.reviewer_ids
        )
        if len({reviewer_id.casefold() for reviewer_id in reviewer_ids}) != len(reviewer_ids):
            raise ValueError("reviewer_ids must not contain duplicates")
        object.__setattr__(self, "reviewer_ids", reviewer_ids)
        if self.status not in REVIEWED_TRANSLATION_STATUSES:
            return self
        missing: list[str] = []
        if self.english_fulltext is None:
            missing.append("english_fulltext")
        if self.alignment_relative_path is None:
            missing.append("alignment_relative_path")
        if self.alignment_sha256 is None:
            missing.append("alignment_sha256")
        expected_reviewer_count = 2 if self.status == "human_reviewed" else 1
        if len(self.reviewer_ids) != expected_reviewer_count:
            missing.append(f"{'two' if expected_reviewer_count == 2 else 'one'} reviewer_ids")
        if self.reviewed_on is None:
            missing.append("reviewed_on")
        if self.status == "model_reviewed" and not self.notes.strip():
            missing.append("notes (model provenance)")
        if missing:
            raise ValueError(f"{self.status} translations require: {', '.join(missing)}")
        if self.english_fulltext is not None and not _is_english_language_tag(self.english_fulltext.language):
            raise ValueError("english_fulltext must have an English language tag")
        return self


class ClinicalAssertion(BaseModel):
    """The single pre-selected clinical assertion contributed by one source family."""

    model_config = ConfigDict(frozen=True)

    assertion_id: str = Field(min_length=1)
    gene_symbol: str = Field(min_length=1)
    disease_label: str = Field(min_length=1)
    variant_hgvs_c: str = Field(min_length=1)
    variant_hgvs_p: str = ""
    planned_criterion_families: tuple[CriterionFamily, ...] = ()

    @model_validator(mode="after")
    def normalize_gene_symbol(self) -> ClinicalAssertion:
        """Normalize the only identifier that has a universal uppercase convention."""
        object.__setattr__(self, "gene_symbol", self.gene_symbol.strip().upper())
        if len(set(self.planned_criterion_families)) != len(self.planned_criterion_families):
            raise ValueError("planned_criterion_families must not contain duplicates")
        return self


class ExperimentEntry(BaseModel):
    """One deduplicated source family and its pre-specified index assertion."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    source_family_id: str = Field(min_length=1)
    family_cluster_id: str = Field(min_length=1)
    native_fulltext: SourceArtifact
    translation_review: TranslationReview
    status: ExperimentEntryStatus
    index_assertion: ClinicalAssertion | None = None
    alias_case_ids: tuple[str, ...] = ()
    exclusion_reason: str = ""
    notes: str = ""

    @model_validator(mode="after")
    def validate_entry_readiness(self) -> ExperimentEntry:
        """Make one source family contribute only an explicitly frozen assertion."""
        if not _SAFE_CASE_ID.fullmatch(self.case_id):
            raise ValueError("case_id must be a safe path component")
        if _is_english_language_tag(self.native_fulltext.language):
            raise ValueError("native_fulltext must be a non-English source-language document")
        if self.status == "ready":
            if self.index_assertion is None:
                raise ValueError("ready entries require index_assertion")
            if self.index_assertion is not None and not self.index_assertion.planned_criterion_families:
                raise ValueError("ready entries require planned_criterion_families")
            if self.translation_review.status not in REVIEWED_TRANSLATION_STATUSES:
                raise ValueError("ready entries require a reviewed English full text")
        if self.status == "excluded" and not self.exclusion_reason.strip():
            raise ValueError("excluded entries require exclusion_reason")
        return self


class ExperimentManifest(BaseModel):
    """Frozen manifest for the three-arm content-controlled experiment."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    created_on: date
    arms: tuple[ExperimentArm, ...] = ACMG_MULTILINGUAL_ARMS
    entries: tuple[ExperimentEntry, ...]

    @model_validator(mode="after")
    def validate_arms_and_deduplication(self) -> ExperimentManifest:
        """Freeze all three arms and reject duplicated source-family denominators."""
        if len(set(self.arms)) != len(self.arms) or set(self.arms) != set(ACMG_MULTILINGUAL_ARMS):
            raise ValueError("arms must contain english_pivot, native_only, and dual_track exactly once")
        case_ids: set[str] = set()
        source_family_ids: set[str] = set()
        ready_family_cluster_ids: set[str] = set()
        assertion_ids: set[str] = set()
        aliases: set[str] = set()
        for entry in self.entries:
            if entry.case_id in case_ids:
                raise ValueError(f"Duplicate case_id: {entry.case_id}")
            if entry.source_family_id in source_family_ids:
                raise ValueError(f"Duplicate source_family_id: {entry.source_family_id}")
            case_ids.add(entry.case_id)
            source_family_ids.add(entry.source_family_id)
            if entry.status == "ready":
                if entry.family_cluster_id in ready_family_cluster_ids:
                    raise ValueError(f"Duplicate ready family_cluster_id: {entry.family_cluster_id}")
                ready_family_cluster_ids.add(entry.family_cluster_id)
            for alias_case_id in entry.alias_case_ids:
                if alias_case_id == entry.case_id or alias_case_id in aliases:
                    raise ValueError(f"Duplicate or self-referential alias_case_id: {alias_case_id}")
                aliases.add(alias_case_id)
            if entry.index_assertion is not None:
                assertion_id = entry.index_assertion.assertion_id
                if assertion_id in assertion_ids:
                    raise ValueError(f"Duplicate assertion_id: {assertion_id}")
                assertion_ids.add(assertion_id)
        if case_ids & aliases:
            raise ValueError("A canonical case_id cannot also appear as an alias_case_id")
        return self


class SourceSpan(BaseModel):
    """A compact, human-verifiable source location for an ACMG decision."""

    model_config = ConfigDict(frozen=True)

    location: str = Field(min_length=1)
    quote: str = Field(min_length=1, max_length=800)
    language: str = Field(min_length=2, max_length=16)
    artifact_track: SourceArtifactTrack


class GoldCriterionEvent(BaseModel):
    """One independently adjudicated ACMG criterion-family event."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    assertion_id: str = Field(min_length=1)
    source_family_id: str = Field(min_length=1)
    criterion_family: CriterionFamily
    source_eligibility: EvidenceEligibility = "not_eligible"
    outcome: CriterionOutcome
    criterion: FormalCriterion | None = None
    strength: CriterionStrength = "not_applicable"
    parentage_status: ParentageStatus = "not_applicable"
    prerequisite_complete: bool = False
    required_fact_ids: tuple[str, ...] = ()
    source_spans: tuple[SourceSpan, ...] = ()
    notes: str = ""

    @model_validator(mode="after")
    def validate_qualified_gold_event(self) -> GoldCriterionEvent:
        """A positive gold event must expose facts and source anchors."""
        if self.criterion is not None and _CRITERION_FAMILY_BY_CODE[self.criterion] != self.criterion_family:
            raise ValueError("criterion does not belong to criterion_family")
        if self.outcome == "qualified":
            if self.source_eligibility != "eligible":
                raise ValueError("qualified gold events require source_eligibility=eligible")
            if (
                self.criterion is None
                or self.strength == "not_applicable"
                or not self.prerequisite_complete
                or not self.required_fact_ids
                or not self.source_spans
            ):
                raise ValueError(
                    "qualified gold events require criterion, strength, complete prerequisites, fact ids, and source spans"
                )
            if self.criterion == "PS2" and self.parentage_status != "confirmed":
                raise ValueError("qualified PS2 gold events require parentage_status=confirmed")
            if self.criterion == "PM6" and self.parentage_status == "not_applicable":
                raise ValueError("qualified PM6 gold events require an explicit parentage status")
        return self


def _validate_gold_event_collection(
    *,
    events: tuple[GoldCriterionEvent, ...],
    is_complete: bool,
) -> set[str]:
    """Validate one complete or draft gold event collection and return its event IDs."""
    event_ids: set[str] = set()
    event_keys: set[tuple[str, str, str]] = set()
    for event in events:
        if event.event_id in event_ids:
            raise ValueError(f"Duplicate event_id: {event.event_id}")
        event_ids.add(event.event_id)
        event_key = (event.assertion_id, event.source_family_id, event.criterion_family)
        if event_key in event_keys:
            raise ValueError("Duplicate assertion/source-family/criterion-family gold event")
        event_keys.add(event_key)
        if is_complete and event.outcome == "not_assessed":
            raise ValueError("complete gold sets cannot contain not_assessed events")
    return event_ids


class GoldReviewerDecisionSet(BaseModel):
    """One clinician's independent gold decisions before final adjudication."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    reviewer_id: str = Field(min_length=1)
    is_complete: bool = False
    events: tuple[GoldCriterionEvent, ...]

    @model_validator(mode="after")
    def validate_gold_reviewer_set(self) -> GoldReviewerDecisionSet:
        """Keep an independent gold return attributable and event-complete."""
        if any(character not in _HASH_CHARS for character in self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        reviewer_id = _normalize_reviewer_id(self.reviewer_id, field_name="reviewer_id")
        object.__setattr__(self, "reviewer_id", reviewer_id)
        _validate_gold_event_collection(events=self.events, is_complete=self.is_complete)
        return self


class GoldAdjudicationSet(BaseModel):
    """Adjudicated gold events with the two independent reviewer returns retained."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    reviewer_ids: tuple[str, ...] = ()
    review_panel: ReviewPanel | None = None
    reviewer_decision_sets: tuple[GoldReviewerDecisionSet, ...] = ()
    is_complete: bool = False
    events: tuple[GoldCriterionEvent, ...]

    @model_validator(mode="after")
    def validate_gold_set(self) -> GoldAdjudicationSet:
        """Require two independent complete reviews before a gold set can be final."""
        if any(character not in _HASH_CHARS for character in self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        event_ids = _validate_gold_event_collection(events=self.events, is_complete=self.is_complete)
        if not self.is_complete:
            return self
        if self.review_panel is None:
            raise ValueError("complete gold sets require a review_panel")
        if tuple(self.reviewer_ids) != self.review_panel.reviewer_ids:
            raise ValueError("complete gold sets must record the review panel reviewer_ids")
        if len(self.reviewer_decision_sets) != len(self.review_panel.reviewer_ids):
            raise ValueError("complete gold sets require both independent reviewer decision sets")

        expected_reviewer_ids = set(self.review_panel.reviewer_ids)
        reviewer_ids = {decision_set.reviewer_id for decision_set in self.reviewer_decision_sets}
        if reviewer_ids != expected_reviewer_ids:
            raise ValueError("gold reviewer decision sets must match the assigned review panel")
        for decision_set in self.reviewer_decision_sets:
            if decision_set.study_id != self.study_id:
                raise ValueError("gold reviewer set study_id does not match gold adjudication")
            if decision_set.manifest_sha256 != self.manifest_sha256:
                raise ValueError("gold reviewer set manifest_sha256 does not match gold adjudication")
            if not decision_set.is_complete:
                raise ValueError("complete gold sets require completed independent reviewer decision sets")
            if _validate_gold_event_collection(
                events=decision_set.events,
                is_complete=True,
            ) != event_ids:
                raise ValueError("gold reviewer decision sets must cover the final gold event set")
        return self


class ArmCriterionDecision(BaseModel):
    """A blinded human review of one arm's formal criterion decision."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    criterion_family: CriterionFamily
    source_eligibility: EvidenceEligibility = "not_eligible"
    outcome: CriterionOutcome
    criterion: FormalCriterion | None = None
    strength: CriterionStrength = "not_applicable"
    parentage_status: ParentageStatus = "not_applicable"
    prerequisite_complete: bool = False
    required_fact_ids: tuple[str, ...] = ()
    source_spans: tuple[SourceSpan, ...] = ()
    reviewer_id: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate_formal_decision(self) -> ArmCriterionDecision:
        """Require traceability before a model output can count as a formal code."""
        if self.criterion is not None and _CRITERION_FAMILY_BY_CODE[self.criterion] != self.criterion_family:
            raise ValueError("criterion does not belong to criterion_family")
        if self.outcome != "qualified":
            return self
        missing: list[str] = []
        if self.criterion is None:
            missing.append("criterion")
        if self.strength == "not_applicable":
            missing.append("strength")
        if self.source_eligibility != "eligible":
            missing.append("source_eligibility=eligible")
        if not self.prerequisite_complete:
            missing.append("prerequisite_complete")
        if not self.required_fact_ids:
            missing.append("required_fact_ids")
        if not self.source_spans:
            missing.append("source_spans")
        if self.reviewer_id is None:
            missing.append("reviewer_id")
        if missing:
            raise ValueError(f"qualified decisions require: {', '.join(missing)}")
        if self.criterion == "PS2" and self.parentage_status != "confirmed":
            raise ValueError("qualified PS2 decisions require parentage_status=confirmed")
        if self.criterion == "PM6" and self.parentage_status == "not_applicable":
            raise ValueError("qualified PM6 decisions require an explicit parentage status")
        return self


def _validate_decision_collection(
    *,
    is_complete: bool,
    decisions: tuple[ArmCriterionDecision, ...],
    expected_reviewer_id: str | None = None,
) -> None:
    """Reject duplicate, unsigned, or misattributed decisions before scoring."""
    event_ids: set[str] = set()
    for decision in decisions:
        if decision.event_id in event_ids:
            raise ValueError(f"Duplicate decision for event_id: {decision.event_id}")
        event_ids.add(decision.event_id)
    if is_complete:
        unreviewed_event_ids = tuple(
            decision.event_id
            for decision in decisions
            if decision.outcome == "not_assessed" or not decision.reviewer_id
        )
        if unreviewed_event_ids:
            raise ValueError(
                "complete decision sets require assessed, reviewer-attributed decisions: "
                + ", ".join(unreviewed_event_ids)
            )
        if expected_reviewer_id is not None:
            misattributed_event_ids = tuple(
                decision.event_id
                for decision in decisions
                if decision.reviewer_id != expected_reviewer_id
            )
            if misattributed_event_ids:
                raise ValueError(
                    "complete decision sets must be attributed to the assigned clinician: "
                    + ", ".join(misattributed_event_ids)
                )


class ArmDecisionSet(BaseModel):
    """All independently reviewed and adjudicator-signed decisions for one arm."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    arm: ExperimentArm
    review_panel: ReviewPanel
    is_complete: bool = False
    decisions: tuple[ArmCriterionDecision, ...]

    @model_validator(mode="after")
    def validate_decision_set(self) -> ArmDecisionSet:
        """Reject duplicate decisions before paired scoring."""
        if any(character not in _HASH_CHARS for character in self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        _validate_decision_collection(
            is_complete=self.is_complete,
            decisions=self.decisions,
            expected_reviewer_id=self.review_panel.adjudicator_id,
        )
        return self


class BlindedArmDecisionPacket(BaseModel):
    """One independent reviewer's opaque packet, with no experimental-arm label."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    review_packet_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    evidence_artifacts: tuple[ReviewPacketEvidenceArtifact, ...] = Field(min_length=1)
    is_complete: bool = False
    decisions: tuple[ArmCriterionDecision, ...]

    @model_validator(mode="after")
    def validate_blinded_packet(self) -> BlindedArmDecisionPacket:
        """Keep reviewer packets opaque, complete only after attributable review."""
        if any(character not in _HASH_CHARS for character in self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        _validate_opaque_packet_id(self.review_packet_id)
        reviewer_id = _normalize_reviewer_id(self.reviewer_id, field_name="reviewer_id")
        object.__setattr__(self, "reviewer_id", reviewer_id)
        evidence_case_ids = tuple(artifact.case_id for artifact in self.evidence_artifacts)
        evidence_paths = tuple(artifact.relative_path for artifact in self.evidence_artifacts)
        if len(set(evidence_case_ids)) != len(evidence_case_ids):
            raise ValueError("reviewer packet contains duplicate evidence case_id values")
        if len(set(evidence_paths)) != len(evidence_paths):
            raise ValueError("reviewer packet contains duplicate evidence relative_path values")
        _validate_decision_collection(
            is_complete=self.is_complete,
            decisions=self.decisions,
            expected_reviewer_id=reviewer_id,
        )
        return self


class BlindedArmAdjudicationPacket(BaseModel):
    """A label-masked final decision packet containing both independent reviews."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    review_packet_id: str = Field(min_length=1)
    evidence_artifacts: tuple[ReviewPacketEvidenceArtifact, ...] = Field(min_length=1)
    review_panel: ReviewPanel
    reviewer_packets: tuple[BlindedArmDecisionPacket, BlindedArmDecisionPacket]
    is_complete: bool = False
    decisions: tuple[ArmCriterionDecision, ...]

    @model_validator(mode="after")
    def validate_adjudication_packet(self) -> BlindedArmAdjudicationPacket:
        """Bind two complete independent reviews to one adjudicator-signed result."""
        if any(character not in _HASH_CHARS for character in self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        _validate_opaque_packet_id(self.review_packet_id)
        evidence_case_ids = tuple(artifact.case_id for artifact in self.evidence_artifacts)
        evidence_paths = tuple(artifact.relative_path for artifact in self.evidence_artifacts)
        if len(set(evidence_case_ids)) != len(evidence_case_ids):
            raise ValueError("adjudication packet contains duplicate evidence case_id values")
        if len(set(evidence_paths)) != len(evidence_paths):
            raise ValueError("adjudication packet contains duplicate evidence relative_path values")

        expected_reviewer_ids = set(self.review_panel.reviewer_ids)
        packet_reviewer_ids = {packet.reviewer_id for packet in self.reviewer_packets}
        if packet_reviewer_ids != expected_reviewer_ids:
            raise ValueError("adjudication packet must contain both assigned independent reviewer packets")

        expected_event_ids: set[str] | None = None
        for reviewer_packet in self.reviewer_packets:
            if reviewer_packet.study_id != self.study_id:
                raise ValueError("reviewer packet study_id does not match adjudication packet")
            if reviewer_packet.manifest_sha256 != self.manifest_sha256:
                raise ValueError("reviewer packet manifest_sha256 does not match adjudication packet")
            if reviewer_packet.review_packet_id != self.review_packet_id:
                raise ValueError("reviewer packet ID does not match adjudication packet")
            if reviewer_packet.evidence_artifacts != self.evidence_artifacts:
                raise ValueError("reviewer packet evidence does not match adjudication packet")
            if not reviewer_packet.is_complete:
                raise ValueError("adjudication packet requires completed independent reviewer packets")
            reviewer_event_ids = {decision.event_id for decision in reviewer_packet.decisions}
            if expected_event_ids is None:
                expected_event_ids = reviewer_event_ids
            elif reviewer_event_ids != expected_event_ids:
                raise ValueError("independent reviewer packets must cover the same decision events")

        _validate_decision_collection(
            is_complete=self.is_complete,
            decisions=self.decisions,
            expected_reviewer_id=self.review_panel.adjudicator_id,
        )
        if self.is_complete and {decision.event_id for decision in self.decisions} != expected_event_ids:
            raise ValueError("complete adjudication packet must cover every independently reviewed event")
        return self


class BlindingMapEntry(BaseModel):
    """Coordinator-only association between an opaque packet and an experimental arm."""

    model_config = ConfigDict(frozen=True)

    review_packet_id: str = Field(min_length=1)
    arm: ExperimentArm
    evidence_manifest_sha256: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_packet_id(self) -> BlindingMapEntry:
        """Keep packet identifiers safe and nonrevealing even in the sealed map."""
        _validate_opaque_packet_id(self.review_packet_id)
        if any(character not in _HASH_CHARS for character in self.evidence_manifest_sha256):
            raise ValueError("evidence_manifest_sha256 must be a lowercase SHA-256 digest")
        return self


class BlindingMap(BaseModel):
    """Coordinator-only mapping required to convert reviewer packets into arm decisions."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    review_panel: ReviewPanel
    entries: tuple[BlindingMapEntry, ...]

    @model_validator(mode="after")
    def validate_blinding_map(self) -> BlindingMap:
        """Require one opaque reviewer packet for every experimental arm."""
        if any(character not in _HASH_CHARS for character in self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        packet_ids = tuple(entry.review_packet_id for entry in self.entries)
        arms = tuple(entry.arm for entry in self.entries)
        if len(set(packet_ids)) != len(packet_ids):
            raise ValueError("blinding map contains duplicate review_packet_id values")
        if len(set(arms)) != len(arms) or set(arms) != set(ACMG_MULTILINGUAL_ARMS):
            raise ValueError("blinding map must contain all three experimental arms exactly once")
        return self


class ArmCodeRecoveryMetric(BaseModel):
    """Formal-code accuracy summary for one arm against frozen gold events."""

    model_config = ConfigDict(frozen=True)

    arm: ExperimentArm
    source_family_count: int = Field(ge=0)
    positive_event_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)


class PairedCodeComparison(BaseModel):
    """Per-positive-event paired recovery counts for one planned contrast."""

    model_config = ConfigDict(frozen=True)

    baseline_arm: ExperimentArm
    comparison_arm: ExperimentArm
    positive_event_count: int = Field(ge=0)
    baseline_only_count: int = Field(ge=0)
    comparison_only_count: int = Field(ge=0)
    both_recovered_count: int = Field(ge=0)
    neither_recovered_count: int = Field(ge=0)
    comparison_only_event_ids: tuple[str, ...] = ()
    baseline_only_event_ids: tuple[str, ...] = ()


class CodeRecoveryReport(BaseModel):
    """Stable code-level report; inference is deliberately left to a later analysis step."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    metrics: tuple[ArmCodeRecoveryMetric, ...]
    comparisons: tuple[PairedCodeComparison, ...]
    missing_decision_event_ids: tuple[str, ...] = ()


class MaterializedInput(BaseModel):
    """The frozen two-document input bundle for one ready source family."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    input_dir: Path
    native_sha256: str = Field(min_length=64, max_length=64)
    english_sha256: str = Field(min_length=64, max_length=64)
    alignment_sha256: str = Field(min_length=64, max_length=64)


class ManifestReadinessReport(BaseModel):
    """Explicit gate status before source files can be materialized or run."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    total_entry_count: int = Field(ge=0)
    ready_entry_count: int = Field(ge=0)
    excluded_entry_count: int = Field(ge=0)
    blocking_case_ids: tuple[str, ...] = ()


class NativeSourceVerification(BaseModel):
    """One native-language source artifact verified against a frozen manifest."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    relative_path: Path
    sha256: str = Field(min_length=64, max_length=64)
    language: str = Field(min_length=2, max_length=16)


class NativeSourceVerificationReport(BaseModel):
    """Receipt for a source-only integrity audit before translation review completes."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    source_root: Path
    source_revision: str = ""
    verified_sources: tuple[NativeSourceVerification, ...]


class MaterializationReport(BaseModel):
    """Result of freezing reviewed source files into extraction input bundles."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    inputs: tuple[MaterializedInput, ...]


class ArmExtractionRun(BaseModel):
    """One content-addressed extraction result for a frozen input bundle and arm."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    arm: ExperimentArm
    input_dir: Path
    input_manifest_sha256: str = Field(min_length=64, max_length=64)
    result_path: Path
    result_sha256: str = Field(min_length=64, max_length=64)
    duration_seconds: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_run_hashes(self) -> ArmExtractionRun:
        """Keep the run receipt bound to its materialized input and result bytes."""
        if any(character not in _HASH_CHARS for character in self.input_manifest_sha256):
            raise ValueError("input_manifest_sha256 must be a lowercase SHA-256 digest")
        if any(character not in _HASH_CHARS for character in self.result_sha256):
            raise ValueError("result_sha256 must be a lowercase SHA-256 digest")
        return self


class ArmExtractionRunReport(BaseModel):
    """Receipt for a completed three-arm extraction batch."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    runs: tuple[ArmExtractionRun, ...]

    @model_validator(mode="after")
    def validate_run_report(self) -> ArmExtractionRunReport:
        """Reject duplicate run receipt entries before a reviewer packet can consume them."""
        if any(character not in _HASH_CHARS for character in self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        run_keys = tuple((run.case_id, run.arm) for run in self.runs)
        if len(set(run_keys)) != len(run_keys):
            raise ValueError("arm run report contains duplicate case/arm entries")
        return self


class AdjudicationTemplateReport(BaseModel):
    """Locations of isolated review templates and the sealed arm allocation map."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    gold_template_path: Path
    gold_reviewer_template_paths: tuple[Path, ...]
    reviewer_packet_paths: tuple[Path, ...]
    coordinator_blinding_map_path: Path


class BlindedAdjudicationTemplateReport(BaseModel):
    """Locations of incomplete, label-masked packets issued to the adjudicator."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    adjudication_packet_paths: tuple[Path, ...]
