"""Translation-fidelity verification for the English pivot arm.

If the English full text silently drops a critical fact, a ``native_only``
advantage over ``english_pivot`` measures translation loss rather than native
language capability. This module makes that distinction checkable without a
model: each critical fact names a verbatim native span and the English tokens
that must survive, and the verifier reports retention at both document level and
aligned-chunk level.

Read-only and deterministic. Whitespace is collapsed on both sides so LaTeX-style
spacing in OCR output (``c . 7 1 0 C > G``) still matches a clean English token.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TranslationReviewProvenance = Literal["model_reviewed", "human_reviewed"]

_HASH_CHARS = frozenset("0123456789abcdef")
_WHITESPACE = re.compile(r"\s+")


def _collapse_whitespace(text: str) -> str:
    """Remove every whitespace character so quotes match despite OCR spacing."""
    return _WHITESPACE.sub("", text)


def _validate_relative_path(relative_path: str, *, field_name: str) -> None:
    """Reject absolute or traversing paths before any file is opened."""
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must stay below the reviewed-artifact root")


def _validate_sha256(digest: str, *, field_name: str) -> None:
    """Reject a malformed content hash."""
    if any(character not in _HASH_CHARS for character in digest):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


class CriticalFact(BaseModel):
    """One native evidence span and the English tokens that must survive it."""

    model_config = ConfigDict(frozen=True)

    fact_id: str = Field(min_length=1)
    native_line: int = Field(ge=1)
    native_quote: str = Field(min_length=1)
    required_english_tokens: tuple[str, ...]

    @model_validator(mode="after")
    def validate_fact(self) -> CriticalFact:
        """Require at least one non-blank English token to check retention against."""
        if not self.required_english_tokens:
            raise ValueError("a critical fact needs at least one required English token")
        if any(not token.strip() for token in self.required_english_tokens):
            raise ValueError("required_english_tokens must not contain blank tokens")
        return self


class TranslationFidelityEntry(BaseModel):
    """The three content-addressed artifacts and critical facts for one case."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    native_relative_path: str = Field(min_length=1)
    native_sha256: str = Field(min_length=64, max_length=64)
    english_relative_path: str = Field(min_length=1)
    english_sha256: str = Field(min_length=64, max_length=64)
    alignment_relative_path: str = Field(min_length=1)
    alignment_sha256: str = Field(min_length=64, max_length=64)
    facts: tuple[CriticalFact, ...]

    @model_validator(mode="after")
    def validate_entry(self) -> TranslationFidelityEntry:
        """Reject unsafe paths, malformed hashes, and duplicate fact identifiers."""
        _validate_relative_path(self.native_relative_path, field_name="native_relative_path")
        _validate_relative_path(self.english_relative_path, field_name="english_relative_path")
        _validate_relative_path(self.alignment_relative_path, field_name="alignment_relative_path")
        _validate_sha256(self.native_sha256, field_name="native_sha256")
        _validate_sha256(self.english_sha256, field_name="english_sha256")
        _validate_sha256(self.alignment_sha256, field_name="alignment_sha256")
        if not self.facts:
            raise ValueError("an entry needs at least one critical fact")
        fact_ids = [fact.fact_id for fact in self.facts]
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("fact_id must be unique within an entry")
        return self


class TranslationFidelityFactTable(BaseModel):
    """Frozen fidelity expectations for the reviewed English full texts."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    created_on: str = Field(min_length=1)
    translation_review_status: TranslationReviewProvenance
    provenance: str = Field(min_length=1)
    scope_note: str = Field(min_length=1)
    entries: tuple[TranslationFidelityEntry, ...]

    @model_validator(mode="after")
    def validate_table(self) -> TranslationFidelityFactTable:
        """Reject duplicate case identifiers before verification."""
        case_ids = [entry.case_id for entry in self.entries]
        if not case_ids:
            raise ValueError("the fact table needs at least one entry")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("case_id must be unique within the fact table")
        return self


class AlignmentChunk(BaseModel):
    """One native/English chunk pair from a reviewed alignment file."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(min_length=1)
    original_text: str
    english_text: str


class CriticalFactVerification(BaseModel):
    """Retention result for one critical fact."""

    model_config = ConfigDict(frozen=True)

    fact_id: str
    native_quote_present: bool
    retained_in_document: bool
    retained_in_aligned_chunk: bool
    missing_english_tokens: tuple[str, ...]


class TranslationFidelityEntryVerification(BaseModel):
    """Artifact integrity, alignment shape, and fact retention for one case."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    native_sha256_match: bool
    english_sha256_match: bool
    alignment_sha256_match: bool
    alignment_chunk_count: int = Field(ge=0)
    chunks_verbatim_in_native: int = Field(ge=0)
    native_coverage_ratio: float = Field(ge=0.0)
    facts: tuple[CriticalFactVerification, ...]


class TranslationFidelityReport(BaseModel):
    """Deterministic receipt for a translation-fidelity audit."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    translation_review_status: TranslationReviewProvenance
    total_entries: int = Field(ge=0)
    total_facts: int = Field(ge=0)
    retained_fact_count: int = Field(ge=0)
    lost_fact_ids: tuple[str, ...]
    unverified_native_quote_ids: tuple[str, ...]
    drifted_artifacts: tuple[str, ...]
    entries: tuple[TranslationFidelityEntryVerification, ...]


def load_translation_fidelity_fact_table(path: Path) -> TranslationFidelityFactTable:
    """Load the frozen translation-fidelity fact table from JSON."""
    return TranslationFidelityFactTable.model_validate_json(path.read_text(encoding="utf-8"))


