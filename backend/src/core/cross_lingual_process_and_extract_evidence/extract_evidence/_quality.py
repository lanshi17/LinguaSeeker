"""Quality validation and target entity guarding."""
from __future__ import annotations

import ast


from .catalog import EVIDENCE_FIELD_SPECS, EvidenceFieldSpec
from .contracts import (
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    QualityIssue,
    QualityReport,
    SourcePrecision,
    SpecialEvidenceRecord,
)


class TargetEntityGuard:
    """Validates primary entity fields against the extraction target."""

    _GUARDED_FIELDS: tuple[str, ...] = ("A.gene_symbol",)

    def apply(
        self,
        items: list[EvidenceItem],
        extraction_target: ExtractionTarget | None,
    ) -> list[EvidenceItem]:
        if extraction_target is None:
            return items
        return [self._guard_one(item, extraction_target) for item in items]

    def _guard_one(self, item: EvidenceItem, target: ExtractionTarget) -> EvidenceItem:
        if item.status != EvidenceStatus.FOUND or item.field_id not in self._GUARDED_FIELDS:
            return item
        values = self._extract_gene_values(item.value)
        if len(values) > 1:
            if target.gene_symbol in values:
                return item.model_copy(update={
                    "value": target.gene_symbol,
                    "notes": self._append_note(item.notes, "target_guard:list_to_target"),
                })
            return self._contaminated(
                item,
                f"target gene {target.gene_symbol} not in extracted gene list {values}",
            )
        actual = values[0] if values else str(item.value or "").strip().upper()
        if actual != target.gene_symbol:
            return self._contaminated(
                item,
                f"extracted {actual}, expected {target.gene_symbol}",
            )
        return item.model_copy(update={"value": target.gene_symbol})

    @staticmethod
    def _contaminated(item: EvidenceItem, reason: str) -> EvidenceItem:
        return item.model_copy(update={
            "status": EvidenceStatus.CONTEXT_CONTAMINATION,
            "notes": (
                f"{item.notes}; target_guard:{reason}" if item.notes else f"target_guard:{reason}"
            ),
            "assigned_acmg_codes": [],
            "assigned_clingen_modules": [],
        })

    @staticmethod
    def _extract_gene_values(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(entry).strip().upper() for entry in value if str(entry).strip()]
        text = str(value or "").strip()
        if text.startswith("["):
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return [text.upper()]
            if isinstance(parsed, list):
                return [str(entry).strip().upper() for entry in parsed if str(entry).strip()]
        return [text.upper()] if text else []

    @staticmethod
    def _append_note(existing: str, note: str) -> str:
        return f"{existing}; {note}" if existing else note
