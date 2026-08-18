"""Review-validation stage for primary extraction candidates."""

from __future__ import annotations

import json
from typing import Literal

from loguru import logger

from ..contracts import (
    EvidenceItem,
    EvidenceReviewDecision,
    EvidenceReviewResponse,
    EvidenceStatus,
    EvidenceTriStateReviewDecision,
    EvidenceTriStateReviewResponse,
    SourceLocation,
    TrackDocument,
)
from ..providers import EvidenceModelTier, LangChainEvidenceProvider

ReviewRejectPolicy = Literal["hard_veto", "soft_veto", "tristate_review"]
DEFAULT_REVIEW_REJECT_POLICY: ReviewRejectPolicy = "tristate_review"


def resolve_review_reject_policy(raw: str) -> ReviewRejectPolicy:
    """Resolve review reject policy for benchmark calibration runs."""
    if raw not in ("hard_veto", "soft_veto", "tristate_review"):
        raise ValueError(f"Unknown review_reject_policy {raw!r}")
    return raw  # type: ignore[return-value]


class ReviewValidationStage:
    """Validate primary extraction candidates without adding new candidates."""

    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        review_reject_policy: str = DEFAULT_REVIEW_REJECT_POLICY,
    ):
        self._provider = provider
        self._review_reject_policy = resolve_review_reject_policy(review_reject_policy)

    def run(self, document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]:
        """Review primary candidates and fail open on provider errors."""
        found_items = [item for item in items if item.status == EvidenceStatus.FOUND]
        if not found_items:
            return items
        try:
            response = self._provider.invoke_structured(
                prompt=_build_review_prompt(document, items, self._review_reject_policy),
                output_schema=_review_output_schema(self._review_reject_policy),
                tier=EvidenceModelTier.STANDARD,
                stage="review_validation",
            )
        except Exception as exc:
            logger.warning("review_validation failed open: {}", exc)
            return items
        return _apply_review_decisions(items, response.decisions, self._review_reject_policy)

    async def run_async(self, document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]:
        """Async review validation for async extraction workflows."""
        found_items = [item for item in items if item.status == EvidenceStatus.FOUND]
        if not found_items:
            return items
        try:
            response = await self._provider.ainvoke_structured(
                prompt=_build_review_prompt(document, items, self._review_reject_policy),
                output_schema=_review_output_schema(self._review_reject_policy),
                tier=EvidenceModelTier.STANDARD,
                stage="review_validation",
            )
        except Exception as exc:
            logger.warning("review_validation failed open: {}", exc)
            return items
        return _apply_review_decisions(items, response.decisions, self._review_reject_policy)


def _review_output_schema(
    review_reject_policy: ReviewRejectPolicy,
) -> type[EvidenceReviewResponse | EvidenceTriStateReviewResponse]:
    if review_reject_policy == "tristate_review":
        return EvidenceTriStateReviewResponse
    return EvidenceReviewResponse


