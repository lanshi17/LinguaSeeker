"""Stage-0 source-coverage verification for the ACMG multilingual study.

Read-only: verifies the frozen human-adjudicated PM6-eligible fact table against
an external corpus, without contacting a model. It proves that every positive
observation's cited span exists verbatim in a content-addressed source document;
an "absent" (zero-count) visibility is a clinical review conclusion recorded in
the fact table, not a hash-verifiable span.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CoverageVisibility = Literal["english_abstract", "native_fulltext"]

_HASH_CHARS = frozenset("0123456789abcdef")
_WHITESPACE = re.compile(r"\s+")


def _collapse_whitespace(text: str) -> str:
    """Remove every whitespace character so quotes match source despite spacing."""
    return _WHITESPACE.sub("", text)


class CoverageSpan(BaseModel):
    """One verbatim, line-anchored citation substantiating a positive observation."""

    model_config = ConfigDict(frozen=True)

    line: int = Field(ge=1)
    quote: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=16)


class VisibilityFacts(BaseModel):
    """The adjudicated PM6-eligible observation count for one document visibility."""

    model_config = ConfigDict(frozen=True)

    visibility: CoverageVisibility
    pm6_eligible_count: int = Field(ge=0)
    spans: tuple[CoverageSpan, ...] = ()
    notes: str = ""


class SourceCoverageEntry(BaseModel):
    """One deduplicated source family and its abstract/full-text visibility counts."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    canonical_source: str
    doi: str
    native_language: str = Field(min_length=2, max_length=16)
    source_relative_path: str
    source_sha256: str = Field(min_length=64, max_length=64)
    abstract: VisibilityFacts
    fulltext: VisibilityFacts
    fulltext_increment: int

    @model_validator(mode="after")
    def validate_entry(self) -> SourceCoverageEntry:
        """Reject unsafe paths, malformed hashes, and inconsistent visibility fields."""
        relative_path = Path(self.source_relative_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("source_relative_path must stay below the source root")
        if any(character not in _HASH_CHARS for character in self.source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
        if self.abstract.visibility != "english_abstract":
            raise ValueError("abstract visibility must be english_abstract")
        if self.fulltext.visibility != "native_fulltext":
            raise ValueError("fulltext visibility must be native_fulltext")
        if self.fulltext.pm6_eligible_count - self.abstract.pm6_eligible_count != self.fulltext_increment:
            raise ValueError("fulltext_increment must equal fulltext minus abstract count")
        return self


class SourceCoverageFactTable(BaseModel):
    """Frozen Stage-0 fact table bound to one corpus revision."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    corpus_revision: str = Field(min_length=40, max_length=40)
    created_on: str
    criterion_family: Literal["PS2_PM6"]
    reviewer_id: str
    provenance: str
    review_scope_note: str
    sources: tuple[SourceCoverageEntry, ...]

    @model_validator(mode="after")
    def validate_table(self) -> SourceCoverageFactTable:
        """Reject duplicate case IDs before verification."""
        case_ids = [entry.case_id for entry in self.sources]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case_id must be unique within the fact table")
        return self


class CoverageSpanVerification(BaseModel):
    """Verification result for one cited span."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    visibility: CoverageVisibility
    line: int
    present: bool


class SourceCoverageVerification(BaseModel):
    """Verification result for one source family."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    source_sha256_match: bool
    spans: tuple[CoverageSpanVerification, ...]


class CoverageVerificationReport(BaseModel):
    """Deterministic receipt for a source-coverage integrity audit."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    corpus_revision: str
    total_sources: int
    total_positive_spans: int
    verified_spans: int
    drifted_sources: tuple[str, ...]
    missed_spans: tuple[str, ...]
    sources: tuple[SourceCoverageVerification, ...]


def load_source_coverage_fact_table(path: Path) -> SourceCoverageFactTable:
    """Load the frozen Stage-0 fact table from JSON."""
    return SourceCoverageFactTable.model_validate_json(path.read_text(encoding="utf-8"))


def verify_source_coverage(
    table: SourceCoverageFactTable,
    source_root: Path,
) -> CoverageVerificationReport:
    """Verify every source hash and every positive span against the corpus."""
    source_verifications: list[SourceCoverageVerification] = []
    drifted_sources: list[str] = []
    missed_spans: list[str] = []

    for entry in table.sources:
        source_path = _resolve_source_path(source_root, Path(entry.source_relative_path))
        raw = source_path.read_bytes()
        sha256_match = hashlib.sha256(raw).hexdigest() == entry.source_sha256
        if not sha256_match:
            drifted_sources.append(entry.case_id)

        lines = raw.decode("utf-8").splitlines()
        span_verifications: list[CoverageSpanVerification] = []
        for visibility_facts in (entry.abstract, entry.fulltext):
            for span in visibility_facts.spans:
                present = _span_is_present(lines, span)
                if not present:
                    missed_spans.append(f"{entry.case_id}:{span.line}")
                span_verifications.append(
                    CoverageSpanVerification(
                        case_id=entry.case_id,
                        visibility=visibility_facts.visibility,
                        line=span.line,
                        present=present,
                    )
                )
        source_verifications.append(
            SourceCoverageVerification(
                case_id=entry.case_id,
                source_sha256_match=sha256_match,
                spans=tuple(span_verifications),
            )
        )

    total_positive_spans = sum(len(s.spans) for s in source_verifications)
    verified_spans = sum(1 for s in source_verifications for span in s.spans if span.present)
    return CoverageVerificationReport(
        study_id=table.study_id,
        corpus_revision=table.corpus_revision,
        total_sources=len(table.sources),
        total_positive_spans=total_positive_spans,
        verified_spans=verified_spans,
        drifted_sources=tuple(drifted_sources),
        missed_spans=tuple(missed_spans),
        sources=tuple(source_verifications),
    )


def write_coverage_verification_report(report: CoverageVerificationReport, path: Path) -> None:
    """Persist a deterministic receipt for the coverage audit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")


def _resolve_source_path(source_root: Path, relative_path: Path) -> Path:
    """Resolve a manifest path while preventing escape from the source root."""
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"source path escapes the source root: {relative_path}")
    return source_root / relative_path


def _span_is_present(lines: list[str], span: CoverageSpan) -> bool:
    """Return whether the collapsed quote is a substring of the cited line."""
    if span.line < 1 or span.line > len(lines):
        return False
    line_text = _collapse_whitespace(lines[span.line - 1])
    quote_text = _collapse_whitespace(span.quote)
    return quote_text in line_text
