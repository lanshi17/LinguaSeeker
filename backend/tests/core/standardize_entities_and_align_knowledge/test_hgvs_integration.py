"""Integration tests for HGVS normalizer + precise matcher end-to-end matching.

These tests exercise the realistic path: a variant candidate in one HGVS form
is expanded into alias forms by ``expand_hgvs_aliases`` and matched against
ClinVar terminology entries stored under a different but equivalent form, via
``PreciseTerminologyMatcher``. The ``FakeRepository`` mirrors the real
repository contract by normalizing the queried alias text with
``normalize_variant_text`` before lookup.

The regression suite at the bottom locks in the variant-id-guarantee fix
(Phases 1-6): variant forms that were previously unmapped/ambiguous against
the dev DB (audited 24 unmapped/ambiguous variants) now resolve to a concrete
ClinVar ``external_id`` — or, for genuinely novel variants, are left UNMAPPED
so Phase 4 assigns a deterministic internal ``internal:variant:<sha12>`` id.
"""

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
from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import (
    expand_hgvs_aliases,
)
from src.core.standardize_entities_and_align_knowledge.normalizers import (
    normalize_variant_text,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    PreciseTerminologyMatcher,
)


class FakeRepository:
    """Repository stub keyed by normalized alias text.

    Mirrors the real repository: the queried alias text is normalized with
    ``normalize_variant_text`` before lookup against the alias map.
    """

    def __init__(self, alias_map: dict[str, tuple[TerminologyCandidate, ...]]):
        self._alias_map = alias_map

    async def find_alias_candidates(self, entity_type, raw_text):
        normalized = normalize_variant_text(raw_text)
        return self._alias_map.get(normalized, ())


def _variant_candidate(
    raw_text: str,
    candidate_id: str = "c1",
    gene_symbol: str = "",
) -> StandardizationCandidate:
    """Build a variant candidate, optionally carrying a gene-symbol context."""
    metadata: dict[str, object] = {}
    if gene_symbol:
        metadata["gene_symbol"] = gene_symbol
    return StandardizationCandidate(
        candidate_id=candidate_id,
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text=raw_text,
        chain_id="chain-1",
        track="original",
        metadata=metadata,
    )


def _clinvar_terminology(
    normalized_alias: str,
    entry_id: str = "entry-vcv0001",
    external_id: str = "VCV000000001",
    gene_symbol: str = "",
    alias_type: str = "alias",
) -> TerminologyCandidate:
    """Build a ClinVar variant terminology candidate.

    When ``gene_symbol`` is provided it is stored in ``raw_payload`` so the
    precise matcher's gene-context disambiguation can compare it against the
    candidate's gene signal.
    """
    raw_payload: dict[str, object] = {}
    if gene_symbol:
        raw_payload["gene_symbol"] = gene_symbol
    return TerminologyCandidate(
        entry_id=entry_id,
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id=external_id,
        display_name=normalized_alias,
        normalized_alias=normalized_alias,
        alias_type=alias_type,
        raw_payload=raw_payload,
    )


@pytest.mark.asyncio
async def test_three_letter_protein_matches_clinvar_one_letter() -> None:
    """Three-letter protein variant p.(Glu292Val) matches ClinVar alias p.E292V."""
    terminology = _clinvar_terminology("p.E292V", entry_id="entry-vcv0001", external_id="VCV000000001")
    repository = FakeRepository({"p.E292V": (terminology,)})

    match = await PreciseTerminologyMatcher(repository).match(_variant_candidate("p.(Glu292Val)"))

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "VCV000000001"
    assert match.match_method == MatchMethod.PRECISE


@pytest.mark.asyncio
async def test_bare_dna_notation_matches_clinvar_bare_form() -> None:
    """Bare DNA notation c.727C>T matches ClinVar alias stored as c.727C>T."""
    terminology = _clinvar_terminology("c.727C>T", entry_id="entry-vcv0002", external_id="VCV000000002")
    repository = FakeRepository({"c.727C>T": (terminology,)})

    match = await PreciseTerminologyMatcher(repository).match(_variant_candidate("c.727C>T"))

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "VCV000000002"
    assert match.match_method == MatchMethod.PRECISE


@pytest.mark.parametrize(
    ("raw_text", "expected_alias"),
    [
        ("p.(Glu292Val)", "p.E292V"),
        ("p.Arg243*", "p.R243*"),
        ("p.His97Arg", "p.H97R"),
        ("c.727C>T", "c.727C>T"),
        ("p.Trp159Ter", "p.W159*"),
    ],
)
def test_expand_hgvs_aliases_covers_all_unmapped_patterns(raw_text: str, expected_alias: str) -> None:
    """Every unmapped DB variant pattern expands to its ClinVar-equivalent alias."""
    aliases = expand_hgvs_aliases(raw_text)
    assert expected_alias in aliases, f"expected {expected_alias!r} in expansions of {raw_text!r}, got {aliases}"


