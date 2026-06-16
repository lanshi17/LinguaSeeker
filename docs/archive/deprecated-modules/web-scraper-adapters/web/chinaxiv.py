"""ChinaXiv web provider — Chinese preprint server."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import (
    choose_item,
    crawl4ai_search,
    download_pdf_from_candidates,
    extract_pdf_links_from_html,
)

BASE_URL = "http://www.chinaxiv.org"


async def chinaxiv_search(
    query: str,
    limit: int = 20,
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Search ChinaXiv for preprints."""
    warnings: List[str] = []

    search_url = f"{BASE_URL}/search?q={query}"

    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "authors": {"type": "string"},
                        "year": {"type": "string"},
                        "source_link": {"type": "string"},
                        "subjects": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }

    instruction = f"Extract at most {limit} items. Fields: title, authors, year, source_link, subjects."

    js_code = """
    (async () => {
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));
      await sleep(2000);
    })();
    """

    raw_items, crawl_warnings = await crawl4ai_search(
        url=search_url,
        js_code=js_code,
        wait_xpath="//div[contains(@class,'result')]",
        schema=schema,
        instruction=instruction,
        limit=limit,
        timeout_ms=timeout_ms,
    )
    warnings.extend(crawl_warnings)

    items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_items):
        items.append({
            "title": raw.get("title", ""),
            "authors": raw.get("authors"),
            "year": raw.get("year"),
            "source_link": raw.get("source_link"),
            "subjects": raw.get("subjects"),
            "source": "chinaxiv",
            "index": idx,
        })

    return {"success": bool(items), "items": items[:limit], "warnings": warnings}


async def chinaxiv_download(
    query: str,
    detail_link: Optional[str] = None,
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    download_path: str = "./downloads",
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Download a paper from ChinaXiv."""
    warnings: List[str] = []

    source_link = detail_link
    if not source_link:
        search_result = await chinaxiv_search(query, limit=20, timeout_ms=timeout_ms)
        if not search_result.get("success") or not search_result.get("items"):
            return {"success": False, "warnings": ["no_search_results"]}

        chosen = choose_item(search_result["items"], selected_index, selected_title)
        if not chosen:
            return {"success": False, "warnings": ["invalid_selected_index"]}
        source_link = chosen.get("source_link")

    if not source_link:
        return {"success": False, "warnings": ["missing_source_link"]}

    import httpx
    pdf_links: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            page = await client.get(source_link, headers={"user-agent": "Mozilla/5.0"})
            if page.status_code < 400:
                pdf_links.extend(extract_pdf_links_from_html(page.text, str(page.url)))
    except Exception as exc:
        warnings.append(f"http_parse_failed:{exc}")

    if not pdf_links:
        return {"success": False, "warnings": warnings + ["pdf_not_found"]}

    file_path, final_url, dl_warnings = await download_pdf_from_candidates(
        pdf_links, download_path, selected_title or query
    )
    warnings.extend(dl_warnings)

    if not file_path:
        return {"success": False, "warnings": warnings + ["download_failed"]}

    return {"success": True, "pdf_url": final_url, "file_path": file_path, "warnings": warnings}