class QualityValidator:
    """Rule-based quality validation for extracted evidence."""

    def __init__(
        self,
        required_field_ids: set[str] | None = None,
        catalog: tuple[EvidenceFieldSpec, ...] = EVIDENCE_FIELD_SPECS,
    ):
        if required_field_ids is not None:
            self._required = required_field_ids
        else:
            self._required = {s.field_id for s in catalog if s.required_for_scorable}

    def validate(
        self,
        items: list[EvidenceItem],
        contradictions: list[str],
        chains: list[EvidenceChain] | None = None,
        special_records: list[SpecialEvidenceRecord] | None = None,
        evidence_chain_count: int = 0,
    ) -> QualityReport:
        chains = chains or []
        special_records = special_records or []
        issues: list[QualityIssue] = []
        human_review_reasons: list[str] = []
        human_review_by_category: dict[str, list[str]] = {
            "source_grounding": [],
            "table_grounding": [],
            "scoring_gate": [],
            "contradictions": [],
            "workflow": [],
        }
        found_count = 0
        not_found_count = 0
        source_invalid_count = 0
        ocr_gap_count = 0
        table_ungrounded_count = 0
        ambiguous_source_count = 0
        context_contamination_count = 0

        for item in items:
            if item.status == EvidenceStatus.FOUND:
                found_count += 1
                if item.source is None:
                    if item.field_id == "B.case_count":
                        reason = f"{item.field_id} is inferred from document structure and has no traceable source"
                        human_review_by_category["workflow"].append(reason)
                        human_review_reasons.append(reason)
                    else:
                        issues.append(QualityIssue(
                            issue_type="missing_source",
                            field_id=item.field_id,
                            description=f"Found item {item.field_id} has no source",
                            severity="error",
                        ))
                elif item.source.source_precision == SourcePrecision.AMBIGUOUS:
                    ambiguous_source_count += 1
                    reason = f"{item.field_id} has ambiguous source grounding"
                    human_review_reasons.append(reason)
                    human_review_by_category["source_grounding"].append(reason)
            elif item.status == EvidenceStatus.NOT_FOUND:
                not_found_count += 1
            elif item.status == EvidenceStatus.SOURCE_INVALID:
                source_invalid_count += 1
                reason = f"{item.field_id} has invalid source grounding"
                human_review_reasons.append(reason)
                human_review_by_category["source_grounding"].append(reason)
            elif item.status == EvidenceStatus.OCR_GAP:
                ocr_gap_count += 1
                reason = f"{item.field_id} may require OCR/image review"
                human_review_reasons.append(reason)
                human_review_by_category["source_grounding"].append(reason)
            elif item.status == EvidenceStatus.TABLE_UNGROUNDED:
                table_ungrounded_count += 1
                reason = f"{item.field_id} may require table-path grounding"
                human_review_reasons.append(reason)
                human_review_by_category["table_grounding"].append(reason)
            elif item.status == EvidenceStatus.CONTEXT_CONTAMINATION:
                context_contamination_count += 1
                reason = f"{item.field_id} rejected as target context contamination: {item.notes}"
                issues.append(QualityIssue(
                    issue_type="context_contamination",
                    field_id=item.field_id,
                    description=item.notes,
                    severity="error",
                ))
                human_review_reasons.append(reason)
                human_review_by_category["workflow"].append(reason)
        missing_required = self._required - {
            item.field_id for item in items
            if item.status == EvidenceStatus.FOUND
            and item.source is not None
            and item.source.source_precision != SourcePrecision.AMBIGUOUS
        }
        for field_id in missing_required:
            issues.append(QualityIssue(
                issue_type="missing_required",
                field_id=field_id,
                description=f"Required field {field_id} is missing",
                severity="warning",
            ))
            reason = f"{field_id} is required for scoring but is not grounded"
            human_review_reasons.append(reason)
            human_review_by_category["scoring_gate"].append(reason)

        for contradiction in contradictions:
            issues.append(QualityIssue(
                issue_type="contradiction",
                field_id="",
                description=contradiction,
                severity="warning",
            ))
            reason = f"Contradiction requires review: {contradiction}"
            human_review_reasons.append(reason)
            human_review_by_category["contradictions"].append(reason)

        for record in special_records:
            if record.raw_source is not None and record.source is None:
                reason = f"Special evidence {record.record_type} requires source grounding review"
                human_review_reasons.append(reason)
                human_review_by_category["source_grounding"].append(reason)

        passed = not any(i.severity == "error" for i in issues)
        full_chains = [chain for chain in chains if chain.chain_level == "full"]
        incomplete_chains = [chain for chain in chains if chain.chain_level in {"partial", "singleton"}]
        full_chain_group_ids = {chain.chain_id for chain in full_chains}
        full_chain_items = [item for item in items if item.group_id in full_chain_group_ids]
        full_chain_missing_required = self._required - {
            item.field_id for item in full_chain_items
            if item.status == EvidenceStatus.FOUND
            and item.source is not None
            and item.source.source_precision != SourcePrecision.AMBIGUOUS
        }

        scorable = len(full_chains) > 0 and len(full_chain_missing_required) == 0
        if any(
            item.status in {
                EvidenceStatus.SOURCE_INVALID,
                EvidenceStatus.OCR_GAP,
                EvidenceStatus.TABLE_UNGROUNDED,
                EvidenceStatus.CONTEXT_CONTAMINATION,
            }
            for item in full_chain_items
        ):
            scorable = False
        if any(
            item.status == EvidenceStatus.FOUND
            and item.source is not None
            and item.source.source_precision == SourcePrecision.AMBIGUOUS
            for item in full_chain_items
        ):
            scorable = False
        score_gate_passed = passed and scorable

        if incomplete_chains:
            reason = "Incomplete evidence chain requires review"
            human_review_reasons.append(reason)
            human_review_by_category["workflow"].append(reason)
        if passed and items and not full_chains and evidence_chain_count == 0:
            reason = "No full evidence chain was produced"
            human_review_reasons.append(reason)
            human_review_by_category["workflow"].append(reason)
        if passed and scorable and not chains and evidence_chain_count == 0:
            reason = "No grounded evidence chain was produced"
            human_review_reasons.append(reason)
            human_review_by_category["workflow"].append(reason)

        return QualityReport(
            passed=passed,
            scorable=scorable,
            score_gate_passed=score_gate_passed,
            issues=issues,
            found_count=found_count,
            not_found_count=not_found_count,
            source_invalid_count=source_invalid_count,
            ocr_gap_count=ocr_gap_count,
            table_ungrounded_count=table_ungrounded_count,
            ambiguous_source_count=ambiguous_source_count,
            context_contamination_count=context_contamination_count,
            human_review_required=len(human_review_reasons) > 0,
            human_review_reasons=human_review_reasons,
            human_review_by_category=human_review_by_category,
        )
class IntraTrackConflictChecker:
    """Checks for contradictions within a single track's evidence."""

    def check(self, items: list[EvidenceItem]) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        found_by_field: dict[str, list[EvidenceItem]] = {}

        for item in items:
            if item.status == EvidenceStatus.FOUND:
                found_by_field.setdefault(item.field_id, []).append(item)

        for field_id, field_items in found_by_field.items():
            if len(field_items) > 1:
                values = {str(item.value) for item in field_items}
                if len(values) > 1:
                    issues.append(QualityIssue(
                        issue_type="contradiction",
                        field_id=field_id,
                        description=f"Multiple conflicting values for {field_id}: {values}",
                        severity="warning",
                    ))

        return issues

