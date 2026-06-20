"""Deterministic ACMG evidence value normalization."""
from __future__ import annotations

import re
import unicodedata

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

    _GENE_SYMBOL_FIELDS = {
        "A.gene_symbol",
        "A.gene_aliases",
    }
    _HGVS_OR_REFERENCE_FIELDS = {
        "A.variant_hgvs_g",
        "A.reference_sequence",
        "A.variant_legacy_name",
    }

    _MILESTONE_PATTERNS = (
        r"\bstarted sitting\b",
        r"\bsitting with support\b",
        r"\bstarted walking\b",
        r"\bdelayed walking\b",
        r"\bstarted speaking\b",
        r"\bdevelopmental milestone\b",
    )
    _ONSET_TERMS = ("onset", "presented", "presentation", "diagnosed", "referred", "symptom")
    _GENERIC_PREDICTION_VALUES = {
        "in silico tools",
        "bioinformatics tools",
        "prediction tools",
        "computational tools",
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
        merged, merge_issues = self._merge_duplicates(normalized)
        issues.extend(merge_issues)
        return merged, issues

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
        if item.field_id in self._GENE_SYMBOL_FIELDS:
            return self._normalize_gene_symbol(item)
        if item.field_id == "C.de_novo_status":
            return self._normalize_de_novo(item)
        if item.field_id == "B.consanguinity":
            return self._normalize_consanguinity(item)
        if item.field_id == "C.obligate_carriers":
            return self._normalize_obligate_carriers(item)
        if item.field_id == "B.age_of_onset":
            return self._normalize_age_of_onset(item)
        if item.field_id.startswith("F."):
            return self._reject_in_silico_functional(item)
        if item.field_id == "E.prediction_tools_list":
            return self._normalize_prediction_tools(item)
        return item, []

    def _with_value_issue(
        self, item: EvidenceItem, normalized_value: object,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        return (
            item.model_copy(update={"value": normalized_value}),
            [
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.VALUE_NORMALIZED,
                    severity=EvidenceNormalizationSeverity.INFO,
                    field_id=item.field_id,
                    message="Field value normalized to ACMG-ready representation.",
                    original_value=item.value,
                    normalized_value=normalized_value,
                )
            ],
        )

    def _normalize_de_novo(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip().lower()
        if item.value is False or text in {"0", "false", "not de novo", "not_de_novo", "inherited"}:
            return self._with_value_issue(item, "not_de_novo")
        if item.value is True or text in {"1", "true", "de novo", "denovo"}:
            return self._with_value_issue(item, "de_novo")
        if text in {"unknown", "not reported", "not_reported"}:
            return self._with_value_issue(item, "unknown")
        return item, []

    def _normalize_consanguinity(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip()
        lower = text.lower()
        if lower in {"present", "consanguineous", "true"}:
            return self._with_value_issue(item, "present")
        if lower in {"absent", "non-consanguineous", "false"}:
            return self._with_value_issue(item, "absent")
        if lower in {"unknown", "not reported", "not_reported", "not applicable", "n/a", "na"}:
            return self._with_value_issue(item, "unknown")
        if text:
            return self._with_value_issue(item, f"present:{text}")
        return item, []

    def _normalize_obligate_carriers(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if item.value is True:
            return self._with_value_issue(item, 2)
        if item.value is False:
            return self._with_value_issue(item, 0)
        if isinstance(item.value, int):
            return item, []
        text = str(item.value).strip().lower()
        if text in {"parents", "both parents"}:
            return self._with_value_issue(item, 2)
        if text.isdigit():
            return self._with_value_issue(item, int(text))
        return item, []

    def _normalize_gene_symbol(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        value = item.value
        if isinstance(value, list):
            normalized = [
                unicodedata.normalize("NFKC", str(v)).strip().upper()
                for v in value
            ]
        elif isinstance(value, str):
            normalized = unicodedata.normalize("NFKC", value).strip().upper()
        else:
            return item, []
        if normalized == value:
            return item, []
        return self._with_value_issue(item, normalized)

    def _normalize_age_of_onset(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip()
        lower = text.lower()
        has_milestone = any(re.search(pattern, lower) for pattern in self._MILESTONE_PATTERNS)
        has_onset = any(term in lower for term in self._ONSET_TERMS)
        if has_milestone and not has_onset:
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.SEMANTIC_CONFLICT,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Developmental milestone age must not be used as age of onset.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _reject_in_silico_functional(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value or "").strip().lower()
        if "in silico" in text or "computational" in text:
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.SEMANTIC_CONFLICT,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Computational prediction must not be treated as functional evidence.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _normalize_prediction_tools(
        self, item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if isinstance(item.value, list):
            values = [str(v).strip() for v in item.value if str(v).strip()]
            if not values:
                return self._reject_item(item), []
            named = [v for v in values if v.lower() not in self._GENERIC_PREDICTION_VALUES]
            if named:
                replacement, issues = self._with_value_issue(item, named)
                if len(named) != len(values):
                    issues.append(
                        EvidenceNormalizationIssue(
                            issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                            severity=EvidenceNormalizationSeverity.WARNING,
                            field_id=item.field_id,
                            message="Generic prediction-tool phrase removed from named tool list.",
                            original_value=item.value,
                            normalized_value=named,
                        )
                    )
                return replacement, issues
        else:
            text = str(item.value).strip()
            if text.lower() in self._GENERIC_PREDICTION_VALUES:
                pass  # fall through to reject below
            elif "," in text or ";" in text:
                values = [v.strip() for v in re.split(r"[,;]", text) if v.strip()]
                named = [v for v in values if v.lower() not in self._GENERIC_PREDICTION_VALUES]
                if named:
                    replacement, issues = self._with_value_issue(item, named)
                    if len(named) != len(values):
                        issues.append(
                            EvidenceNormalizationIssue(
                                issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                                severity=EvidenceNormalizationSeverity.WARNING,
                                field_id=item.field_id,
                                message="Generic prediction-tool phrase removed from named tool list.",
                                original_value=item.value,
                                normalized_value=named,
                            )
                        )
                    return replacement, issues
            else:
                return item, []
        return (
            self._reject_item(item),
            [
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                    severity=EvidenceNormalizationSeverity.WARNING,
                    field_id=item.field_id,
                    message="Prediction tool evidence requires named algorithms.",
                    original_value=item.value,
                )
            ],
        )

    def _merge_duplicates(
        self, items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], list[EvidenceNormalizationIssue]]:
        by_key: dict[tuple[str, str, str, str], EvidenceItem] = {}
        order: list[tuple[str, str, str, str]] = []
        issues: list[EvidenceNormalizationIssue] = []
        for item in items:
            base_key = (item.group_id, item.field_id, self._normalized_value_key(item.value))
            key = self._dedupe_key(base_key, item, by_key)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = self._clean_value(item)
                order.append(key)
                continue
            if item.confidence > existing.confidence:
                by_key[key] = self._clean_value(self._merge_source(item, existing))
            elif existing.raw_source is None and item.raw_source is not None:
                by_key[key] = existing.model_copy(update={"raw_source": item.raw_source})
            issues.append(
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.DUPLICATE_MERGED,
                    severity=EvidenceNormalizationSeverity.INFO,
                    field_id=item.field_id,
                    message="Duplicate evidence item merged by normalized fact key.",
                    original_value=item.value,
                    normalized_value=by_key[key].value,
                )
            )
        return [by_key[key] for key in order], issues

    @staticmethod
    def _clean_value(item: EvidenceItem) -> EvidenceItem:
        if isinstance(item.value, str):
            cleaned = re.sub(r"\s+", " ", item.value.strip())
            if cleaned != item.value:
                return item.model_copy(update={"value": cleaned})
        return item

    def _dedupe_key(
        self,
        base_key: tuple[str, str, str],
        item: EvidenceItem,
        by_key: dict[tuple[str, str, str, str], EvidenceItem],
    ) -> tuple[str, str, str, str]:
        source_signature = self._source_signature(item)
        exact_key = (*base_key, source_signature)
        if exact_key in by_key:
            return exact_key
        if source_signature == "source:none":
            for existing_key in by_key:
                if existing_key[:3] == base_key:
                    return existing_key
            return exact_key
        none_key = (*base_key, "source:none")
        if none_key in by_key:
            return none_key
        return exact_key

    def _normalized_value_key(self, value: object) -> str:
        if isinstance(value, list):
            return "list:" + "|".join(sorted(str(entry).strip().lower() for entry in value))
        if value is None:
            return "none:"
        normalized_text = re.sub(r"\s+", " ", str(value).strip().lower())
        return f"{type(value).__name__}:{normalized_text}"

    def _source_signature(self, item: EvidenceItem) -> str:
        source = item.raw_source or item.source
        if source is None:
            return "source:none"
        return f"source:{source.block_index}:{source.context_type}:{source.context_ref}:{source.text_snippet}"

    def _merge_source(self, winner: EvidenceItem, loser: EvidenceItem) -> EvidenceItem:
        if winner.raw_source is None and loser.raw_source is not None:
            return winner.model_copy(update={"raw_source": loser.raw_source})
        if winner.source is None and loser.source is not None:
            return winner.model_copy(update={"source": loser.source})
        return winner

    def _reject_item(self, item: EvidenceItem) -> EvidenceItem:
        return item.model_copy(update={
            "status": EvidenceStatus.NOT_FOUND,
            "value": None,
            "confidence": 0.0,
            "assigned_acmg_codes": [],
            "assigned_clingen_modules": [],
        })
