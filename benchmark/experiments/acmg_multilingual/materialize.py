"""Freeze reviewed native/English source pairs into Phase-2 input bundles."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, TypedDict

from .contracts import (
    REVIEWED_TRANSLATION_STATUSES,
    ExperimentEntry,
    ExperimentManifest,
    MaterializationReport,
    MaterializedInput,
    NativeSourceVerification,
    NativeSourceVerificationReport,
    SourceArtifact,
)
from .scoring import fingerprint_manifest


@dataclass(frozen=True)
class VerifiedSource:
    """A source file whose content matches the hash frozen in the manifest."""

    path: Path
    text: str
    sha256: str


@dataclass(frozen=True)
class PreparedMaterializedInput:
    """Verified source pair and alignment held in memory before output is written."""

    entry: ExperimentEntry
    native: VerifiedSource
    english: VerifiedSource
    alignment_raw: bytes
    alignment: list[object]


class PersistedTrackMetadata(TypedDict):
    """Metadata persisted beside one source-language track."""

    doc_id: str
    source_language: str
    content_sha256: str
    translation_alignment: list[object]


class PersistedTrackPayload(TypedDict):
    """Minimal JSON shape consumed by EvidenceExtractionService's loader."""

    metadata: PersistedTrackMetadata
    formatted_text: str
    blocks: list[object]


def materialize_reviewed_inputs(
    manifest: ExperimentManifest,
    source_root: Path,
    output_root: Path,
) -> MaterializationReport:
    """Write one immutable original/translated JSON pair per ready entry.

    The caller supplies a source root so that the manifest remains portable and
    never commits locally downloaded medical literature. Existing case output is
    rejected instead of silently being overwritten.
    """
    blockers = tuple(entry.case_id for entry in manifest.entries if entry.status not in {"ready", "excluded"})
    if blockers:
        raise ValueError("Cannot materialize a partial manifest: " + ", ".join(blockers))
    ready_entries = tuple(entry for entry in manifest.entries if entry.status == "ready")
    if not ready_entries:
        raise ValueError("The manifest has no ready entries to materialize")
    resolved_source_root = source_root.resolve()
    prepared_inputs = tuple(_prepare_materialized_input(entry, resolved_source_root) for entry in ready_entries)
    resolved_output_root = output_root.resolve()
    existing_case_ids = tuple(
        prepared.entry.case_id
        for prepared in prepared_inputs
        if _output_case_directory(resolved_output_root, prepared.entry.case_id).exists()
        or _output_case_directory(resolved_output_root, prepared.entry.case_id).is_symlink()
    )
    if existing_case_ids:
        raise FileExistsError("Refusing to overwrite materialized input: " + ", ".join(existing_case_ids))
    report_inputs: list[MaterializedInput] = []
    for prepared in prepared_inputs:
        report_inputs.append(_write_materialized_input(prepared=prepared, output_root=resolved_output_root))
    return MaterializationReport(
        study_id=manifest.study_id,
        manifest_sha256=fingerprint_manifest(manifest),
        inputs=tuple(report_inputs),
    )


def verify_native_source_artifacts(
    manifest: ExperimentManifest,
    source_root: Path,
    source_revision: str = "",
) -> NativeSourceVerificationReport:
    """Verify every native source, including entries blocked on translation review.

    This read-only audit intentionally runs before the full three-arm readiness
    gate. It establishes that a candidate manifest still identifies the exact
    local non-English documents without treating them as eligible experiment
    inputs.
    """
    resolved_source_root = source_root.resolve()
    verified_sources = tuple(
        _verify_native_source(entry, resolved_source_root)
        for entry in manifest.entries
    )
    return NativeSourceVerificationReport(
        study_id=manifest.study_id,
        manifest_sha256=fingerprint_manifest(manifest),
        source_root=resolved_source_root,
        source_revision=source_revision,
        verified_sources=verified_sources,
    )


def write_native_source_verification_report(report: NativeSourceVerificationReport, path: Path) -> None:
    """Persist a deterministic receipt for a source-only integrity audit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(payload + "\n", encoding="utf-8")


def write_materialization_report(report: MaterializationReport, path: Path) -> None:
    """Persist a deterministic materialization receipt for reproducibility."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(payload + "\n", encoding="utf-8")


