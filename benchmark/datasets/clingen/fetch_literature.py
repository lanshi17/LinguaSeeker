"""Fetch PMID/PMC ID from EuropePMC for each ClinGen ground truth entry.

For each entry, searches EuropePMC with gene + disease keywords and selects
the most relevant result with PMC full text available.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# Max concurrent requests to EuropePMC
_CONCURRENCY = 3


async def search_europepmc(
    client: httpx.AsyncClient,
    gene: str,
    disease: str,
) -> dict | None:
    """Search EuropePMC for best matching article with PMC full text."""
    query = f'"{gene}" AND "{disease}" AND OPEN_ACCESS:y'
    params = {
        "query": query,
        "format": "json",
        "pageSize": 5,
        "resultType": "core",
    }
    try:
        resp = await client.get(EUROPEPMC_SEARCH, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("resultList", {}).get("result", [])
        if not results:
            # Try broader search without quotes
            params["query"] = f'{gene} AND {disease} AND OPEN_ACCESS:y'
            resp = await client.get(EUROPEPMC_SEARCH, params=params, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("resultList", {}).get("result", [])

        # Prefer results with PMC ID
        for r in results:
            pmcid = r.get("pmcid", "")
            pmid = r.get("pmid", "")
            if pmcid:
                return {
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "title": r.get("title", ""),
                    "journal": r.get("journalTitle", ""),
                    "year": r.get("pubYear", ""),
                    "pdf_url": f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}?pdf=render",
                }

        # Fallback: return first result even without PMC
        if results:
            r = results[0]
            return {
                "pmid": r.get("pmid", ""),
                "pmcid": r.get("pmcid", ""),
                "title": r.get("title", ""),
                "journal": r.get("journalTitle", ""),
                "year": r.get("pubYear", ""),
                "pdf_url": None,
            }
    except Exception as e:
        print(f"  Error searching for {gene}/{disease}: {e}")
    return None


async def fetch_all():
    """Fetch literature info for all ground truth entries."""
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))

    sem = asyncio.Semaphore(_CONCURRENCY)
    results = {}

    async def process_one(client: httpx.AsyncClient, entry: dict):
        entry_id = entry["entry_id"]
        gene = entry["gene_symbol"]
        disease = entry["disease_label"]
        async with sem:
            result = await search_europepmc(client, gene, disease)
            results[entry_id] = result
            status = "OK" if result else "NO RESULT"
            pmcid = result.get("pmcid", "-") if result else "-"
            print(f"  {entry_id}: {gene:10s} | {status:10s} | {pmcid}")
            # Rate limit
            await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        tasks = [process_one(client, e) for e in entries]
        await asyncio.gather(*tasks)

    # Update entries with literature info
    found_count = 0
    pmc_count = 0
    for entry in entries:
        entry_id = entry["entry_id"]
        lit = results.get(entry_id)
        if lit:
            entry["source_pmid"] = lit.get("pmid")
            entry["source_pmc"] = lit.get("pmcid")
            entry["source_pdf_url"] = lit.get("pdf_url")
            entry["source_title"] = lit.get("title")
            entry["source_journal"] = lit.get("journal")
            entry["source_year"] = lit.get("year")
            found_count += 1
            if lit.get("pmcid"):
                pmc_count += 1

    # Save updated selection
    selection_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    # Update individual entries
    for entry in entries:
        entry_dir = GROUND_TRUTH_DIR / entry["entry_id"]
        expected_path = entry_dir / "expected.json"
        expected_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSummary: {found_count}/{len(entries)} found, {pmc_count} with PMC full text")


if __name__ == "__main__":
    asyncio.run(fetch_all())
