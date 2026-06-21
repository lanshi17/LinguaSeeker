"""Precise deterministic terminology matching rules for Phase 3."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import expand_hgvs_aliases
from src.core.standardize_entities_and_align_knowledge.normalizers import normalize_gene_symbol
from src.core.standardize_entities_and_align_knowledge.repositories import StandardizationRepository


ALIAS_TYPE_PRIORITY = {
    "primary": 0,
    "alias": 1,
    "previous_symbol": 2,
    "name": 3,
    "rsid": 4,
}


class PreciseTerminologyMatcher:
    """Apply deterministic source-priority matching against terminology candidates."""

    def __init__(self, repository: StandardizationRepository):
        self._repository = repository

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Match one candidate to zero, one, or many deterministic terminology entries."""
        if candidate.entity_type == EntityType.VARIANT:
            return await self._match_variant(candidate)
        choices = await self._repository.find_alias_candidates(candidate.entity_type, candidate.raw_text)
        return self._finalize(candidate, choices)

    async def _match_variant(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Match a variant candidate by trying every normalized HGVS alias form.

        ClinVar aliases may store the one-letter protein form, the transcript
        prefix stripped, or list-literal sub-variants, while source text may use
        any equivalent form. We expand the raw text into all alias forms and
        merge repository lookups, deduplicating by ``entry_id`` so a single
        ClinVar entry reachable via multiple aliases is not double counted.
        """
        seen_entry_ids: set[str] = set()
        merged: list[TerminologyCandidate] = []
        for alias in expand_hgvs_aliases(candidate.raw_text):
            for choice in await self._repository.find_alias_candidates(EntityType.VARIANT, alias):
                if choice.entry_id in seen_entry_ids:
                    continue
                seen_entry_ids.add(choice.entry_id)
                merged.append(choice)
        return self._finalize(candidate, merged)

    def _finalize(
        self,
        candidate: StandardizationCandidate,
        choices: list[TerminologyCandidate] | tuple[TerminologyCandidate, ...],
    ) -> EntityMatch:
        """Rank choices and build the final ``EntityMatch`` verdict."""
        ranked = self._rank(candidate.entity_type, tuple(choices), candidate)
        if len(ranked) == 1:
            selected = ranked[0]
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id=selected.external_id,
                display_name=selected.display_name,
                terminology_candidates=(selected,),
                rationale=f"unique {selected.source_db} {selected.alias_type} match",
                match_method=MatchMethod.PRECISE,
            )
        if len(ranked) > 1:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(ranked),
                rationale="multiple deterministic terminology candidates",
                match_method=MatchMethod.PRECISE,
            )
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale="no deterministic terminology candidate",
            match_method=MatchMethod.PRECISE,
        )

    def _rank(
        self,
        entity_type: EntityType,
        choices: tuple[TerminologyCandidate, ...],
        candidate: StandardizationCandidate | None = None,
    ) -> tuple[TerminologyCandidate, ...]:
        """Apply deterministic source ranking by entity type."""
        if entity_type == EntityType.GENE:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "HGNC"),
            )
        if entity_type == EntityType.DISEASE:
            omim = tuple(candidate for candidate in choices if candidate.source_db == "OMIM")
            if omim:
                return self._apply_alias_type_priority(omim)
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db in {"HPO", "MONDO"}),
            )
        if entity_type == EntityType.PHENOTYPE:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "HPO"),
            )
        if entity_type == EntityType.VARIANT:
            ranked = self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "ClinVar"),
            )
            return self._filter_variant_candidates_by_gene_context(ranked, candidate)
        raise ValueError(f"Unsupported entity type: {entity_type}")

    def _apply_alias_type_priority(
        self,
        choices: tuple[TerminologyCandidate, ...],
    ) -> tuple[TerminologyCandidate, ...]:
        """Keep only candidates at the best alias-type priority level."""
        if not choices:
            return ()
        best_priority = min(ALIAS_TYPE_PRIORITY.get(candidate.alias_type, 99) for candidate in choices)
        return tuple(
            candidate
            for candidate in choices
            if ALIAS_TYPE_PRIORITY.get(candidate.alias_type, 99) == best_priority
        )

    def _filter_variant_candidates_by_gene_context(
        self,
        choices: tuple[TerminologyCandidate, ...],
        candidate: StandardizationCandidate | None,
    ) -> tuple[TerminologyCandidate, ...]:
        """Reduce ClinVar variant ambiguities using normalized gene-symbol context.

        Decision tree (D3):
        1. ``choices`` empty → return ``()`` (UNMAPPED).
        2. ``candidate is None`` → return a single deterministic winner
           (``_pick_deterministic_winner``); no gene signal is available, so a
           single winner is acceptable since no gene can disagree.
        3. Normalize the candidate gene (``norm_gene``) and each choice's ClinVar
           ``gene_symbol`` with ``normalize_gene_symbol`` so casing/alias surface
           forms compare equal. Partition choices into ``same_gene`` (normalized
           gene equals ``norm_gene``), only when ``norm_gene`` is truthy.
        4. When ``same_gene`` is non-empty, keep the best alias-type tier within it
           and return a single deterministic winner (entry_id ascending). Same-gene
           same-priority entries are ClinVar duplicates across transcripts/submitters
           and must NOT collapse to ambiguous (STANDARDIZED — correct).
        5. When ``same_gene`` is empty (candidate gene matches no ClinVar entry):
           - ``len(choices) == 1`` → return ``choices`` (a single unambiguous HGVS
             match is a strong identity signal; safe to standardize even without a
             gene match).
           - ``len(choices) > 1`` → return ``()`` (UNMAPPED). Multiple cross-gene
             matches with no gene signal are genuine ambiguity; do NOT guess, since
             a wrong-gene ClinVar ``external_id`` is the primary variant pivot and
             must not be attached gene-agnostically. Phase 4 assigns an internal
             variant id instead.

        The filter therefore returns at most one entry whenever a deterministic
        signal exists, so ``_finalize`` produces ``STANDARDIZED`` rather than
        ``AMBIGUOUS`` for multi-hit variants — while never falsely standardizing a
        multi-gene mismatch to a single wrong-gene ClinVar id.
        """
        if not choices:
            return choices
        if candidate is None:
            return self._pick_deterministic_winner(choices)

        norm_gene = normalize_gene_symbol(str(candidate.metadata.get("gene_symbol", "") or ""))
        same_gene = tuple(
            choice
            for choice in choices
            if normalize_gene_symbol(str(choice.raw_payload.get("gene_symbol", "") or "")) == norm_gene
            and norm_gene
        )
        if same_gene:
            best = self._apply_alias_type_priority(same_gene) or same_gene
            return self._pick_deterministic_winner(best)
        # No gene-matched ClinVar entry. A single unambiguous HGVS match is a safe
        # identity signal; multiple cross-gene matches with no gene signal are genuine
        # ambiguity — do not guess (Phase 4 assigns an internal variant id instead).
        if len(choices) == 1:
            return choices
        return ()

    @staticmethod
    def _pick_deterministic_winner(
        choices: tuple[TerminologyCandidate, ...],
    ) -> tuple[TerminologyCandidate, ...]:
        """Return a single stable winner (entry_id ascending), never ambiguous."""
        if len(choices) <= 1:
            return choices
        return (min(choices, key=lambda item: item.entry_id),)
