"""Readiness gate for a frozen three-arm multilingual experiment manifest."""

from __future__ import annotations

from .contracts import ExperimentManifest, ManifestReadinessReport


def assess_manifest_readiness(manifest: ExperimentManifest) -> ManifestReadinessReport:
    """Report whether every non-excluded source family has a reviewed English pair."""
    ready_entries = tuple(entry for entry in manifest.entries if entry.status == "ready")
    excluded_entries = tuple(entry for entry in manifest.entries if entry.status == "excluded")
    blockers = tuple(
        entry.case_id
        for entry in manifest.entries
        if entry.status not in {"ready", "excluded"}
    )
    return ManifestReadinessReport(
        study_id=manifest.study_id,
        total_entry_count=len(manifest.entries),
        ready_entry_count=len(ready_entries),
        excluded_entry_count=len(excluded_entries),
        blocking_case_ids=blockers,
    )
