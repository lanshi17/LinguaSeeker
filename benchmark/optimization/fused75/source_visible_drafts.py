"""Generate deterministic source-visible draft annotations for fused-75."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from benchmark.optimization.fused75.adjudication_contracts import (
    Fused75EntryAdjudication,
    Fused75FieldAdjudication,
)

_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication")
_DEFAULT_ADJUDICATOR = "exact-match-preannotator"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class SourceVisibleDraftResult:
    """Summary of a source-visible draft preannotation run."""

    processed_entries: int
    source_visible_labels: int
    unchanged_labels: int
    missing_sources: tuple[Path, ...]


@dataclass(frozen=True)
class SourceMatch:
    """One deterministic source match for an expected value."""

    quote: str
    location: str


def preannotate_adjudication_directory(
    *,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    adjudicator: str = _DEFAULT_ADJUDICATOR,
    project_root: Path = _PROJECT_ROOT,
) -> SourceVisibleDraftResult:
    """Fill exact source-visible draft labels across an adjudication directory.

    The output remains a draft: ``is_complete`` is never changed. Existing manual
    decisions are preserved.
    """
    processed_entries = 0
    source_visible_labels = 0
    unchanged_labels = 0
    missing_sources: list[Path] = []

    for path in _adjudication_paths(adjudication_root):
        adjudication = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
        source_path = _resolve_project_path(adjudication.source_path, project_root)
        if not source_path.exists():
            missing_sources.append(source_path)
            continue

        source_text = source_path.read_text(encoding="utf-8")
        updated_labels: list[Fused75FieldAdjudication] = []
        for label in adjudication.labels:
            if label.visibility is not None and label.adjudicator != adjudicator:
                unchanged_labels += 1
                updated_labels.append(label)
                continue

            match = _find_exact_match(source_text, label.expected_value, source_path)
            if match is None:
                unchanged_labels += 1
                updated_labels.append(_clear_machine_label(label, adjudicator))
                continue

            source_visible_labels += 1
            updated_labels.append(
                label.model_copy(
                    update={
                        "visibility": "source_visible",
                        "source_quote": match.quote,
                        "source_location": match.location,
                        "adjudicator": adjudicator,
                    }
                )
            )

        updated = adjudication.model_copy(update={"is_complete": False, "labels": tuple(updated_labels)})
        _write_adjudication(updated, path)
        processed_entries += 1

    return SourceVisibleDraftResult(
        processed_entries=processed_entries,
        source_visible_labels=source_visible_labels,
        unchanged_labels=unchanged_labels,
        missing_sources=tuple(missing_sources),
    )


def _adjudication_paths(adjudication_root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for split in ("dev", "test") for path in (adjudication_root / split).glob("*.json")))


def _resolve_project_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


def _find_exact_match(source_text: str, expected_value: str, source_path: Path) -> SourceMatch | None:
    needle = expected_value.strip()
    if not needle:
        return None
    pattern = _exact_value_pattern(needle)
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        if pattern.search(line) is None:
            continue
        quote = " ".join(line.strip().split())
        if len(quote) > 500:
            quote = _trim_quote_around_match(quote, needle, max_length=500)
        return SourceMatch(quote=quote, location=f"{source_path}:{line_number}")
    return None


def _exact_value_pattern(needle: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])", re.IGNORECASE)


def _clear_machine_label(label: Fused75FieldAdjudication, adjudicator: str) -> Fused75FieldAdjudication:
    if label.adjudicator != adjudicator:
        return label
    return label.model_copy(
        update={
            "visibility": None,
            "source_quote": None,
            "source_location": None,
            "adjudicator": None,
        }
    )


def _trim_quote_around_match(line: str, needle: str, *, max_length: int) -> str:
    index = line.casefold().find(needle.casefold())
    if index < 0:
        return line[:max_length]
    half_window = max((max_length - len(needle)) // 2, 0)
    start = max(index - half_window, 0)
    end = min(start + max_length, len(line))
    start = max(end - max_length, 0)
    return line[start:end].strip()


def _write_adjudication(adjudication: Fused75EntryAdjudication, path: Path) -> None:
    path.write_text(
        json.dumps(adjudication.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudication-root", type=Path, default=_DEFAULT_ADJUDICATION_ROOT)
    parser.add_argument("--adjudicator", default=_DEFAULT_ADJUDICATOR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run source-visible preannotation from the command line."""
    args = _parse_args(argv)
    result = preannotate_adjudication_directory(
        adjudication_root=args.adjudication_root,
        adjudicator=args.adjudicator,
    )
    print(
        json.dumps(
            {
                "processed_entries": result.processed_entries,
                "source_visible_labels": result.source_visible_labels,
                "unchanged_labels": result.unchanged_labels,
                "missing_sources": [str(path) for path in result.missing_sources],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
