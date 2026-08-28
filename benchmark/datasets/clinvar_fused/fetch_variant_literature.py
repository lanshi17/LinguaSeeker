"""Fetch PMC literature for fused ClinGen+ClinVar benchmark entries.

Search strategy:
1. Primary: gene_symbol + variant_hgvs_name + OPEN_ACCESS:y
2. Fallback: gene_symbol + disease_label + OPEN_ACCESS:y
3. Prefer results with PMC full text
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_CONCURRENCY = 3


async def search_europepmc(
    client: httpx.AsyncClient,
    query: str,
) -> dict | None:
    """Search EuropePMC for best matching article with PMC full text."""
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

        # Prefer results with PMC ID
        for r in results:
            pmcid = r.get("pmcid", "")
            if pmcid:
                return {
                    "pmid": r.get("pmid", ""),
                    "pmcid": pmcid,
                    "title": r.get("title", ""),
                    "journal": r.get("journalTitle", ""),
                    "year": r.get("pubYear", ""),
                    "pdf_url": f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}?pdf=render",
                    "matched_query": query,
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
                "matched_query": query,
            }
    except Exception as e:
        print(f"  Error searching [{query[:60]}...]: {e}")
    return None


def _clean_variant_name(name: str) -> str:
    """Extract a searchable short name from HGVS notation."""
    # Remove transcript prefix
    name = re.sub(r"^[NXYM]{2}_[0-9]+\.[0-9]+(?:\([^)]*\))?\s*:\s*", "", name)
    # Remove protein part in parentheses
    name = re.sub(r"\s*\(p\.[^)]*\)", "", name)
    return name.strip()


async def fetch_one(
    client: httpx.AsyncClient,
    entry: dict,
    sem: asyncio.Semaphore,
) -> dict | None:
    """Fetch literature for one fused entry."""
    gene = entry.get("clingen", {}).get("gene_symbol", "") or entry.get("gene_symbol", "")
    disease = entry.get("clingen", {}).get("disease_label", "") or entry.get("disease_label", "")
    variants = entry.get("clinvar_variants", [])

    async with sem:
        # Strategy 1: gene + variant
        for v in variants[:2]:
            variant_name = v.get("hgvs_name", "") or v.get("hgvs_c", "")
            if variant_name:
                short_name = _clean_variant_name(variant_name)
                query = f'"{gene}" AND "{short_name}" AND OPEN_ACCESS:y'
                result = await search_europepmc(client, query)
                if result and result.get("pmcid"):
                    await asyncio.sleep(0.3)
                    return result

        # Strategy 2: gene + disease
        if gene and disease:
            query = f'"{gene}" AND "{disease}" AND OPEN_ACCESS:y'
            result = await search_europepmc(client, query)
            if result:
                await asyncio.sleep(0.3)
                return result

        # Strategy 3: gene only (broad)
        if gene:
            query = f'{gene} AND OPEN_ACCESS:y'
            result = await search_europepmc(client, query)
            await asyncio.sleep(0.3)
            return result

    return None


async def fetch_all(target_count: int | None = None) -> None:
    """Fetch literature for all fused entries."""
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    if not selection_path.exists():
        print("ERROR: selection.json not found. Run select_fused_entries.py first.")
        return

    entries = json.loads(selection_path.read_text(encoding="utf-8"))
    if target_count:
        entries = entries[:target_count]
    print(f"Fetching literature for {len(entries)} entries...")

    sem = asyncio.Semaphore(_CONCURRENCY)
    results: dict[str, dict | None] = {}

    async with httpx.AsyncClient() as client:
        async def process_one(entry: dict) -> None:
            entry_id = entry["entry_id"]
            result = await fetch_one(client, entry, sem)
            results[entry_id] = result
            gene = entry.get("clingen", {}).get("gene_symbol", "")
            status = "OK" if result else "NO RESULT"
            pmcid = (result or {}).get("pmcid", "-")
            strategy = (result or {}).get("matched_query", "-")[:40]
            print(f"  {entry_id}: {gene:10s} | {status:10s} | {pmcid:12s} | {strategy}")

        await asyncio.gather(*(process_one(e) for e in entries))

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
            entry["literature_search_strategy"] = lit.get("matched_query", "")
            found_count += 1
            if lit.get("pmcid"):
                pmc_count += 1

    # Save
    selection_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for entry in entries:
        entry_dir = GROUND_TRUTH_DIR / entry["entry_id"]
        entry_dir.mkdir(parents=True, exist_ok=True)
        (entry_dir / "expected.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"\nSummary: {found_count}/{len(entries)} found, {pmc_count} with PMC full text")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch literature for fused benchmark entries")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entries")
    args = parser.parse_args()

    asyncio.run(fetch_all(target_count=args.limit))
