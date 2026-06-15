"""Contextual verifier-driven cross-track reconcile."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionResult,
    EvidenceItem,
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
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.core import (
    _Candidate,
    _agreement_score,
    _append_note,
    _build_candidates,
    _deduplicate_chains,
    _first_conflicting_score,
    _reconciled_status,
    _source_score,
    _status_score,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.verify.contracts import (
    EvidenceVerificationInput,
    EvidenceVerificationResult,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.verify.core import (
    score_candidate_support,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    TargetContextPack,
)


def reconcile_with_context(
    original: EvidenceExtractionResult,
    translated: EvidenceExtractionResult,
    context: TargetContextPack,
    params: ReconcileParams = ReconcileParams(),
) -> ReconcileOutput:
    """Reconcile dual-track results using target context and deterministic verifier scores."""
    evidence_decisions = _decide_fields(
        _build_candidates(original, translated, phenotype=False),
        context,
        params,
    )
    phenotype_decisions = _decide_fields(
        _build_candidates(original, translated, phenotype=True),
        context,
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
        alignment_records=build_alignment_records(original, translated, entry_id=context.entry_id),
    )


def _decide_fields(
    candidates: tuple[_Candidate, ...],
    context: TargetContextPack,
    params: ReconcileParams,
) -> tuple[FieldDecision, ...]:
    decisions: list[FieldDecision] = []
    for field_id in sorted({candidate.item.field_id for candidate in candidates}):
        field_candidates = tuple(candidate for candidate in candidates if candidate.item.field_id == field_id)
        scored = tuple(
            (candidate, _score_candidate(candidate, field_candidates, context))
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
        accepted = _annotate_accepted(
            accepted_candidate.item,
            rationale,
            accepted_score,
            requires_review,
            context,
        )
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


def _score_candidate(
    candidate: _Candidate,
    field_candidates: tuple[_Candidate, ...],
    context: TargetContextPack,
) -> CandidateScore:
    verification = score_candidate_support(_verification_input(candidate, context))
    source_score = _source_score(candidate.item)
    confidence_score = candidate.item.confidence
    agreement_score = _agreement_score(candidate, field_candidates)
    status_score = _status_score(candidate.item.status)
    contradiction_penalty = verification.contradiction_score
    score = round(
        0.30 * source_score
        + 0.20 * agreement_score
        + 0.20 * verification.support_score
        + 0.15 * verification.target_specificity_score
        + 0.10 * confidence_score
        + 0.05 * status_score
        - 0.25 * contradiction_penalty,
        12,
    )
    return CandidateScore(
        field_id=candidate.item.field_id,
        track=candidate.track,
        normalized_value=(
            verification.recommended_value
            if _can_override(candidate.item, verification)
            else candidate.normalized_value
        ),
        score=score,
        source_score=source_score,
        confidence_score=confidence_score,
        agreement_score=agreement_score,
        status_score=status_score,
        verifier_support_score=verification.support_score,
        target_specificity_score=verification.target_specificity_score,
        contradiction_penalty=contradiction_penalty,
    )


def _verification_input(candidate: _Candidate, context: TargetContextPack) -> EvidenceVerificationInput:
    source = candidate.item.source or candidate.item.raw_source
    return EvidenceVerificationInput(
        entry_id=context.entry_id,
        field_id=candidate.item.field_id,
        candidate_value=str(candidate.item.value or ""),
        source_snippet=source.text_snippet if source is not None else "",
        source_precision=source.source_precision.value if source is not None else None,
        track=candidate.track.value,
        target_gene=context.gene.symbol,
        target_disease=context.disease.label,
        disease_aliases=context.disease.aliases,
        moi=context.moi,
    )


def _can_override(item: EvidenceItem, verification: EvidenceVerificationResult) -> bool:
    return (
        item.field_id == "A.gene_disease_relationship"
        and verification.support_score >= 0.55
        and verification.contradiction_score < 0.5
        and verification.recommended_value in {
            "causative",
            "susceptibility",
            "uncertain",
            "disputed",
            "refuted",
            "no_relationship",
        }
    )


def _can_apply_relationship_override(item: EvidenceItem, score: CandidateScore) -> bool:
    return (
        item.field_id == "A.gene_disease_relationship"
        and score.verifier_support_score >= 0.55
        and score.contradiction_penalty < 0.5
        and score.source_score > 0.0
        and score.normalized_value in {
            "causative",
            "susceptibility",
            "uncertain",
            "disputed",
            "refuted",
            "no_relationship",
        }
    )


def _accepted_rationale(score: CandidateScore, requires_review: bool) -> str:
    rationale = (
        f"contextual verifier reconcile selected {score.track.value} candidate "
        f"with score={score.score:.3f}"
    )
    if score.verifier_support_score > 0:
        rationale += f", verifier_support={score.verifier_support_score:.3f}"
    if score.target_specificity_score > 0:
        rationale += f", target_specificity={score.target_specificity_score:.3f}"
    if requires_review:
        rationale += "; manual review recommended for close conflict"
    return rationale


def _annotate_accepted(
    item: EvidenceItem,
    rationale: str,
    score: CandidateScore,
    requires_review: bool,
    context: TargetContextPack,
) -> EvidenceItem:
    basis = [*item.inference_basis, "contextual verifier reconcile"]
    update: dict[str, object] = {
        "notes": _append_note(item.notes, rationale),
        "inference_basis": basis,
    }
    if _can_apply_relationship_override(item, score):
        update["value"] = score.normalized_value
        update["inference_basis"] = [*basis, "verifier relationship override"]
    if _can_canonicalize_target_disease(item, context):
        update["value"] = context.disease.label
        update["inference_basis"] = [*basis, "target disease boundary canonicalization"]
    if requires_review:
        update["notes"] = _append_note(str(update["notes"]), "manual review recommended")
    return item.model_copy(update=update)


def _can_canonicalize_target_disease(item: EvidenceItem, context: TargetContextPack) -> bool:
    if item.field_id != "B.disease_diagnosis" or not context.disease.label:
        return False
    source = item.source or item.raw_source
    if source is None:
        return False
    snippet = source.text_snippet.casefold()
    aliases = tuple(alias.casefold() for alias in context.disease.aliases if alias)
    return any(alias and alias in snippet for alias in aliases)


def _annotate_rejected(
    item: EvidenceItem,
    track: Track,
    score: CandidateScore,
    accepted_score: CandidateScore,
) -> EvidenceItem:
    rationale = (
        f"Rejected by contextual verifier reconcile: {track.value} score={score.score:.3f} "
        f"ranked below {accepted_score.track.value} score={accepted_score.score:.3f}."
    )
    return item.model_copy(update={"notes": _append_note(item.notes, rationale)})