def _build_review_prompt(
    document: TrackDocument,
    items: list[EvidenceItem],
    review_reject_policy: ReviewRejectPolicy,
) -> str:
    """Build a review-only prompt over existing primary candidates."""
    candidates = [
        {
            "candidate_index": index,
            "field_id": item.field_id,
            "status": item.status.value,
            "value": item.value,
            "confidence": item.confidence,
            "raw_source": _source_payload(item.raw_source or item.source),
            "notes": item.notes,
        }
        for index, item in enumerate(items)
        if item.status == EvidenceStatus.FOUND
    ]
    target = document.extraction_target
    target_text = (
        "TARGET: Not provided."
        if target is None
        else (
            f"TARGET GENE: {target.gene_symbol}\n"
            f"TARGET DISEASE: {target.disease_name}\n"
            f"TARGET VARIANT C: {target.variant_hgvs_c or 'not specified'}\n"
            f"TARGET VARIANT P: {target.variant_hgvs_p or 'not specified'}"
        )
    )
    decision_policy = (
        "Decision policy:\n"
        "- approve: the candidate is directly supported by the document.\n"
        "- reject: the candidate is unsupported, inferred too weakly, or belongs to another gene/disease/context.\n"
        "- correct: the candidate field is relevant but its value or source quote should be fixed.\n\n"
    )
    action_instruction = (
        "Return JSON with a decisions array. Each decision must include candidate_index, field_id, "
        "action (approve, reject, or correct), confidence, source_quote, and reason. "
        "For correct, include the corrected value and a verbatim contiguous source_quote from the document. "
        "For reject, value and source_quote may be empty.\n\n"
    )
    if review_reject_policy == "tristate_review":
        decision_policy = (
            "Decision policy:\n"
            "- approve: the candidate is directly supported by the document and can be treated as DB-ready.\n"
            "- uncertain_keep_for_review: the candidate is plausible and relevant but needs expert review, "
            "including long-tail medical entities, indirect entailment, or incomplete local evidence.\n"
            "- reject: use only when the candidate is clearly unsupported, contradicted, or belongs to another "
            "gene/disease/context. Do not reject solely because the entity is rare, compound, or domain-specific.\n"
            "  For variant/HGVS fields, animal or cell model context is a confidence penalty, not a deletion reason; "
            "use uncertain_keep_for_review unless the quote is absent or the gene/disease target is clearly wrong.\n"
            "- correct: the candidate field is relevant but its value or source quote should be fixed.\n\n"
        )
        action_instruction = (
            "Return JSON with a decisions array. Each decision must include candidate_index, field_id, "
            "action (approve, uncertain_keep_for_review, reject, or correct), confidence, source_quote, and reason. "
            "For correct, include the corrected value and a verbatim contiguous source_quote from the document. "
            "For uncertain_keep_for_review, keep the original value unless a small quote correction is needed. "
            "For reject, value and source_quote may be empty.\n\n"
        )
    return (
        "You are the review track for ACMG/ClinGen evidence extraction.\n"
        "Review only the primary extraction candidates listed below. "
        "Do not add new field IDs, do not create new candidates, and do not perform a second full extraction.\n"
        "Do not treat author-stated ACMG criterion codes (PS2, PM2, PP3, PVS1, or combinations) as granted codes.\n"
        "Reject C.de_novo_status when the quote shows maternal or paternal inheritance of the target variant.\n"
        "Reject J.clinvar_assertion when the value is an ACMG criterion list rather than Pathogenic/LP/VUS/Benign.\n"
        "Do not migrate de novo, segregation, or assay facts from a different gene or patient onto the target.\n\n"
        f"{decision_policy}"
        f"{target_text}\n\n"
        "Primary candidates JSON:\n"
        f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n\n"
        f"{action_instruction}"
        "Document text:\n"
        f"{document.formatted_text}"
    )


def _source_payload(source: SourceLocation | None) -> dict[str, object] | None:
    if source is None:
        return None
    return {
        "text_snippet": source.text_snippet,
        "context_type": source.context_type,
        "context_ref": source.context_ref,
        "block_index": source.block_index,
    }


def _apply_review_decisions(
    items: list[EvidenceItem],
    decisions: list[EvidenceReviewDecision] | list[EvidenceTriStateReviewDecision],
    review_reject_policy: ReviewRejectPolicy = DEFAULT_REVIEW_REJECT_POLICY,
) -> list[EvidenceItem]:
    """Apply review decisions while preserving the original candidate set."""
    by_index = {decision.candidate_index: decision for decision in decisions if decision.candidate_index is not None}
    by_field: dict[str, EvidenceReviewDecision] = {}
    for decision in decisions:
        if decision.candidate_index is None and decision.field_id not in by_field:
            by_field[decision.field_id] = decision

    reviewed: list[EvidenceItem] = []
    for index, item in enumerate(items):
        decision = by_index.get(index)
        if decision is None:
            decision = by_field.get(item.field_id)
        if decision is None or decision.field_id != item.field_id:
            reviewed.append(item)
            continue
        if decision.action == "reject":
            reviewed.append(_reject_item(item, decision, review_reject_policy))
            continue
        if decision.action == "correct":
            reviewed.append(_correct_item(item, decision))
            continue
        if decision.action == "uncertain_keep_for_review":
            reviewed.append(_uncertain_item(item, decision))
            continue
        reviewed.append(_append_review_note(item, "review_track: approved", decision.reason))
    return reviewed


