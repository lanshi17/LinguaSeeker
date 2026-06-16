"""CLI: Review workflow — list, approve, reject, promote annotation entries."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.config import get_config
from src.manifest import (
    get_entries_by_status,
    get_stats,
    load_manifest,
    save_manifest,
)
from src.review import (
    approve_entry,
    generate_selection_json,
    promote_all_approved,
    promote_entry,
    reject_entry,
)


def _print_entries(entries, title: str = "") -> None:
    if title:
        print(f"\n{title} ({len(entries)} entries):")
    if not entries:
        print("  (none)")
        return
    print(f"  {'Entry ID':<15} {'Lang':<6} {'Status':<15} {'Directory'}")
    print(f"  {'-'*15} {'-'*6} {'-'*15} {'-'*40}")
    for e in entries:
        print(f"  {e.entry_id:<15} {e.language:<6} {e.status:<15} {e.current_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotation review workflow")
    parser.add_argument("--list", action="store_true", help="List all entries")
    parser.add_argument("--status", type=str, help="Filter by status")
    parser.add_argument("--stats", action="store_true", help="Show summary statistics")
    parser.add_argument("--approve", type=str, help="Approve entry by ID")
    parser.add_argument("--reject", type=str, help="Reject entry by ID")
    parser.add_argument("--reason", type=str, default="", help="Rejection reason")
    parser.add_argument("--reviewer", type=str, help="Reviewer name")
    parser.add_argument("--notes", type=str, default="", help="Review notes")
    parser.add_argument("--promote", type=str, help="Promote specific entry to ground_truth")
    parser.add_argument("--promote-all", action="store_true", help="Promote all approved entries")
    args = parser.parse_args()

    cfg = get_config()
    paths = cfg.resolved_paths
    draft_dir = paths["draft_dir"]
    approved_dir = paths["approved_dir"]
    rejected_dir = paths["rejected_dir"]
    gt_dir = paths["ground_truth_dir"]
    manifest_path = gt_dir / "manifest.json"
    manifest = load_manifest(manifest_path)

    if args.stats:
        stats = get_stats(manifest)
        print(f"\nTotal entries: {stats['total']}")
        print(f"By status: {stats['by_status']}")
        print(f"By language: {stats['by_language']}")
        return

    if args.list:
        if args.status:
            entries = get_entries_by_status(manifest, args.status)
            _print_entries(entries, f"Status: {args.status}")
        else:
            _print_entries(manifest.entries, "All entries")
        return

    if args.approve:
        ok = approve_entry(args.approve, manifest, draft_dir, approved_dir,
                           reviewer=args.reviewer, notes=args.notes)
        if ok:
            save_manifest(manifest, manifest_path)
            print(f"Approved: {args.approve}")
        else:
            print(f"Failed to approve: {args.approve}")
        return

    if args.reject:
        ok = reject_entry(args.reject, manifest, draft_dir, rejected_dir, reason=args.reason)
        if ok:
            save_manifest(manifest, manifest_path)
            print(f"Rejected: {args.reject}")
        else:
            print(f"Failed to reject: {args.reject}")
        return

    if args.promote:
        ok = promote_entry(args.promote, manifest, approved_dir, gt_dir)
        if ok:
            save_manifest(manifest, manifest_path)
            generate_selection_json(gt_dir)
            print(f"Promoted: {args.promote}")
        else:
            print(f"Failed to promote: {args.promote}")
        return

    if args.promote_all:
        count = promote_all_approved(manifest, approved_dir, gt_dir)
        save_manifest(manifest, manifest_path)
        generate_selection_json(gt_dir)
        print(f"Promoted {count} entries to ground_truth")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
