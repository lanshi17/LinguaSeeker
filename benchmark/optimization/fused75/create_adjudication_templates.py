"""Generate source-visible adjudication templates for fused-75 dev/test entries."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from benchmark.optimization.fused75.adjudication_contracts import (
    Fused75EntryAdjudication,
    Fused75FieldAdjudication,
)
from benchmark.optimization.fused75.contracts import Fused75SplitManifest

_DEFAULT_SPLIT_MANIFEST = Path("benchmark/optimization/fused75/fused75_split_manifest.json")
_DEFAULT_OUTPUT_ROOT = Path("benchmark/optimization/fused75/adjudication")
_DEFAULT_DATASET_ROOT = Path("benchmark/data/ground_truth/clinvar_fused")


@dataclass(frozen=True)
class AdjudicationTemplateResult:
    """Paths created by adjudication template generation."""

    templates: tuple[Path, ...]


def create_adjudication_templates(
    *,
    split_manifest_path: Path = _DEFAULT_SPLIT_MANIFEST,
    output_root: Path = _DEFAULT_OUTPUT_ROOT,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
) -> AdjudicationTemplateResult:
    """Create incomplete adjudication templates for frozen dev/test entries."""
    manifest = Fused75SplitManifest.model_validate_json(split_manifest_path.read_text(encoding="utf-8"))
    created: list[Path] = []
    for entry in manifest.entries:
        if entry.split not in {"adjudication_dev", "adjudication_test"}:
            continue
        expected_path = dataset_root / entry.entry_id / "expected.json"
        payload = _load_json(expected_path)
        template = Fused75EntryAdjudication(
            entry_id=entry.entry_id,
            split=entry.split,
            source_path=entry.source_path,
            expected_path=entry.expected_path,
            is_complete=False,
            labels=tuple(_field_templates(payload)),
        )
        split_dir = "dev" if entry.split == "adjudication_dev" else "test"
        output_path = output_root / split_dir / f"{entry.entry_id}.json"
        _write_template(template, output_path)
        created.append(output_path)
    return AdjudicationTemplateResult(templates=tuple(created))


def _field_templates(expected_payload: dict[str, Any]) -> tuple[Fused75FieldAdjudication, ...]:
    return tuple(
        Fused75FieldAdjudication(
            field_id=str(item["field_id"]),
            expected_value=str(item["value"]),
        )
        for item in expected_payload.get("expected_evidence", ())
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_template(template: Fused75EntryAdjudication, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(template.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-manifest", type=Path, default=_DEFAULT_SPLIT_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Generate adjudication templates from the frozen split manifest."""
    args = _parse_args(argv)
    create_adjudication_templates(
        split_manifest_path=args.split_manifest,
        output_root=args.output_root,
        dataset_root=args.dataset_root,
    )


if __name__ == "__main__":
    main()
