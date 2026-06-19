"""CLI and helpers for fused-75 source-visible adjudication review."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, cast

from benchmark.optimization.fused75.adjudication_contracts import (
    Fused75EntryAdjudication,
    Fused75FieldAdjudication,
    Fused75Visibility,
)
from benchmark.optimization.fused75.adjudication_review_queue import build_review_queue

_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication")
_VISIBILITY_CHOICES = (
    "source_visible",
    "not_source_visible",
    "ambiguous_boundary",
    "unsupported_prediction",
)

_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


@dataclass(frozen=True)
class ReviewStats:
    """Summary of fused-75 adjudication review progress."""

    total_entries: int
    complete_entries: int
    total_labels: int
    unresolved_labels: int
    source_visible_labels: int
    not_source_visible_labels: int
    ambiguous_boundary_labels: int
    unsupported_prediction_labels: int


def load_review_stats(*, adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT) -> ReviewStats:
    """Count entry and label review status across an adjudication directory."""
    total_entries = 0
    complete_entries = 0
    total_labels = 0
    unresolved_labels = 0
    source_visible_labels = 0
    not_source_visible_labels = 0
    ambiguous_boundary_labels = 0
    unsupported_prediction_labels = 0

    for path in _adjudication_paths(adjudication_root):
        adjudication = _load_adjudication(path)
        total_entries += 1
        complete_entries += int(adjudication.is_complete)
        for label in adjudication.labels:
            total_labels += 1
            if label.visibility is None:
                unresolved_labels += 1
            elif label.visibility == "source_visible":
                source_visible_labels += 1
            elif label.visibility == "not_source_visible":
                not_source_visible_labels += 1
            elif label.visibility == "ambiguous_boundary":
                ambiguous_boundary_labels += 1
            elif label.visibility == "unsupported_prediction":
                unsupported_prediction_labels += 1

    return ReviewStats(
        total_entries=total_entries,
        complete_entries=complete_entries,
        total_labels=total_labels,
        unresolved_labels=unresolved_labels,
        source_visible_labels=source_visible_labels,
        not_source_visible_labels=not_source_visible_labels,
        ambiguous_boundary_labels=ambiguous_boundary_labels,
        unsupported_prediction_labels=unsupported_prediction_labels,
    )


def set_label_decision(
    *,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    entry_id: str,
    field_id: str,
    visibility: Fused75Visibility,
    reviewer: str,
    source_quote: str | None = None,
    source_location: str | None = None,
    notes: str | None = None,
) -> Fused75EntryAdjudication:
    """Set one field-level adjudication decision."""
    if visibility == "source_visible" and (not source_quote or not source_location):
        raise ValueError("source_visible decisions require source_quote and source_location")

    path = _entry_path(adjudication_root, entry_id)
    adjudication = _load_adjudication(path)
    labels: list[Fused75FieldAdjudication] = []
    found = False
    for label in adjudication.labels:
        if label.field_id != field_id:
            labels.append(label)
            continue
        found = True
        labels.append(
            label.model_copy(
                update={
                    "visibility": visibility,
                    "source_quote": source_quote,
                    "source_location": source_location,
                    "adjudicator": reviewer,
                    "notes": notes,
                }
            )
        )
    if not found:
        raise ValueError(f"{entry_id}: field_id not found: {field_id}")

    updated = adjudication.model_copy(update={"is_complete": False, "labels": tuple(labels)})
    _write_adjudication(updated, path)
    return updated


def complete_entry(
    *,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    entry_id: str,
) -> Fused75EntryAdjudication:
    """Mark one entry complete after all labels have decisions."""
    path = _entry_path(adjudication_root, entry_id)
    adjudication = _load_adjudication(path)
    unresolved = tuple(label.field_id for label in adjudication.labels if label.visibility is None)
    if unresolved:
        raise ValueError(f"{entry_id}: unresolved labels: {', '.join(unresolved)}")
    updated = adjudication.model_copy(update={"is_complete": True})
    _write_adjudication(updated, path)
    return updated


def _adjudication_paths(adjudication_root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for split in ("dev", "test") for path in (adjudication_root / split).glob("*.json")))


def _entry_path(adjudication_root: Path, entry_id: str) -> Path:
    matches = tuple(path for path in _adjudication_paths(adjudication_root) if path.stem == entry_id)
    if not matches:
        raise ValueError(f"entry not found: {entry_id}")
    if len(matches) > 1:
        raise ValueError(f"duplicate entry files for {entry_id}")
    return matches[0]


def _load_adjudication(path: Path) -> Fused75EntryAdjudication:
    return Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))


def _write_adjudication(adjudication: Fused75EntryAdjudication, path: Path) -> None:
    path.write_text(
        json.dumps(adjudication.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _color(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


def _print_stats(stats: ReviewStats) -> None:
    print(f"total_entries: {stats.total_entries}")
    print(f"complete_entries: {stats.complete_entries}")
    print(f"total_labels: {stats.total_labels}")
    print(f"unresolved_labels: {stats.unresolved_labels}")
    print(f"source_visible_labels: {stats.source_visible_labels}")
    print(f"not_source_visible_labels: {stats.not_source_visible_labels}")
    print(f"ambiguous_boundary_labels: {stats.ambiguous_boundary_labels}")
    print(f"unsupported_prediction_labels: {stats.unsupported_prediction_labels}")


def _print_entries(adjudication_root: Path) -> None:
    print(f"{'Entry ID':<12} {'Split':<18} {'Complete':<9} {'Done':<9} {'Unresolved'}")
    print(f"{'-' * 12} {'-' * 18} {'-' * 9} {'-' * 9} {'-' * 10}")
    for path in _adjudication_paths(adjudication_root):
        adjudication = _load_adjudication(path)
        done = sum(1 for label in adjudication.labels if label.visibility is not None)
        unresolved = len(adjudication.labels) - done
        print(
            f"{adjudication.entry_id:<12} {adjudication.split:<18} "
            f"{str(adjudication.is_complete):<9} {done}/{len(adjudication.labels):<7} {unresolved}"
        )


def _show_entry(adjudication_root: Path, entry_id: str) -> None:
    adjudication = _load_adjudication(_entry_path(adjudication_root, entry_id))
    print(_color(f"Entry {adjudication.entry_id}", _BOLD))
    print(f"split: {adjudication.split}")
    print(f"complete: {adjudication.is_complete}")
    print(f"source_path: {adjudication.source_path}")
    for label in adjudication.labels:
        status = label.visibility or "UNRESOLVED"
        print(f"- {label.field_id}: {label.expected_value} [{status}]")
        if label.source_location:
            print(f"  location: {label.source_location}")
        if label.source_quote:
            print(f"  quote: {label.source_quote}")
        if label.notes:
            print(f"  notes: {label.notes}")


def _interactive_review(adjudication_root: Path, reviewer: str) -> None:
    queue = build_review_queue(adjudication_root=adjudication_root)
    if not queue.items:
        print(_color("No unresolved labels.", _GREEN))
        return

    print(_color(f"Interactive fused-75 review: {queue.unresolved_labels} unresolved labels", _BOLD))
    print("Commands: sv=source_visible, ns=not_source_visible, ab=ambiguous_boundary, up=unsupported_prediction, s=skip, q=quit")

    reviewed = 0
    skipped = 0
    for index, item in enumerate(queue.items, start=1):
        print()
        print(_color(f"[{index}/{queue.unresolved_labels}] {item.entry_id} {item.field_id}", _CYAN))
        print(f"expected_value: {item.expected_value}")
        print(f"source_path: {item.source_path}")

        command = _prompt("decision [sv/ns/ab/up/s/q] > ").strip().lower()
        if command in {"q", "quit"}:
            break
        if command in {"", "s", "skip"}:
            skipped += 1
            continue

        visibility = _visibility_from_command(command)
        if visibility is None:
            print(_color("Unknown decision; skipped.", _YELLOW))
            skipped += 1
            continue

        source_quote = None
        source_location = None
        if visibility == "source_visible":
            source_location = _prompt("source_location > ").strip()
            source_quote = _prompt("source_quote > ").strip()
            if not source_location or not source_quote:
                print(_color("source_visible requires location and quote; skipped.", _RED))
                skipped += 1
                continue
        notes = _prompt("notes (optional) > ").strip() or None

        set_label_decision(
            adjudication_root=adjudication_root,
            entry_id=item.entry_id,
            field_id=item.field_id,
            visibility=visibility,
            reviewer=reviewer,
            source_quote=source_quote,
            source_location=source_location,
            notes=notes,
        )
        reviewed += 1
        print(_color("saved", _GREEN))

    print(_color(f"Reviewed: {reviewed}; skipped: {skipped}", _BOLD))


def _visibility_from_command(command: str) -> Fused75Visibility | None:
    mapping = {
        "sv": "source_visible",
        "source_visible": "source_visible",
        "ns": "not_source_visible",
        "not_source_visible": "not_source_visible",
        "ab": "ambiguous_boundary",
        "ambiguous_boundary": "ambiguous_boundary",
        "up": "unsupported_prediction",
        "unsupported_prediction": "unsupported_prediction",
    }
    value = mapping.get(command)
    if value is None:
        return None
    return cast(Fused75Visibility, value)


def _prompt(text: str) -> str:
    try:
        return input(text)
    except (EOFError, KeyboardInterrupt):
        return "q"


def _parse_visibility(value: str) -> Fused75Visibility:
    if value not in _VISIBILITY_CHOICES:
        raise argparse.ArgumentTypeError(f"visibility must be one of: {', '.join(_VISIBILITY_CHOICES)}")
    return cast(Fused75Visibility, value)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fused-75 adjudication review workflow")
    parser.add_argument("--adjudication-root", type=Path, default=_DEFAULT_ADJUDICATION_ROOT)
    parser.add_argument("--stats", action="store_true", help="Show review progress statistics")
    parser.add_argument("--list", action="store_true", help="List adjudication entries")
    parser.add_argument("--show", help="Show one entry")
    parser.add_argument("--set", dest="set_entry_id", help="Set a field decision for one entry")
    parser.add_argument("--field", help="Field ID to update with --set")
    parser.add_argument("--visibility", type=_parse_visibility, help="Visibility decision for --set")
    parser.add_argument("--reviewer", default="human-reviewer", help="Reviewer name")
    parser.add_argument("--source-location", help="Source location for source_visible")
    parser.add_argument("--source-quote", help="Source quote for source_visible")
    parser.add_argument("--notes", help="Optional review notes")
    parser.add_argument("--complete", help="Mark one entry complete after all labels are decided")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run interactive field-level review")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run fused-75 review status CLI."""
    args = _parse_args(argv)
    adjudication_root = args.adjudication_root

    if args.stats:
        _print_stats(load_review_stats(adjudication_root=adjudication_root))
        return
    if args.list:
        _print_entries(adjudication_root)
        return
    if args.show:
        _show_entry(adjudication_root, args.show)
        return
    if args.set_entry_id:
        if not args.field or args.visibility is None:
            raise SystemExit("--set requires --field and --visibility")
        updated = set_label_decision(
            adjudication_root=adjudication_root,
            entry_id=args.set_entry_id,
            field_id=args.field,
            visibility=args.visibility,
            reviewer=args.reviewer,
            source_quote=args.source_quote,
            source_location=args.source_location,
            notes=args.notes,
        )
        print(f"Updated {updated.entry_id} {args.field}: {args.visibility}")
        return
    if args.complete:
        updated = complete_entry(adjudication_root=adjudication_root, entry_id=args.complete)
        print(f"Completed {updated.entry_id}")
        return

    if args.interactive or not any((args.stats, args.list, args.show, args.set_entry_id, args.complete)):
        _interactive_review(adjudication_root, args.reviewer)
        return

    raise SystemExit("No action requested")


if __name__ == "__main__":
    main()
