"""Deterministic source grounding and quality validation."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import re

from loguru import logger

from .catalog import EVIDENCE_FIELD_SPECS, EvidenceFieldSpec
from .contracts import (
    ContentBlock,
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
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
_MISSING_GROUP_VALUE = "__missing__"


def _normalize_for_grounding(text: str) -> str:
    """Normalize text for fuzzy grounding: collapse whitespace, lowercase."""
    text = _MULTISPACE_PATTERN.sub(" ", text).strip()
    return text.lower()


def _fuzzy_ellipsis_match(snippet: str, doc_text: str) -> bool:
    """Check if an ellipsis-containing snippet matches the document.

    Splits on ellipsis and verifies each fragment appears in the document
    in order.  Returns True if all fragments are found sequentially.
    """
    fragments = _ELLIPSIS_PATTERN.split(snippet)
    fragments = [f.strip() for f in fragments if f.strip()]
    if not fragments:
        return False

    normalized_doc = _normalize_for_grounding(doc_text)
    last_pos = -1
    for frag in fragments:
        norm_frag = _normalize_for_grounding(frag)
        if not norm_frag:
            continue
        pos = normalized_doc.find(norm_frag, last_pos + 1)
        if pos == -1:
            return False
        last_pos = pos
    return True


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

    def normalize_grouped(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
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

    @staticmethod
    def _choose_better(current: EvidenceItem, candidate: EvidenceItem) -> EvidenceItem:
        rank = {
            EvidenceStatus.FOUND: 3,
            EvidenceStatus.SOURCE_INVALID: 2,
            EvidenceStatus.TABLE_UNGROUNDED: 1,
            EvidenceStatus.OCR_GAP: 1,
            EvidenceStatus.NOT_FOUND: 0,
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


class GroupAssigner:
    """Assigns deterministic variant-centered group ids to evidence."""

    _VARIANT_FIELDS = {"A.variant_hgvs_c", "A.variant_hgvs_p", "F.tested_variant"}
    _GENE_FIELD = "A.gene_symbol"

    def assign(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]:
        group_ids = self._build_group_ids(document, items)
        grouped_items = [
            item.model_copy(update={"group_id": self._assign_item_group(item, group_ids, items, document)})
            for item in items
        ]
        grouped_special = [
            record.model_copy(update={"group_id": self._assign_special_group(record, group_ids, grouped_items)})
            for record in special_records
        ]
        return grouped_items, grouped_special

    def _build_group_ids(self, document: TrackDocument, items: list[EvidenceItem]) -> list[str]:
        gene_items = [item for item in items if item.field_id == self._GENE_FIELD and item.value is not None]
        variant_items = [item for item in items if item.field_id in self._VARIANT_FIELDS and item.value is not None]

        group_ids: list[str] = []
        for variant_item in variant_items:
            gene_value = self._resolve_gene_for_variant(variant_item, gene_items, document)
            group_id = make_group_id(gene_value, variant_item.value)
            if group_id not in group_ids:
                group_ids.append(group_id)

        for gene_item in gene_items:
            has_variant_group = any(
                group_id.startswith(f"gene={normalize_group_token(gene_item.value)}|")
                and not group_id.endswith(f"variant={_MISSING_GROUP_VALUE}")
                for group_id in group_ids
            )
            group_id = make_group_id(gene_item.value, "")
            if not has_variant_group and group_id not in group_ids:
                group_ids.append(group_id)

        return sorted(group_ids)

    def _resolve_gene_for_variant(
        self,
        variant_item: EvidenceItem,
        gene_items: list[EvidenceItem],
        document: TrackDocument,
    ) -> object:
        variant_block = self._block_index_for_item(variant_item)
        if gene_items:
            same_block = [item for item in gene_items if self._block_index_for_item(item) == variant_block]
            if same_block:
                return same_block[0].value
            nearest_gene = min(
                gene_items,
                key=lambda item: (
                    abs(self._block_index_for_item(item) - variant_block),
                    normalize_group_token(item.value),
                ),
            )
            if nearest_gene.value:
                return nearest_gene.value

        text = self._document_block_text(document, variant_block)
        for gene_item in gene_items:
            gene_text = str(gene_item.value or "").strip()
            if gene_text and gene_text in text:
                return gene_text
        inferred_gene = self._infer_gene_from_text(text)
        if inferred_gene:
            return inferred_gene
        return ""

    def _assign_item_group(
        self,
        item: EvidenceItem,
        group_ids: list[str],
        items: list[EvidenceItem],
        document: TrackDocument,
    ) -> str:
        if item.field_id == self._GENE_FIELD:
            variant = self._match_variant_for_gene(item, items)
            return make_group_id(item.value, variant)
        if item.field_id in self._VARIANT_FIELDS:
            gene = self._resolve_gene_for_variant(item, [candidate for candidate in items if candidate.field_id == self._GENE_FIELD], document)
            return make_group_id(gene, item.value)

        matched = self._match_group_by_text(item, group_ids)
        if matched is not None:
            return matched
        return self._nearest_group(item, group_ids, items)

    def _assign_special_group(
        self,
        record: SpecialEvidenceRecord,
        group_ids: list[str],
        grouped_items: list[EvidenceItem],
    ) -> str:
        matched = self._match_group_by_text(record, group_ids)
        if matched is not None:
            return matched
        return self._nearest_group_for_block(self._block_index_for_special_record(record), group_ids, grouped_items)

    def _match_variant_for_gene(self, gene_item: EvidenceItem, items: list[EvidenceItem]) -> object:
        same_block_variants = [
            item for item in items
            if item.field_id in self._VARIANT_FIELDS and self._block_index_for_item(item) == self._block_index_for_item(gene_item)
        ]
        if same_block_variants:
            return same_block_variants[0].value
        nearest_variants = [item for item in items if item.field_id in self._VARIANT_FIELDS]
        if not nearest_variants:
            return ""
        nearest = min(
            nearest_variants,
            key=lambda item: (
                abs(self._block_index_for_item(item) - self._block_index_for_item(gene_item)),
                normalize_group_token(item.value),
            ),
        )
        return nearest.value

    def _match_group_by_text(self, obj: EvidenceItem | SpecialEvidenceRecord, group_ids: list[str]) -> str | None:
        haystacks = self._text_haystacks(obj)
        matches: list[str] = []
        for group_id in group_ids:
            gene_token, variant_token = self._parse_group_id(group_id)
            for haystack in haystacks:
                gene_ok = gene_token == _MISSING_GROUP_VALUE or gene_token in haystack
                variant_ok = variant_token == _MISSING_GROUP_VALUE or variant_token in haystack
                if gene_ok and variant_ok:
                    matches.append(group_id)
                    break
        if not matches:
            return None
        return sorted(matches, key=self._group_sort_key)[0]

    def _nearest_group(
        self,
        item: EvidenceItem,
        group_ids: list[str],
        items: list[EvidenceItem],
    ) -> str:
        return self._nearest_group_for_block(self._block_index_for_item(item), group_ids, items)

    def _nearest_group_for_block(
        self,
        block_index: int,
        group_ids: list[str],
        items: list[EvidenceItem],
    ) -> str:
        if not group_ids:
            return make_group_id("", "")
        anchors: dict[str, list[int]] = {group_id: [] for group_id in group_ids}
        for candidate in items:
            candidate_group = candidate.group_id
            if candidate_group in anchors:
                anchors[candidate_group].append(self._block_index_for_item(candidate))

        ranked = []
        for group_id in group_ids:
            distances = anchors.get(group_id) or []
            ranked.append((
                min(abs(block - block_index) for block in distances) if distances else float("inf"),
                self._group_sort_key(group_id),
                group_id,
            ))
        ranked.sort()
        return ranked[0][2]

    def _group_sort_key(self, group_id: str) -> tuple[int, str]:
        gene_token, variant_token = self._parse_group_id(group_id)
        complete = 0 if gene_token != _MISSING_GROUP_VALUE and variant_token != _MISSING_GROUP_VALUE else 1
        return (complete, group_id)

    @staticmethod
    def _parse_group_id(group_id: str) -> tuple[str, str]:
        parts = dict(part.split("=", maxsplit=1) for part in group_id.split("|"))
        return parts.get("gene", _MISSING_GROUP_VALUE), parts.get("variant", _MISSING_GROUP_VALUE)

    @staticmethod
    def _block_index_for_item(item: EvidenceItem) -> int:
        source = item.raw_source or item.source
        if source is None:
            return -1
        return source.block_index

    @staticmethod
    def _block_index_for_special_record(record: SpecialEvidenceRecord) -> int:
        source = record.raw_source or record.source
        if source is None:
            return -1
        return source.block_index

    @staticmethod
    def _document_block_text(document: TrackDocument, block_index: int) -> str:
        if block_index < 0 or block_index >= len(document.blocks):
            return document.formatted_text
        block = document.blocks[block_index]
        parts = [*block.table_caption, *block.image_caption, *block.chart_caption]
        for value in (block.text, block.content, block.table_body):
            if value.strip():
                parts.append(value.strip())
        return "\n".join(parts)

    @staticmethod
    def _text_haystacks(obj: EvidenceItem | SpecialEvidenceRecord) -> list[str]:
        haystacks: list[str] = []
        if isinstance(obj, EvidenceItem):
            for value in (obj.value, obj.notes):
                if value is not None:
                    haystacks.append(normalize_group_token(value))
            source = obj.raw_source or obj.source
            if source is not None:
                haystacks.append(normalize_group_token(source.text_snippet))
        else:
            haystacks.append(normalize_group_token(obj.description))
            source = obj.raw_source or obj.source
            if source is not None:
                haystacks.append(normalize_group_token(source.text_snippet))
        return haystacks

    @staticmethod
    def _infer_gene_from_text(text: str) -> str:
        match = re.search(r"\b([A-Z][A-Z0-9-]{1,})\b", text)
        return match.group(1) if match else ""


class SourceGrounder:
    """Validates and repairs source spans against the document."""

    def ground_items(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        grounded: list[EvidenceItem] = []
        for item in items:
            source = self._raw_input_source(item)
            if item.status == EvidenceStatus.FOUND and source is None and item.field_id == "B.case_count":
                grounded.append(item.model_copy(update={"status": EvidenceStatus.TABLE_UNGROUNDED}))
                continue
            if item.status != EvidenceStatus.FOUND or source is None:
                grounded.append(item)
                continue
            grounded.append(self._ground_one(document, item, source))
        return grounded

    def ground_special_records(
        self,
        document: TrackDocument,
        records: list[SpecialEvidenceRecord],
    ) -> list[SpecialEvidenceRecord]:
        grounded: list[SpecialEvidenceRecord] = []
        for record in records:
            source = record.raw_source or record.source
            if source is None:
                grounded.append(record)
                continue
            grounded_source = self._ground_source(document, source)
            if grounded_source is None:
                grounded.append(record.model_copy(update={"source": None}))
                continue
            grounded.append(record.model_copy(update={"source": grounded_source, "raw_source": source}))
        return grounded

    def _ground_one(
        self,
        document: TrackDocument,
        item: EvidenceItem,
        source: SourceLocation,
    ) -> EvidenceItem:
        snippet = source.text_snippet

        if self._snippet_has_ellipsis(snippet):
            # Try fuzzy match: split on ellipsis, verify each fragment in order
            block = self._block_for_index(document, source.block_index)
            block_text = self._block_readable_text(block) if block is not None else ""
            if _fuzzy_ellipsis_match(snippet, block_text):
                logger.debug("Snippet matched via fuzzy grounding (ellipsis fragments found in order)")
            else:
                logger.warning("Snippet '{}' contains ellipsis and not found via fuzzy match, marking SOURCE_INVALID", snippet)
                return item.model_copy(update={
                    "status": EvidenceStatus.SOURCE_INVALID,
                    "raw_source": source,
                    "source": None,
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                })


        grounded_source = self._ground_source(document, source)
        if grounded_source is None:
            block = self._block_for_index(document, source.block_index)
            mapped_type = self._map_block_type(block.type) if block is not None else source.block_type
            if mapped_type == "table":
                logger.warning("Snippet '{}' not found in table source, marking TABLE_UNGROUNDED", snippet)
                return item.model_copy(update={
                    "status": EvidenceStatus.TABLE_UNGROUNDED,
                    "raw_source": source,
                    "source": None,
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                })
            if mapped_type in {"image", "figure"}:
                logger.warning("Snippet '{}' not found in document image/table source, marking OCR_GAP", snippet)
                return item.model_copy(update={
                    "status": EvidenceStatus.OCR_GAP,
                    "raw_source": source,
                    "source": None,
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                })
            logger.warning("Snippet '{}' not found in document, marking SOURCE_INVALID", snippet)
            return item.model_copy(update={
                "status": EvidenceStatus.SOURCE_INVALID,
                "raw_source": source,
                "source": None,
                "assigned_acmg_codes": [],
                "assigned_clingen_modules": [],
            })

        return item.model_copy(update={"source": grounded_source, "raw_source": source})

    def _ground_source(self, document: TrackDocument, source: SourceLocation) -> SourceLocation | None:
        block = self._block_for_index(document, source.block_index)
        if block is not None:
            block_text = self._block_readable_text(block)
            if source.text_snippet and source.text_snippet in block_text:
                return self._build_source_from_text(document, source, source.text_snippet, block_index=source.block_index, block=block)

        if self._is_exact_match(document, source):
            block_match = self._find_block_for_offsets(document, source.start_offset, source.end_offset)
            if block_match is None:
                return source.model_copy(update={"block_index": -1, "bbox": [], "source_precision": SourcePrecision.EXACT})
            block_index, matched_block = block_match
            return source.model_copy(update={
                "block_index": block_index,
                "bbox": matched_block.bbox,
                "block_type": self._map_block_type(matched_block.type),
                "source_precision": SourcePrecision.EXACT,
            })

        corrected = self._search_snippet(document, source, source.text_snippet, "")
        if corrected is None:
            return None
        if len(corrected) > 1:
            logger.info("Snippet '{}' found {} times, marking ambiguous", source.text_snippet, len(corrected))
            corrected_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.AMBIGUOUS})
        else:
            corrected_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.CORRECTED})

        block_match = self._find_block_for_offsets(document, corrected_source.start_offset, corrected_source.end_offset)
        if block_match is None:
            return corrected_source.model_copy(update={"block_index": -1, "bbox": []})
        block_index, matched_block = block_match
        return corrected_source.model_copy(update={
            "block_index": block_index,
            "bbox": matched_block.bbox,
            "block_type": self._map_block_type(matched_block.type),
        })

    @staticmethod
    def _raw_input_source(item: EvidenceItem) -> SourceLocation | None:
        return item.raw_source or item.source

    @staticmethod
    def _block_for_index(document: TrackDocument, block_index: int) -> ContentBlock | None:
        if block_index < 0 or block_index >= len(document.blocks):
            return None
        return document.blocks[block_index]

    @staticmethod
    def _block_readable_text(block: ContentBlock) -> str:
        parts = [*block.table_caption, *block.image_caption, *block.chart_caption]
        for value in (block.text, block.content, block.table_body):
            if value.strip():
                parts.append(value.strip())
        return "\n".join(parts).strip()

    @staticmethod
    _KNOWN_CONTEXT_TYPES = frozenset({
        "text", "table", "figure", "supplementary", "caption",
        "abstract", "introduction", "methods", "results", "discussion",
        "conclusion", "background",
    })

    @staticmethod
    def _map_block_type(block_type: str) -> str:
        mapping = {"chart": "figure", "image": "figure", "table": "table"}
        mapped = mapping.get(block_type, block_type)
        return mapped if mapped in EvidenceItemNormalizer._KNOWN_CONTEXT_TYPES else "text"

    def _find_block_for_offsets(
        self,
        document: TrackDocument,
        start: int,
        end: int,
    ) -> tuple[int, ContentBlock] | None:
        if not document.blocks:
            return None
        for index, block in enumerate(document.blocks):
            block_text = self._block_readable_text(block)
            if not block_text:
                continue
            pos = document.formatted_text.find(block_text)
            if pos == -1:
                continue
            block_end = pos + len(block_text)
            if pos <= start and end <= block_end:
                return index, block
        return None

    def _build_source_from_text(
        self,
        document: TrackDocument,
        source: SourceLocation,
        text_snippet: str,
        block_index: int,
        block: ContentBlock,
    ) -> SourceLocation | None:
        start = document.formatted_text.find(text_snippet)
        if start >= 0:
            end = start + len(text_snippet)
            span = self._find_span(document.page_spans, start, end)
            if span is None:
                return None
            return SourceLocation(
                span_id=span.span_id,
                page=span.page,
                start_offset=start,
                end_offset=end,
                context_type=source.context_type,
                context_ref=source.context_ref,
                text_snippet=text_snippet,
                block_index=block_index,
                bbox=block.bbox,
                block_type=self._map_block_type(block.type),
                source_precision=SourcePrecision.EXACT,
            )

        block_text = self._block_readable_text(block)
        snippet_offset = block_text.find(text_snippet)
        span = self._find_span(document.page_spans, 0, len(document.formatted_text))
        if span is None:
            span = PageSpan(
                span_id=f"{document.track.value}-p{block.page_idx + 1}",
                page=block.page_idx + 1,
                start_offset=0,
                end_offset=max(len(document.formatted_text), 0),
            )
        return SourceLocation(
            span_id=span.span_id,
            page=span.page,
            start_offset=span.start_offset + max(snippet_offset, 0),
            end_offset=span.start_offset + max(snippet_offset, 0) + len(text_snippet),
            context_type=source.context_type,
            context_ref=source.context_ref,
            text_snippet=text_snippet,
            block_index=block_index,
            bbox=block.bbox,
            block_type=self._map_block_type(block.type),
            source_precision=SourcePrecision.EXACT,
        )

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
        del field_id
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

        return None

    @staticmethod
    def _snippet_has_ellipsis(snippet: str) -> bool:
        return bool(_ELLIPSIS_PATTERN.search(snippet))

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
                    block_index=source.block_index,
                    bbox=source.bbox,
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
                    block_index=source.block_index,
                    bbox=source.bbox,
                    block_type=source.block_type,
                    source_precision=SourcePrecision.EXACT,
                ))
            idx = pos + 1
        return results

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
    """Builds variant-centered identity chains from grounded grouped evidence."""

    def build(
        self,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> list[EvidenceChain]:
        grouped_items: dict[str, list[EvidenceItem]] = {}
        for item in items:
            if not self._is_valid_grounded(item):
                continue
            group_id = item.group_id
            if not group_id:
                continue
            grouped_items.setdefault(group_id, []).append(item)

        chains: list[EvidenceChain] = []
        for group_id, group_items in grouped_items.items():
            by_field: dict[str, list[EvidenceItem]] = {}
            for item in group_items:
                by_field.setdefault(item.field_id, []).append(item)

            gene = self._first_value(by_field, "A.gene_symbol")
            disease = self._first_value(by_field, "B.disease_diagnosis")
            variant = self._first_value(by_field, "A.variant_hgvs_c") or self._first_value(by_field, "A.variant_hgvs_p")

            core_count = sum(1 for value in (gene, disease, variant) if value is not None)
            if core_count == 0:
                continue
            if core_count == 3:
                chain_level = "full"
            elif core_count == 2:
                chain_level = "partial"
            else:
                chain_level = "singleton"

            case_ids = sorted({
                str(item.value)
                for item in by_field.get("B.case_id", [])
                if item.value is not None
            })
            special_indices = [
                index for index, record in enumerate(special_records)
                if record.group_id == group_id
            ]
            contradictions = [
                record.description
                for record in special_records
                if record.group_id == group_id and record.record_type == "contradiction"
            ]

            chains.append(EvidenceChain(
                chain_id=group_id,
                chain_level=chain_level,
                gene_text=str(gene.value) if gene is not None and gene.value is not None else "",
                disease_text=str(disease.value) if disease is not None and disease.value is not None else "",
                variant_text=str(variant.value) if variant is not None and variant.value is not None else "",
                case_ids=case_ids,
                special_evidence_ids=[f"special-{index}" for index in special_indices],
                evidence_field_ids=sorted({item.field_id for item in group_items}),
                contradictions=contradictions,
            ))
        return sorted(chains, key=lambda chain: chain.chain_id)

    @staticmethod
    def _is_valid_grounded(item: EvidenceItem) -> bool:
        return (
            item.status == EvidenceStatus.FOUND
            and item.value is not None
            and item.source is not None
            and item.source.source_precision != SourcePrecision.AMBIGUOUS
        )

    @staticmethod
    def _first_value(by_field: dict[str, list[EvidenceItem]], field_id: str) -> EvidenceItem | None:
        values = by_field.get(field_id, [])
        return values[0] if values else None


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
            if item.status == EvidenceStatus.FOUND and (item.source is not None or item.raw_source is not None)
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
        source = record.source or record.raw_source
        if source is None:
            return False
        if (
            source.start_offset == source.end_offset
            and not self._source_is_traceable(source, document)
        ):
            return False
        if not self._source_is_traceable(source, document):
            return False
        if any(field_id not in valid_field_ids for field_id in record.evidence_field_ids):
            return False
        if record.record_type == "case_control":
            combined_text = f"{record.description} {source.text_snippet}"
            if "[REDACTED]" in combined_text:
                return False
        return True

    @staticmethod
    def _source_is_traceable(source: SourceLocation, document: TrackDocument) -> bool:
        if 0 <= source.block_index < len(document.blocks):
            block = document.blocks[source.block_index]
            block_text_parts = [*block.table_caption, *block.image_caption, *block.chart_caption]
            for value in (block.text, block.content, block.table_body):
                if value.strip():
                    block_text_parts.append(value.strip())
            if source.text_snippet in "\n".join(block_text_parts):
                return True
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
