from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.domain.literature.unified.workflow import literature_unified_workflow

MANIFEST_PATH = Path(__file__).resolve().parents[3] / "docs" / "data" / "v1.1-15-multilingual-manifest.json"


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _build_search_payload(paper: dict[str, Any]) -> dict[str, Any]:
    rp = paper.get("request_payload") or {}
    identifiers = rp.get("identifiers") or {}
    id_list = [f"{k}:{v}" for k, v in identifiers.items() if v]
    return {
        "action": "search",
        "query": rp.get("query", ""),
        "identifiers": id_list,
        "prefer": "api" if paper.get("entry_kind") == "api" else "web",
        "api_provider": paper.get("source") if paper.get("entry_kind") == "api" else None,
        "web_provider": paper.get("source") if paper.get("entry_kind") == "web" else None,
        "raw": True,
        "limit": 5,
    }


def _build_download_payload(paper: dict[str, Any], search_result: dict[str, Any]) -> dict[str, Any]:
    rp = paper.get("request_payload") or {}
    identifiers = rp.get("identifiers") or {}
    id_list = [f"{k}:{v}" for k, v in identifiers.items() if v]

    # Try to get detail_link from request_payload or first search item
    detail_link = rp.get("detail_link")
    selected_title = rp.get("selected_title")
    if not detail_link:
        items = search_result.get("items") or []
        if items:
            first = items[0]
            detail_link = first.get("url") or first.get("detail_link")
            if not selected_title:
                selected_title = first.get("title")

    return {
        "action": "download",
        "query": rp.get("query", ""),
        "identifiers": id_list,
        "prefer": "api" if paper.get("entry_kind") == "api" else "web",
        "api_provider": paper.get("source") if paper.get("entry_kind") == "api" else None,
        "web_provider": paper.get("source") if paper.get("entry_kind") == "web" else None,
        "raw": True,
        "limit": 5,
        "download_path": str(tempfile.mkdtemp(prefix="lit_test_")),
        "selected_index": 0,
        "selected_title": selected_title or rp.get("query", ""),
        "detail_link": detail_link,
    }


async def _test_paper(paper: dict[str, Any]) -> dict[str, Any]:
    paper_id = paper["paper_id"]
    result: dict[str, Any] = {
        "paper_id": paper_id,
        "title": paper.get("title"),
        "source": paper.get("source"),
        "entry_kind": paper.get("entry_kind"),
        "search": {},
        "download": {},
    }

    # Search
    search_payload = _build_search_payload(paper)
    try:
        search_start = time.monotonic()
        search_res = await literature_unified_workflow(search_payload)
        search_elapsed = time.monotonic() - search_start
        result["search"] = {
            "success": search_res.get("success"),
            "items_count": len(search_res.get("items") or []),
            "route": search_res.get("route"),
            "warnings": search_res.get("warnings"),
            "elapsed_seconds": round(search_elapsed, 2),
        }
    except Exception as exc:
        result["search"] = {"success": False, "error": str(exc)}
        return result

    # Download
    download_payload = _build_download_payload(paper, search_res)
    try:
        dl_start = time.monotonic()
        dl_res = await literature_unified_workflow(download_payload)
        dl_elapsed = time.monotonic() - dl_start
        downloads = dl_res.get("downloads") or []
        result["download"] = {
            "success": dl_res.get("success"),
            "downloads_count": len(downloads),
            "route": dl_res.get("route"),
            "warnings": dl_res.get("warnings"),
            "elapsed_seconds": round(dl_elapsed, 2),
        }
        if downloads:
            result["download"]["first_download"] = downloads[0]
    except Exception as exc:
        result["download"] = {"success": False, "error": str(exc)}

    return result


async def _run_all(papers: list[dict[str, Any]], verbose: bool = False) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for paper in papers:
        if verbose:
            print(f"Testing {paper['paper_id']} ...", file=sys.stderr)
        res = await _test_paper(paper)
        results.append(res)
        if verbose:
            print(f"  search={res['search'].get('success')} download={res['download'].get('success')}", file=sys.stderr)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 15-paper multilingual test suite")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="Path to manifest JSON")
    parser.add_argument("--paper-id", help="Run a single paper by ID")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    papers = manifest.get("papers", [])

    if args.paper_id:
        papers = [p for p in papers if p.get("paper_id") == args.paper_id]
        if not papers:
            print(f"Paper ID not found: {args.paper_id}", file=sys.stderr)
            return 1

    results = asyncio.run(_run_all(papers, verbose=args.verbose))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    # Summary table
    print(f"\n{'Paper ID':<25} {'Source':<12} {'Kind':<5} {'Search':<8} {'Download':<8} {'DL Route':<20} {'Warnings'}")
    print("-" * 140)
    for r in results:
        search_ok = "OK" if r["search"].get("success") else "FAIL"
        dl_ok = "OK" if r["download"].get("success") else "FAIL"
        route = r["download"].get("route") or {}
        route_str = f"{route.get('used','-')}:{route.get('api_provider') or route.get('web_provider','-')}"
        warnings = "; ".join(r["download"].get("warnings") or r["search"].get("warnings") or [])
        print(f"{r['paper_id']:<25} {r['source']:<12} {r['entry_kind']:<5} {search_ok:<8} {dl_ok:<8} {route_str:<20} {warnings}")

    total = len(results)
    search_ok = sum(1 for r in results if r["search"].get("success"))
    dl_ok = sum(1 for r in results if r["download"].get("success"))
    print("-" * 140)
    print(f"Total: {total} | Search OK: {search_ok} | Download OK: {dl_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
