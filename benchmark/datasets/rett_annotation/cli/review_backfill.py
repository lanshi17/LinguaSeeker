"""Interactive field-level review for backfilled ground truth entries.

Displays new fields (added by the 57→59 expansion) alongside source text,
allowing the reviewer to approve, edit, or skip each entry.

Usage:
    uv run python cli/review_backfill.py
    uv run python cli/review_backfill.py --entry rett_009
    uv run python cli/review_backfill.py --stats
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_config

# ── Original 13 fields (pre-expansion) ──────────────────────────────
ORIGINAL_FIELDS = {
    "A.gene_symbol", "A.gene_disease_relationship",
    "A.variant_hgvs_c", "A.variant_hgvs_p", "A.variant_type",
    "A.functional_domain_or_hotspot",
    "B.disease_diagnosis", "B.mode_of_inheritance_reported",
    "B.hpo_terms", "B.clinical_phenotypes",
    "B.sex", "B.age_of_onset",
    "C.de_novo_status",
}

# ── ANSI ─────────────────────────────────────────────────────────────
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


def _load_entry(entry_dir: Path) -> dict | None:
    p = entry_dir / "expected.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def _save_entry(entry_dir: Path, data: dict) -> None:
    p = entry_dir / "expected.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_new_fields(expected: dict) -> list[dict]:
    """Extract fields added by the expansion (not in ORIGINAL_FIELDS)."""
    return [e for e in expected.get("expected_evidence", [])
            if e["field_id"] not in ORIGINAL_FIELDS]


def _display_entry(idx: int, total: int, entry_id: str, expected: dict,
                   source_text: str) -> None:
    """Display an entry's new fields with source context."""
    print(f"\n{'═' * 70}")
    print(_c(f"  Entry {idx}/{total}: {entry_id}", _BOLD))
    print(f"  Language: {expected.get('source_language', '?')}  |  "
          f"Title: {(expected.get('source_title') or '?')[:60]}")
    print(f"  Gene: {expected.get('gene_symbol', '?')}  |  "
          f"Disease: {expected.get('disease_label', '?')}")

    variants = expected.get("variants", [])
    if variants:
        for v in variants:
            hgvs = v.get("hgvs_c") or v.get("hgvs_p") or "?"
            print(f"  Variant: {hgvs} ({v.get('variant_type', '?')})")

    new_fields = _get_new_fields(expected)
    print(f"\n  {_c('NEW FIELDS', _MAGENTA)} ({len(new_fields)} added)")
    print(f"  {'─' * 60}")

    # Group by category
    by_cat: dict[str, list[dict]] = {}
    for f in new_fields:
        cat = f["field_id"].split(".")[0]
        by_cat.setdefault(cat, []).append(f)

    for cat in sorted(by_cat):
        cat_name = {
            "A": "Variant", "B": "Case/Phenotype", "C": "Segregation",
            "D": "Population", "E": "Computational", "F": "Functional",
            "G": "Case-Control", "I": "Gene Function", "J": "Authority",
        }.get(cat, cat)
        print(f"\n  {_c(f'[{cat}] {cat_name}', _CYAN)}")
        for f in by_cat[cat]:
            fid = f["field_id"]
            val = f.get("value", "")
            val_display = val[:80] + "..." if len(val) > 80 else val
            color = _GREEN if val else _DIM
            print(f"    {fid:<42} {_c(val_display or '(empty)', color)}")

    # Show source excerpt (first 2000 chars)
    print(f"\n  {_c('SOURCE TEXT (excerpt)', _DIM)}")
    excerpt = source_text[:2000]
    for line in excerpt.split("\n")[:30]:
        print(f"  {_c(line, _DIM)}")
    if len(source_text) > 2000:
        print(f"  {_c(f'... ({len(source_text)} chars total)', _DIM)}")


