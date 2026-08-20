"""Run frozen input bundles through the three content-controlled extraction arms."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Sequence

from pydantic import BaseModel

from .contracts import (
    ACMG_MULTILINGUAL_ARMS,
    ArmExtractionRun,
    ArmExtractionRunReport,
    ClinicalAssertion,
    ExperimentArm,
    ExperimentEntry,
    ExperimentManifest,
)
from .materialize import validate_materialized_input_bundle
from .scoring import fingerprint_manifest, load_manifest

if TYPE_CHECKING:
    from src.core.evidence_extraction.contracts import DualTrackDocuments


class DualTrackExtractionService(Protocol):
    """Minimum product facade needed by this benchmark runner."""

    async def run_dual(
        self,
        documents: DualTrackDocuments,
        *,
        extraction_track_mode: str,
        enable_translation_traceback: bool,
    ) -> BaseModel:
        """Run a fixed native/English document pair in one extraction-track mode."""


class DualTrackDocumentBuilder(Protocol):
    """Build the product's dual-document contract from one materialized bundle."""

    def __call__(self, input_dir: Path, assertion: ClinicalAssertion) -> DualTrackDocuments:
        """Return a product-owned dual-document instance."""


_TRACK_MODE_BY_ARM: dict[ExperimentArm, str] = {
    "english_pivot": "english_pivot",
    "native_only": "original_only",
    "dual_track": "dual",
}


async def run_ready_arms(
    manifest: ExperimentManifest,
    input_root: Path,
    output_root: Path,
    service: DualTrackExtractionService,
    document_builder: DualTrackDocumentBuilder,
) -> ArmExtractionRunReport:
    """Run all three arms without re-translating or changing the frozen inputs.

    The complete batch is staged below the requested output root's parent and
    published only after every case/arm result has succeeded. This prevents a
    partial batch from blocking a retry of the same explicit run command.
    """
    entries = _ready_entries_only(manifest)
    resolved_output_root = _prepare_batch_output_root(output_root)
    prepared_entries: list[tuple[ExperimentEntry, Path, str, DualTrackDocuments]] = []
    for entry in entries:
        if entry.index_assertion is None:
            raise ValueError(f"{entry.case_id}: ready entry has no index assertion")
        validate_materialized_input_bundle(entry, input_root)
        input_dir = _input_bundle_directory(input_root, entry.case_id)
        input_manifest_sha256 = _sha256_file(input_dir / "input_manifest.json")
        documents = document_builder(input_dir, entry.index_assertion)
        prepared_entries.append((entry, input_dir, input_manifest_sha256, documents))

    staging_output_root = _create_batch_staging_root(resolved_output_root)
    runs: list[ArmExtractionRun] = []
    for entry, input_dir, input_manifest_sha256, documents in prepared_entries:
        for arm in ACMG_MULTILINGUAL_ARMS:
            runs.append(
                await _run_one_arm(
                    case_id=entry.case_id,
                    arm=arm,
                    input_dir=input_dir,
                    input_manifest_sha256=input_manifest_sha256,
                    output_root=staging_output_root,
                    documents=documents,
                    service=service,
                )
            )
    final_runs = tuple(
        run.model_copy(
            update={
                "result_path": _arm_output_directory(
                    resolved_output_root,
                    run.case_id,
                    run.arm,
                )
                / "extraction_result.json",
            }
        )
        for run in runs
    )
    if resolved_output_root.exists() or resolved_output_root.is_symlink():
        raise FileExistsError(f"Refusing to overwrite arm output batch: {resolved_output_root}")
    staging_output_root.rename(resolved_output_root)
    return ArmExtractionRunReport(
        study_id=manifest.study_id,
        manifest_sha256=fingerprint_manifest(manifest),
        runs=final_runs,
    )


async def run_live_manifest(
    manifest_path: Path,
    input_root: Path,
    output_root: Path,
) -> ArmExtractionRunReport:
    """Build the configured product service and execute a frozen manifest explicitly."""
    manifest = load_manifest(manifest_path)
    service, document_builder = _build_live_dependencies()
    return await run_ready_arms(
        manifest=manifest,
        input_root=input_root,
        output_root=output_root,
        service=service,
        document_builder=document_builder,
    )


