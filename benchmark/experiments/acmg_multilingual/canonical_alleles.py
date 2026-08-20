"""Frozen MECP2 allele registry: transcript aliases and hard non-identities."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_ALLELES_PATH = Path(__file__).with_name("canonical_alleles.json")


class AlleleAlias(BaseModel):
    """One transcript-level writing of a genomic allele."""

    model_config = ConfigDict(frozen=True)

    transcript: str
    hgvs_c: str
    hgvs_p: str = ""


class CanonicalAllele(BaseModel):
    """One genomic allele. Aliases share this id; not_same_as alleles must not."""

    model_config = ConfigDict(frozen=True)

    allele_id: str = Field(min_length=1)
    gene: str = "MECP2"
    aliases: tuple[AlleleAlias, ...]
    grch38_spdi: str = ""
    clinvar_vcv: str = ""
    clinvar_match: str = "unmatched"
    queried_on: str = ""
    not_same_as: tuple[str, ...] = ()
    notes: str = ""

    @model_validator(mode="after")
    def validate_allele(self) -> CanonicalAllele:
        """Require at least one alias and forbid self-identity in not_same_as."""
        if not self.aliases:
            raise ValueError(f"{self.allele_id}: aliases must not be empty")
        if self.allele_id in self.not_same_as:
            raise ValueError(f"{self.allele_id}: not_same_as cannot include itself")
        return self


class CanonicalAlleleRegistry(BaseModel):
    """Closed set of alleles referenced by the direct-inference table."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    created_on: str
    scope_note: str
    alleles: tuple[CanonicalAllele, ...]

    @model_validator(mode="after")
    def validate_registry(self) -> CanonicalAlleleRegistry:
        """Reject duplicate ids and dangling not_same_as pointers."""
        ids = [allele.allele_id for allele in self.alleles]
        if len(set(ids)) != len(ids):
            raise ValueError("allele_id values must be unique")
        known = set(ids)
        for allele in self.alleles:
            missing = [other for other in allele.not_same_as if other not in known]
            if missing:
                raise ValueError(f"{allele.allele_id}: unknown not_same_as {missing}")
        by_vcv: dict[str, str] = {}
        for allele in self.alleles:
            if not allele.clinvar_vcv:
                continue
            previous = by_vcv.get(allele.clinvar_vcv)
            if previous and previous != allele.allele_id:
                raise ValueError(
                    f"ClinVar {allele.clinvar_vcv} is bound to both {previous} and {allele.allele_id}"
                )
            by_vcv[allele.clinvar_vcv] = allele.allele_id
        return self


def load_canonical_allele_registry(path: Path | None = None) -> CanonicalAlleleRegistry:
    """Load and validate the frozen allele registry."""
    payload = json.loads((path or DEFAULT_ALLELES_PATH).read_text(encoding="utf-8"))
    return CanonicalAlleleRegistry.model_validate(payload)


def assert_events_resolve(
    registry: CanonicalAlleleRegistry,
    allele_ids: tuple[str, ...],
) -> None:
    """Fail if an inference event points at an unregistered allele."""
    known = {allele.allele_id for allele in registry.alleles}
    missing = sorted({allele_id for allele_id in allele_ids if allele_id not in known})
    if missing:
        raise ValueError(f"unregistered canonical_allele_id values: {missing}")


class EventAlleleBinding(BaseModel):
    """One inference event's pointer into the allele registry."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    canonical_allele_id: str
    clinvar_vcv: str = ""
    clinvar_match: str = "unmatched"


_IDENTITY_MATCHES = frozenset({"exact", "transcript_alias"})
_REQUIRED_SPLITS = (
    ("VCV000143702", "VCV000011815"),
    ("unmatched_c.194delC", "VCV001076185"),
    ("unmatched_c.194delC", "lovd_c.194C>G_S65X"),
)


def assert_hard_non_identities(registry: CanonicalAlleleRegistry) -> None:
    """Require the reviewer-facing allele splits to stay bidirectional."""
    by_id = {allele.allele_id: allele for allele in registry.alleles}
    for left, right in _REQUIRED_SPLITS:
        if left not in by_id or right not in by_id:
            raise ValueError(f"required split {left} / {right} is missing from the registry")
        if right not in by_id[left].not_same_as or left not in by_id[right].not_same_as:
            raise ValueError(f"{left} and {right} must list each other in not_same_as")


def assert_event_bindings(
    registry: CanonicalAlleleRegistry,
    bindings: tuple[EventAlleleBinding, ...],
) -> None:
    """Keep inference allele_ids aligned with registry VCV identity rules."""
    assert_events_resolve(registry, tuple(binding.canonical_allele_id for binding in bindings))
    assert_hard_non_identities(registry)
    by_id = {allele.allele_id: allele for allele in registry.alleles}
    for binding in bindings:
        allele = by_id[binding.canonical_allele_id]
        if binding.clinvar_match in _IDENTITY_MATCHES:
            if allele.clinvar_vcv and binding.clinvar_vcv != allele.clinvar_vcv:
                raise ValueError(
                    f"{binding.event_id}: clinvar_vcv {binding.clinvar_vcv} "
                    f"does not match registry {allele.clinvar_vcv}"
                )
        if binding.clinvar_match == "coordinate_near":
            if binding.canonical_allele_id == binding.clinvar_vcv:
                raise ValueError(
                    f"{binding.event_id}: coordinate_near must not reuse the near VCV as allele_id"
                )
            if binding.clinvar_vcv and binding.clinvar_vcv not in allele.not_same_as:
                raise ValueError(
                    f"{binding.event_id}: near VCV {binding.clinvar_vcv} must sit in "
                    f"{allele.allele_id}.not_same_as"
                )
