"""Stage-0c: catalog field items visible in English vs native layers of one PDF.

This is not ACMG code recovery. A field_id counts as present when a frozen
span in that visibility layer supports it. English-visible includes author
English abstracts plus English figure/table captions in the same file.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .coverage import CoverageSpan, _resolve_source_path, _span_is_present

DEFAULT_FACTS_PATH = Path(__file__).with_name("evidence_item_coverage_facts.json")
_HASH_CHARS = frozenset("0123456789abcdef")
VisibilityLayer = Literal["english_abstract", "english_visible", "native_fulltext"]
IncrementKind = Literal["same_pdf_bilingual", "missing_english_pivot", "none"]

ALLOWED_FIELD_IDS = frozenset(
    {
        "A.gene_symbol",
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_type",
        "A.functional_domain_or_hotspot",
        "B.disease_diagnosis",
        "C.de_novo_status",
        "C.maternal_genotype",
        "C.paternal_genotype",
        "C.parentage_confirmed",
    }
)


class LayerField(BaseModel):
    """One catalog field supported by a verbatim span in a visibility layer."""

    model_config = ConfigDict(frozen=True)

    field_id: str = Field(min_length=1)
    span: CoverageSpan

    @model_validator(mode="after")
    def validate_field(self) -> LayerField:
        """Keep the increment ledger on the closed catalog subset."""
        if self.field_id not in ALLOWED_FIELD_IDS:
            raise ValueError(f"unsupported field_id: {self.field_id}")
        return self


class EvidenceItemSource(BaseModel):
    """One source family: English layers versus native full text."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    source_cluster_id: str = Field(min_length=1)
    native_language: str = Field(min_length=2, max_length=16)
    increment_kind: IncrementKind
    source_relative_path: str
    source_sha256: str = Field(min_length=64, max_length=64)
    english_abstract: tuple[LayerField, ...] = ()
    english_visible: tuple[LayerField, ...] = ()
    native_fulltext: tuple[LayerField, ...] = ()
    increment_over_abstract: tuple[str, ...] = ()
    increment_over_english_visible: tuple[str, ...] = ()
    notes: str = ""

    @model_validator(mode="after")
    def validate_source(self) -> EvidenceItemSource:
        """Reject path escape, hash typos, and increment set mismatches."""
        relative_path = Path(self.source_relative_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"{self.case_id}: source_relative_path must stay below its root")
        if any(character not in _HASH_CHARS for character in self.source_sha256):
            raise ValueError(f"{self.case_id}: source_sha256 must be a lowercase SHA-256 digest")
        abstract_ids = _unique_field_ids(self.english_abstract, case_id=self.case_id, layer="english_abstract")
        visible_ids = _unique_field_ids(self.english_visible, case_id=self.case_id, layer="english_visible")
        native_ids = _unique_field_ids(self.native_fulltext, case_id=self.case_id, layer="native_fulltext")
        if not abstract_ids.issubset(visible_ids):
            raise ValueError(f"{self.case_id}: english_visible must contain english_abstract")
        if not visible_ids.issubset(native_ids):
            raise ValueError(f"{self.case_id}: native_fulltext must contain english_visible")
        if set(self.increment_over_abstract) != native_ids - abstract_ids:
            raise ValueError(f"{self.case_id}: increment_over_abstract must equal native minus abstract")
        if set(self.increment_over_english_visible) != native_ids - visible_ids:
            raise ValueError(f"{self.case_id}: increment_over_english_visible must equal native minus visible")
        if self.increment_kind == "none" and self.increment_over_abstract:
            raise ValueError(f"{self.case_id}: increment_kind=none forbids abstract increment")
        return self


class EvidenceItemCoverageTable(BaseModel):
    """Frozen field-item increment table bound to reviewed source.md hashes."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    created_on: str
    scope_note: str
    sources: tuple[EvidenceItemSource, ...]

    @model_validator(mode="after")
    def validate_table(self) -> EvidenceItemCoverageTable:
        """Reject empty tables and duplicate case ids."""
        if not self.sources:
            raise ValueError("evidence item coverage table must contain at least one source")
        case_ids = [source.case_id for source in self.sources]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("case_id values must be unique")
        return self


class EvidenceItemSpanResult(BaseModel):
    """One span check against source.md."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    visibility: VisibilityLayer
    field_id: str
    line: int
    present: bool


