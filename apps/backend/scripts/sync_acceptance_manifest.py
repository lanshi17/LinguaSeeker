from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.services.acceptance_runner import sync_manifest_from_postgres


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Refresh an acceptance manifest from PostgreSQL paper-task results.')
    parser.add_argument('--manifest', required=True, help='Path to the acceptance manifest JSON file.')
    parser.add_argument('--write', action='store_true', help='Write updated rows back to the manifest file.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = sync_manifest_from_postgres(args.manifest, write=args.write)
    print(manifest.model_dump(mode='json'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
