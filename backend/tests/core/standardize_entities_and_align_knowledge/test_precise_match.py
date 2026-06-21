"""Tests for precise deterministic terminology matching."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import PreciseTerminologyMatcher


class FakeRepository:
    """Repository stub returning predefined terminology candidates."""

    def __init__(self, candidates):
        self.candidates = tuple(candidates)

    async def find_alias_candidates(self, entity_type, raw_text):
        return self.candidates


class AliasKeyedRepository:
    """Repository stub keyed by the queried alias text.

    Returns the candidates registered for an exact alias, or empty when the
    alias has no entry. Used to simulate ClinVar only knowing the normalized
    one-letter / stripped-transcript form of a variant.
    """

    def __init__(self, entries: dict[str, list[TerminologyCandidate]]):
        self._entries = entries
        self.calls: list[tuple[EntityType, str]] = []

    async def find_alias_candidates(self, entity_type, raw_text):
        self.calls.append((entity_type, raw_text))
        return list(self._entries.get(raw_text, []))


@pytest.mark.asyncio
async def test_precise_matcher_standardizes_unique_hgnc_alias() -> None:
    """Precise matcher preserves existing deterministic matching semantics."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:1100",
        display_name="BRCA1",
        normalized_alias="BRCA1",
        alias_type="primary",
    )

    match = await PreciseTerminologyMatcher(FakeRepository([terminology])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.PRECISE


@pytest.mark.asyncio
async def test_precise_matcher_tries_hgvs_aliases_for_variant() -> None:
    """Three-letter protein variant matches ClinVar alias stored as one-letter form."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="p.(Glu292Val)",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-vcv0001",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="VCV000000001",
        display_name="NM_000059.4(BRCA2):c.5946del",
        normalized_alias="p.E292V",
        alias_type="alias",
    )
    repository = AliasKeyedRepository({"p.E292V": [terminology]})

    match = await PreciseTerminologyMatcher(repository).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "VCV000000001"
    assert match.match_method == MatchMethod.PRECISE
    # The first lookup (3-letter form) must miss, the second (1-letter) must hit.
    assert repository.calls[0] == (EntityType.VARIANT, "p.(Glu292Val)")
    assert repository.calls[1] == (EntityType.VARIANT, "p.E292V")


@pytest.mark.asyncio
async def test_precise_matcher_tries_stripped_transcript_for_variant() -> None:
    """Transcript-prefixed HGVS matches ClinVar alias stored without the prefix."""
    candidate = StandardizationCandidate(
        candidate_id="c2",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="NM_000059.4(BRCA2):c.5946del",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-vcv0002",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="VCV000000002",
        display_name="NM_000059.4(BRCA2):c.5946del",
        normalized_alias="c.5946del",
        alias_type="alias",
    )
    repository = AliasKeyedRepository({"c.5946del": [terminology]})

    match = await PreciseTerminologyMatcher(repository).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "VCV000000002"
    assert match.match_method == MatchMethod.PRECISE
    assert repository.calls[0] == (EntityType.VARIANT, "NM_000059.4(BRCA2):c.5946del")
    assert repository.calls[1] == (EntityType.VARIANT, "c.5946del")


def _variant_candidate(gene_symbol: str, raw_text: str = "p.A168T") -> StandardizationCandidate:
    """Build a variant candidate carrying a gene-symbol context in metadata."""
    return StandardizationCandidate(
        candidate_id="c-variant",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text=raw_text,
        chain_id="chain-1",
        track="original",
        metadata={"gene_symbol": gene_symbol},
    )


def _clinvar(
    entry_id: str,
    external_id: str,
    gene_symbol: str,
    alias_type: str = "protein_short",
    normalized_alias: str = "p.A168T",
) -> TerminologyCandidate:
    """Build a ClinVar variant terminology candidate with a gene-symbol payload."""
    return TerminologyCandidate(
        entry_id=entry_id,
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id=external_id,
        display_name=f"{gene_symbol} {normalized_alias}",
        normalized_alias=normalized_alias,
        alias_type=alias_type,
        raw_payload={"gene_symbol": gene_symbol},
    )


@pytest.mark.asyncio
async def test_variant_gene_context_resolves_despite_casing_mismatch() -> None:
    """Multi-gene variant hit resolves to the gene matching the candidate context (D3)."""
    candidate = _variant_candidate(gene_symbol="DRD4")
    drd4_a = _clinvar("entry-vcv-drd4-1", "VCV000000001", "DRD4")
    drd4_b = _clinvar("entry-vcv-drd4-2", "VCV000000002", "DRD4")
    brca1 = _clinvar("entry-vcv-brca1", "VCV000000003", "BRCA1")

    match = await PreciseTerminologyMatcher(FakeRepository([drd4_a, drd4_b, brca1])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.terminology_candidates[0].raw_payload["gene_symbol"] == "DRD4"


@pytest.mark.asyncio
async def test_variant_gene_context_resolves_with_lowercase_literature_gene() -> None:
    """Lowercase literature gene symbol matches ClinVar uppercase gene via normalization."""
    candidate = _variant_candidate(gene_symbol="brca1", raw_text="p.A168T")
    brca1 = _clinvar("entry-vcv-brca1", "VCV000000003", "BRCA1")

    match = await PreciseTerminologyMatcher(FakeRepository([brca1])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.terminology_candidates[0].raw_payload["gene_symbol"] == "BRCA1"


@pytest.mark.asyncio
async def test_variant_gene_context_absent_gene_multi_candidate_is_unmapped() -> None:
    """Empty candidate gene with multiple ClinVar hits is UNMAPPED, not guessed.

    With no candidate gene signal and several cross-gene ClinVar entries, picking
    any winner gene-agnostically would risk attaching a wrong-gene ClinVar
    external_id (the primary variant pivot). The variant is left UNMAPPED so Phase
    4 assigns a deterministic internal variant id instead.
    """
    candidate = _variant_candidate(gene_symbol="")
    gene_a = _clinvar("entry-vcv-geneA", "VCV000000010", "GENEA")
    gene_b = _clinvar("entry-vcv-geneB", "VCV000000020", "GENEB")

    match = await PreciseTerminologyMatcher(FakeRepository([gene_a, gene_b])).match(candidate)

    assert match.status == MatchStatus.UNMAPPED
    assert match.terminology_candidates == ()


@pytest.mark.asyncio
async def test_variant_same_gene_same_priority_duplicate_collapses_to_single_winner() -> None:
    """Same-gene same-priority ClinVar duplicates resolve to one deterministic entry."""
    candidate = _variant_candidate(gene_symbol="DRD4")
    dup_a = _clinvar("entry-vcv-drd4-1", "VCV000000001", "DRD4")
    dup_b = _clinvar("entry-vcv-drd4-2", "VCV000000002", "DRD4")

    match = await PreciseTerminologyMatcher(FakeRepository([dup_a, dup_b])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert len(match.terminology_candidates) == 1
    assert match.terminology_candidates[0].entry_id == "entry-vcv-drd4-1"


@pytest.mark.asyncio
async def test_variant_gene_context_mismatch_multi_candidate_is_unmapped() -> None:
    """Multiple cross-gene ClinVar hits with no gene signal must NOT be standardized.

    The candidate gene (XYZ) matches no ClinVar entry's gene. Picking any winner
    gene-agnostically would attach a wrong-gene ClinVar external_id — the primary
    variant pivot — so the variant must be left UNMAPPED for Phase 4 internal-id
    assignment instead.
    """
    candidate = _variant_candidate(gene_symbol="XYZ")
    drd4 = _clinvar("entry-vcv-drd4", "VCV000000001", "DRD4")
    bard1 = _clinvar("entry-vcv-bard1", "VCV000000002", "BARD1")
    shh = _clinvar("entry-vcv-shh", "VCV000000003", "SHH")

    match = await PreciseTerminologyMatcher(FakeRepository([drd4, bard1, shh])).match(candidate)

    assert match.status == MatchStatus.UNMAPPED
    assert match.terminology_candidates == ()


@pytest.mark.asyncio
async def test_variant_gene_context_mismatch_single_candidate_standardizes() -> None:
    """A single unambiguous HGVS match standardizes even without a gene match.

    One ClinVar hit is a strong identity signal; with no competing gene to disagree
    with, standardizing is safe (no wrong-gene attribution risk).
    """
    candidate = _variant_candidate(gene_symbol="XYZ")
    drd4 = _clinvar("entry-vcv-drd4", "VCV000000001", "DRD4")

    match = await PreciseTerminologyMatcher(FakeRepository([drd4])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert len(match.terminology_candidates) == 1
    assert match.terminology_candidates[0].entry_id == "entry-vcv-drd4"
