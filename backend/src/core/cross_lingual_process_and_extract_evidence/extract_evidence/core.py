"""Deterministic source grounding and quality validation."""
from __future__ import annotations

from dataclasses import dataclass
import re

from loguru import logger

from .catalog import EVIDENCE_FIELD_SPECS, EvidenceFieldSpec
from .contracts import (
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    QualityIssue,
    QualityReport,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
    TrackDocument,
)

_MAX_SNIPPET_MATCHES = 50
_ELLIPSIS_PATTERN = re.compile(r"\.\.\.|…")
_CJK_SPACED_TOKEN_PATTERN = re.compile(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])")
_CJK_NUMERIC_SPACE_PATTERN = re.compile(r"(?<=[\u4e00-\u9fffA-Za-z])\s+(?=[A-Za-z0-9(（])")
_MULTISPACE_PATTERN = re.compile(r"\s+")


class EvidenceItemNormalizer:
    """Normalizes model evidence output to the static field catalog."""

    def __init__(self, catalog: tuple[EvidenceFieldSpec, ...] = EVIDENCE_FIELD_SPECS):
        self._catalog = catalog

    def normalize(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        by_field: dict[str, EvidenceItem] = {}
        for item in items:
            if item.field_id not in by_field:
                by_field[item.field_id] = item
                continue
            by_field[item.field_id] = self._choose_better(by_field[item.field_id], item)

        normalized: list[EvidenceItem] = []
        for spec in self._catalog:
            item = by_field.get(spec.field_id)
            if item is None:
                item = self._not_found_item(spec)
            normalized.append(self._normalize_one(spec, item))
        return normalized

    def _normalize_one(self, spec: EvidenceFieldSpec, item: EvidenceItem) -> EvidenceItem:
        status = item.status
        # Give a second chance to items that carry both a value and a grounded source.
        # The model may over-penalize the source during extraction, but later grounding can recover it.
        if item.status == EvidenceStatus.SOURCE_INVALID and item.value is not None and item.source is not None:
            status = EvidenceStatus.FOUND

        assigned_acmg_codes = item.assigned_acmg_codes
        assigned_clingen_modules = item.assigned_clingen_modules
        if status != EvidenceStatus.FOUND:
            assigned_acmg_codes = []
            assigned_clingen_modules = []

        requires_external_completion = item.requires_external_completion
        external_completion_note = item.external_completion_note
        if spec.field_id == "D.allele_frequency" and status != EvidenceStatus.FOUND:
            requires_external_completion = True
            if not external_completion_note:
                external_completion_note = (
                    "Population frequency must be completed by an external annotation provider."
                )

        return item.model_copy(update={
            "category": spec.category_id,
            "field_name": spec.field_name,
            "status": status,
            "assigned_acmg_codes": assigned_acmg_codes,
            "assigned_clingen_modules": assigned_clingen_modules,
            "requires_external_completion": requires_external_completion,
            "external_completion_note": external_completion_note,
        })

    def _not_found_item(self, spec: EvidenceFieldSpec) -> EvidenceItem:
        return EvidenceItem(
            field_id=spec.field_id,
            category=spec.category_id,
            field_name=spec.field_name,
            status=EvidenceStatus.NOT_FOUND,
            value=None,
            confidence=0.0,
        )

    @staticmethod
    def _choose_better(current: EvidenceItem, candidate: EvidenceItem) -> EvidenceItem:
        rank = {
            EvidenceStatus.FOUND: 3,
            EvidenceStatus.SOURCE_INVALID: 2,
            EvidenceStatus.OCR_GAP: 1,
            EvidenceStatus.NOT_FOUND: 0,
        }
        current_score = (rank[current.status], current.confidence)
        candidate_score = (rank[candidate.status], candidate.confidence)
        return candidate if candidate_score > current_score else current


class SourceGrounder:
    """Validates and repairs source spans against the document."""

    def ground_items(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        grounded: list[EvidenceItem] = []
        for item in items:
            if item.status != EvidenceStatus.FOUND or item.source is None:
                grounded.append(item)
                continue
            grounded.append(self._ground_one(document, item))
        return grounded

    def _ground_one(self, document: TrackDocument, item: EvidenceItem) -> EvidenceItem:
        source = item.source
        snippet = source.text_snippet

        if self._is_exact_match(document, source):
            return item

        corrected = self._search_snippet(document, source, snippet, item.field_id)
        if corrected is None:
            if self._looks_like_ocr_gap(source):
                logger.warning("Snippet '{}' not found in document image/table source, marking OCR_GAP", snippet)
                return item.model_copy(update={
                    "status": EvidenceStatus.OCR_GAP,
                    "raw_source": source,
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                })
            logger.warning("Snippet '{}' not found in document, marking SOURCE_INVALID", snippet)
            return item.model_copy(update={
                "status": EvidenceStatus.SOURCE_INVALID,
                "raw_source": source,
                "assigned_acmg_codes": [],
                "assigned_clingen_modules": [],
            })

        if len(corrected) > 1:
            preferred = self._prefer_candidates(source, corrected, item.field_id)
            if preferred is not None:
                new_source = preferred.model_copy(update={"source_precision": SourcePrecision.CORRECTED})
                return item.model_copy(update={"source": new_source, "raw_source": source})
            # TODO: wire to LLM ambiguity resolution stage (get_source_ambiguity_review_prompt)
            logger.info("Snippet '{}' found {} times, marking ambiguous", snippet, len(corrected))
            new_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.AMBIGUOUS})
            return item.model_copy(update={"source": new_source, "raw_source": source})

        new_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.CORRECTED})
        return item.model_copy(update={"source": new_source, "raw_source": source})

    @staticmethod
    def _looks_like_ocr_gap(source: SourceLocation) -> bool:
        return source.block_type in {"image", "figure", "table"} or source.context_type in {"figure", "table", "caption"}

    def _is_exact_match(self, document: TrackDocument, source: SourceLocation) -> bool:
        text = document.formatted_text
        start = source.start_offset
        end = source.end_offset

        if start < 0 or end > len(text):
            return False

        actual = text[start:end]
        return actual == source.text_snippet

    def _search_snippet(
        self,
        document: TrackDocument,
        source: SourceLocation,
        snippet: str,
        field_id: str,
    ) -> list[SourceLocation] | None:
        text = document.formatted_text
        spans = document.page_spans
        direct_results = self._find_snippet_occurrences(text, spans, snippet, source)
        if direct_results:
            return direct_results

        normalized_snippet = self._normalize_snippet_for_search(snippet)
        if normalized_snippet and normalized_snippet != snippet:
            normalized_results = self._find_normalized_occurrences(text, spans, normalized_snippet, source)
            if normalized_results:
                return normalized_results

        if source.context_type == "table" or source.block_type == "table":
            table_results = self._search_table_related_text(text, spans, source, normalized_snippet or snippet)
            if table_results:
                return table_results

        return None

    def _find_snippet_occurrences(
        self,
        text: str,
        spans: list[PageSpan],
        snippet: str,
        source: SourceLocation,
    ) -> list[SourceLocation]:
        results: list[SourceLocation] = []

        idx = 0
        while True:
            if len(results) >= _MAX_SNIPPET_MATCHES:
                logger.warning("Snippet '{}' found >{} times, truncating", snippet, _MAX_SNIPPET_MATCHES)
                break
            pos = text.find(snippet, idx)
            if pos == -1:
                break
            end_pos = pos + len(snippet)
            span = self._find_span(spans, pos, end_pos)
            if span:
                results.append(SourceLocation(
                    span_id=span.span_id,
                    page=span.page,
                    start_offset=pos,
                    end_offset=end_pos,
                    context_type=source.context_type,
                    context_ref=source.context_ref,
                    text_snippet=snippet,
                    block_type=source.block_type,
                    source_precision=SourcePrecision.EXACT,
                ))
            idx = pos + 1

        return results

    def _find_normalized_occurrences(
        self,
        text: str,
        spans: list[PageSpan],
        normalized_snippet: str,
        source: SourceLocation,
    ) -> list[SourceLocation]:
        normalized_text, index_map = self._normalize_text_with_index_map(text)
        results: list[SourceLocation] = []
        idx = 0
        while True:
            if len(results) >= _MAX_SNIPPET_MATCHES:
                logger.warning("Normalized snippet '{}' found >{} times, truncating", normalized_snippet, _MAX_SNIPPET_MATCHES)
                break
            pos = normalized_text.find(normalized_snippet, idx)
            if pos == -1:
                break
            end_pos = pos + len(normalized_snippet)
            actual_start = index_map[pos]
            actual_end = index_map[end_pos - 1] + 1
            span = self._find_span(spans, actual_start, actual_end)
            if span:
                results.append(SourceLocation(
                    span_id=span.span_id,
                    page=span.page,
                    start_offset=actual_start,
                    end_offset=actual_end,
                    context_type=source.context_type,
                    context_ref=source.context_ref,
                    text_snippet=text[actual_start:actual_end],
                    block_type=source.block_type,
                    source_precision=SourcePrecision.EXACT,
                ))
            idx = pos + 1
        return results

    def _search_table_related_text(
        self,
        text: str,
        spans: list[PageSpan],
        source: SourceLocation,
        snippet: str,
    ) -> list[SourceLocation]:
        normalized_text, index_map = self._normalize_text_with_index_map(text)
        normalized_ref = self._normalize_snippet_for_search(source.context_ref)
        normalized_snippet = self._normalize_snippet_for_search(snippet)
        candidates = [value for value in (normalized_ref, normalized_snippet) if value]
        for candidate in candidates:
            pos = normalized_text.find(candidate)
            if pos == -1:
                continue
            end_pos = pos + len(candidate)
            actual_start = index_map[pos]
            actual_end = index_map[end_pos - 1] + 1
            span = self._find_span(spans, actual_start, actual_end)
            if span:
                return [SourceLocation(
                    span_id=span.span_id,
                    page=span.page,
                    start_offset=actual_start,
                    end_offset=actual_end,
                    context_type=source.context_type,
                    context_ref=source.context_ref,
                    text_snippet=text[actual_start:actual_end],
                    block_type=source.block_type,
                    source_precision=SourcePrecision.EXACT,
                )]
        return []

    def _prefer_candidates(
        self,
        source: SourceLocation,
        corrected: list[SourceLocation],
        field_id: str,
    ) -> SourceLocation | None:
        if field_id != "B.disease_diagnosis":
            return None
        if not corrected:
            return None
        return min(
            corrected,
            key=lambda candidate: (
                abs(candidate.start_offset - source.start_offset),
                candidate.start_offset,
            ),
        )

    @staticmethod
    def _normalize_snippet_for_search(snippet: str) -> str:
        value = _ELLIPSIS_PATTERN.sub("", snippet)
        value = value.replace("[REDACTED]", "")
        value = value.replace("...", "")
        value = value.replace("（ ）", "")
        value = value.replace("( )", "")
        value = _CJK_SPACED_TOKEN_PATTERN.sub("", value)
        value = _CJK_NUMERIC_SPACE_PATTERN.sub("", value)
        value = _MULTISPACE_PATTERN.sub(" ", value)
        return value.strip()

    @staticmethod
    def _normalize_text_with_index_map(text: str) -> tuple[str, list[int]]:
        chars: list[str] = []
        index_map: list[int] = []
        previous_kept = ""
        for index, char in enumerate(text):
            if char.isspace():
                if previous_kept and previous_kept.isascii() and index + 1 < len(text) and text[index + 1].isascii():
                    if chars and chars[-1] != " ":
                        chars.append(" ")
                        index_map.append(index)
                        previous_kept = " "
                continue
            chars.append(char)
            index_map.append(index)
            previous_kept = char
        return "".join(chars), index_map

    def _find_span(
        self,
        spans: list[PageSpan],
        start: int,
        end: int,
    ) -> PageSpan | None:
        for span in spans:
            if span.start_offset <= start and end <= span.end_offset:
                return span
        return None