def write_arm_run_report(report: ArmExtractionRunReport, path: Path) -> None:
    """Write a stable receipt separate from the full extraction artifacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    _atomic_write_bytes(path, (payload + "\n").encode("utf-8"))


def load_arm_run_report(path: Path) -> ArmExtractionRunReport:
    """Load one schema-validated content-addressed arm-run receipt."""
    return ArmExtractionRunReport.model_validate_json(path.read_text(encoding="utf-8"))


async def _run_one_arm(
    *,
    case_id: str,
    arm: ExperimentArm,
    input_dir: Path,
    input_manifest_sha256: str,
    output_root: Path,
    documents: DualTrackDocuments,
    service: DualTrackExtractionService,
) -> ArmExtractionRun:
    """Run one arm and atomically publish its result only after success."""
    arm_output_dir = _arm_output_directory(output_root, case_id, arm)
    if arm_output_dir.exists() or arm_output_dir.is_symlink():
        raise FileExistsError(f"Refusing to overwrite arm result: {arm_output_dir}")
    started_at = time.perf_counter()
    result = await service.run_dual(
        documents,
        extraction_track_mode=_TRACK_MODE_BY_ARM[arm],
        enable_translation_traceback=arm != "english_pivot",
    )
    duration_seconds = round(time.perf_counter() - started_at, 6)
    arm_output_dir = _arm_output_directory(output_root, case_id, arm)
    if arm_output_dir.exists() or arm_output_dir.is_symlink():
        raise FileExistsError(f"Refusing to overwrite arm result: {arm_output_dir}")
    arm_output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{arm}.staging-", dir=arm_output_dir.parent))
    staged_result_path = staging_dir / "extraction_result.json"
    staged_result_path.write_bytes((result.model_dump_json(indent=2) + "\n").encode("utf-8"))
    result_sha256 = _sha256_file(staged_result_path)
    if arm_output_dir.exists() or arm_output_dir.is_symlink():
        raise FileExistsError(f"Refusing to overwrite arm result: {arm_output_dir}")
    staging_dir.rename(arm_output_dir)
    result_path = arm_output_dir / "extraction_result.json"
    return ArmExtractionRun(
        case_id=case_id,
        arm=arm,
        input_dir=input_dir,
        input_manifest_sha256=input_manifest_sha256,
        result_path=result_path,
        result_sha256=result_sha256,
        duration_seconds=duration_seconds,
    )


def _ready_entries_only(manifest: ExperimentManifest) -> tuple[ExperimentEntry, ...]:
    """Forbid a partial scientific run with candidate or unreviewed entries."""
    not_ready = tuple(entry.case_id for entry in manifest.entries if entry.status not in {"ready", "excluded"})
    if not_ready:
        raise ValueError(
            "Cannot run a partial manifest; entries need translation review first: " + ", ".join(not_ready)
        )
    entries = tuple(entry for entry in manifest.entries if entry.status == "ready")
    if not entries:
        raise ValueError("The manifest has no ready entries to run")
    return entries


def _input_bundle_directory(input_root: Path, case_id: str) -> Path:
    """Resolve a validated input bundle without following it outside its root."""
    resolved_input_root = input_root.resolve()
    input_dir = (resolved_input_root / case_id).resolve()
    if not input_dir.is_relative_to(resolved_input_root):
        raise ValueError(f"Input bundle escapes root: {case_id}")
    return input_dir


def _arm_output_directory(output_root: Path, case_id: str, arm: ExperimentArm) -> Path:
    """Return one direct arm-output child after a runtime path-boundary check."""
    if not isinstance(case_id, str):
        raise ValueError("case_id must be a safe output path component")
    case_path = Path(case_id)
    if (
        case_path.is_absolute()
        or len(case_path.parts) != 1
        or case_path.parts[0] in {".", ".."}
    ):
        raise ValueError(f"Arm output escapes root: {case_id}")
    if arm not in _TRACK_MODE_BY_ARM:
        raise ValueError(f"Unknown experiment arm: {arm}")
    resolved_output_root = output_root.resolve()
    case_output_dir = resolved_output_root / case_path
    if case_output_dir.parent != resolved_output_root:
        raise ValueError(f"Arm output escapes root: {case_id}")
    if case_output_dir.is_symlink():
        raise ValueError(f"Arm output case directory must not be a symlink: {case_id}")
    return case_output_dir / arm


def _prepare_batch_output_root(output_root: Path) -> Path:
    """Validate an unused batch target and create its parent if necessary."""
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"Refusing to overwrite arm output batch: {output_root}")
    resolved_output_root = output_root.resolve()
    resolved_output_root.parent.mkdir(parents=True, exist_ok=True)
    return resolved_output_root


def _create_batch_staging_root(resolved_output_root: Path) -> Path:
    """Create an invisible sibling staging root for one all-or-nothing batch."""
    staging_output_root = Path(
        tempfile.mkdtemp(
            prefix=f".{resolved_output_root.name}.staging-",
            dir=resolved_output_root.parent,
        )
    )
    return staging_output_root


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 of an artifact's exact persisted bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Atomically replace a receipt after writing complete JSON bytes to a sibling file."""
    descriptor, temporary_path_text = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_path_text)
    with os.fdopen(descriptor, "wb") as temporary_file:
        temporary_file.write(payload)
    temporary_path.replace(path)


def _build_live_dependencies() -> tuple[DualTrackExtractionService, DualTrackDocumentBuilder]:
    """Load product dependencies lazily so unit tests do not require model configuration."""
    from src.core.config import get_config
    from src.core.evidence_extraction.api import EvidenceExtractionService
    from src.core.evidence_extraction.contracts import ExtractionTarget

    get_config.cache_clear()
    service = EvidenceExtractionService(cfg=get_config())

    def build_documents(input_dir: Path, assertion: ClinicalAssertion) -> DualTrackDocuments:
        target = ExtractionTarget(
            gene_symbol=assertion.gene_symbol,
            disease_name=assertion.disease_label,
            variant_hgvs_c=assertion.variant_hgvs_c,
            variant_hgvs_p=assertion.variant_hgvs_p,
            clingen_entry_id=assertion.assertion_id,
        )
        return EvidenceExtractionService.build_dual_documents_from_output_dir(input_dir, target)

    return service, build_documents


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the explicit live-run command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the configured product only when this CLI is explicitly invoked."""
    args = _parse_args(argv)
    report = asyncio.run(
        run_live_manifest(
            manifest_path=args.manifest,
            input_root=args.input_root,
            output_root=args.output_root,
        )
    )
    write_arm_run_report(report, args.report)
    print(f"Completed {len(report.runs)} arm runs for {report.study_id}")


if __name__ == "__main__":
    main()