def _verify_native_source(entry: ExperimentEntry, source_root: Path) -> NativeSourceVerification:
    """Read one native artifact and return its manifest-bound audit receipt."""
    verified_source = _read_verified_source(source_root, entry.native_fulltext)
    return NativeSourceVerification(
        case_id=entry.case_id,
        relative_path=entry.native_fulltext.relative_path,
        sha256=verified_source.sha256,
        language=entry.native_fulltext.language,
    )


def _prepare_materialized_input(entry: ExperimentEntry, source_root: Path) -> PreparedMaterializedInput:
    """Read all immutable source artifacts before creating any experiment output."""
    review = entry.translation_review
    if review.status not in REVIEWED_TRANSLATION_STATUSES or review.english_fulltext is None:
        raise ValueError(f"{entry.case_id}: entry is not ready for materialization")
    if review.alignment_relative_path is None or review.alignment_sha256 is None:
        raise ValueError(f"{entry.case_id}: reviewed translation has no alignment artifact")
    native = _read_verified_source(source_root, entry.native_fulltext)
    english = _read_verified_source(source_root, review.english_fulltext)
    alignment_path = _resolve_relative_path(source_root, review.alignment_relative_path)
    alignment_raw = alignment_path.read_bytes()
    alignment_sha256 = hashlib.sha256(alignment_raw).hexdigest()
    if alignment_sha256 != review.alignment_sha256:
        raise ValueError(f"{entry.case_id}: alignment SHA-256 does not match the manifest")
    alignment = _load_alignment(alignment_path)
    _validate_alignment_texts(
        entry.case_id,
        alignment,
        native_text=native.text,
        english_text=english.text,
    )
    return PreparedMaterializedInput(
        entry=entry,
        native=native,
        english=english,
        alignment_raw=alignment_raw,
        alignment=alignment,
    )


def _write_materialized_input(
    *,
    prepared: PreparedMaterializedInput,
    output_root: Path,
) -> MaterializedInput:
    """Atomically publish one previously verified native/English pair."""
    entry = prepared.entry
    native = prepared.native
    english = prepared.english
    review = entry.translation_review
    if review.alignment_sha256 is None:
        raise ValueError(f"{entry.case_id}: reviewed translation has no alignment SHA-256")

    case_dir = _output_case_directory(output_root, entry.case_id)
    if case_dir.exists() or case_dir.is_symlink():
        raise FileExistsError(f"Refusing to overwrite materialized input: {entry.case_id}")
    case_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{case_dir.name}.staging-", dir=case_dir.parent))
    _write_json(
        staging_dir / "original.json",
        _track_payload(
            document_id=entry.case_id,
            formatted_text=native.text,
            source_language=entry.native_fulltext.language,
            content_sha256=native.sha256,
            alignment=prepared.alignment,
        ),
    )
    _write_json(
        staging_dir / "translated.json",
        _track_payload(
            document_id=entry.case_id,
            formatted_text=english.text,
            source_language="en",
            content_sha256=english.sha256,
            alignment=prepared.alignment,
        ),
    )
    _write_json(
        staging_dir / "input_manifest.json",
        {
            "case_id": entry.case_id,
            "source_family_id": entry.source_family_id,
            "family_cluster_id": entry.family_cluster_id,
            "assertion": entry.index_assertion.model_dump(mode="json") if entry.index_assertion else None,
            "native_sha256": native.sha256,
            "english_sha256": english.sha256,
            "alignment_sha256": review.alignment_sha256,
            "alignment_path": "translation_alignment.json",
        },
    )
    (staging_dir / "translation_alignment.json").write_bytes(prepared.alignment_raw)
    if case_dir.exists() or case_dir.is_symlink():
        raise FileExistsError(f"Refusing to overwrite materialized input: {entry.case_id}")
    staging_dir.rename(case_dir)
    return MaterializedInput(
        case_id=entry.case_id,
        input_dir=case_dir,
        native_sha256=native.sha256,
        english_sha256=english.sha256,
        alignment_sha256=review.alignment_sha256,
    )


