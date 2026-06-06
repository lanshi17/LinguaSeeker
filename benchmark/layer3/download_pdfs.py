"""Download PMC full text via NCBI efetch API and convert to markdown.

Uses the proxy from config/environments/development.yaml for external requests.
The efetch API returns JATS XML which we convert to pipeline-friendly markdown.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import yaml

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_CONCURRENCY = 2
_TIMEOUT = 120.0


def load_proxy() -> str | None:
    """Load proxy from config/environments/development.yaml."""
    config_path = Path(__file__).resolve().parent.parent.parent / "backend" / "config" / "environments" / "development.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        proxy = cfg.get("network", {}).get("proxy", "")
        if proxy:
            return proxy
    return None


def xml_to_markdown(xml_text: str) -> str:
    """Convert JATS XML article to markdown text."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Fallback: strip tags
        text = re.sub(r"<[^>]+>", " ", xml_text)
        return re.sub(r"\s+", " ", text).strip()

    parts: list[str] = []

    # Title
    for title in root.iter("article-title"):
        title_text = _extract_text(title)
        if title_text:
            parts.append(f"# {title_text}\n")

    # Abstract
    for abstract in root.iter("abstract"):
        abstract_text = _extract_text(abstract)
        if abstract_text:
            parts.append(f"## Abstract\n\n{abstract_text}\n")

    # Body sections
    for body in root.iter("body"):
        for section in body.iter("sec"):
            sec_title = section.find("title")
            sec_text = _extract_text(sec_title) if sec_title is not None else ""
            if sec_text:
                parts.append(f"\n## {sec_text}\n")
            # Extract paragraphs
            for p in section.findall("p"):
                p_text = _extract_text(p)
                if p_text:
                    parts.append(f"{p_text}\n")

        # Direct paragraphs in body (not in sections)
        for p in body.findall("p"):
            p_text = _extract_text(p)
            if p_text:
                parts.append(f"{p_text}\n")

    # Tables
    for table in root.iter("table"):
        table_text = _extract_table(table)
        if table_text:
            parts.append(f"\n{table_text}\n")

    result = "\n".join(parts)
    if len(result) < 100:
        # Fallback: extract all text
        result = _extract_text(root)
    return result


def _extract_text(element: ET.Element) -> str:
    """Recursively extract text from XML element."""
    parts: list[str] = []
    if element.text:
        parts.append(element.text.strip())
    for child in element:
        child_text = _extract_text(child)
        if child_text:
            parts.append(child_text)
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(parts)


def _extract_table(table: ET.Element) -> str:
    """Extract table content as markdown."""
    rows: list[str] = []
    for tr in table.iter("tr"):
        cells: list[str] = []
        for td in tr.iter("td"):
            cells.append(_extract_text(td))
        for th in tr.iter("th"):
            cells.append(f"**{_extract_text(th)}**")
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


async def fetch_article(
    client: httpx.AsyncClient,
    entry: dict,
    sem: asyncio.Semaphore,
) -> bool:
    """Fetch PMC article XML and convert to markdown."""
    entry_id = entry["entry_id"]
    pmcid = entry.get("source_pmc", "")
    if not pmcid:
        print(f"  {entry_id}: no PMC ID, skipping")
        return False

    entry_dir = GROUND_TRUTH_DIR / entry_id
    md_path = entry_dir / "source.md"
    if md_path.exists() and md_path.stat().st_size > 500:
        print(f"  {entry_id}: already exists ({md_path.stat().st_size/1024:.1f} KB)")
        return True

    pmc_num = pmcid.replace("PMC", "")
    params = {"db": "pmc", "id": pmc_num, "rettype": "xml"}

    async with sem:
        try:
            resp = await client.get(EFETCH_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            xml_text = resp.text

            if len(xml_text) < 200:
                print(f"  {entry_id}: response too small ({len(xml_text)} chars)")
                return False

            md = xml_to_markdown(xml_text)
            if len(md) < 100:
                print(f"  {entry_id}: extracted text too small ({len(md)} chars)")
                return False

            md_path.write_text(md, encoding="utf-8")
            print(f"  {entry_id}: saved {len(md)/1024:.1f} KB text")
            return True

        except Exception as e:
            print(f"  {entry_id}: fetch failed: {e}")
            return False


async def main():
    proxy = load_proxy()
    print(f"Proxy: {proxy or 'none'}")

    selection_path = GROUND_TRUTH_DIR / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))

    sem = asyncio.Semaphore(_CONCURRENCY)
    transport_kwargs = {}
    if proxy:
        transport_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**transport_kwargs) as client:
        tasks = [fetch_article(client, e, sem) for e in entries]
        results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r)
    print(f"\nFetched: {success}/{len(entries)} articles")


if __name__ == "__main__":
    asyncio.run(main())
