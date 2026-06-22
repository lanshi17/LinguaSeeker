"""Deterministic source-grounded reconcile for dual-track evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceChain,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    SourcePrecision,
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    CandidateScore,
    FieldDecision,
    ReconcileOutput,
    ReconcileParams,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.alignment import (
    build_alignment_records,
)
from src.utils.text_normalize import normalize_text as _normalize_text
from src.utils.text_normalize import normalize_value as _normalize_value


@dataclass(frozen=True)
class _Candidate:
    """Internal candidate with the track context missing from EvidenceItem."""

    item: EvidenceItem
    track: Track
    normalized_value: str


def reconcile_results(
    original: EvidenceExtractionResult,
    translated: EvidenceExtractionResult,
    params: ReconcileParams = ReconcileParams(),
) -> ReconcileOutput:
    """Reconcile original and translated extraction outputs into one source-grounded result."""
    evidence_decisions = _decide_fields(
        _build_candidates(original, translated, phenotype=False),
        params,
    )
    phenotype_decisions = _decide_fields(
        _build_candidates(original, translated, phenotype=True),
        params,
    )
    accepted_evidence = [decision.accepted for decision in evidence_decisions if decision.accepted is not None]
    accepted_phenotype = [decision.accepted for decision in phenotype_decisions if decision.accepted is not None]
    rejected_evidence = [
        item
        for decision in (*evidence_decisions, *phenotype_decisions)
        for item in decision.rejected
    ]

    result = EvidenceExtractionResult(
        status=_reconciled_status(original, translated),
        document_id=original.document_id,
        track=Track.RECONCILED,
        evidence_map=original.evidence_map or translated.evidence_map,
        evidence_items=accepted_evidence,
        evidence_chains=_deduplicate_chains(original, translated),
        special_evidence=[*original.special_evidence, *translated.special_evidence],
        quality_report=original.quality_report or translated.quality_report,
        normalization_issues=[*original.normalization_issues, *translated.normalization_issues],
        extraction_target=original.extraction_target or translated.extraction_target,
        phenotype_evidence=accepted_phenotype,
        discarded_evidence=[*original.discarded_evidence, *translated.discarded_evidence, *rejected_evidence],
    )
    return ReconcileOutput(
        result=result,
        decisions=(*evidence_decisions, *phenotype_decisions),
        alignment_records=build_alignment_records(original, translated),
    )


def _build_candidates(
    original: EvidenceExtractionResult,
    translated: EvidenceExtractionResult,
    *,
    phenotype: bool,
) -> tuple[_Candidate, ...]:
    original_items = original.phenotype_evidence if phenotype else original.evidence_items
    translated_items = translated.phenotype_evidence if phenotype else translated.evidence_items
    return tuple(
        [
            *(_Candidate(item=item, track=Track.ORIGINAL, normalized_value=_normalize_value(item.value)) for item in original_items),
            *(
                _Candidate(item=item, track=Track.TRANSLATED, normalized_value=_normalize_value(item.value))
                for item in translated_items
            ),
        ]
    )


def _decide_fields(candidates: tuple[_Candidate, ...], params: ReconcileParams) -> tuple[FieldDecision, ...]:
    decisions: list[FieldDecision] = []
    for field_id in sorted({candidate.item.field_id for candidate in candidates}):
        field_candidates = tuple(candidate for candidate in candidates if candidate.item.field_id == field_id)
        scored = tuple(
            (candidate, _score_candidate(candidate, field_candidates))
            for candidate in field_candidates
        )
        ranked = sorted(
            scored,
            key=lambda entry: (
                -entry[1].score,
                entry[1].field_id,
                entry[1].normalized_value,
                entry[1].track.value,
            ),
        )
        accepted_candidate, accepted_score = ranked[0]
        competing_score = _first_conflicting_score(accepted_score, ranked)
        requires_review = (
            competing_score is not None
            and accepted_score.score - competing_score.score < params.conflict_margin
        )
        rationale = _accepted_rationale(accepted_score, requires_review)
        accepted = _annotate_accepted(accepted_candidate.item, rationale, accepted_score, requires_review)
        rejected = tuple(
            _annotate_rejected(candidate.item, candidate.track, score, accepted_score)
            for candidate, score in ranked[1:]
        )
        decisions.append(
            FieldDecision(
                field_id=field_id,
                accepted=accepted,
                accepted_score=accepted_score,
                rejected=rejected,
                requires_review=requires_review,
                rationale=rationale,
            )
        )
    return tuple(decisions)


def _score_candidate(candidate: _Candidate, field_candidates: tuple[_Candidate, ...]) -> CandidateScore:
    source_score = _source_score(candidate.item)
    confidence_score = candidate.item.confidence
    agreement_score = _agreement_score(candidate, field_candidates)
    status_score = _status_score(candidate.item.status)
    score = round(
        0.45 * source_score
        + 0.30 * confidence_score
        + 0.15 * agreement_score
        + 0.10 * status_score,
        12,
    )
    return CandidateScore(
        field_id=candidate.item.field_id,
        track=candidate.track,
        normalized_value=candidate.normalized_value,
        score=score,
        source_score=source_score,
        confidence_score=confidence_score,
        agreement_score=agreement_score,
        status_score=status_score,
    )


def _source_score(item: EvidenceItem) -> float:
    if item.source is None:
        return 0.0
    if item.source.source_precision == SourcePrecision.EXACT:
        return 1.0
    if item.source.source_precision == SourcePrecision.CORRECTED:
        return 0.8
    if item.source.source_precision == SourcePrecision.AMBIGUOUS:
        return 0.45
    return 0.0


def _status_score(status: EvidenceStatus) -> float:
    if status == EvidenceStatus.FOUND:
        return 1.0
    if status == EvidenceStatus.NOT_FOUND:
        return 0.4
    if status == EvidenceStatus.OCR_GAP:
        return 0.2
    return 0.1


def _agreement_score(candidate: _Candidate, field_candidates: tuple[_Candidate, ...]) -> float:
    for other in field_candidates:
        if other.track == candidate.track:
            continue
        if other.normalized_value == candidate.normalized_value:
            return 1.0
    return 0.0


def _first_conflicting_score(
    accepted_score: CandidateScore,
    ranked: list[tuple[_Candidate, CandidateScore]],
) -> CandidateScore | None:
    for _, score in ranked[1:]:
        if score.normalized_value != accepted_score.normalized_value:
            return score
    return None


def _accepted_rationale(
    score: CandidateScore,
    requires_review: bool,
) -> str:
    rationale = (
        f"source-grounded cross-track reconcile selected {score.track.value} "
        f"candidate with score={score.score:.3f}"
    )
    if score.agreement_score > 0:
        rationale += " and cross-track agreement"
    if requires_review:
        rationale += "; manual review recommended for close conflict"
    return rationale


def _annotate_accepted(
    item: EvidenceItem,
    rationale: str,
    score: CandidateScore,
    requires_review: bool,
) -> EvidenceItem:
    basis = [*item.inference_basis, "source-grounded cross-track reconcile"]
    if score.agreement_score > 0:
        basis.append("cross-track agreement")
    notes = _append_note(item.notes, rationale)
    if requires_review and "manual review" not in notes:
        notes = _append_note(notes, "manual review recommended")
    return item.model_copy(
        update={
            "notes": notes,
            "inference_basis": basis,
        }
    )


def _annotate_rejected(
    item: EvidenceItem,
    track: Track,
    score: CandidateScore,
    accepted_score: CandidateScore,
) -> EvidenceItem:
    rationale = (
        f"Rejected by source-grounded cross-track reconcile: {track.value} score={score.score:.3f} "
        f"ranked below {accepted_score.track.value} score={accepted_score.score:.3f}."
    )
    return item.model_copy(update={"notes": _append_note(item.notes, rationale)})


def _append_note(existing: str, addition: str) -> str:
    if not existing.strip():
        return addition
    if addition in existing:
        return existing
    return f"{existing.rstrip()} {addition}"




def _deduplicate_chains(
    original: EvidenceExtractionResult,
    translated: EvidenceExtractionResult,
) -> list[EvidenceChain]:
    chains: list[EvidenceChain] = []
    seen: set[tuple[str, str, str, str]] = set()
    for chain in [*original.evidence_chains, *translated.evidence_chains]:
        key = (
            chain.chain_id,
            chain.gene_text.strip().casefold(),
            chain.disease_text.strip().casefold(),
            chain.variant_text.strip().casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        chains.append(chain)
    return chains


def _reconciled_status(
    original: EvidenceExtractionResult,
    translated: EvidenceExtractionResult,
) -> EvidenceExtractionStatus:
    if (
        original.status == EvidenceExtractionStatus.NOT_RELEVANT
        and translated.status == EvidenceExtractionStatus.NOT_RELEVANT
    ):
        return EvidenceExtractionStatus.NOT_RELEVANT
    return EvidenceExtractionStatus.COMPLETED
