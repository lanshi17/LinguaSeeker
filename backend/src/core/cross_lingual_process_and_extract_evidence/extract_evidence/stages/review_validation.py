"""Review-validation stage for primary extraction candidates."""
from __future__ import annotations

import json

from loguru import logger

from ..contracts import (
    EvidenceItem,
    EvidenceReviewDecision,
    EvidenceReviewResponse,
    EvidenceStatus,
    SourceLocation,
    TrackDocument,
)
from ..providers import EvidenceModelTier, LangChainEvidenceProvider


class ReviewValidationStage:
    """Validate primary extraction candidates without adding new candidates."""

    def __init__(self, provider: LangChainEvidenceProvider):
        self._provider = provider

    def run(self, document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]:
        """Review primary candidates and fail open on provider errors."""
        found_items = [item for item in items if item.status == EvidenceStatus.FOUND]
        if not found_items:
            return items
        try:
            response = self._provider.invoke_structured(
                prompt=_build_review_prompt(document, items),
                output_schema=EvidenceReviewResponse,
                tier=EvidenceModelTier.STANDARD,
                stage="review_validation",
            )
        except Exception as exc:
            logger.warning("review_validation failed open: {}", exc)
            return items
        return _apply_review_decisions(items, response.decisions)

    async def run_async(self, document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]:
        """Async review validation for async extraction workflows."""
        found_items = [item for item in items if item.status == EvidenceStatus.FOUND]
        if not found_items:
            return items
        try:
            response = await self._provider.ainvoke_structured(
                prompt=_build_review_prompt(document, items),
                output_schema=EvidenceReviewResponse,
                tier=EvidenceModelTier.STANDARD,
                stage="review_validation",
            )
        except Exception as exc:
            logger.warning("review_validation failed open: {}", exc)
            return items
        return _apply_review_decisions(items, response.decisions)


def _build_review_prompt(document: TrackDocument, items: list[EvidenceItem]) -> str:
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
            f"TARGET VARIANT P: {target.variant_hgvs_p or 'not specified'}"
        )
    )
    return (
        "You are the review track for ACMG/ClinGen evidence extraction.\n"
        "Review only the primary extraction candidates listed below. "
        "Do not add new field IDs, do not create new candidates, and do not perform a second full extraction.\n\n"
        "Decision policy:\n"
        "- approve: the candidate is directly supported by the document.\n"
        "- reject: the candidate is unsupported, inferred too weakly, or belongs to another gene/disease/context.\n"
        "- correct: the candidate field is relevant but its value or source quote should be fixed.\n\n"
        f"{target_text}\n\n"
        "Primary candidates JSON:\n"
        f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n\n"
        "Return JSON with a decisions array. Each decision must include candidate_index, field_id, "
        "action (approve, reject, or correct), confidence, source_quote, and reason. "
        "For correct, include the corrected value and a verbatim contiguous source_quote from the document. "
        "For reject, value and source_quote may be empty.\n\n"
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
    decisions: list[EvidenceReviewDecision],
) -> list[EvidenceItem]:
    """Apply review decisions while preserving the original candidate set."""
    by_index = {
        decision.candidate_index: decision
        for decision in decisions
        if decision.candidate_index is not None
    }
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
            reviewed.append(_reject_item(item, decision))
            continue
        if decision.action == "correct":
            reviewed.append(_correct_item(item, decision))
            continue
        reviewed.append(_append_review_note(item, "review_track: approved", decision.reason))
    return reviewed


def _reject_item(item: EvidenceItem, decision: EvidenceReviewDecision) -> EvidenceItem:
    return item.model_copy(update={
        "status": EvidenceStatus.NOT_FOUND,
        "value": None,
        "confidence": 0.0,
        "source": None,
        "raw_source": None,
        "assigned_acmg_codes": [],
        "assigned_clingen_modules": [],
        "notes": _merged_note(item.notes, "review_track: rejected", decision.reason),
    })


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
    return item.model_copy(update={
        "status": EvidenceStatus.FOUND,
        "value": value,
        "confidence": decision.confidence or item.confidence,
        "source": None,
        "raw_source": raw_source,
        "notes": _merged_note(item.notes, "review_track: corrected", decision.reason),
    })


def _append_review_note(item: EvidenceItem, prefix: str, reason: str) -> EvidenceItem:
    return item.model_copy(update={"notes": _merged_note(item.notes, prefix, reason)})


def _merged_note(existing: str, prefix: str, reason: str) -> str:
    new_note = f"{prefix}: {reason}" if reason else prefix
    if not existing:
        return new_note
    if new_note in existing:
        return existing
    return f"{existing}; {new_note}"
