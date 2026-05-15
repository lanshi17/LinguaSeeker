"""Deterministic source grounding and quality validation."""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from .contracts import (
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    QualityIssue,
    QualityReport,
    SourceLocation,
    SourcePrecision,
    TrackDocument,
)


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

        corrected = self._search_snippet(document, snippet)
        if corrected is None:
            logger.warning("Snippet '{}' not found in document", snippet)
            return item

        if len(corrected) > 1:
            logger.info("Snippet '{}' found {} times, marking ambiguous", snippet, len(corrected))
            new_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.AMBIGUOUS})
            return item.model_copy(update={"source": new_source, "raw_source": source})

        new_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.CORRECTED})
        return item.model_copy(update={"source": new_source, "raw_source": source})

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
        snippet: str,
    ) -> list[SourceLocation] | None:
        text = document.formatted_text
        spans = document.page_spans
        results: list[SourceLocation] = []

        idx = 0
        while True:
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
                    context_type="text",
                    context_ref="",
                    text_snippet=snippet,
                    source_precision=SourcePrecision.EXACT,
                ))
            idx = pos + 1

        return results if results else None

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


class QualityValidator:
    """Rule-based quality validation for extracted evidence."""

    def __init__(self, required_field_ids: set[str]):
        self._required_field_ids = required_field_ids

    def validate(
        self,
        items: list[EvidenceItem],
        contradictions: list[str],
    ) -> QualityReport:
        issues: list[QualityIssue] = []
        found_count = 0
        not_found_count = 0
        source_invalid_count = 0

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
            elif item.status == EvidenceStatus.NOT_FOUND:
                not_found_count += 1
            elif item.status == EvidenceStatus.SOURCE_INVALID:
                source_invalid_count += 1

        missing_required = self._required_field_ids - {
            item.field_id for item in items
            if item.status == EvidenceStatus.FOUND
        }
        for field_id in missing_required:
            issues.append(QualityIssue(
                issue_type="missing_required",
                field_id=field_id,
                description=f"Required field {field_id} is missing",
                severity="warning",
            ))

        for contradiction in contradictions:
            issues.append(QualityIssue(
                issue_type="contradiction",
                field_id="",
                description=contradiction,
                severity="warning",
            ))

        passed = not any(i.severity == "error" for i in issues)
        scorable = len(missing_required) == 0

        return QualityReport(
            passed=passed,
            scorable=scorable,
            issues=issues,
            found_count=found_count,
            not_found_count=not_found_count,
            source_invalid_count=source_invalid_count,
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
