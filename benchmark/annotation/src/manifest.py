"""Manifest tracking and status workflow for annotation entries."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .models import Manifest, ManifestEntry


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_manifest(path: Path) -> Manifest:
    if not path.exists():
        return Manifest()
    with open(path) as f:
        return Manifest(**json.load(f))


def save_manifest(manifest: Manifest, path: Path) -> None:
    manifest.last_updated = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest.model_dump(), f, indent=2, ensure_ascii=False)


def find_entry(manifest: Manifest, entry_id: str) -> ManifestEntry | None:
    for entry in manifest.entries:
        if entry.entry_id == entry_id:
            return entry
    return None


def add_entry(manifest: Manifest, entry: ManifestEntry) -> None:
    existing = find_entry(manifest, entry.entry_id)
    if existing:
        existing.status = entry.status
        existing.current_dir = entry.current_dir
        existing.updated_at = _now_iso()
    else:
        manifest.entries.append(entry)


def update_status(manifest: Manifest, entry_id: str, status: str, current_dir: str = "") -> bool:
    entry = find_entry(manifest, entry_id)
    if entry is None:
        logger.warning("Entry {} not found in manifest", entry_id)
        return False
    entry.status = status
    if current_dir:
        entry.current_dir = current_dir
    entry.updated_at = _now_iso()
    return True


def get_entries_by_status(manifest: Manifest, status: str) -> list[ManifestEntry]:
    return [e for e in manifest.entries if e.status == status]


def get_stats(manifest: Manifest) -> dict[str, dict[str, int]]:
    by_status: dict[str, int] = {}
    by_lang: dict[str, int] = {}
    for entry in manifest.entries:
        by_status[entry.status] = by_status.get(entry.status, 0) + 1
        by_lang[entry.language] = by_lang.get(entry.language, 0) + 1
    return {"by_status": by_status, "by_language": by_lang, "total": len(manifest.entries)}