# ---------------------------------------------------------------------------
# Regression suite — variant-id-guarantee fix (Phases 1-6).
#
# Each case below was unmapped or ambiguous against the dev DB before the fix
# (audited set of 24 unmapped/ambiguous variants). They now resolve to a
# concrete ClinVar external_id, or are correctly left UNMAPPED.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_text", "gene_symbol", "alias_specs", "expected_external_id"),
    [
        # Case 1: bare c. coding alias (Phase 1) + DICER1 gene context.
        # ClinVar indexes both the bare coding form and the derived protein
        # alias for the same entry; literature citing only c.4748T>G now hits.
        pytest.param(
            "c.4748T>G",
            "DICER1",
            [
                ("c.4748T>G", "vcv-4468", "ClinVarVariation:4468", "DICER1", "coding"),
                ("p.L1583R", "vcv-4468", "ClinVarVariation:4468", "DICER1", "protein_short"),
            ],
            "ClinVarVariation:4468",
            id="coding-alias-dicer1",
        ),
        # Case 2: stop-codon unification. p.Arg243* expands to the canonical
        # p.R243* ClinVar alias (Ter/*/stop/X all fold to *).
        pytest.param(
            "p.Arg243*",
            "",
            [("p.R243*", "vcv-1781", "ClinVarVariation:1781", "", "protein_short")],
            "ClinVarVariation:1781",
            id="stop-codon-star",
        ),
        # Case 3: stop-codon unification via the "stop" word. p.Arg75stop
        # expands to p.R75* and matches the ClinVar alias.
        pytest.param(
            "p.Arg75stop",
            "",
            [("p.R75*", "vcv-43197", "ClinVarVariation:43197", "", "protein_short")],
            "ClinVarVariation:43197",
            id="stop-codon-stop-word",
        ),
        # Case 5: Phase 2 fs/del/dup/ins one-letter protein alias. The importer
        # derives p.F508del from ClinVar names containing p.Phe508del and indexes
        # it; literature citing the one-letter del form now resolves.
        pytest.param(
            "p.F508del",
            "",
            [("p.F508del", "vcv-7109", "ClinVarVariation:7109", "", "protein_short")],
            "ClinVarVariation:7109",
            id="del-protein-phase2",
        ),
    ],
)
@pytest.mark.asyncio
async def test_previously_unmapped_variant_form_resolves(
    raw_text: str,
    gene_symbol: str,
    alias_specs: list[tuple[str, str, str, str, str]],
    expected_external_id: str,
) -> None:
    """Regression: variant forms unmapped before the fix now STANDARDIZE.

    Covers bare c. coding aliases (Phase 1), stop-codon unification (Phase 2),
    and fs/del/dup/ins one-letter protein aliases (Phase 2).
    """
    terms: dict[str, TerminologyCandidate] = {}
    alias_map: dict[str, tuple[TerminologyCandidate, ...]] = {}
    for alias_key, entry_id, external_id, gene, alias_type in alias_specs:
        term = terms.get(entry_id)
        if term is None:
            term = _clinvar_terminology(
                alias_key,
                entry_id=entry_id,
                external_id=external_id,
                gene_symbol=gene,
                alias_type=alias_type,
            )
            terms[entry_id] = term
        alias_map[alias_key] = alias_map.get(alias_key, ()) + (term,)

    repository = FakeRepository(alias_map)
    match = await PreciseTerminologyMatcher(repository).match(_variant_candidate(raw_text, gene_symbol=gene_symbol))

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == expected_external_id
    assert match.match_method == MatchMethod.PRECISE


@pytest.mark.asyncio
async def test_multi_gene_protein_hit_resolves_to_candidate_gene() -> None:
    """Case 4: p.A168T with gene DRD4 resolves to the DRD4 entry, not ambiguous.

    Both DRD4 and BRCA1 ClinVar entries share the protein_short alias p.A168T.
    Before the Phase 3 gene-context fix this collapsed to AMBIGUOUS; now the
    candidate's gene signal selects the DRD4 entry deterministically.
    """
    drd4 = _clinvar_terminology(
        "p.A168T",
        entry_id="vcv-drd4",
        external_id="ClinVarVariation:DRD4",
        gene_symbol="DRD4",
        alias_type="protein_short",
    )
    brca1 = _clinvar_terminology(
        "p.A168T",
        entry_id="vcv-brca1",
        external_id="ClinVarVariation:BRCA1",
        gene_symbol="BRCA1",
        alias_type="protein_short",
    )
    repository = FakeRepository({"p.A168T": (drd4, brca1)})

    match = await PreciseTerminologyMatcher(repository).match(_variant_candidate("p.A168T", gene_symbol="DRD4"))

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "ClinVarVariation:DRD4"
    assert match.terminology_candidates[0].raw_payload["gene_symbol"] == "DRD4"
    assert match.match_method == MatchMethod.PRECISE


@pytest.mark.asyncio
async def test_novel_variant_with_no_clinvar_alias_is_unmapped() -> None:
    """Case 6: a genuinely novel variant with no ClinVar alias is UNMAPPED.

    The matcher returns UNMAPPED; Phase 4's guarantee layer (tested in
    test_repositories.py) then assigns a deterministic internal
    ``internal:variant:<sha12>`` external_id so the variant entity is never
    persisted with a NULL external_id.
    """
    repository = FakeRepository({})

    match = await PreciseTerminologyMatcher(repository).match(_variant_candidate("c.9999X>Y", gene_symbol="NOVELGENE"))

    assert match.status == MatchStatus.UNMAPPED
    assert match.external_id is None
    assert match.terminology_candidates == ()
