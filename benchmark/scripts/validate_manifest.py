"""Validate unified ground-truth manifest integrity.

Checks:
  1. Every gs_NNN directory has a manifest entry.
  2. Every manifest entry points to an existing expected.json.
  3. No duplicate entry_id / unified_id.
  4. source_dataset and source_entry_id (original_entry_id) are non-empty.
  5. Schema version is present.

Usage:
    python benchmark/scripts/validate_manifest.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_unified_dir() -> Path:
    """Resolve the unified ground-truth directory."""
    # Walk up from this script to find benchmark/data/ground_truth/unified
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "ground_truth" / "unified"
        if candidate.is_dir():
            return candidate
    # Fallback: relative to cwd
    cwd_candidate = Path("benchmark/data/ground_truth/unified")
    if cwd_candidate.is_dir():
        return cwd_candidate.resolve()
    print("ERROR: cannot locate unified ground-truth directory", file=sys.stderr)
    sys.exit(1)


def validate(unified_dir: Path | None = None) -> list[str]:
    """Run all validation checks. Returns a list of error strings (empty = pass)."""
    if unified_dir is None:
        unified_dir = _resolve_unified_dir()

    manifest_path = unified_dir / "manifest.json"
    if not manifest_path.exists():
        return [f"manifest.json not found at {manifest_path}"]

    with open(manifest_path) as f:
        manifest = json.load(f)

    errors: list[str] = []

    # --- Check 5: schema version ---
    if not manifest.get("schema_version"):
        errors.append("manifest missing schema_version")

    entries = manifest.get("entries", [])
    if not entries:
        errors.append("manifest has no entries")
        return errors

    # Build lookup maps
    entry_ids: set[str] = set()
    manifest_ids: set[str] = set()

    for i, entry in enumerate(entries):
        uid = entry.get("unified_id", "")
        eid = entry.get("entry_id", "")
        src_ds = entry.get("source_dataset", "")
        orig_id = entry.get("original_entry_id", "")

        # --- Check 4: non-empty required fields ---
        if not src_ds:
            errors.append(f"entry[{i}] ({uid or eid}): source_dataset is empty")
        if not orig_id:
            errors.append(f"entry[{i}] ({uid or eid}): original_entry_id is empty")

        # --- Check 3: no duplicates ---
        key = uid or eid
        if key in entry_ids:
            errors.append(f"duplicate entry_id/unified_id: {key}")
        entry_ids.add(key)
        manifest_ids.add(key)

        # --- Check 2: expected.json exists ---
        expected = unified_dir / key / "expected.json"
        if not expected.exists():
            errors.append(f"entry {key}: expected.json not found at {expected}")

    # --- Check 1: every gs_NNN dir has a manifest entry ---
    gs_dirs = sorted(
        d.name
        for d in unified_dir.iterdir()
        if d.is_dir() and d.name.startswith("gs_")
    )
    for gs_dir in gs_dirs:
        if gs_dir not in manifest_ids:
            errors.append(f"directory {gs_dir}/ has no manifest entry")

    return errors


def main() -> None:
    unified_dir = _resolve_unified_dir()
    print(f"Validating: {unified_dir}")

    errors = validate(unified_dir)

    if errors:
        print(f"\nFAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("PASSED — all manifest checks OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
