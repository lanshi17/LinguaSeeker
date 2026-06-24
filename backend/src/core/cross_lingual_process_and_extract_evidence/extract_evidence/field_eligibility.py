"""Field eligibility policy for target-scoped evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass

from .catalog import CATALOG_GROUPS, EvidenceFieldSpec
from .channel_contracts import DocumentChannelClassification
from .contracts import DocumentEvidenceMap, ExtractionTarget
from .field_profile import intersect_profile_fields, resolve_channel_profile_fields


@dataclass(frozen=True)
class FieldEligibilityDecision:
    """Immutable set of field ids allowed for an extraction pass."""

    allowed_field_ids: frozenset[str]
    excluded_field_ids: frozenset[str]
    channel_rejected_field_ids: frozenset[str] = frozenset()
    reasons: tuple[str, ...] = ()


class FieldEligibilityPolicy:
    """Selects source-visible catalog fields for a target extraction pass."""

    _CORE_IDENTITY_FIELDS = frozenset(
        {
            "A.gene_symbol",
            "A.gene_disease_relationship",
            "B.disease_diagnosis",
        }
    )
    _FUNCTIONAL_CUE_WORDS = (
        "assay",
        "biochemical",
        "cell model",
        "expression",
        "functional",
        "function",
        "patient cell",
        "patient cells",
        "rescue",
    )
    _POPULATION_CUE_WORDS = (
        "allele frequency",
        "ancestry",
        "carrier frequency",
        "frequency",
        "gnomad",
        "population",
    )
    _AUTHORITY_CUE_WORDS = (
        "assertion",
        "classified",
        "classification",
        "clinvar",
        "expert panel",
        "known pathogenic",
        "pathogenic",
    )
    _VARIANT_CUE_WORDS = (
        "c.",
        "p.",
        "variant",
        "mutation",
        "missense",
        "frameshift",
        "splice",
        "deletion",
        "duplication",
    )

    def decide(
        self,
        extraction_target: ExtractionTarget | None,
        evidence_map: DocumentEvidenceMap | None = None,
        selected_text: str = "",
    ) -> FieldEligibilityDecision:
        """Return the fields eligible for extraction."""
        extractable = self._extractable_field_ids()
        if extraction_target is None:
            return FieldEligibilityDecision(
                allowed_field_ids=extractable,
                excluded_field_ids=frozenset(),
                reasons=("no_target:all_extractable",),
            )

        allowed = set(self._CORE_IDENTITY_FIELDS)
        reasons: list[str] = ["target:core_identity"]
        cue_text = self._cue_text(extraction_target, evidence_map, selected_text)

        if self._has_variant_cue(extraction_target, evidence_map, cue_text):
            allowed.update(self._variant_field_ids())
            reasons.append("cue:variant")
        if self._has_keyword(cue_text, self._AUTHORITY_CUE_WORDS):
            allowed.update(self._authority_field_ids())
            reasons.append("cue:authority")
        if self._has_keyword(cue_text, self._FUNCTIONAL_CUE_WORDS):
            allowed.update(self._functional_field_ids())
            reasons.append("cue:functional")
        if self._has_keyword(cue_text, self._POPULATION_CUE_WORDS):
            allowed.update(self._population_field_ids())
            reasons.append("cue:population")

        allowed_frozenset = frozenset(field_id for field_id in allowed if field_id in extractable)
        excluded = extractable - allowed_frozenset
        return FieldEligibilityDecision(
            allowed_field_ids=allowed_frozenset,
            excluded_field_ids=excluded,
            reasons=tuple(reasons),
        )

    def decide_with_channels(
        self,
        extraction_target: ExtractionTarget | None,
        evidence_map: DocumentEvidenceMap | None = None,
        selected_text: str = "",
        channel_classification: DocumentChannelClassification | None = None,
    ) -> FieldEligibilityDecision:
        """Target/source eligibility ∩ document-channel field matrix.

        The target/source :meth:`decide` result is the **base**.  When a
        channel classification is supplied, the allowed set is further
        restricted to fields extractable from the detected channel(s).
        ``channel_classification is None`` (no classification available)
        is permissive — the base decision is returned unchanged.

        Audit reasons are extended with ``channel:<name>`` entries for each
        effective channel and ``rejected:not_extractable_for_channel`` when
        any base-allowed field is dropped by the channel filter.
        """
        base = self.decide(extraction_target, evidence_map, selected_text)
        if channel_classification is None:
            return base

        channel_fields = resolve_channel_profile_fields(channel_classification)
        allowed = intersect_profile_fields(base.allowed_field_ids, channel_fields)
        if allowed is None:
            allowed = frozenset()

        reasons: list[str] = list(base.reasons)
        effective = channel_classification.effective_channels
        if effective:
            for ch in effective:
                reasons.append(f"channel:{ch.value}")
        else:
            reasons.append("channel:unknown")

        rejected = base.allowed_field_ids - allowed
        if rejected:
            reasons.append("rejected:not_extractable_for_channel")

        # Combine target-excluded and channel-excluded fields
        excluded = base.excluded_field_ids | rejected

        return FieldEligibilityDecision(
            allowed_field_ids=allowed,
            excluded_field_ids=excluded,
            channel_rejected_field_ids=rejected,
            reasons=tuple(reasons),
        )

    @classmethod
    def _extractable_specs(cls) -> tuple[EvidenceFieldSpec, ...]:
        return tuple(
            spec
            for group_name, group in CATALOG_GROUPS.items()
            if group_name != "curation"
            for spec in group
        )

    @classmethod
    def _extractable_field_ids(cls) -> frozenset[str]:
        return frozenset(spec.field_id for spec in cls._extractable_specs())

    @classmethod
    def _variant_field_ids(cls) -> frozenset[str]:
        variant_field_ids = {
            spec.field_id
            for spec in cls._extractable_specs()
            if "variant_evidence" in spec.clingen_modules
            or (
                spec.category_id == "A"
                and (
                    "variant" in spec.field_id
                    or spec.field_id
                    in {
                        "A.transcript_id",
                        "A.reference_sequence",
                        "A.null_variant_detail",
                        "A.protein_effect",
                        "A.functional_domain_or_hotspot",
                        "A.protein_length_change",
                        "A.repeat_region_status",
                        "A.splice_or_synonymous_effect",
                    }
                )
            )
        }
        variant_field_ids.add("F.tested_variant")
        return frozenset(variant_field_ids)

    @classmethod
    def _authority_field_ids(cls) -> frozenset[str]:
        return frozenset(
            spec.field_id
            for spec in cls._extractable_specs()
            if spec.category_id == "J" or "time_validity" in spec.clingen_modules
        )

    @classmethod
    def _functional_field_ids(cls) -> frozenset[str]:
        return frozenset(
            spec.field_id
            for spec in cls._extractable_specs()
            if spec.category_id in {"F", "I"}
            or "functional_alteration" in spec.clingen_modules
            or "function" in spec.clingen_modules
        )

    @classmethod
    def _population_field_ids(cls) -> frozenset[str]:
        return frozenset(
            spec.field_id
            for spec in cls._extractable_specs()
            if spec.category_id == "D"
            or "population" in spec.clingen_modules
            or spec.field_id in {"B.ancestry_or_population", "A.identity_by_descent_variant"}
        )

    @classmethod
    def _has_variant_cue(
        cls,
        extraction_target: ExtractionTarget,
        evidence_map: DocumentEvidenceMap | None,
        cue_text: str,
    ) -> bool:
        if extraction_target.variant_hgvs_p:
            return True
        if evidence_map is not None and evidence_map.variant_terms:
            return True
        return cls._has_keyword(cue_text, cls._VARIANT_CUE_WORDS)

    @classmethod
    def _cue_text(
        cls,
        extraction_target: ExtractionTarget,
        evidence_map: DocumentEvidenceMap | None,
        selected_text: str,
    ) -> str:
        parts = [extraction_target.variant_hgvs_p, selected_text]
        if evidence_map is not None:
            parts.extend(evidence_map.variant_terms)
            parts.extend(evidence_map.structure_hints)
            parts.extend(evidence_map.case_references)
            parts.extend(evidence_map.authority_references)
        return " ".join(part for part in parts if part).casefold()

    @classmethod
    def _has_keyword(cls, text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)