class EvidenceChainBuilder:
    """Builds conservative identity chains from grounded evidence items."""

    def build(self, items: list[EvidenceItem]) -> list[EvidenceChain]:
        valid_by_field = {item.field_id: item for item in items if self._is_valid_grounded(item)}
        gene = valid_by_field.get("A.gene_symbol")
        disease = valid_by_field.get("B.disease_diagnosis")
        variant = valid_by_field.get("A.variant_hgvs_c") or valid_by_field.get("A.variant_hgvs_p")
        if gene is None or disease is None or variant is None:
            return []

        field_ids = [gene.field_id, disease.field_id, variant.field_id]
        case = valid_by_field.get("B.case_id")
        if case is not None:
            field_ids.append(case.field_id)

        chain_id = "-".join(field_ids)
        return [EvidenceChain(
            chain_id=chain_id,
            gene_text=str(gene.value or ""),
            disease_text=str(disease.value or ""),
            variant_text=str(variant.value or ""),
            case_id=str(case.value) if case and case.value is not None else None,
            evidence_field_ids=field_ids,
        )]

    @staticmethod
    def _is_valid_grounded(item: EvidenceItem) -> bool:
        return (
            item.status == EvidenceStatus.FOUND
            and item.value is not None
            and item.source is not None
            and item.source.source_precision != SourcePrecision.AMBIGUOUS
        )


