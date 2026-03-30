from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def purge_old_outputs(path: Path, keep_latest: int, dry_run: bool) -> int:
    if not path.exists():
        return 0

    dirs = [p for p in path.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    removed = 0
    for target in dirs[keep_latest:]:
        if dry_run:
            print(f"[dry-run] remove {target}")
            removed += 1
            continue
        shutil.rmtree(target)
        removed += 1
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge old output folders")
    parser.add_argument("--path", required=True, help="Target output directory")
    parser.add_argument("--keep-latest", type=int, default=3, help="Number of folders to keep")
    parser.add_argument("--dry-run", action="store_true", help="Only print deletions")
    args = parser.parse_args()

    removed = purge_old_outputs(Path(args.path), args.keep_latest, args.dry_run)
    print(f"Removed {removed} folder(s)")


if __name__ == "__main__":
    main()
