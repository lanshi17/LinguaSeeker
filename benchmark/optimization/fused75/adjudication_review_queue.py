"""Build human review queues for fused-75 adjudication drafts."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TypedDict

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication

_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication")
_DEFAULT_JSON_PATH = Path("benchmark/optimization/fused75/reports/adjudication_review_queue.json")
_DEFAULT_MARKDOWN_PATH = Path("benchmark/optimization/fused75/reports/adjudication_review_queue.md")


@dataclass(frozen=True)
class ReviewQueueItem:
    """One unresolved fused-75 field awaiting human adjudication."""

    entry_id: str
    split: str
    field_id: str
    expected_value: str
    source_path: str
    expected_path: str


class ReviewQueueItemPayload(TypedDict):
    """JSON payload for one review queue item."""

    entry_id: str
    split: str
    field_id: str
    expected_value: str
    source_path: str
    expected_path: str


class ReviewQueuePayload(TypedDict):
    """JSON payload for a review queue report."""

    items: list[ReviewQueueItemPayload]
    total_entries: int
    total_labels: int
    unresolved_labels: int


@dataclass(frozen=True)
class ReviewQueueReport:
    """Summary and item list for fused-75 human adjudication."""

    total_entries: int
    total_labels: int
    unresolved_labels: int
    items: tuple[ReviewQueueItem, ...]

    def to_payload(self) -> ReviewQueuePayload:
        """Return a stable JSON-ready payload."""
        return {
            "items": [
                {
                    "entry_id": item.entry_id,
                    "split": item.split,
                    "field_id": item.field_id,
                    "expected_value": item.expected_value,
                    "source_path": item.source_path,
                    "expected_path": item.expected_path,
                }
                for item in self.items
            ],
            "total_entries": self.total_entries,
            "total_labels": self.total_labels,
            "unresolved_labels": self.unresolved_labels,
        }


def build_review_queue(*, adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT) -> ReviewQueueReport:
    """Build a report of all labels that still have no adjudication decision."""
    items: list[ReviewQueueItem] = []
    total_entries = 0
    total_labels = 0

    for path in _adjudication_paths(adjudication_root):
        adjudication = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
        total_entries += 1
        for label in adjudication.labels:
            total_labels += 1
            if label.visibility is not None:
                continue
            items.append(
                ReviewQueueItem(
                    entry_id=adjudication.entry_id,
                    split=adjudication.split,
                    field_id=label.field_id,
                    expected_value=label.expected_value,
                    source_path=str(adjudication.source_path),
                    expected_path=str(adjudication.expected_path),
                )
            )

    return ReviewQueueReport(
        total_entries=total_entries,
        total_labels=total_labels,
        unresolved_labels=len(items),
        items=tuple(items),
    )


def write_review_queue(
    *,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    json_path: Path = _DEFAULT_JSON_PATH,
    markdown_path: Path = _DEFAULT_MARKDOWN_PATH,
) -> ReviewQueueReport:
    """Write JSON and Markdown review queue reports."""
    report = build_review_queue(adjudication_root=adjudication_root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report.to_payload(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_to_markdown(report), encoding="utf-8")
    return report


def _adjudication_paths(adjudication_root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for split in ("dev", "test") for path in (adjudication_root / split).glob("*.json")))


def _to_markdown(report: ReviewQueueReport) -> str:
    lines = [
        "# Fused-75 Adjudication Review Queue",
        "",
        f"- total_entries: {report.total_entries}",
        f"- total_labels: {report.total_labels}",
        f"- unresolved_labels: {report.unresolved_labels}",
        "",
        "| entry_id | split | field_id | expected_value | source_path |",
        "|---|---|---|---|---|",
    ]
    for item in report.items:
        lines.append(
            f"| {item.entry_id} | {item.split} | {item.field_id} | "
            f"{_escape_markdown_cell(item.expected_value)} | {item.source_path} |"
        )
    return "\n".join(lines) + "\n"


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudication-root", type=Path, default=_DEFAULT_ADJUDICATION_ROOT)
    parser.add_argument("--json", type=Path, default=_DEFAULT_JSON_PATH)
    parser.add_argument("--markdown", type=Path, default=_DEFAULT_MARKDOWN_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Write the fused-75 adjudication review queue reports."""
    args = _parse_args(argv)
    report = write_review_queue(
        adjudication_root=args.adjudication_root,
        json_path=args.json,
        markdown_path=args.markdown,
    )
    print(
        json.dumps(
            {
                "json_path": str(args.json),
                "markdown_path": str(args.markdown),
                "total_entries": report.total_entries,
                "total_labels": report.total_labels,
                "unresolved_labels": report.unresolved_labels,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
