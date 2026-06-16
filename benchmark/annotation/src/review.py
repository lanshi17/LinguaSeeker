"""Review workflow helpers: approve, reject, promote entries."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .manifest import add_entry, find_entry, load_manifest, save_manifest, update_status
from .models import DraftMeta, Manifest, ManifestEntry


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def approve_entry(
    entry_id: str,
    manifest: Manifest,
    draft_dir: Path,
    approved_dir: Path,
    reviewer: str | None = None,
    notes: str = "",
) -> bool:
    entry = find_entry(manifest, entry_id)
    if entry is None or entry.status not in ("parsed", "draft", "generated"):
        logger.warning("Cannot approve {}: status={}", entry_id, entry and entry.status)
        return False

    src = draft_dir / entry_id
    dst = approved_dir / entry_id
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)

    meta_path = dst / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = DraftMeta(**json.load(f))
        meta.review_status = "approved"
        meta.reviewer = reviewer
        meta.review_notes = notes
        meta.reviewed_at = _now_iso()
        with open(meta_path, "w") as f:
            json.dump(meta.model_dump(), f, indent=2, ensure_ascii=False)

    update_status(manifest, entry_id, "approved", str(dst))
    return True


def reject_entry(
    entry_id: str,
    manifest: Manifest,
    draft_dir: Path,
    rejected_dir: Path,
    reason: str = "",
) -> bool:
    entry = find_entry(manifest, entry_id)
    if entry is None or entry.status not in ("parsed", "draft", "generated"):
        logger.warning("Cannot reject {}: status={}", entry_id, entry and entry.status)
        return False

    src = draft_dir / entry_id
    dst = rejected_dir / entry_id
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)

    meta_path = dst / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = DraftMeta(**json.load(f))
        meta.review_status = "rejected"
        meta.rejection_reason = reason
        meta.reviewed_at = _now_iso()
        with open(meta_path, "w") as f:
            json.dump(meta.model_dump(), f, indent=2, ensure_ascii=False)

    update_status(manifest, entry_id, "rejected", str(dst))
    return True


def promote_entry(
    entry_id: str,
    manifest: Manifest,
    approved_dir: Path,
    ground_truth_dir: Path,
) -> bool:
    entry = find_entry(manifest, entry_id)
    if entry is None or entry.status != "approved":
        logger.warning("Cannot promote {}: status={}", entry_id, entry and entry.status)
        return False

    src = approved_dir / entry_id
    dst = ground_truth_dir / entry_id
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)

    meta_path = dst / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = DraftMeta(**json.load(f))
        meta.review_status = "ground_truth"
        meta.promoted_at = _now_iso()
        with open(meta_path, "w") as f:
            json.dump(meta.model_dump(), f, indent=2, ensure_ascii=False)

    update_status(manifest, entry_id, "ground_truth", str(dst))
    return True


def promote_all_approved(
    manifest: Manifest,
    approved_dir: Path,
    ground_truth_dir: Path,
) -> int:
    promoted = 0
    for entry in manifest.entries:
        if entry.status == "approved":
            if promote_entry(entry.entry_id, manifest, approved_dir, ground_truth_dir):
                promoted += 1
    return promoted


def generate_selection_json(ground_truth_dir: Path) -> None:
    """Build selection.json from all ground_truth entries."""
    selection: list[dict] = []
    for entry_dir in sorted(ground_truth_dir.iterdir()):
        if not entry_dir.is_dir():
            continue
        expected_path = entry_dir / "expected.json"
        if expected_path.exists():
            with open(expected_path) as f:
                data = json.load(f)
            selection.append({
                "entry_id": data.get("entry_id", entry_dir.name),
                "gene_symbol": data.get("gene_symbol", ""),
                "disease_label": data.get("disease_label", ""),
                "source_language": data.get("source_language", ""),
            })

    out_path = ground_truth_dir / "selection.json"
    with open(out_path, "w") as f:
        json.dump(selection, f, indent=2, ensure_ascii=False)
    logger.info("Generated selection.json with {} entries", len(selection))