def validate_materialized_input_bundle(entry: ExperimentEntry, input_root: Path) -> None:
    """Reject a changed bundle before an arm can consume its frozen inputs."""
    review = entry.translation_review
    if review.status not in REVIEWED_TRANSLATION_STATUSES or review.english_fulltext is None:
        raise ValueError(f"{entry.case_id}: entry is not ready for input validation")
    if review.alignment_sha256 is None:
        raise ValueError(f"{entry.case_id}: reviewed translation has no alignment SHA-256")
    input_dir = _resolve_input_directory(input_root, entry.case_id)
    original = _load_json_object(input_dir / "original.json")
    translated = _load_json_object(input_dir / "translated.json")
    input_manifest = _load_json_object(input_dir / "input_manifest.json")
    alignment_path = input_dir / "translation_alignment.json"
    if not alignment_path.is_file():
        raise FileNotFoundError(alignment_path)
    alignment_raw = alignment_path.read_bytes()
    if hashlib.sha256(alignment_raw).hexdigest() != review.alignment_sha256:
        raise ValueError(f"{entry.case_id}: materialized alignment SHA-256 does not match the manifest")
    alignment = _load_alignment(alignment_path)
    _validate_persisted_track(
        payload=original,
        case_id=entry.case_id,
        expected_source=entry.native_fulltext,
        expected_language=entry.native_fulltext.language,
        alignment=alignment,
    )
    _validate_persisted_track(
        payload=translated,
        case_id=entry.case_id,
        expected_source=review.english_fulltext,
        expected_language="en",
        alignment=alignment,
    )
    expected_assertion = entry.index_assertion.model_dump(mode="json") if entry.index_assertion else None
    expected_manifest_values: Mapping[str, object] = {
        "case_id": entry.case_id,
        "source_family_id": entry.source_family_id,
        "family_cluster_id": entry.family_cluster_id,
        "assertion": expected_assertion,
        "native_sha256": entry.native_fulltext.sha256,
        "english_sha256": review.english_fulltext.sha256,
        "alignment_sha256": review.alignment_sha256,
        "alignment_path": "translation_alignment.json",
    }
    for key, expected_value in expected_manifest_values.items():
        if input_manifest.get(key) != expected_value:
            raise ValueError(f"{entry.case_id}: materialized input manifest value drifted for {key}")


def _resolve_input_directory(input_root: Path, case_id: str) -> Path:
    """Resolve one safe case bundle without following it outside the input root."""
    resolved_root = input_root.resolve()
    input_dir = (resolved_root / case_id).resolve()
    if not input_dir.is_relative_to(resolved_root):
        raise ValueError(f"Input bundle escapes root: {case_id}")
    if not input_dir.is_dir():
        raise FileNotFoundError(input_dir)
    return input_dir


def _output_case_directory(output_root: Path, case_id: str) -> Path:
    """Resolve a direct output child even if a caller bypassed Pydantic validation."""
    if not isinstance(case_id, str):
        raise ValueError("case_id must be a safe output path component")
    relative_case_path = Path(case_id)
    if (
        relative_case_path.is_absolute()
        or len(relative_case_path.parts) != 1
        or relative_case_path.parts[0] in {".", ".."}
    ):
        raise ValueError(f"Output case directory escapes root: {case_id}")
    resolved_output_root = output_root.resolve()
    case_dir = resolved_output_root / relative_case_path
    if case_dir.parent != resolved_output_root:
        raise ValueError(f"Output case directory escapes root: {case_id}")
    return case_dir


def _load_json_object(path: Path) -> Mapping[str, object]:
    """Load a JSON object rather than accepting a malformed persisted artifact."""
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return parsed


def _validate_persisted_track(
    *,
    payload: Mapping[str, object],
    case_id: str,
    expected_source: SourceArtifact,
    expected_language: str,
    alignment: list[object],
) -> None:
    """Verify a persisted document retains its source text and closed alignment."""
    text = payload.get("formatted_text")
    if not isinstance(text, str):
        raise ValueError(f"{case_id}: materialized track has no formatted_text")
    actual_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual_sha256 != expected_source.sha256:
        raise ValueError(f"{case_id}: materialized track content SHA-256 does not match the manifest")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"{case_id}: materialized track has no metadata object")
    if metadata.get("doc_id") != case_id:
        raise ValueError(f"{case_id}: materialized track doc_id drifted")
    if metadata.get("source_language") != expected_language:
        raise ValueError(f"{case_id}: materialized track source language drifted")
    if metadata.get("content_sha256") != expected_source.sha256:
        raise ValueError(f"{case_id}: materialized track metadata hash drifted")
    if metadata.get("translation_alignment") != alignment:
        raise ValueError(f"{case_id}: materialized track alignment drifted")
    if payload.get("blocks") != []:
        raise ValueError(f"{case_id}: materialized track blocks must remain empty")


