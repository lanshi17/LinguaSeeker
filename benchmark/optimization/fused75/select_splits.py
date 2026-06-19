"""Deterministic split selector for fused-75 optimization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from benchmark.optimization.fused75.contracts import (
    Fused75Split,
    Fused75SplitEntry,
    Fused75SplitManifest,
    Fused75SplitMetadata,
)

_DEFAULT_DATASET_ROOT = Path("benchmark/data/ground_truth/clinvar_fused")
_DEFAULT_OUTPUT_PATH = Path("benchmark/optimization/fused75/fused75_split_manifest.json")


def build_split_manifest(
    *,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    dev_count: int = 10,
    test_count: int = 10,
    repo_relative_root: Path | None = None,
) -> Fused75SplitManifest:
    """Build a deterministic fused-75 split manifest from selection.json."""
    manifest_root = repo_relative_root or dataset_root
    entry_ids = _load_entry_ids(dataset_root / "selection.json")
    sorted_entry_ids = tuple(sorted(entry_ids))
    entries = tuple(
        _build_entry(
            entry_id=entry_id,
            index=index,
            dataset_root=dataset_root,
            repo_relative_root=manifest_root,
            dev_count=dev_count,
            test_count=test_count,
        )
        for index, entry_id in enumerate(sorted_entry_ids)
    )
    return Fused75SplitManifest(
        metadata=Fused75SplitMetadata(
            dataset_root=manifest_root,
            selection_path=manifest_root / "selection.json",
            selection_method="sorted_entry_id_v1",
            split_seed="sorted-entry-id-v1",
            dev_count=dev_count,
            test_count=test_count,
            total_entries=len(entries),
        ),
        entries=entries,
    )


def write_split_manifest(manifest: Fused75SplitManifest, output_path: Path) -> None:
    """Write a split manifest as stable JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_entry_ids(selection_path: Path) -> tuple[str, ...]:
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    return tuple(str(entry["entry_id"]) for entry in payload)


def _build_entry(
    *,
    entry_id: str,
    index: int,
    dataset_root: Path,
    repo_relative_root: Path,
    dev_count: int,
    test_count: int,
) -> Fused75SplitEntry:
    source_path = dataset_root / entry_id / "source.md"
    expected_path = dataset_root / entry_id / "expected.json"
    _require_file(source_path)
    _require_file(expected_path)
    return Fused75SplitEntry(
        entry_id=entry_id,
        split=_split_for_index(index, dev_count, test_count),
        source_path=repo_relative_root / entry_id / "source.md",
        expected_path=repo_relative_root / entry_id / "expected.json",
        selection_reason=_selection_reason(index, dev_count, test_count),
        sha256=_sha256_file(expected_path),
    )


def _split_for_index(index: int, dev_count: int, test_count: int) -> Fused75Split:
    if index < dev_count:
        return "adjudication_dev"
    if index < dev_count + test_count:
        return "adjudication_test"
    return "auto_pool"


def _selection_reason(index: int, dev_count: int, test_count: int) -> str:
    if index < dev_count:
        return f"first {dev_count} sorted entries reserved for adjudication dev"
    if index < dev_count + test_count:
        return f"next {test_count} sorted entries reserved for held-out adjudication test"
    return "remaining sorted entries retained for automatic evaluation pool"


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument(
        "--repo-relative-root",
        type=Path,
        default=None,
        help="Path to record in the manifest. Defaults to --dataset-root.",
    )
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT_PATH)
    parser.add_argument("--dev-count", type=int, default=10)
    parser.add_argument("--test-count", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Generate the fused-75 split manifest."""
    args = _parse_args(argv)
    manifest = build_split_manifest(
        dataset_root=args.dataset_root,
        repo_relative_root=args.repo_relative_root,
        dev_count=args.dev_count,
        test_count=args.test_count,
    )
    write_split_manifest(manifest, args.output)


if __name__ == "__main__":
    main()
