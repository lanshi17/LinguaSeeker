from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from src.domain.evidence.gold_standard_converter import convert_gold_standard_payload
from src.domain.models import EvidenceOutput


def convert_file(source_path: Path, target_path: Path, source_id: str | None = None) -> int:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    records = convert_gold_standard_payload(payload, source_id=source_id or source_path.stem)
    validated_records = [
        EvidenceOutput.model_validate(record).model_dump(mode="json") for record in records
    ]

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(validated_records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(validated_records)


def convert_directory(source_dir: Path, target_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source_path in sorted(source_dir.glob("*.json")):
        target_path = target_dir / f"{source_path.stem}.evidence.json"
        counts[source_path.name] = convert_file(source_path, target_path)
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert gold standard annotation JSON to EvidenceOutput JSON."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args(argv)

    if args.source.is_dir():
        counts = convert_directory(args.source, args.target)
        for name, count in counts.items():
            print(f"{name}: {count}")
    else:
        count = convert_file(args.source, args.target)
        print(f"{args.source.name}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
