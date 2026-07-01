"""Tests for deterministic terminology matching."""

from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityMatch,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.matchers import (
    HybridTerminologyMatcher,
    TerminologyMatcher,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SemanticMatchServiceError,
)


class FakeRepository:
    """Repository stub returning predefined terminology candidates."""

    def __init__(self, candidates):
        self.candidates = tuple(candidates)

    async def find_alias_candidates(self, entity_type, raw_text):
        return self.candidates


@pytest.mark.asyncio
async def test_unique_gene_alias_match_standardizes() -> None:
    """A unique HGNC gene alias match standardizes the candidate."""
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

    matcher = TerminologyMatcher(FakeRepository([terminology]))
    match = await matcher.match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"


@pytest.mark.asyncio
async def test_gene_match_prefers_primary_alias_type_within_hgnc() -> None:
    """Within one source, primary aliases outrank historical or secondary aliases."""
    candidate = StandardizationCandidate(
        candidate_id="c1b",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    previous_symbol = TerminologyCandidate(
        entry_id="entry-old",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:old",
        display_name="Old BRCA1",
        normalized_alias="BRCA1",
        alias_type="previous_symbol",
    )
    primary = TerminologyCandidate(
        entry_id="entry-primary",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:1100",
        display_name="BRCA1",
        normalized_alias="BRCA1",
        alias_type="primary",
    )

    match = await TerminologyMatcher(FakeRepository([previous_symbol, primary])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"


@pytest.mark.asyncio
async def test_multiple_candidates_are_ambiguous() -> None:
    """Multiple deterministic disease candidates remain ambiguous."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="mitochondrial disease",
        chain_id="chain-1",
        track="original",
    )
    choices = [
        TerminologyCandidate("e1", EntityType.DISEASE, "OMIM", "OMIM:1", "Disease A", "mitochondrial disease", "name"),
        TerminologyCandidate("e2", EntityType.DISEASE, "OMIM", "OMIM:2", "Disease B", "mitochondrial disease", "name"),
    ]

    match = await TerminologyMatcher(FakeRepository(choices)).match(candidate)

    assert match.status == MatchStatus.AMBIGUOUS
    assert match.external_id is None


@pytest.mark.asyncio
async def test_disease_match_prefers_omim_over_hpo_and_mondo() -> None:
    """Disease ranking prefers OMIM candidates when they exist."""
    candidate = StandardizationCandidate(
        candidate_id="c2",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="breast cancer",
        chain_id="chain-2",
        track="translated",
    )
    omim = TerminologyCandidate(
        "e1", EntityType.DISEASE, "OMIM", "OMIM:114480", "Breast cancer", "breast cancer", "name"
    )
    hpo = TerminologyCandidate(
        "e2", EntityType.DISEASE, "HPO", "HP:0100013", "Breast neoplasm", "breast cancer", "alias"
    )

    match = await TerminologyMatcher(FakeRepository([hpo, omim])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "OMIM:114480"


@pytest.mark.asyncio
async def test_no_candidates_yields_unmapped() -> None:
    """Candidates with no deterministic terminology match remain unmapped."""
    candidate = StandardizationCandidate(
        candidate_id="c3",
        entity_type=EntityType.VARIANT,
        role=BindingRole.TARGET,
        raw_text="c.9999A>T",
        chain_id="chain-3",
        track="original",
    )

    match = await TerminologyMatcher(FakeRepository([])).match(candidate)

    assert match.status == MatchStatus.UNMAPPED
    assert match.external_id is None


@pytest.mark.asyncio
async def test_variant_match_prefers_candidate_with_matching_gene_symbol_context() -> None:
    """Variant alias ambiguities should be reduced when one ClinVar candidate matches the chain gene context."""
    candidate = StandardizationCandidate(
        candidate_id="c-variant",
        entity_type=EntityType.VARIANT,
        role=BindingRole.TARGET,
        raw_text="p.R227X",
        chain_id="chain-1",
        track="original",
        metadata={"gene_symbol": "GLA"},
    )
    same_alias_other_gene = TerminologyCandidate(
        entry_id="entry-other",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:999",
        display_name="NM_000348.4(SRD5A2):c.679C>T (p.Arg227Ter)",
        normalized_alias="p.R227X",
        alias_type="protein_short",
        raw_payload={"gene_symbol": "SRD5A2"},
    )
    same_alias_expected_gene = TerminologyCandidate(
        entry_id="entry-gla",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:10733",
        display_name="NM_000169.3(GLA):c.679C>T (p.Arg227Ter)",
        normalized_alias="p.R227X",
        alias_type="protein_short",
        raw_payload={"gene_symbol": "GLA"},
    )

    match = await TerminologyMatcher(FakeRepository([same_alias_other_gene, same_alias_expected_gene])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "ClinVarVariation:10733"


def test_rank_raises_for_unsupported_entity_type() -> None:
    """Unsupported entity types fail loudly instead of silently returning no matches."""
    matcher = TerminologyMatcher(FakeRepository([]))

    with pytest.raises(ValueError, match="Unsupported entity type"):
        matcher._rank("protein", ())  # type: ignore[arg-type]


class FakePreciseMatcher:
    """Precise matcher test double."""

    def __init__(self, match):
        self.match_result = match
        self.calls = 0

    async def match(self, candidate):
        self.calls += 1
        return self.match_result


class FakeSimilarityMatcher:
    """Similarity matcher test double."""

    def __init__(self, match):
        self.match_result = match
        self.calls = 0

    async def match(self, candidate):
        self.calls += 1
        return self.match_result


@pytest.mark.asyncio
async def test_hybrid_matcher_uses_similarity_for_unmapped_precise_result() -> None:
    """Similarity matching is a fallback for precise unmapped candidates."""
    candidate = StandardizationCandidate(
        candidate_id="c-semantic",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )
    precise = EntityMatch(candidate, MatchStatus.UNMAPPED, None, "BRCA one")
    semantic = EntityMatch(
        candidate,
        MatchStatus.STANDARDIZED,
        "HGNC:1100",
        "BRCA1",
        match_method=MatchMethod.SIMILARITY,
    )
    semantic_matcher = FakeSimilarityMatcher(semantic)

    match = await HybridTerminologyMatcher(FakePreciseMatcher(precise), semantic_matcher).match(candidate)

    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.SIMILARITY
    assert semantic_matcher.calls == 1


@pytest.mark.asyncio
async def test_hybrid_matcher_does_not_override_precise_standardized_result() -> None:
    """Precise standardized results are authoritative."""
    candidate = StandardizationCandidate(
        candidate_id="c-precise",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    precise = EntityMatch(candidate, MatchStatus.STANDARDIZED, "HGNC:1100", "BRCA1")
    semantic = EntityMatch(
        candidate,
        MatchStatus.STANDARDIZED,
        "HGNC:9999",
        "Wrong",
        match_method=MatchMethod.SIMILARITY,
    )
    semantic_matcher = FakeSimilarityMatcher(semantic)

    match = await HybridTerminologyMatcher(FakePreciseMatcher(precise), semantic_matcher).match(candidate)

    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.PRECISE
    assert semantic_matcher.calls == 0


class FailingSimilarityMatcher:
    """Similarity matcher that raises SemanticMatchServiceError."""

    def __init__(self):
        self.calls = 0

    async def match(self, candidate):
        self.calls += 1
        raise SemanticMatchServiceError("inference service unreachable")


@pytest.mark.asyncio
async def test_hybrid_matcher_degrades_to_unmapped_on_semantic_service_error() -> None:
    """When semantic matching fails with service error, hybrid matcher returns unmapped."""
    candidate = StandardizationCandidate(
        candidate_id="c-error",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )
    precise = EntityMatch(candidate, MatchStatus.UNMAPPED, None, "BRCA one")
    semantic_matcher = FailingSimilarityMatcher()

    match = await HybridTerminologyMatcher(FakePreciseMatcher(precise), semantic_matcher).match(candidate)

    assert match.status == MatchStatus.UNMAPPED
    assert match.match_method == MatchMethod.SIMILARITY
    assert "semantic matching unavailable" in match.rationale
    assert semantic_matcher.calls == 1


class FakeCrossLingualResolver:
    """Cross-lingual disease resolver test double."""

    def __init__(self, resolved: str | None):
        self._resolved = resolved
        self.calls = 0
        self.last_raw_text: str | None = None

    async def resolve(self, raw_text: str) -> str | None:
        self.calls += 1
        self.last_raw_text = raw_text
        return self._resolved


class FakePreciseMatcherWithRetry:
    """Precise matcher that returns UNMAPPED for the original text and a match for the retry text."""

    def __init__(self, unmapped: EntityMatch, retry_match: EntityMatch, retry_raw_text: str):
        self._unmapped = unmapped
        self._retry_match = retry_match
        self._retry_raw_text = retry_raw_text
        self.calls = 0
        self.last_candidate_raw_text: str | None = None

    async def match(self, candidate):
        self.calls += 1
        self.last_candidate_raw_text = candidate.raw_text
        if candidate.raw_text == self._retry_raw_text:
            return self._retry_match
        return self._unmapped


@pytest.mark.asyncio
async def test_hybrid_matcher_uses_cross_lingual_resolver_for_unmapped_disease() -> None:
    """A DISEASE candidate resolved cross-lingually standardizes via a precise retry."""
    candidate = StandardizationCandidate(
        candidate_id="c-xling",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="乳腺癌",
        chain_id="chain-1",
        track="translated",
    )
    unmapped = EntityMatch(candidate, MatchStatus.UNMAPPED, None, "乳腺癌")
    retry_candidate = StandardizationCandidate(
        candidate_id="c-xling",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="breast cancer",
        chain_id="chain-1",
        track="translated",
    )
    retry_match = EntityMatch(
        retry_candidate,
        MatchStatus.STANDARDIZED,
        "OMIM:114480",
        "Breast cancer",
    )
    precise = FakePreciseMatcherWithRetry(unmapped, retry_match, retry_raw_text="breast cancer")
    resolver = FakeCrossLingualResolver(resolved="breast cancer")
    semantic_matcher = FakeSimilarityMatcher(
        EntityMatch(candidate, MatchStatus.STANDARDIZED, "WRONG", "wrong", match_method=MatchMethod.SIMILARITY)
    )

    match = await HybridTerminologyMatcher(
        precise,
        semantic_matcher,
        cross_lingual_disease_resolver=resolver,
    ).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "OMIM:114480"
    assert match.rationale == "cross-lingual fuzzy match"
    assert resolver.calls == 1
    assert resolver.last_raw_text == "乳腺癌"
    assert semantic_matcher.calls == 0


@pytest.mark.asyncio
async def test_hybrid_matcher_falls_through_when_resolver_fails() -> None:
    """When the resolver returns None, similarity matching is still attempted."""
    candidate = StandardizationCandidate(
        candidate_id="c-xling-none",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="未知疾病",
        chain_id="chain-1",
        track="translated",
    )
    unmapped = EntityMatch(candidate, MatchStatus.UNMAPPED, None, "未知疾病")
    precise = FakePreciseMatcher(unmapped)
    resolver = FakeCrossLingualResolver(resolved=None)
    semantic_matcher = FakeSimilarityMatcher(
        EntityMatch(
            candidate,
            MatchStatus.STANDARDIZED,
            "OMIM:1",
            "Disease A",
            match_method=MatchMethod.SIMILARITY,
        )
    )

    match = await HybridTerminologyMatcher(
        precise,
        semantic_matcher,
        cross_lingual_disease_resolver=resolver,
    ).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.match_method == MatchMethod.SIMILARITY
    assert resolver.calls == 1
    assert semantic_matcher.calls == 1


@pytest.mark.asyncio
async def test_hybrid_matcher_skips_resolver_for_non_disease() -> None:
    """Non-DISEASE candidates skip the cross-lingual resolver entirely."""
    candidate = StandardizationCandidate(
        candidate_id="c-variant-xling",
        entity_type=EntityType.VARIANT,
        role=BindingRole.TARGET,
        raw_text="c.9999A>T",
        chain_id="chain-1",
        track="original",
    )
    unmapped = EntityMatch(candidate, MatchStatus.UNMAPPED, None, "c.9999A>T")
    precise = FakePreciseMatcher(unmapped)
    resolver = FakeCrossLingualResolver(resolved="should-not-be-called")
    semantic_matcher = FakeSimilarityMatcher(
        EntityMatch(
            candidate,
            MatchStatus.STANDARDIZED,
            "ClinVarVariation:1",
            "Variant A",
            match_method=MatchMethod.SIMILARITY,
        )
    )

    match = await HybridTerminologyMatcher(
        precise,
        semantic_matcher,
        cross_lingual_disease_resolver=resolver,
    ).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.match_method == MatchMethod.SIMILARITY
    assert resolver.calls == 0
    assert semantic_matcher.calls == 1
