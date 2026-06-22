"""Baseline B: Multilingual evidence coverage analysis.

Compares gene and variant coverage between English-only retrieval
and the full multilingual corpus (7 languages, 1,602 papers).
Quantifies the incremental evidence value of non-English literature.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

_DEFAULT_FILTER_REPORT = Path("benchmark/runners/downloads/filter_report.json")
_DEFAULT_OUTPUT = Path("benchmark/optimization/fused75/reports/baseline_multilingual_coverage.json")

_CHROMO_RE = re.compile(r"^\d+[pq]\d")
_GENE_LIKE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
_HGVS_C_RE = re.compile(r"^c\.\d")
_HGVS_P_RE = re.compile(r"^p\.")
_RS_RE = re.compile(r"^rs\d+$")
_NM_RE = re.compile(r"^(NM|NP|ENST)\d")


def _classify_pattern(pattern: str) -> str:
    if _CHROMO_RE.match(pattern):
        return "locus"
    if _HGVS_C_RE.match(pattern):
        return "hgvs_c"
    if _HGVS_P_RE.match(pattern):
        return "hgvs_p"
    if _RS_RE.match(pattern):
        return "rsid"
    if _NM_RE.match(pattern):
        return "transcript"
    if _GENE_LIKE_RE.match(pattern):
        return "gene"
    return "other"


def run_multilingual_coverage(
    *,
    filter_report_path: Path = _DEFAULT_FILTER_REPORT,
    output_path: Path = _DEFAULT_OUTPUT,
) -> dict:
    data = json.loads(filter_report_path.read_text(encoding="utf-8"))
    kept = [r for r in data["results"] if r["action"] == "keep"]

    lang_counts = defaultdict(lambda: {"scanned": 0, "kept": 0, "genes": set(), "variants": set(), "all_patterns": set()})

    for r in data["results"]:
        lang = r["lang"]
        lang_counts[lang]["scanned"] += 1
        if r["action"] == "keep":
            lang_counts[lang]["kept"] += 1
            for pattern in r.get("matched_patterns", []):
                cat = _classify_pattern(pattern)
                lang_counts[lang]["all_patterns"].add(pattern)
                if cat == "gene":
                    lang_counts[lang]["genes"].add(pattern)
                elif cat in ("hgvs_c", "hgvs_p", "rsid"):
                    lang_counts[lang]["variants"].add(pattern)

    en_genes = lang_counts["en"]["genes"]
    en_variants = lang_counts["en"]["variants"]

    all_genes: set[str] = set()
    all_variants: set[str] = set()
    gene_by_lang: dict[str, set[str]] = {}
    variant_by_lang: dict[str, set[str]] = {}

    for lang, counts in lang_counts.items():
        all_genes.update(counts["genes"])
        all_variants.update(counts["variants"])
        gene_by_lang[lang] = counts["genes"]
        variant_by_lang[lang] = counts["variants"]

    non_en_genes = all_genes - en_genes
    non_en_variants = all_variants - en_variants

    gene_lang_provenance: dict[str, list[str]] = {}
    for gene in sorted(non_en_genes):
        gene_lang_provenance[gene] = [lang for lang, genes in gene_by_lang.items() if gene in genes and lang != "en"]

    variant_lang_provenance: dict[str, list[str]] = {}
    for variant in sorted(non_en_variants):
        variant_lang_provenance[variant] = [lang for lang, variants in variant_by_lang.items() if variant in variants and lang != "en"]

    report = {
        "baseline_type": "multilingual_coverage",
        "description": "English-only vs multilingual gene and variant coverage across 7 languages",
        "corpus": {
            "total_scanned": data["total_scanned"],
            "total_kept": data["total_kept"],
            "languages": sorted(lang_counts.keys()),
        },
        "per_language": {
            lang: {
                "scanned": counts["scanned"],
                "kept": counts["kept"],
                "keep_rate": round(counts["kept"] / counts["scanned"], 4) if counts["scanned"] else 0,
                "unique_genes": len(counts["genes"]),
                "unique_variants": len(counts["variants"]),
                "unique_patterns": len(counts["all_patterns"]),
            }
            for lang, counts in sorted(lang_counts.items())
        },
        "gene_coverage": {
            "total_unique_genes": len(all_genes),
            "english_genes": len(en_genes),
            "non_english_only_genes": len(non_en_genes),
            "non_english_only_pct": round(len(non_en_genes) / len(all_genes) * 100, 1) if all_genes else 0,
            "by_lang_contribution": {lang: len(genes - en_genes) for lang, genes in gene_by_lang.items() if lang != "en"},
        },
        "variant_coverage": {
            "total_unique_variants": len(all_variants),
            "english_variants": len(en_variants),
            "non_english_only_variants": len(non_en_variants),
            "non_english_only_pct": round(len(non_en_variants) / len(all_variants) * 100, 1) if all_variants else 0,
            "by_lang_contribution": {lang: len(variants - en_variants) for lang, variants in variant_by_lang.items() if lang != "en"},
        },
        "non_english_only_genes": gene_lang_provenance,
        "non_english_only_variants": variant_lang_provenance,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run_multilingual_coverage()

    print("=== Multilingual Evidence Coverage Baseline ===\n")
    print(f"Corpus: {report['corpus']['total_scanned']} scanned, {report['corpus']['total_kept']} kept, {len(report['corpus']['languages'])} languages\n")

    print("Per-language breakdown:")
    print(f"{'Lang':>6} {'Kept':>6} {'Rate':>7} {'Genes':>7} {'Variants':>9}")
    for lang, stats in report["per_language"].items():
        print(f"{lang:>6} {stats['kept']:>6} {stats['keep_rate']:>6.1%} {stats['unique_genes']:>7} {stats['unique_variants']:>9}")

    gc = report["gene_coverage"]
    print(f"\nGene coverage:")
    print(f"  Total unique genes: {gc['total_unique_genes']}")
    print(f"  Found in English:   {gc['english_genes']}")
    print(f"  Non-English only:   {gc['non_english_only_genes']} ({gc['non_english_only_pct']}%)")
    print(f"  Per-lang contribution: {gc['by_lang_contribution']}")

    vc = report["variant_coverage"]
    print(f"\nVariant coverage (HGVS + rsID):")
    print(f"  Total unique variants: {vc['total_unique_variants']}")
    print(f"  Found in English:      {vc['english_variants']}")
    print(f"  Non-English only:      {vc['non_english_only_variants']} ({vc['non_english_only_pct']}%)")
    print(f"  Per-lang contribution:  {vc['by_lang_contribution']}")

    print(f"\nReport: benchmark/optimization/fused75/reports/baseline_multilingual_coverage.json")


if __name__ == "__main__":
    main()
