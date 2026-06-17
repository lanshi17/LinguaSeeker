"""Rewrite sample report artifact paths from legacy worktree to current checkout."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

LEGACY_PREFIX = "/data/yangzs/.config/superpowers/worktrees/01_ACMG_Lingua/feature/bibm-multilingual-source-strategy/"
CHECKOUT_ROOT = "/data/yangzs/Projects/01_ACMG_Lingua"


def rewrite(payload, checkout_root: str) -> tuple[object, int]:
    rewritten = 0
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            if key in {"artifact_path", "source_pdf_path"} and isinstance(value, str) and value.startswith(LEGACY_PREFIX):
                relative = value[len(LEGACY_PREFIX):]
                out[key] = f"{checkout_root}/{relative}"
                rewritten += 1
            else:
                child, n = rewrite(value, checkout_root)
                out[key] = child
                rewritten += n
        return out, rewritten
    if isinstance(payload, list):
        out_list = []
        for item in payload:
            child, n = rewrite(item, checkout_root)
            out_list.append(child)
            rewritten += n
        return out_list, rewritten
    return payload, rewritten


def main() -> int:
    reports = [Path(arg) for arg in sys.argv[1:]]
    if not reports:
        print("usage: rewrite_sample_paths.py <report.json> [<report2.json> ...]")
        return 1
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    for report in reports:
        payload = json.loads(report.read_text(encoding="utf-8"))
        rewritten_payload, count = rewrite(payload, CHECKOUT_ROOT)
        if count == 0:
            print(f"SKIP (no legacy paths): {report}")
            continue
        new_path = report.parent / f"{report.stem.rsplit('_', 1)[0]}_{timestamp}.json"
        # Avoid collision: if same stem prefix exists, append a suffix
        if new_path.exists():
            new_path = report.parent / f"{report.stem}_{timestamp}_relpath.json"
        new_path.write_text(json.dumps(rewritten_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"REWRITE {count} paths: {report.name} -> {new_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
