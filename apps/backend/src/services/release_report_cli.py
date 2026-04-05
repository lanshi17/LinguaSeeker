from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from loguru import logger

from src.services.release_reporting import (
    calculate_release_gate_summary,
    load_acceptance_manifest,
    render_release_report,
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a markdown release report from an acceptance manifest.",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the acceptance manifest JSON file.",
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Where to write the rendered markdown report. Defaults to stdout only.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    manifest = load_acceptance_manifest(args.manifest)
    summary = calculate_release_gate_summary(manifest)
    rendered = render_release_report(manifest, summary)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        logger.info(
            "Rendered release report for {} to {} ({})",
            manifest.release_no,
            output_path,
            summary.gate_status,
        )
    else:
        print(rendered)
        logger.info(
            "Rendered release report for {} to stdout ({})",
            manifest.release_no,
            summary.gate_status,
        )
    return 0
