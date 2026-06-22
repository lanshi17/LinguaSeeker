"""Export the Parkinson literature XLSX collection to audited JSON artifacts."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path

from benchmark.datasets.parkinson_literature.xlsx_dataset import (
    build_audit_report,
    load_workbook_tables,
)

DEFAULT_INPUT = Path("tmp/test_liter_collect(1).xlsx")
DEFAULT_OUTPUT_DIR = Path("benchmark/data/processed/parkinson_literature")


@dataclass(frozen=True)
class DatasetExportPaths:
    """Paths written by the Parkinson literature dataset exporter."""

    audit_report: Path
    jsonl_paths: tuple[Path, ...]


def export_dataset(
    *,
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> DatasetExportPaths:
    """Export workbook sheets to normalized JSONL plus a structural audit report."""
    tables = load_workbook_tables(input_path)
    report = build_audit_report(tables)
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_paths = []
    for table in tables.values():
        path = output_dir / f"{_safe_name(table.name)}.jsonl"
        with path.open("w", encoding="utf-8") as jsonl_file:
            for row_number, row in zip(table.row_numbers, table.rows, strict=True):
                payload = {
                    "_sheet": table.name,
                    "_row_number": row_number,
                    **dict(row),
                }
                jsonl_file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        jsonl_paths.append(path)

    audit_path = output_dir / "audit_report.json"
    audit_path.write_text(
        json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return DatasetExportPaths(audit_report=audit_path, jsonl_paths=tuple(jsonl_paths))


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for exporting the Parkinson literature dataset."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    paths = export_dataset(input_path=args.input, output_dir=args.output_dir)
    print(f"AUDIT_REPORT: {paths.audit_report}")
    for jsonl_path in paths.jsonl_paths:
        print(f"JSONL: {jsonl_path}")


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)


if __name__ == "__main__":
    main()
