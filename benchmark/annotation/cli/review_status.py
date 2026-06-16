"""CLI: Review workflow — list, approve, reject, promote, and interactive batch review."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_config
from src.manifest import (
    get_entries_by_status,
    get_stats,
    load_manifest,
    save_manifest,
)
from src.models import DraftMeta
from src.review import (
    approve_entry,
    generate_selection_json,
    promote_all_approved,
    promote_entry,
    reject_entry,
)

# ── ANSI helpers ──────────────────────────────────────────────────────

_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _color(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


def _header(text: str) -> str:
    return _color(f"══ {text} ══", _BOLD)


def _label(label: str, value: str, color: str = _DIM) -> str:
    return f"  {_color(label + ':', _CYAN)} {value}"


# ── Display helpers ───────────────────────────────────────────────────

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


def _load_expected(entry_dir: Path) -> dict | None:
    p = entry_dir / "expected.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def _load_meta(entry_dir: Path) -> DraftMeta | None:
    p = entry_dir / "meta.json"
    if not p.exists():
        return None
    with open(p) as f:
        return DraftMeta(**json.load(f))


def _display_entry(idx: int, total: int, entry_id: str, entry_dir: Path) -> None:
    """Pretty-print the key fields of an annotation entry."""
    expected = _load_expected(entry_dir)
    meta = _load_meta(entry_dir)

    print(f"\n{_header(f'Entry {idx}/{total}: {entry_id}')}")

    if not expected:
        print(_color("  [!] expected.json not found", _RED))
        return

    # Source info
    print(f"\n  {_color('SOURCE', _BOLD)}")
    print(_label("Title", expected.get("source_title") or "(none)"))
    print(_label("Journal", f"{expected.get('source_journal') or '?'} ({expected.get('source_year') or '?'})"))
    print(_label("Language", expected.get("source_language", "?")))
    print(_label("DOI/PMID", expected.get("source_doi") or expected.get("source_pmid") or "—"))

    # Gene / Disease
    print(f"\n  {_color('GENE / DISEASE', _BOLD)}")
    print(_label("Gene", expected.get("gene_symbol", "?")))
    print(_label("Disease", expected.get("disease_label", "?")))
    print(_label("MOI", expected.get("moi", "?")))

    # Variants
    variants = expected.get("variants", [])
    print(f"\n  {_color('VARIANTS', _BOLD)} ({len(variants)})")
    if variants:
        for i, v in enumerate(variants, 1):
            hgvs = v.get("hgvs_c") or v.get("hgvs_p") or "?"
            vtype = v.get("variant_type", "")
            sig = v.get("clinical_significance", "")
            domain = v.get("domain", "")
            extras = " | ".join(filter(None, [vtype, sig, domain]))
            print(f"    {i}. {hgvs}" + (f"  {_color(f'[{extras}]', _DIM)}" if extras else ""))
    else:
        print(_color("    (none)", _YELLOW))

    # Evidence fields
    evidence = expected.get("expected_evidence", [])
    print(f"\n  {_color('EVIDENCE FIELDS', _BOLD)} ({len(evidence)})")
    for ev in evidence:
        fid = ev.get("field_id", "")
        val = ev.get("value", "")
        etype = ev.get("evaluation_type", "")
        tag_color = _GREEN if val else _RED
        fid_padded = fid.ljust(40)
        print(f"    {_color(fid_padded, tag_color)} {_color(val or '(empty)', tag_color if val else _RED)}"
              f"  {_color(f'[{etype}]', _DIM)}")

    # Meta
    if meta:
        print(f"\n  {_color('META', _BOLD)}")
        print(_label("Parse", meta.parse_status))
        print(_label("Annotation", meta.annotation_status))
        print(_label("LLM", meta.llm_model or "?"))
        if meta.review_notes:
            print(_label("Notes", meta.review_notes))


def _prompt_action() -> str:
    """Prompt the reviewer and return the action command."""
    try:
        raw = input(
            f"\n  {_color('[a]', _GREEN)} approve  "
            f"{_color('[r]', _RED)} reject  "
            f"{_color('[s]', _YELLOW)} skip  "
            f"{_color('[v]', _CYAN)} view JSON  "
            f"{_color('[q]', _DIM)} quit  > "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"
    return raw


def _interactive_review(
    manifest,
    entries,
    draft_dir: Path,
    approved_dir: Path,
    rejected_dir: Path,
    manifest_path: Path,
    reviewer: str | None = None,
) -> dict[str, int]:
    """Run interactive review on a list of entries. Returns action counts."""
    stats = {"approved": 0, "rejected": 0, "skipped": 0}
    total = len(entries)

    if total == 0:
        print(_color("\nNo entries to review.", _YELLOW))
        return stats

    print(f"\n{_header(f'Interactive Review — {total} entries')}")
    print(f"  {_color('a', _GREEN)}=approve  {_color('r', _RED)}=reject  "
          f"{_color('s', _YELLOW)}=skip  {_color('q', _DIM)}=quit")

    save_needed = False

    for idx, entry in enumerate(entries, 1):
        eid = entry.entry_id
        entry_dir = Path(entry.current_dir)

        # Fallback to draft_dir if current_dir doesn't exist
        if not entry_dir.exists():
            entry_dir = draft_dir / eid

        _display_entry(idx, total, eid, entry_dir)

        while True:
            cmd = _prompt_action()

            if cmd == "v":
                expected_path = entry_dir / "expected.json"
                if expected_path.exists():
                    print(expected_path.read_text())
                else:
                    print(_color("  expected.json not found", _RED))
                continue

            if cmd in ("a", "yes", "approve"):
                notes = ""
                try:
                    notes = input(f"  {_color('Notes (optional):', _DIM)} ").strip()
                except (EOFError, KeyboardInterrupt):
                    pass
                ok = approve_entry(eid, manifest, draft_dir, approved_dir,
                                   reviewer=reviewer, notes=notes)
                if ok:
                    save_needed = True
                    stats["approved"] += 1
                    print(_color(f"  ✓ Approved {eid}", _GREEN))
                else:
                    print(_color(f"  ✗ Failed to approve {eid}", _RED))
                break

            if cmd in ("r", "no", "reject"):
                reason = ""
                try:
                    reason = input(f"  {_color('Reason:', _RED)} ").strip()
                except (EOFError, KeyboardInterrupt):
                    pass
                ok = reject_entry(eid, manifest, draft_dir, rejected_dir, reason=reason)
                if ok:
                    save_needed = True
                    stats["rejected"] += 1
                    print(_color(f"  ✗ Rejected {eid}: {reason}", _RED))
                else:
                    print(_color(f"  ✗ Failed to reject {eid}", _RED))
                break

            if cmd in ("s", "skip", ""):
                stats["skipped"] += 1
                print(f"  — Skipped {eid}")
                break

            if cmd in ("q", "quit"):
                if save_needed:
                    save_manifest(manifest, manifest_path)
                print(f"\n{_header('Quit')}")
                _print_summary(stats)
                return stats

            print(_color("  Unknown command. Use a/r/s/v/q.", _YELLOW))

    if save_needed:
        save_manifest(manifest, manifest_path)

    print(f"\n{_header('Review Complete')}")
    _print_summary(stats)
    return stats


def _print_summary(stats: dict[str, int]) -> None:
    print(f"  {_color('Approved:', _GREEN)} {stats['approved']}  "
          f"{_color('Rejected:', _RED)} {stats['rejected']}  "
          f"Skipped: {stats['skipped']}")


# ── CLI entry ─────────────────────────────────────────────────────────

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
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Interactive batch review (default: all draft entries)")
    parser.add_argument("--review-status", type=str, default="draft",
                        help="Filter entries by review status for interactive mode (default: draft)")
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

    if args.interactive or not any([
        args.list, args.stats, args.approve, args.reject,
        args.promote, args.promote_all,
    ]):
        status_filter = args.review_status
        reviewable = ("parsed", "draft", "generated")
        entries = [
            e for e in manifest.entries
            if e.status in reviewable
            and (status_filter == "draft" or e.status == status_filter)
        ]

        _interactive_review(
            manifest, entries, draft_dir, approved_dir, rejected_dir,
            manifest_path, reviewer=args.reviewer,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
