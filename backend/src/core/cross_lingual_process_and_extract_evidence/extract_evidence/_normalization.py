"""Value normalization for evidence items and raw sources."""
from __future__ import annotations

import re


from .catalog import EVIDENCE_FIELD_SPECS, EvidenceFieldSpec
from .contracts import (
    EvidenceItem,
    EvidenceStatus,
    SpecialEvidenceRecord,
)

_MISSING_GROUP_VALUE = "__missing__"

def normalize_group_token(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "", text)
    return text or _MISSING_GROUP_VALUE
def make_group_id(gene: object, variant: object) -> str:
    return f"gene={normalize_group_token(gene)}|variant={normalize_group_token(variant)}"
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

    def normalize_grouped(
        self,
        items: list[EvidenceItem],
        channel_excluded_field_ids: frozenset[str] = frozenset(),
        target_excluded_field_ids: frozenset[str] = frozenset(),
    ) -> list[EvidenceItem]:
        grouped: dict[str, list[EvidenceItem]] = {}
        for item in items:
            group_id = item.group_id or make_group_id("", "")
            grouped.setdefault(group_id, []).append(item)

        normalized: list[EvidenceItem] = []
        for group_id, group_items in grouped.items():
            by_field: dict[str, EvidenceItem] = {}
            for item in group_items:
                current = by_field.get(item.field_id)
                if current is None:
                    by_field[item.field_id] = item
                    continue
                by_field[item.field_id] = self._choose_better(current, item)

            for spec in self._catalog:
                item = by_field.get(spec.field_id)
                if item is None:
                    # Determine status based on eligibility
                    if spec.field_id in channel_excluded_field_ids:
                        item = self._not_applicable_item(spec).model_copy(update={"group_id": group_id})
                    elif spec.field_id in target_excluded_field_ids:
                        item = self._not_attempted_item(spec).model_copy(update={"group_id": group_id})
                    else:
                        item = self._not_found_item(spec).model_copy(update={"group_id": group_id})
                elif not item.group_id:
                    item = item.model_copy(update={"group_id": group_id})
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

    def _not_applicable_item(self, spec: EvidenceFieldSpec) -> EvidenceItem:
        return EvidenceItem(
            field_id=spec.field_id,
            category=spec.category_id,
            field_name=spec.field_name,
            status=EvidenceStatus.NOT_APPLICABLE,
            value=None,
            confidence=0.0,
            notes="Field excluded by document channel eligibility.",
        )

    def _not_attempted_item(self, spec: EvidenceFieldSpec) -> EvidenceItem:
        return EvidenceItem(
            field_id=spec.field_id,
            category=spec.category_id,
            field_name=spec.field_name,
            status=EvidenceStatus.NOT_ATTEMPTED,
            value=None,
            confidence=0.0,
            notes="Field not attempted due to target/source eligibility or other constraints.",
        )

    @staticmethod
    def _choose_better(current: EvidenceItem, candidate: EvidenceItem) -> EvidenceItem:
        rank = {
            EvidenceStatus.FOUND: 3,
            EvidenceStatus.SOURCE_INVALID: 2,
            EvidenceStatus.TABLE_UNGROUNDED: 1,
            EvidenceStatus.OCR_GAP: 1,
            EvidenceStatus.NOT_FOUND: 0,
            EvidenceStatus.NOT_APPLICABLE: -1,
            EvidenceStatus.NOT_ATTEMPTED: -2,
            EvidenceStatus.CONTEXT_CONTAMINATION: 0,
        }
        current_score = (rank[current.status], current.confidence)
        candidate_score = (rank[candidate.status], candidate.confidence)
        return candidate if candidate_score > current_score else current