def _prompt() -> str:
    try:
        return input(
            f"\n  {_c('[a]', _GREEN)} approve  "
            f"{_c('[e]', _YELLOW)} edit field  "
            f"{_c('[s]', _DIM)} skip  "
            f"{_c('[v]', _CYAN)} view full JSON  "
            f"{_c('[q]', _DIM)} quit  > "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"


def _edit_field(expected: dict) -> bool:
    """Let the reviewer edit a specific field value. Returns True if changed."""
    new_fields = _get_new_fields(expected)
    print(f"\n  {_c('Editable fields:', _YELLOW)}")
    for i, f in enumerate(new_fields, 1):
        val = f.get("value", "")[:50]
        print(f"    {i}. {f['field_id']}: {val or '(empty)'}")

    try:
        choice = input(f"  Field number (1-{len(new_fields)}, or 0 to cancel): ").strip()
        if not choice or choice == "0":
            return False
        idx = int(choice) - 1
        if idx < 0 or idx >= len(new_fields):
            print(_c("  Invalid choice", _RED))
            return False
    except (ValueError, EOFError, KeyboardInterrupt):
        return False

    target = new_fields[idx]
    print(f"  Current: {target['value']}")
    try:
        new_val = input(f"  New value (empty to clear): ").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    # Update in the expected_evidence list
    for ev in expected.get("expected_evidence", []):
        if ev["field_id"] == target["field_id"]:
            ev["value"] = new_val
            print(_c(f"  ✓ Updated {target['field_id']}", _GREEN))
            return True
    return False


def review_entry(entry_id: str, entry_dir: Path, gt_dir: Path) -> str:
    """Review a single entry. Returns 'approved', 'skipped', or 'quit'."""
    expected = _load_entry(entry_dir)
    if not expected:
        print(_c(f"  expected.json not found for {entry_id}", _RED))
        return "skipped"

    source_path = entry_dir / "source.md"
    source_text = source_path.read_text(encoding="utf-8") if source_path.exists() else ""

    while True:
        _display_entry(1, 1, entry_id, expected, source_text)
        cmd = _prompt()

        if cmd in ("a", "approve"):
            # Mark as reviewed in meta
            meta_path = entry_dir / "meta.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
            else:
                meta = {}
            meta["backfill_reviewed"] = True
            meta["review_status"] = "ground_truth"
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            print(_c(f"  ✓ Approved {entry_id}", _GREEN))
            return "approved"

        elif cmd in ("e", "edit"):
            if _edit_field(expected):
                _save_entry(entry_dir, expected)
                print(_c("  Saved.", _GREEN))
            continue

        elif cmd in ("v", "view"):
            print(json.dumps(expected, indent=2, ensure_ascii=False)[:5000])
            continue

        elif cmd in ("s", "skip", ""):
            print(f"  — Skipped {entry_id}")
            return "skipped"

        elif cmd in ("q", "quit"):
            return "quit"

        else:
            print(_c("  Unknown command. Use a/e/s/v/q.", _YELLOW))


def batch_review(gt_dir: Path, entry_id: str | None = None) -> None:
    """Run batch review on all or one ground truth entry."""
    entries = []
    for d in sorted(gt_dir.iterdir()):
        if not d.is_dir():
            continue
        ep = d / "expected.json"
        if not ep.exists():
            continue
        if entry_id and d.name != entry_id:
            continue
        meta_path = d / "meta.json"
        already_reviewed = False
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            already_reviewed = meta.get("backfill_reviewed", False)
        entries.append((d.name, d, already_reviewed))

    if entry_id:
        entries = [(eid, edir, rev) for eid, edir, rev in entries if eid == entry_id]
        if not entries:
            print(_c(f"Entry {entry_id} not found", _RED))
            return

    unreviewed = [(eid, edir) for eid, edir, rev in entries if not rev]
    reviewed = [(eid, edir) for eid, edir, rev in entries if rev]

    print(f"\n{'═' * 70}")
    print(_c(f"  Backfill Review — {len(entries)} entries", _BOLD))
    print(f"  Already reviewed: {len(reviewed)}  |  Pending: {len(unreviewed)}")

    if not unreviewed:
        print(_c("  All entries reviewed!", _GREEN))
        return

    stats = {"approved": 0, "skipped": 0}
    for idx, (eid, edir) in enumerate(unreviewed, 1):
        result = review_entry(eid, edir, gt_dir)
        if result == "quit":
            break
        elif result == "approved":
            stats["approved"] += 1
        else:
            stats["skipped"] += 1

    print(f"\n{'═' * 70}")
    print(_c(f"  Review Summary", _BOLD))
    print(f"  Approved: {_c(str(stats['approved']), _GREEN)}  "
          f"Skipped: {stats['skipped']}")


def show_stats(gt_dir: Path) -> None:
    """Show review statistics."""
    total = 0
    reviewed = 0
    field_counts = []
    by_lang = {}

    for d in sorted(gt_dir.iterdir()):
        if not d.is_dir():
            continue
        ep = d / "expected.json"
        if not ep.exists():
            continue
        total += 1

        with open(ep) as f:
            data = json.load(f)

        new_fields = _get_new_fields(data)
        populated = [f for f in new_fields if f.get("value")]
        field_counts.append(len(populated))

        lang = data.get("source_language", "?")
        by_lang.setdefault(lang, {"count": 0, "new_fields": []})
        by_lang[lang]["count"] += 1
        by_lang[lang]["new_fields"].append(len(populated))

        meta_path = d / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("backfill_reviewed"):
                reviewed += 1

    import statistics
    print(f"\n{'═' * 70}")
    print(_c("  Backfill Review Statistics", _BOLD))
    print(f"  Total entries: {total}")
    print(f"  Reviewed: {reviewed}  |  Pending: {total - reviewed}")
    print(f"  New fields per entry: min={min(field_counts)}, "
          f"max={max(field_counts)}, mean={statistics.mean(field_counts):.1f}, "
          f"median={statistics.median(field_counts):.1f}")
    print(f"\n  By language:")
    for lang in sorted(by_lang):
        info = by_lang[lang]
        vals = info["new_fields"]
        print(f"    {lang}: n={info['count']}, "
              f"new_fields mean={statistics.mean(vals):.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review backfilled ground truth fields")
    parser.add_argument("--entry", type=str, help="Review a specific entry")
    parser.add_argument("--stats", action="store_true", help="Show review statistics")
    args = parser.parse_args()

    cfg = get_config()
    gt_dir = cfg.resolved_paths["ground_truth_dir"]

    if args.stats:
        show_stats(gt_dir)
    else:
        batch_review(gt_dir, entry_id=args.entry)


if __name__ == "__main__":
    main()
