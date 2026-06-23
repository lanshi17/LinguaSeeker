"""Scan parkinson source.md files for medium/complex field evidence.

Read-only — outputs a scan report, does not modify ground truth.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GT_DIR = ROOT / "benchmark" / "data" / "ground_truth" / "parkinson"
REPORTS_DIR = ROOT / "benchmark" / "data" / "reports"

PATTERNS: dict[str, dict[str, str]] = {
    "inheritance": {
        "autosomal_dominant": r"(?i)(autosomal[\s-]+dominant|AD[\s,;])",
        "autosomal_recessive": r"(?i)(autosomal[\s-]+recessive|AR[\s,;])",
        "dominant_pattern": r"(?i)\bdominant\s+(inheritance|pattern|trait)",
        "recessive_pattern": r"(?i)\brecessive\s+(inheritance|pattern|trait)",
    },
    "de_novo": {
        "de_novo": r"(?i)(de\s*novo|sporadic\s+mutation|new\s+mutation)",
        "germline_mosaicism": r"(?i)germline\s+mosaicism",
    },
    "segregation": {
        "cosegregation": r"(?i)(co-?segregat|segregat\w*\s+with\s+(the\s+)?disease|family[\s-]+based|pedigree|affected\s+(family\s+)?members)",
        "family_study": r"(?i)(family\s+stud|kindred|sibship|sibling)",
    },
    "functional_assay": {
        "in_vitro": r"(?i)(in\s+vitro|cell[\s-]+based\s+assay|transfected|overexpress|knock[\s-]+(?:in|out|down))",
        "enzyme_activity": r"(?i)(enzyme\s+activ|glucocerebrosidase\s+activ|GCase\s+activ)",
        "protein_function": r"(?i)(protein\s+(function|expression|level|stability|folding|aggregat))",
        "animal_model": r"(?i)(mouse\s+model|transgenic\s+mouse|Drosophila|zebrafish|C\.\s*elegans)",
    },
    "variant_type": {
        "missense": r"(?i)\bmissense\b",
        "nonsense": r"(?i)\bnonsense\b",
        "frameshift": r"(?i)\bframeshift\b",
        "splice_site": r"(?i)(splice[\s-]+site|splice[\s-]+variant|IVS)",
        "deletion": r"(?i)\bdeletion\b",
        "insertion": r"(?i)\binsertion\b",
        "duplication": r"(?i)\bduplication\b",
        "exon_deletion": r"(?i)(exon[\s-]+\d+\s+deletion|multi[\s-]+exon\s+deletion)",
        "point_mutation": r"(?i)\bpoint\s+mutation\b",
    },
    "phenotype": {
        "parkinsonism": r"(?i)\bparkinsonism\b",
        "tremor": r"(?i)\btremor\b",
        "rigidity": r"(?i)\brigidity\b",
        "bradykinesia": r"(?i)\bbradykinesia\b",
        "dystonia": r"(?i)\bdystonia\b",
        "cognitive_decline": r"(?i)(cognitive\s+(decline|impairment|deficit)|dementia)",
        "early_onset": r"(?i)(early[\s-]+onset|young[\s-]+onset|juvenile)",
        "late_onset": r"(?i)(late[\s-]+onset)",
        "age_of_onset_mention": r"(?i)(age\s+of\s+onset|onset\s+age|mean\s+age|median\s+age|onset\s+at\s+age)",
    },
    "population": {
        "population_study": r"(?i)(prevalence|incidence|carrier\s+frequency|population[\s-]+based|cohort|case[\s-]+control)",
        "ethnicity": r"(?i)(ethnic|ancestry|Ashkenazi|North\s+African|East\s+Asian|European|Hispanic)",
    },
    "contradiction": {
        "conflicting": r"(?i)(conflicting|controversi|discrepanc|inconsisten|contradict|debated|unclear\s+whether)",
    },
}


def _extract_snippet(text: str, match: re.Match[str], context: int = 80) -> str:
    start = max(0, match.start() - context)
    end = min(len(text), match.end() + context)
    return text[start:end].replace("\n", " ").strip()


def scan_entry(entry_dir: Path) -> dict[str, object]:
    source_path = entry_dir / "source.md"
    expected_path = entry_dir / "expected.json"
    if not source_path.exists() or not expected_path.exists():
        return {"entry_id": entry_dir.name, "error": "missing files"}

    text = source_path.read_text(encoding="utf-8")
    exp = json.loads(expected_path.read_text(encoding="utf-8"))
    gene = str(exp.get("gene_symbol", ""))

    findings: dict[str, list[dict[str, str]]] = {}
    for category, patterns in PATTERNS.items():
        cat_findings: list[dict[str, str]] = []
        seen_labels: set[str] = set()
        for label, pattern in patterns.items():
            for m in re.finditer(pattern, text):
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                cat_findings.append({
                    "label": label,
                    "match": m.group(0)[:120],
                    "snippet": _extract_snippet(text, m),
                })
                break  # one snippet per label
        if cat_findings:
            findings[category] = cat_findings

    return {
        "entry_id": entry_dir.name,
        "gene_symbol": gene,
        "source_chars": len(text),
        "categories_found": sorted(findings.keys()),
        "findings": findings,
    }


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []

    for entry_dir in sorted(GT_DIR.iterdir()):
        if not entry_dir.is_dir():
            continue
        result = scan_entry(entry_dir)
        results.append(result)
        cats = result.get("categories_found", [])
        gene = result.get("gene_symbol", "?")
        print(f"{result['entry_id']} ({gene}): {', '.join(cats) if cats else 'NONE'}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out = REPORTS_DIR / f"parkinson_source_scan_{timestamp}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nScan saved: {out}")

    # Summary stats
    categories: dict[str, int] = {}
    for r in results:
        for cat in r.get("categories_found", []):  # type: ignore[union-attr]
            categories[cat] = categories.get(cat, 0) + 1
    print("\nCategory coverage across 20 entries:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}/20")


if __name__ == "__main__":
    main()
