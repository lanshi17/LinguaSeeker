"""Deterministic ACMG evidence value normalization."""
from __future__ import annotations

import re

from .contracts import (
    EvidenceItem,
    EvidenceNormalizationIssue,
    EvidenceNormalizationIssueType,
    EvidenceNormalizationSeverity,
    EvidenceStatus,
)

_COORDINATE_ONLY_RE = re.compile(r"^(?:chr)?[0-9XYM]+[_:][0-9]+$", re.IGNORECASE)
_HGVS_G_RE = re.compile(
    r"^[A-Z]{1,3}_[0-9]+(?:\.[0-9]+)?:g\."
    r"(?:"
    r"[0-9]+[ACGT]>[ACGT]|"
    r"[0-9]+(?:_[0-9]+)?del(?:[ACGT]+)?|"
    r"[0-9]+(?:_[0-9]+)?ins[ACGT]+|"
    r"[0-9]+(?:_[0-9]+)?dup(?:[ACGT]+)?|"
    r"[0-9]+_[0-9]+inv"
    r")$"
)


class AcmgEvidenceValueNormalizer:
    """Normalize extracted values before catalog backfill and quality gates."""

    _HGVS_OR_REFERENCE_FIELDS = {
        "A.variant_hgvs_g",
        "A.reference_sequence",
        "A.variant_legacy_name",
    }

    def normalize(
        self, items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], list[EvidenceNormalizationIssue]]:
        normalized: list[EvidenceItem] = []
        issues: list[EvidenceNormalizationIssue] = []
        for item in items:
            replacement, item_issues = self._normalize_one(item)
            normalized.append(replacement)
            issues.extend(item_issues)
        return normalized, issues

    def _normalize_one(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if item.status != EvidenceStatus.FOUND or item.value is None:
            return item, []
        value_text = str(item.value).strip()
        if item.field_id in self._HGVS_OR_REFERENCE_FIELDS and _COORDINATE_ONLY_RE.fullmatch(value_text):
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Coordinate-only value is not valid for this HGVS/reference field.",
                        original_value=item.value,
                    )
                ],
            )
        if item.field_id == "A.variant_hgvs_g" and value_text and not _HGVS_G_RE.fullmatch(value_text):
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="HGVS genomic variant must include reference sequence, g. coordinate, and base change.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _reject_item(self, item: EvidenceItem) -> EvidenceItem:
        return item.model_copy(update={
            "status": EvidenceStatus.NOT_FOUND,
            "value": None,
            "confidence": 0.0,
            "assigned_acmg_codes": [],
            "assigned_clingen_modules": [],
        })
