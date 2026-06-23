"""Convert parkinson_literature processed data to ground_truth format.

Creates benchmark/data/ground_truth/parkinson/ with:
- selection.json
- parkinson_XXX/ per entry (source.md, expected.json, meta.json)

Only entries with both downloaded PDF and variant data are included.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import fitz  # pymupdf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# HGNC canonical gene symbols for PD-associated genes
# PARK2 is not HGNC canonical; PRKN is. PARKIN is the protein name.
GENE_CANONICAL: dict[str, str] = {
    "PARK2": "PRKN",
    "PRKN": "PRKN",
    "PARKIN": "PRKN",
    "LRRK2": "LRRK2",
    "PINK1": "PINK1",
    "GBA": "GBA",      # GBA (not GBA1) per PD literature convention
    "VPS35": "VPS35",
    "GIGYF2": "GIGYF2",
    "SNCA": "SNCA",
    "PARK7": "PARK7",
    "DJ1": "PARK7",
    "DJ-1": "PARK7",
    "CHCHD2": "CHCHD2",
    "ATP13A2": "ATP13A2",
    "PLA2G6": "PLA2G6",
    "FBXO7": "FBXO7",
}

# Gene-specific inheritance (explicit from literature consensus)
GENE_INHERITANCE: dict[str, str] = {
    "PRKN": "AR",
    "PINK1": "AR",
    "LRRK2": "AD",
    "VPS35": "AD",
    "GBA": "AR",       # Gaucher's is AR; PD risk factor
    "GIGYF2": "AD",
    "SNCA": "AD",
}

# Gene name patterns for title extraction (order matters — longer patterns first)
_GENE_TITLE_PATTERNS: list[tuple[str, str]] = [
    (r"\bLRRK2\b", "LRRK2"),
    (r"\bPINK1\b", "PINK1"),
    (r"\bGIGYF2\b", "GIGYF2"),
    (r"\bCHCHD2\b", "CHCHD2"),
    (r"\bATP13A2\b", "ATP13A2"),
    (r"\bPLA2G6\b", "PLA2G6"),
    (r"\bFBXO7\b", "FBXO7"),
    (r"\bVPS35\b", "VPS35"),
    (r"\bSNCA\b", "SNCA"),
    (r"\bPARK7\b", "PARK7"),
    (r"\bDJ-?1\b", "PARK7"),
    (r"\bGBA1?\b", "GBA"),
    (r"\bglucocerebrosidase\b", "GBA"),
    (r"\bgaucher", "GBA"),
    (r"\bparkin\b", "PRKN"),
    (r"\bPRKN\b", "PRKN"),
    (r"\bPARK2\b", "PRKN"),
]
PROCESSED_DIR = REPO_ROOT / "benchmark" / "data" / "processed" / "parkinson_literature"
MANIFEST_PATH = PROCESSED_DIR / "publications_full" / "manifest.json"
VARIANT_PATH = PROCESSED_DIR / "table2_seq_study_var.jsonl"
PUB_INFO_PATH = PROCESSED_DIR / "table7_publication_info.jsonl"
PDF_DIR = PROCESSED_DIR / "publications_full" / "pdfs"
OUTPUT_DIR = REPO_ROOT / "benchmark" / "data" / "ground_truth" / "parkinson"


def load_manifest() -> dict[str, dict]:
    """Load manifest and index by PMID."""
    with open(MANIFEST_PATH) as f:
        data = json.load(f)
    records = data.get("records", data.get("entries", []))
    return {r["pmid"]: r for r in records if r.get("pmid")}


def load_variants() -> dict[str, list[dict]]:
    """Load variant table, grouped by PMID."""
    by_pmid: dict[str, list[dict]] = defaultdict(list)
    with open(VARIANT_PATH) as f:
        for line in f:
            row = json.loads(line)
            pmid = row.get("Pubmed_id", "")
            if pmid:
                by_pmid[pmid].append(row)
    return by_pmid


def load_pub_info() -> dict[str, dict]:
    """Load publication info, indexed by PMID."""
    by_pmid: dict[str, dict] = {}
    with open(PUB_INFO_PATH) as f:
        for line in f:
            row = json.loads(line)
            pmid = row.get("Pubmed_id", "")
            if pmid and row.get("Title"):
                by_pmid[pmid] = row
    return by_pmid


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pymupdf."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages)


def extract_gene_from_title(title: str) -> str:
    """Extract HGNC canonical gene symbol from publication title.

    Returns the canonical gene symbol or empty string if not found.
    PARK2/PARKIN/parkin → PRKN (HGNC canonical).
    """
    for pattern, canonical in _GENE_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return canonical
    return ""


def build_expected_evidence(
    gene_symbol: str,
    variants: list[dict],
    source_text: str,
) -> list[dict]:
    """Build expected_evidence from gene, variant, and source data."""
    evidence = []

    # Gene symbol (canonical HGNC)
    if gene_symbol:
        evidence.append({
            "field_id": "A.gene_symbol",
            "value": gene_symbol,
            "candidates": [],
            "source": "article",
            "evaluation_type": "precision_recall",
        })

    # Disease
    evidence.append({
        "field_id": "B.disease_diagnosis",
        "value": "Parkinson disease",
        "candidates": ["Parkinson disease", "Parkinson's disease"],
        "source": "article",
        "evaluation_type": "precision_recall",
    })

    # Gene-disease relationship
    evidence.append({
        "field_id": "A.gene_disease_relationship",
        "value": "associated",
        "candidates": [],
        "source": "article",
        "evaluation_type": "precision_recall",
    })

    # Variants (deduplicated)
    seen_variants: set[str] = set()
    for var in variants:
        var_name = var.get("Field name")
        if var_name and var_name not in (None, "", "None") and var_name not in seen_variants:
            seen_variants.add(var_name)
            evidence.append({
                "field_id": "A.variant_hgvs_p",
                "value": var_name,
                "candidates": [],
                "source": "article",
                "evaluation_type": "precision_recall",
            })

    # Inheritance (only if explicit gene-specific text exists in source)
    inh_value = GENE_INHERITANCE.get(gene_symbol, "")
    if inh_value and _has_gene_inheritance_text(source_text, gene_symbol):
        evidence.append({
            "field_id": "B.mode_of_inheritance_reported",
            "value": inh_value,
            "candidates": [],
            "source": "article",
            "evaluation_type": "precision_recall",
        })

    return evidence


def _has_gene_inheritance_text(source: str, gene: str) -> bool:
    """Check if source text has explicit gene-specific inheritance mention."""
    if not gene:
        return False
    gene_escaped = re.escape(gene)
    patterns = [
        rf"(?i)(?:{gene_escaped})[^.]*(?:autosomal[\s-]+(?:dominant|recessive))",
        rf"(?i)(?:autosomal[\s-]+(?:dominant|recessive))[^.]*(?:{gene_escaped})",
    ]
    return any(re.search(p, source) for p in patterns)


def build_expected_entities(variants: list[dict]) -> dict:
    """Build expected_entities from variant data."""
    entities: dict = {}
    # Disease entity
    entities["disease"] = {
        "text": "Parkinson disease",
        "mondo_id": "MONDO:0005180",
    }
    # Collect unique genes from variant data
    # The gene name is often in the variant name or we infer PARK2/LRRK2 etc.
    return entities


def main() -> None:
    manifest = load_manifest()
    variants = load_variants()
    pub_info = load_pub_info()

    # Find PMIDs with both PDF and variant data
    downloaded_pmids = {
        pmid for pmid, r in manifest.items()
        if r.get("status") == "downloaded" and r.get("pmid")
    }
    variant_pmids = set(variants.keys())
    eligible = sorted(downloaded_pmids & variant_pmids)

    print(f"Eligible PMIDs (PDF + variants): {len(eligible)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selection = []

    for idx, pmid in enumerate(eligible):
        entry_id = f"parkinson_{idx:03d}"
        entry_dir = OUTPUT_DIR / entry_id
        entry_dir.mkdir(parents=True, exist_ok=True)

        # Parse PDF
        pdf_path = PDF_DIR / f"{pmid}.pdf"
        if not pdf_path.exists():
            print(f"  SKIP {entry_id}: PDF not found at {pdf_path}")
            continue

        source_text = extract_text_from_pdf(pdf_path)
        if len(source_text.strip()) < 100:
            print(f"  SKIP {entry_id}: PDF text too short ({len(source_text)} chars)")
            continue

        # Write source.md
        source_path = entry_dir / "source.md"
        source_path.write_text(source_text, encoding="utf-8")

        # Build expected.json
        pmid_variants = variants.get(pmid, [])
        pub = pub_info.get(pmid, {})
        title = pub.get("Title", manifest.get(pmid, {}).get("title", ""))
        gene_symbol = extract_gene_from_title(title or "")

        expected = {
            "entry_id": entry_id,
            "gene_symbol": gene_symbol,
            "disease_label": "Parkinson disease",
            "mondo_id": "MONDO:0005180",
            "source_pmid": pmid,
            "source_doi": manifest.get(pmid, {}).get("doi", ""),
            "source_title": title,
            "expected_evidence": build_expected_evidence(gene_symbol, pmid_variants, source_text),
            "expected_entities": build_expected_entities(pmid_variants),
            "expected_standardization": {
                "disease": "MONDO:0005180",
                "gene": gene_symbol,
            },
            "notes": f"Converted from parkinson_literature dataset, PMID {pmid}",
        }
        expected_path = entry_dir / "expected.json"
        expected_path.write_text(json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")

        # Write meta.json
        meta = {
            "entry_id": entry_id,
            "pdf_path": str(pdf_path),
            "language": "en",
            "parse_status": "parsed",
            "annotation_status": "generated",
            "review_status": "ground_truth",
            "reviewer": "auto-convert",
            "review_notes": "",
            "rejection_reason": "",
            "generated_at": "",
            "reviewed_at": "",
            "promoted_at": "",
            "llm_model": "",
            "parse_backend": "pymupdf",
            "variant_count": len([v for v in pmid_variants if v.get("Field name") not in (None, "", "None")]),
        }
        meta_path = entry_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        # Add to selection
        selection.append({
            "entry_id": entry_id,
            "gene_symbol": gene_symbol,
            "disease_label": "Parkinson disease",
            "mondo_id": "MONDO:0005180",
            "source_pmid": pmid,
            "source_doi": manifest.get(pmid, {}).get("doi", ""),
            "source_title": title,
            "expected_evidence": expected["expected_evidence"],
            "expected_entities": expected["expected_entities"],
            "expected_standardization": expected["expected_standardization"],
            "notes": expected["notes"],
        })
        print(f"  {entry_id}: PMID {pmid}, {len(source_text)} chars, {len(pmid_variants)} variant rows")

    # Write selection.json
    selection_path = OUTPUT_DIR / "selection.json"
    selection_path.write_text(json.dumps(selection, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone: {len(selection)} entries written to {OUTPUT_DIR}")
    print(f"selection.json: {selection_path}")


if __name__ == "__main__":
    main()
