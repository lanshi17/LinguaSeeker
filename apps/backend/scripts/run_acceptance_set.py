from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.services.acceptance_runner import run_acceptance_set
from src.services.release_reporting import load_acceptance_manifest, save_acceptance_manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Queue missing entries from a locked acceptance manifest.')
    parser.add_argument('--manifest', required=True, help='Path to the acceptance manifest JSON file.')
    parser.add_argument('--write', action='store_true', help='Write queued paper_task_ids back to the manifest.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = load_acceptance_manifest(args.manifest)
    report = run_acceptance_set(
        manifest,
        enqueue=lambda paper: {'paper_task_id': paper.paper_task_id or f"queued-{paper.paper_id}"},
    )
    if args.write:
        save_acceptance_manifest(args.manifest, manifest)
    print(report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