def _reject_item(
    item: EvidenceItem,
    decision: EvidenceReviewDecision,
    review_reject_policy: ReviewRejectPolicy,
) -> EvidenceItem:
    if review_reject_policy == "soft_veto":
        return item.model_copy(
            update={
                "status": EvidenceStatus.FOUND,
                "confidence": min(item.confidence, 0.35),
                "notes": _merged_note(item.notes, "review_track: soft_rejected", decision.reason),
                "inference_basis": [*item.inference_basis, "review_soft_reject"],
            }
        )
    if review_reject_policy == "tristate_review" and _is_non_human_model_variant_reject(item, decision.reason):
        return item.model_copy(
            update={
                "status": EvidenceStatus.FOUND,
                "confidence": min(item.confidence, 0.35),
                "notes": _merged_note(
                    item.notes,
                    "review_track: non_human_model_soft_rejected",
                    decision.reason,
                ),
                "inference_basis": [*item.inference_basis, "review_non_human_model_soft_reject"],
            }
        )
    return item.model_copy(
        update={
            "status": EvidenceStatus.NOT_FOUND,
            "value": None,
            "confidence": 0.0,
            "source": None,
            "raw_source": None,
            "assigned_acmg_codes": [],
            "assigned_clingen_modules": [],
            "notes": _merged_note(item.notes, "review_track: rejected", decision.reason),
        }
    )


_VARIANT_REVIEW_FIELDS = frozenset(
    {
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_type",
        "A.variant_consequence_class",
    }
)

_NON_HUMAN_MODEL_REJECT_HINTS = (
    "mouse",
    "mice",
    "murine",
    "animal model",
    "non-human",
    "nonhuman",
    "no human participant",
    "no human subjects",
)


def _is_non_human_model_variant_reject(item: EvidenceItem, reason: str) -> bool:
    """Return whether a variant rejection is only animal/model-context caution."""
    if item.field_id not in _VARIANT_REVIEW_FIELDS:
        return False
    normalized_reason = reason.casefold()
    return any(hint in normalized_reason for hint in _NON_HUMAN_MODEL_REJECT_HINTS)


def _correct_item(item: EvidenceItem, decision: EvidenceReviewDecision) -> EvidenceItem:
    value = decision.value if decision.value not in (None, "") else item.value
    source = item.raw_source or item.source
    raw_source = source
    if decision.source_quote.strip():
        raw_source = SourceLocation(
            context_type=source.context_type if source else "text",
            context_ref=source.context_ref if source else "review_validation",
            text_snippet=decision.source_quote.strip(),
            block_index=source.block_index if source else -1,
        )
    return item.model_copy(
        update={
            "status": EvidenceStatus.FOUND,
            "value": value,
            "confidence": decision.confidence or item.confidence,
            "source": None,
            "raw_source": raw_source,
            "notes": _merged_note(item.notes, "review_track: corrected", decision.reason),
        }
    )


def _uncertain_item(item: EvidenceItem, decision: EvidenceTriStateReviewDecision) -> EvidenceItem:
    confidence = min(item.confidence, decision.confidence or item.confidence, 0.45)
    return item.model_copy(
        update={
            "status": EvidenceStatus.FOUND,
            "confidence": confidence,
            "notes": _merged_note(item.notes, "review_track: uncertain_keep_for_review", decision.reason),
            "inference_basis": [*item.inference_basis, "review_uncertain_keep_for_review"],
        }
    )


def _append_review_note(item: EvidenceItem, prefix: str, reason: str) -> EvidenceItem:
    return item.model_copy(update={"notes": _merged_note(item.notes, prefix, reason)})


def _merged_note(existing: str, prefix: str, reason: str) -> str:
    new_note = f"{prefix}: {reason}" if reason else prefix
    if not existing:
        return new_note
    if new_note in existing:
        return existing
    return f"{existing}; {new_note}"
