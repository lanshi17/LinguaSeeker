#!/usr/bin/env python3
"""Derive English-visible word counts per source family from the frozen ledger.

Reviewer request: justify the >=100-word English-abstract threshold used to
separate English-pivot comparators from availability-only families by reporting
the retained English-visible word count for every family with any English anchor.

The English-visible extent is defined mechanically from the ledger's own
recorded anchors: for each family we take the retained source.md lines that the
frozen facts file cites in its ``english_abstract`` and ``english_visible``
layers, deduplicate them by line number, and count whitespace-delimited tokens.
This uses only retained local files and adds no new judgement.

Usage:
    python3 scripts/stage0_english_visible_wordcount.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

LEDGER_ROOT = Path("benchmark/experiments/acmg_multilingual")
FACTS = LEDGER_ROOT / "evidence_item_coverage_facts.json"
REVIEWED = LEDGER_ROOT / "reviewed"

ENGLISH_LAYERS = ("english_abstract", "english_visible")
ABSTRACT_THRESHOLD = 100


@dataclass
class FamilyCount:
    """Per-family English-visible extent derived from ledger anchors."""

    source_cluster_id: str
    native_language: str
    is_comparator: bool
    abstract_words: int = 0
    other_english_words: int = 0
    anchor_lines: list[int] = field(default_factory=list)

    @property
    def total_words(self) -> int:
        return self.abstract_words + self.other_english_words

    @property
    def meets_threshold(self) -> bool:
        return self.abstract_words >= ABSTRACT_THRESHOLD


def _count_words(text: str) -> int:
    """Count whitespace-delimited tokens containing at least one letter."""
    return sum(1 for tok in re.split(r"\s+", text.strip()) if re.search(r"[A-Za-z]", tok))


def _line_map(path: Path) -> dict[int, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {i: line for i, line in enumerate(lines, start=1)}


def collect(repo_root: Path) -> list[FamilyCount]:
    facts = json.loads((repo_root / FACTS).read_text(encoding="utf-8"))
    comparators = set(facts["english_visible_comparator_source_cluster_ids"])
    results: list[FamilyCount] = []

    for source in facts["sources"]:
        cid = source["source_cluster_id"]
        row = FamilyCount(
            source_cluster_id=cid,
            native_language=source.get("native_language", "?"),
            is_comparator=cid in comparators,
        )
        source_path = repo_root / REVIEWED / source["source_relative_path"]
        if not source_path.exists():
            results.append(row)
            continue
        lines = _line_map(source_path)

        # Both English layers frequently cite the same physical line; count each
        # retained line once, attributing it to the abstract layer when cited there.
        abstract_lines: set[int] = {
            a["span"]["line"] for a in (source.get("english_abstract") or [])
        }
        visible_lines: set[int] = {
            a["span"]["line"] for a in (source.get("english_visible") or [])
        }
        for line_no in sorted(abstract_lines):
            row.abstract_words += _count_words(lines.get(line_no, ""))
        for line_no in sorted(visible_lines - abstract_lines):
            row.other_english_words += _count_words(lines.get(line_no, ""))
        row.anchor_lines = sorted(abstract_lines | visible_lines)
        results.append(row)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="write machine-readable output here")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    rows = collect(args.repo_root)
    with_english = [r for r in rows if r.total_words > 0]

    header = f"{'family':<12}{'lang':<6}{'abstract':>9}{'other':>7}{'total':>7}  {'>=100':<6} comparator"
    print(header)
    print("-" * len(header))
    for r in sorted(rows, key=lambda x: (not x.is_comparator, x.source_cluster_id)):
        print(
            f"{r.source_cluster_id:<12}{r.native_language:<6}{r.abstract_words:>9}"
            f"{r.other_english_words:>7}{r.total_words:>7}  "
            f"{'yes' if r.meets_threshold else 'no':<6} {'yes' if r.is_comparator else 'no'}"
        )

    print()
    print(f"families with any English anchor: {len(with_english)}")
    print(f"families meeting >={ABSTRACT_THRESHOLD}-word abstract threshold: "
          f"{sum(1 for r in rows if r.meets_threshold)}")
    print(f"frozen comparators: {sum(1 for r in rows if r.is_comparator)}")

    if args.json:
        args.json.write_text(
            json.dumps(
                [
                    {
                        "source_cluster_id": r.source_cluster_id,
                        "native_language": r.native_language,
                        "is_comparator": r.is_comparator,
                        "english_abstract_words": r.abstract_words,
                        "english_other_words": r.other_english_words,
                        "english_total_words": r.total_words,
                        "meets_abstract_threshold": r.meets_threshold,
                    }
                    for r in rows
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