class SpecialEvidenceValidator:
    """Filters special evidence records that are not safe to consume."""

    def filter_records(
        self,
        records: list[SpecialEvidenceRecord],
        current_items: list[EvidenceItem],
        document: TrackDocument,
    ) -> list[SpecialEvidenceRecord]:
        valid_field_ids = {
            item.field_id
            for item in current_items
            if item.status == EvidenceStatus.FOUND and item.source is not None
        }
        return [
            record for record in records
            if self._is_valid_record(record, valid_field_ids, document)
        ]

    def _is_valid_record(
        self,
        record: SpecialEvidenceRecord,
        valid_field_ids: set[str],
        document: TrackDocument,
    ) -> bool:
        if record.source is None:
            return False
        if (
            record.source.start_offset == record.source.end_offset
            and not self._source_is_traceable(record.source, document)
        ):
            return False
        if not self._source_is_traceable(record.source, document):
            return False
        if any(field_id not in valid_field_ids for field_id in record.evidence_field_ids):
            return False
        if record.record_type == "case_control":
            combined_text = f"{record.description} {record.source.text_snippet}"
            if "[REDACTED]" in combined_text:
                return False
        return True

    @staticmethod
    def _source_is_traceable(source: SourceLocation, document: TrackDocument) -> bool:
        text = document.formatted_text
        if source.start_offset >= source.end_offset and len(source.text_snippet) < 8:
            return False
        if source.start_offset >= 0 and source.end_offset <= len(text):
            if text[source.start_offset:source.end_offset] == source.text_snippet:
                return True
        if len(source.text_snippet) < 8:
            return False
        return source.text_snippet in text


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
        evidence_chain_count: int = 0,
    ) -> QualityReport:
        issues: list[QualityIssue] = []
        human_review_reasons: list[str] = []
        human_review_by_category: dict[str, list[str]] = {
            "source_grounding": [],
            "scoring_gate": [],
            "contradictions": [],
            "workflow": [],
        }
        found_count = 0
        not_found_count = 0
        source_invalid_count = 0
        ocr_gap_count = 0
        ambiguous_source_count = 0

        for item in items:
            if item.status == EvidenceStatus.FOUND:
                found_count += 1
                if item.source is None:
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

        passed = not any(i.severity == "error" for i in issues)
        scorable = len(missing_required) == 0
        if ocr_gap_count > 0 or ambiguous_source_count > 0:
            scorable = False
        score_gate_passed = passed and scorable and evidence_chain_count > 0
        if passed and scorable and evidence_chain_count == 0:
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
            ambiguous_source_count=ambiguous_source_count,
            human_review_required=len(human_review_reasons) > 0,
            human_review_reasons=human_review_reasons,
            human_review_by_category=human_review_by_category,
        )


@dataclass
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
