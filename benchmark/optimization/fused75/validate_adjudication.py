"""Validate fused-75 source-visible adjudication payloads."""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from pydantic import ValidationError

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.contracts import Fused75SplitManifest

_DEFAULT_SPLIT_MANIFEST = Path("benchmark/optimization/fused75/fused75_split_manifest.json")
_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication")


@dataclass(frozen=True)
class AdjudicationValidationResult:
    """Validation summary for fused-75 adjudication files."""

    ok: bool
    checked_entries: int
    errors: tuple[str, ...]
    test_file_hashes: tuple[tuple[str, str], ...]


def validate_adjudication(
    *,
    split_manifest_path: Path = _DEFAULT_SPLIT_MANIFEST,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    frozen_test_hashes: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
) -> AdjudicationValidationResult:
    """Validate all frozen dev/test adjudication payloads."""
    manifest = Fused75SplitManifest.model_validate_json(split_manifest_path.read_text(encoding="utf-8"))
    expected_test_hashes = dict(frozen_test_hashes or ())
    errors: list[str] = []
    checked_entries = 0
    test_hashes: list[tuple[str, str]] = []

    for split_entry in manifest.entries:
        if split_entry.split not in {"adjudication_dev", "adjudication_test"}:
            continue
        checked_entries += 1
        split_dir = "dev" if split_entry.split == "adjudication_dev" else "test"
        path = adjudication_root / split_dir / f"{split_entry.entry_id}.json"
        if not path.is_file():
            errors.append(f"{split_entry.entry_id}: missing adjudication file {path}")
            continue

        if split_entry.split == "adjudication_test":
            digest = _sha256_file(path)
            test_hashes.append((split_entry.entry_id, digest))
            if split_entry.entry_id in expected_test_hashes and expected_test_hashes[split_entry.entry_id] != digest:
                errors.append(f"{split_entry.entry_id}: frozen test hash changed")

        try:
            adjudication = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            errors.append(f"{split_entry.entry_id}: {exc}")
            continue

        if not adjudication.is_complete:
            errors.append(f"{split_entry.entry_id}: is_complete=false")
        if adjudication.entry_id != split_entry.entry_id:
            errors.append(f"{split_entry.entry_id}: entry_id mismatch ({adjudication.entry_id})")
        if adjudication.split != split_entry.split:
            errors.append(f"{split_entry.entry_id}: split mismatch ({adjudication.split})")

    return AdjudicationValidationResult(
        ok=not errors,
        checked_entries=checked_entries,
        errors=tuple(errors),
        test_file_hashes=tuple(sorted(test_hashes)),
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-manifest", type=Path, default=_DEFAULT_SPLIT_MANIFEST)
    parser.add_argument("--adjudication-root", type=Path, default=_DEFAULT_ADJUDICATION_ROOT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Validate adjudication files and raise SystemExit on failure."""
    args = _parse_args(argv)
    result = validate_adjudication(
        split_manifest_path=args.split_manifest,
        adjudication_root=args.adjudication_root,
    )
    if not result.ok:
        for error in result.errors:
            print(error)
        raise SystemExit(1)
    print(f"Validated {result.checked_entries} adjudication entries")


if __name__ == "__main__":
    main()
