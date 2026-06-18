"""Test full 134-field extraction on a single ground truth entry.

Reads field definitions from the main project's catalog, builds a comprehensive
LLM prompt, and runs extraction to see how many fields are actually populated.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

from loguru import logger

from src.config import get_config


def _parse_catalog_fields() -> dict[str, list[dict]]:
    """Parse field definitions directly from catalog.py source."""
    catalog_path = Path(__file__).resolve().parent.parent.parent / \
        "backend" / "src" / "core" / "cross_lingual_process_and_extract_evidence" / \
        "extract_evidence" / "catalog.py"
    content = catalog_path.read_text(encoding="utf-8")

    import re
    # Catalog format: EvidenceFieldSpec("A.gene_symbol", "A", "Variant Information", "Gene symbol", "Gene symbol", ...)
    # field_id = 1st arg, description = 5th arg
    pattern = re.compile(
        r'EvidenceFieldSpec\("([^"]+)",\s*"[^"]*",\s*"[^"]*",\s*"([^"]*)",\s*"([^"]*)"',
    )

    categories: dict[str, list[dict]] = {}
    for match in pattern.finditer(content):
        field_id = match.group(1)
        field_name = match.group(2)
        description = match.group(3)
        cat = field_id.split(".")[0]
        categories.setdefault(cat, []).append({
            "field_id": field_id,
            "description": description or field_name,
        })

    return categories


def _build_full_prompt() -> str:
    """Build a prompt covering all 134 fields from the catalog."""
    categories = _parse_catalog_fields()

    cat_names = {
        "A": "Variant Information",
        "B": "Case/Phenotype Information",
        "C": "Segregation/Family Information",
        "D": "Population/Frequency Information",
        "E": "Computational/Prediction Evidence",
        "F": "Functional Evidence",
        "G": "Case-Control Evidence",
        "H": "Contradiction/Exclusion Evidence",
        "I": "Gene Function/Experimental Evidence",
        "J": "Authority/Time Validity",
    }

    field_lines = []
    total = 0
    for cat in sorted(categories):
        field_lines.append(f"\n### Category {cat}: {cat_names.get(cat, cat)}")
        for spec in categories[cat]:
            desc = spec["description"]
            field_lines.append(f"- {spec['field_id']}: {desc}")
            total += 1

    fields_text = "\n".join(field_lines)

    return f"""\
You are a medical genetics expert extracting structured evidence from a \
genetics research article. Extract ALL applicable fields from the article text.

For each field, output the value if found in the article, or empty string if not found. \
Do NOT fabricate data not present in the article.

## Fields to extract ({total} total)

{fields_text}

## Output format

Respond with a valid JSON object where keys are field_ids and values are strings. \
For fields with multiple values, join them with "; ". \
If a field is not mentioned in the article, use empty string "".

Example:
{{
  "A.gene_symbol": "MECP2",
  "A.variant_hgvs_c": "c.808C>T",
  "B.disease_diagnosis": "Rett syndrome",
  ...
}}

IMPORTANT: Include ALL {total} field_ids in the output, even if the value is "".
"""


def _count_populated(result: dict) -> dict:
    """Count how many fields were populated."""
    populated = {k: v for k, v in result.items() if v and v.strip()}
    by_cat: Counter = Counter()
    for fid in populated:
        cat = fid.split(".")[0]
        by_cat[cat] += 1
    return {
        "total_populated": len(populated),
        "total_empty": len(result) - len(populated),
        "by_category": dict(sorted(by_cat.items())),
        "populated_fields": sorted(populated.keys()),
    }


async def test_entry(entry_id: str, config) -> dict:
    """Run full-field extraction on a single entry."""
    gt_dir = config.resolved_paths["ground_truth_dir"]
    entry_dir = gt_dir / entry_id
    source_md_path = entry_dir / "source.md"

    if not source_md_path.exists():
        logger.error("source.md not found for {}", entry_id)
        return {}

    source_md = source_md_path.read_text(encoding="utf-8")

    # Read language
    meta_path = entry_dir / "meta.json"
    language = "en"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        language = meta.get("language", "en")

    # Build prompt and call LLM
    prompt = _build_full_prompt()
    logger.info("Testing {} (lang={}, md={} chars, prompt={} chars)",
                entry_id, language, len(source_md), len(prompt))

    from langchain_core.messages import HumanMessage, SystemMessage

    client = config.build_llm_client()
    fallback = config.build_fallback_client()

    # Truncate if too long
    max_text = 80000
    if len(source_md) > max_text:
        source_md = source_md[:max_text] + "\n\n[TRUNCATED]"

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Article language: {language}\n\nArticle text:\n\n{source_md}"),
    ]

    parsed = None
    for llm in [client, fallback]:
        if llm is None:
            continue
        try:
            t0 = time.time()
            response = await llm.ainvoke(messages)
            elapsed = time.time() - t0
            logger.info("LLM responded in {:.1f}s", elapsed)
            content = response.content
            json_match = __import__("re").search(r"\{[\s\S]*\}", content)
            if json_match:
                parsed = json.loads(json_match.group())
                break
        except Exception as e:
            logger.warning("LLM failed: {}", e)

    if parsed is None:
        logger.error("All LLM providers failed for {}", entry_id)
        return {}

    stats = _count_populated(parsed)
    logger.info("Populated: {}/134 fields", stats["total_populated"])
    for cat, count in stats["by_category"].items():
        logger.info("  {}: {} fields", cat, count)

    return {"entry_id": entry_id, "language": language, "stats": stats, "raw": parsed}


async def main():
    entry_id = sys.argv[1] if len(sys.argv) > 1 else "rett_009"
    config = get_config()

    result = await test_entry(entry_id, config)
    if not result:
        return

    # Save full result
    output_path = Path("test_full_fields_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info("Full result saved to {}", output_path)

    # Print summary
    stats = result["stats"]
    total = len(result.get("raw", {}))
    print(f"\n{'='*60}")
    print(f"Entry: {result['entry_id']} (lang={result['language']})")
    print(f"Populated: {stats['total_populated']}/{total} fields")
    print(f"Empty: {stats['total_empty']}/{total} fields")
    print(f"\nBy category:")
    cat_totals = {}
    cats = _parse_catalog_fields()
    for cat, fields in cats.items():
        cat_totals[cat] = len(fields)
    for cat, count in stats["by_category"].items():
        print(f"  {cat}: {count}/{cat_totals.get(cat, '?')}")
    print(f"\nPopulated field_ids:")
    for fid in stats["populated_fields"]:
        val = result["raw"].get(fid, "")
        val_display = val[:80] + "..." if len(val) > 80 else val
        print(f"  {fid}: {val_display}")


if __name__ == "__main__":
    asyncio.run(main())