def _read_verified_source(source_root: Path, artifact: SourceArtifact) -> VerifiedSource:
    """Read one frozen source artifact and verify its digest before use."""
    path = _resolve_relative_path(source_root, artifact.relative_path)
    raw = path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != artifact.sha256:
        raise ValueError(f"Content SHA-256 does not match manifest for {artifact.relative_path}")
    return VerifiedSource(path=path, text=raw.decode("utf-8"), sha256=actual_sha256)


def _resolve_relative_path(source_root: Path, relative_path: Path) -> Path:
    """Resolve a manifest path while preventing escape from the source root."""
    path = (source_root / relative_path).resolve()
    if not path.is_relative_to(source_root):
        raise ValueError(f"Path escapes source root: {relative_path}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _load_alignment(path: Path) -> list[object]:
    """Load the reviewed source-to-English alignment consumed by Phase 2."""
    from src.core.cross_lingual_translation.contracts import TranslationAlignmentChunk

    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError(f"Translation alignment must be a JSON list: {path}")
    if not parsed:
        raise ValueError(f"Translation alignment must contain at least one reviewed chunk: {path}")
    validated_alignment: list[object] = []
    for index, raw_chunk in enumerate(parsed):
        if not isinstance(raw_chunk, dict):
            raise ValueError(f"Translation alignment chunk {index} must be a JSON object: {path}")
        try:
            chunk = TranslationAlignmentChunk.model_validate(raw_chunk)
        except ValueError as error:
            raise ValueError(f"Invalid translation alignment chunk {index}: {path}") from error
        if not chunk.original_text.strip() or not chunk.english_text.strip():
            raise ValueError(f"Translation alignment chunk {index} must contain both source-language and English text")
        validated_alignment.append(chunk.model_dump(mode="json"))
    return validated_alignment


def _validate_alignment_texts(
    case_id: str,
    alignment: list[object],
    *,
    native_text: str,
    english_text: str,
) -> None:
    """Ensure each reviewed alignment excerpt is traceable to both frozen texts."""
    for index, raw_chunk in enumerate(alignment):
        if not isinstance(raw_chunk, dict):
            raise ValueError(f"{case_id}: alignment chunk {index} is not an object")
        _validate_alignment_excerpt(
            case_id=case_id,
            index=index,
            full_text=native_text,
            excerpt=raw_chunk["original_text"],
            start_offset=raw_chunk["original_start_offset"],
            end_offset=raw_chunk["original_end_offset"],
            language_label="native",
        )
        _validate_alignment_excerpt(
            case_id=case_id,
            index=index,
            full_text=english_text,
            excerpt=raw_chunk["english_text"],
            start_offset=raw_chunk["english_start_offset"],
            end_offset=raw_chunk["english_end_offset"],
            language_label="English",
        )


def _validate_alignment_excerpt(
    *,
    case_id: str,
    index: int,
    full_text: str,
    excerpt: object,
    start_offset: object,
    end_offset: object,
    language_label: str,
) -> None:
    """Verify one alignment excerpt and its optional offsets against a frozen text."""
    if not isinstance(excerpt, str) or not isinstance(start_offset, int) or not isinstance(end_offset, int):
        raise ValueError(f"{case_id}: alignment chunk {index} has invalid {language_label} fields")
    if start_offset >= 0 or end_offset >= 0:
        if start_offset < 0 or end_offset < start_offset or end_offset > len(full_text):
            raise ValueError(f"{case_id}: alignment chunk {index} has invalid {language_label} offsets")
        if full_text[start_offset:end_offset] != excerpt:
            raise ValueError(f"{case_id}: alignment chunk {index} {language_label} text does not match its offsets")
    elif excerpt not in full_text:
        raise ValueError(f"{case_id}: alignment chunk {index} {language_label} text is absent from the frozen text")


def _track_payload(
    *,
    document_id: str,
    formatted_text: str,
    source_language: str,
    content_sha256: str,
    alignment: list[object],
) -> PersistedTrackPayload:
    """Build the persisted shape understood by EvidenceExtractionService."""
    return {
        "metadata": {
            "doc_id": document_id,
            "source_language": source_language,
            "content_sha256": content_sha256,
            "translation_alignment": alignment,
        },
        "formatted_text": formatted_text,
        "blocks": [],
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write an internal JSON persistence payload with a stable representation."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