class EvidenceItemVerificationReport(BaseModel):
    """Receipt for hash and quote checks."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    total_sources: int
    verified_sources: int
    total_spans: int
    verified_spans: int
    missed_spans: tuple[str, ...]
    spans: tuple[EvidenceItemSpanResult, ...]


@dataclass(frozen=True)
class EvidenceItemIncrementSummary:
    """Reviewer-facing counts; cluster, not event, is the bilingual unit."""

    total_sources: int
    languages: tuple[str, ...]
    sources_with_abstract_increment: int
    sources_with_visible_increment: int
    abstract_increment_without_rett_007: int
    same_pdf_bilingual_sources: int
    missing_english_pivot_sources: int


def _unique_field_ids(fields: Sequence[LayerField], *, case_id: str, layer: str) -> set[str]:
    """Reject duplicate catalog fields inside one visibility layer."""
    field_ids = [item.field_id for item in fields]
    unique_ids = set(field_ids)
    if len(field_ids) != len(unique_ids):
        raise ValueError(f"{case_id}: duplicate field_id in {layer}")
    return unique_ids


def load_evidence_item_coverage_table(path: Path | None = None) -> EvidenceItemCoverageTable:
    """Load the frozen field-item increment table."""
    payload = (path or DEFAULT_FACTS_PATH).read_text(encoding="utf-8")
    return EvidenceItemCoverageTable.model_validate_json(payload)


def summarize_evidence_item_coverage(table: EvidenceItemCoverageTable) -> EvidenceItemIncrementSummary:
    """Count source families with a native-minus-English field increment."""
    languages = tuple(sorted({source.native_language for source in table.sources}))
    abstract_hits = [source for source in table.sources if source.increment_over_abstract]
    return EvidenceItemIncrementSummary(
        total_sources=len(table.sources),
        languages=languages,
        sources_with_abstract_increment=len(abstract_hits),
        sources_with_visible_increment=sum(1 for source in table.sources if source.increment_over_english_visible),
        abstract_increment_without_rett_007=sum(
            1 for source in abstract_hits if source.source_cluster_id != "rett_007"
        ),
        same_pdf_bilingual_sources=sum(
            1 for source in table.sources if source.increment_kind == "same_pdf_bilingual"
        ),
        missing_english_pivot_sources=sum(
            1 for source in table.sources if source.increment_kind == "missing_english_pivot"
        ),
    )


def verify_evidence_item_coverage(
    table: EvidenceItemCoverageTable,
    reviewed_root: Path,
) -> EvidenceItemVerificationReport:
    """Check hashes and line-anchored quotes against reviewed source.md files."""
    span_results: list[EvidenceItemSpanResult] = []
    missed: list[str] = []
    verified_sources = 0
    for source in table.sources:
        source_path = _resolve_source_path(reviewed_root, Path(source.source_relative_path))
        raw = source_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        hash_ok = digest == source.source_sha256
        lines = raw.decode("utf-8").splitlines()
        layers: tuple[tuple[VisibilityLayer, tuple[LayerField, ...]], ...] = (
            ("english_abstract", source.english_abstract),
            ("english_visible", source.english_visible),
            ("native_fulltext", source.native_fulltext),
        )
        source_ok = hash_ok
        for visibility, fields in layers:
            for item in fields:
                present = _span_is_present(lines, item.span) if hash_ok else False
                if not present:
                    source_ok = False
                    missed.append(f"{source.case_id}:{visibility}:{item.field_id}:{item.span.line}")
                span_results.append(
                    EvidenceItemSpanResult(
                        case_id=source.case_id,
                        visibility=visibility,
                        field_id=item.field_id,
                        line=item.span.line,
                        present=present,
                    )
                )
        if source_ok:
            verified_sources += 1
    return EvidenceItemVerificationReport(
        study_id=table.study_id,
        total_sources=len(table.sources),
        verified_sources=verified_sources,
        total_spans=len(span_results),
        verified_spans=sum(item.present for item in span_results),
        missed_spans=tuple(missed),
        spans=tuple(span_results),
    )


def write_evidence_item_verification_report(report: EvidenceItemVerificationReport, path: Path) -> None:
    """Write the verification receipt as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")