def write_translation_fidelity_report(report: TranslationFidelityReport, path: Path) -> None:
    """Persist a deterministic receipt for the fidelity audit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")


def verify_translation_fidelity(
    table: TranslationFidelityFactTable,
    reviewed_root: Path,
) -> TranslationFidelityReport:
    """Verify artifact hashes and whether every critical fact survives translation."""
    entries: list[TranslationFidelityEntryVerification] = []
    drifted_artifacts: list[str] = []
    lost_fact_ids: list[str] = []
    unverified_native_quote_ids: list[str] = []

    for entry in table.entries:
        native_bytes = _read_artifact(reviewed_root, entry.native_relative_path)
        english_bytes = _read_artifact(reviewed_root, entry.english_relative_path)
        alignment_bytes = _read_artifact(reviewed_root, entry.alignment_relative_path)

        native_match = hashlib.sha256(native_bytes).hexdigest() == entry.native_sha256
        english_match = hashlib.sha256(english_bytes).hexdigest() == entry.english_sha256
        alignment_match = hashlib.sha256(alignment_bytes).hexdigest() == entry.alignment_sha256
        for matched, artifact in (
            (native_match, entry.native_relative_path),
            (english_match, entry.english_relative_path),
            (alignment_match, entry.alignment_relative_path),
        ):
            if not matched:
                drifted_artifacts.append(f"{entry.case_id}:{artifact}")

        native_lines = native_bytes.decode("utf-8").splitlines()
        collapsed_native = _collapse_whitespace(native_bytes.decode("utf-8"))
        collapsed_english = _collapse_whitespace(english_bytes.decode("utf-8"))
        chunks = _load_alignment_chunks(alignment_bytes)

        fact_verifications: list[CriticalFactVerification] = []
        for fact in entry.facts:
            verification = _verify_fact(
                fact,
                native_lines=native_lines,
                collapsed_english=collapsed_english,
                chunks=chunks,
            )
            if not verification.retained_in_document:
                lost_fact_ids.append(f"{entry.case_id}:{fact.fact_id}")
            if not verification.native_quote_present:
                unverified_native_quote_ids.append(f"{entry.case_id}:{fact.fact_id}")
            fact_verifications.append(verification)

        covered = sum(len(_collapse_whitespace(chunk.original_text)) for chunk in chunks)
        entries.append(
            TranslationFidelityEntryVerification(
                case_id=entry.case_id,
                native_sha256_match=native_match,
                english_sha256_match=english_match,
                alignment_sha256_match=alignment_match,
                alignment_chunk_count=len(chunks),
                chunks_verbatim_in_native=sum(
                    1
                    for chunk in chunks
                    if _collapse_whitespace(chunk.original_text) in collapsed_native
                ),
                native_coverage_ratio=_ratio(covered, len(collapsed_native)),
                facts=tuple(fact_verifications),
            )
        )

    total_facts = sum(len(entry.facts) for entry in table.entries)
    retained_fact_count = sum(
        1
        for verification in entries
        for fact in verification.facts
        if fact.retained_in_document
    )
    return TranslationFidelityReport(
        study_id=table.study_id,
        translation_review_status=table.translation_review_status,
        total_entries=len(table.entries),
        total_facts=total_facts,
        retained_fact_count=retained_fact_count,
        lost_fact_ids=tuple(lost_fact_ids),
        unverified_native_quote_ids=tuple(unverified_native_quote_ids),
        drifted_artifacts=tuple(drifted_artifacts),
        entries=tuple(entries),
    )


def _verify_fact(
    fact: CriticalFact,
    *,
    native_lines: list[str],
    collapsed_english: str,
    chunks: tuple[AlignmentChunk, ...],
) -> CriticalFactVerification:
    """Check the native span, document-level retention, and chunk-level retention."""
    collapsed_quote = _collapse_whitespace(fact.native_quote)
    native_quote_present = (
        1 <= fact.native_line <= len(native_lines)
        and collapsed_quote in _collapse_whitespace(native_lines[fact.native_line - 1])
    )
    missing = tuple(
        token
        for token in fact.required_english_tokens
        if _collapse_whitespace(token) not in collapsed_english
    )
    carrying_chunks = [
        chunk for chunk in chunks if collapsed_quote in _collapse_whitespace(chunk.original_text)
    ]
    retained_in_aligned_chunk = bool(carrying_chunks) and any(
        all(
            _collapse_whitespace(token) in _collapse_whitespace(chunk.english_text)
            for token in fact.required_english_tokens
        )
        for chunk in carrying_chunks
    )
    return CriticalFactVerification(
        fact_id=fact.fact_id,
        native_quote_present=native_quote_present,
        retained_in_document=not missing,
        retained_in_aligned_chunk=retained_in_aligned_chunk,
        missing_english_tokens=missing,
    )


def _load_alignment_chunks(alignment_bytes: bytes) -> tuple[AlignmentChunk, ...]:
    """Parse the reviewed alignment file into typed native/English chunk pairs."""
    payload = json.loads(alignment_bytes.decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("an alignment file must be a JSON list of chunk objects")
    return tuple(AlignmentChunk.model_validate(chunk) for chunk in payload)


def _read_artifact(reviewed_root: Path, relative_path: str) -> bytes:
    """Read one reviewed artifact after re-checking its path stays in the root."""
    _validate_relative_path(relative_path, field_name="relative_path")
    return (reviewed_root / relative_path).read_bytes()


def _ratio(numerator: int, denominator: int) -> float:
    """Return a ratio, treating an empty denominator as zero."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)