class RawSourceNormalizer:
    """Moves ungrounded LLM sources to raw_source before grounding."""

    def normalize_items(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        normalized: list[EvidenceItem] = []
        for item in items:
            if item.status == EvidenceStatus.NOT_FOUND:
                continue
            if item.source is None:
                normalized.append(item)
                continue
            normalized.append(item.model_copy(update={
                "raw_source": item.source,
                "source": None,
            }))
        return normalized

    def normalize_special_records(self, records: list[SpecialEvidenceRecord]) -> list[SpecialEvidenceRecord]:
        normalized: list[SpecialEvidenceRecord] = []
        for record in records:
            if record.source is None:
                normalized.append(record)
                continue
            normalized.append(record.model_copy(update={
                "raw_source": record.source,
                "source": None,
            }))
        return normalized
class FieldValueNormalizer:
    """Enforces enum/format constraints on specific evidence field values."""

    # Fields with strict enum constraints
    _ENUM_FIELDS: dict[str, tuple[str, ...]] = {
        "A.gene_disease_relationship": (
            "causative", "associated", "susceptibility",
            "uncertain", "disputed", "refuted", "no_relationship",
        ),
    }

    _GENE_SYMBOL_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]{1,9}\b")
    _GENE_RELATIONSHIP_PREFIX_RE = re.compile(
        r"\b(?P<gene>[A-Za-z][A-Za-z0-9]{1,9})(?:[-\s]+)(?:related|mutation|associated)\b",
        re.IGNORECASE,
    )
    _GENE_NON_SYMBOL_VALUES = {
        "ACMG", "CNV", "DNA", "HGNC", "HGVS", "OMIM", "RNA", "SNP",
    }
    _GENE_PLACEHOLDER_OR_COMMON_WORDS = {
        "unknown", "none", "not found", "not_found", "n/a", "na",
        "gene", "genes", "patient", "patients", "proband", "family",
        "control", "controls", "case", "cases", "study", "studies",
        "sample", "samples", "variant", "variants", "mutation",
        "mutations", "exon", "exons", "intron", "introns",
        "chromosome", "deletion", "insertion", "analysis", "testing",
        "normal", "abnormal", "positive", "negative", "wildtype",
        "heterozygous", "homozygous", "carrier", "carriers",
    }

    @classmethod
    def normalize_items(cls, items: list[EvidenceItem]) -> list[EvidenceItem]:
        """Normalize field values to their constrained formats."""
        normalized: list[EvidenceItem] = []
        for item in items:
            if item.status != EvidenceStatus.FOUND:
                normalized.append(item)
                continue
            if item.field_id == "A.gene_symbol" and item.value is not None:
                normalized.append(cls._normalize_gene_symbol(item))
                continue
            enum_values = cls._ENUM_FIELDS.get(item.field_id)
            if enum_values and item.value is not None:
                normalized.append(cls._normalize_enum(item, enum_values))
            else:
                normalized.append(item)
        return normalized

    @classmethod
    def _normalize_gene_symbol(cls, item: EvidenceItem) -> EvidenceItem:
        """Extract a clean HGNC-style gene symbol from the raw value.

        Only uppercases tokens that are already in gene-symbol-like form
        (contains at least one uppercase letter) or were extracted from a
        disease-prefix phrase. Rejects common placeholder words and English
        words that are not gene symbols.
        """
        raw = str(item.value).strip()
        if cls._GENE_SYMBOL_RE.fullmatch(raw):
            if raw.lower() in cls._GENE_PLACEHOLDER_OR_COMMON_WORDS:
                return cls._reject_gene_symbol(item)
            if raw == raw.lower():
                return item
            normalized = raw.upper()
            if normalized in cls._GENE_NON_SYMBOL_VALUES:
                return item
            return item.model_copy(update={"value": normalized})
        match = cls._GENE_RELATIONSHIP_PREFIX_RE.search(raw)
        if match is None:
            return item
        candidate = match.group("gene")
        if candidate.lower() in cls._GENE_PLACEHOLDER_OR_COMMON_WORDS:
            return cls._reject_gene_symbol(item)
        normalized = candidate.upper()
        if normalized in cls._GENE_NON_SYMBOL_VALUES:
            return item
        return item.model_copy(update={"value": normalized})

    @staticmethod
    def _reject_gene_symbol(item: EvidenceItem) -> EvidenceItem:
        """Reject a gene symbol value as not_found."""
        return item.model_copy(update={
            "status": EvidenceStatus.NOT_FOUND,
            "value": None,
            "confidence": 0.0,
        })

    @classmethod
    def _normalize_enum(cls, item: EvidenceItem, valid_values: tuple[str, ...]) -> EvidenceItem:
        """Normalize a field value to the best matching enum value."""
        raw = str(item.value).strip().lower()
        # Exact match
        if raw in valid_values:
            return item
        # Negation and hedging checks — must run before substring/keyword matching
        if item.field_id == "A.gene_disease_relationship":
            if re.search(r"\b(?:non[-\s]?caus(?:al|ative)?|not (?:a )?caus(?:al|ative)?)\b", raw):
                return item.model_copy(update={"value": "associated"})
            if re.search(r"\bnot (?:a )?(?:known )?disease gene\b", raw):
                return item.model_copy(update={"value": "uncertain"})
            if "preliminary association" in raw or "only a preliminary" in raw:
                return item.model_copy(update={"value": "associated"})
        # Substring match — find the valid value contained in the raw text
        for v in valid_values:
            if v in raw:
                return item.model_copy(update={"value": v})
        # Keyword match — word-boundary regex patterns
        keyword_map = {
            "causative": (
                r"\bcauses?\b",
                r"\bcausative\b",
                r"\bcausal\b",
                r"\bpathogenic\b",
                r"\bresponsible\b",
                r"\bknown disease gene\b",
                r"\bdisease gene\b",
            ),
            "associated": (
                r"\bassociated\b",
                r"\bassociation\b",
                r"\blink(?:ed)?\b",
                r"\brelated\b",
            ),
            "susceptibility": (
                r"\bsusceptibility\b",
                r"\bsusceptible\b",
                r"\brisk\b",
                r"\bpredispos",
            ),
            "uncertain": (
                r"\buncertain\b",
                r"\bunclear\b",
                r"\bpossible\b",
                r"\bpotential\b",
            ),
            "disputed": (
                r"\bdisputed\b",
                r"\bcontroversial\b",
                r"\bconflicting\b",
            ),
            "refuted": (
                r"\brefuted\b",
                r"\brefute\b",
                r"\bno evidence\b",
                r"\bnot supported\b",
            ),
            "no_relationship": (
                r"\bno relationship\b",
                r"\bno known\b",
                r"\bnot related\b",
            ),
        }
        for value, patterns in keyword_map.items():
            if any(re.search(pattern, raw) for pattern in patterns):
                return item.model_copy(update={"value": value})
        # Default: keep original but log
        return item

