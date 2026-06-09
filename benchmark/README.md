# Benchmark

> Benchmarking and evaluation infrastructure for ACMG Lingua. Covers literature acquisition, full pipeline execution, and ClinGen Layer 3 ground-truth evaluation.

## Directory Structure

```
benchmark/
├── __init__.py
├── README.md
├── layer3/                    ClinGen Layer 3 evaluation
│   ├── evaluate.py            Main evaluator: pipeline vs ground truth
│   ├── visualize.py           Charts and HTML report generation
│   ├── select_entries.py      Select representative ClinGen entries
│   ├── fetch_literature.py    Query EuropePMC for PMID/PMC IDs
│   ├── download_pdfs.py       Download PMC full-text articles
│   ├── generate_ground_truth.py  Build expected.json from ClinGen CSV
│   ├── mondo_hierarchy.py     MONDO ontology hierarchy utilities
│   ├── ground_truth/          30 ClinGen entries (clingen_000..029 + selection.json)
│   └── reports/               Evaluation reports (JSON, PNG, HTML)
├── literature_acquisition/    Literature download benchmarks
│   ├── benchmark.py           General cancer/genomics benchmark (7 languages)
│   ├── rett_download.py       Rett/MECP2 disease-specific benchmark (12 languages)
│   ├── rett_config.json       Rett config v2
│   ├── rett_config_02.json    Rett config v4 (expanded)
│   ├── downloads/             Downloaded PDFs + report JSONs
│   └── log/                   Rotating log files
└── pipeline/                  Full pipeline benchmark (Phases 1-3)
    ├── benchmark.py           Benchmark runner (HTTP client)
    ├── evidence_metrics.py    Evidence extraction metrics
    ├── manifest.json          Selected PDFs (1 case_report per language)
    ├── input/                 Test PDFs organized by language
    │   ├── en/                English (case_report, functional, sequencing, unclassified)
    │   ├── zh/                Chinese
    │   ├── ja/                Japanese
    │   ├── ko/                Korean
    │   ├── es/                Spanish
    │   ├── pt/                Portuguese
    │   └── ru/                Russian
    └── reports/               Timestamped JSON reports (38 runs)
```

## Sub-module Reference

- **[layer3/](./layer3/README.md)** -- ClinGen Layer 3 evaluation against 30 ground-truth entries. Measures field P/R/F1, entity standardization accuracy, and cross-lingual consistency.
- **[literature_acquisition/](./literature_acquisition/README.md)** -- Multilingual literature download benchmark. Evaluates provider coverage and success rates across 7-12 languages.
- **[pipeline/](./pipeline/README.md)** -- Full pipeline benchmark (Phases 1-3) via HTTP API. Measures per-phase timing and reliability across 7 languages.

## Notes

- Downloaded PDFs are not committed to git (in `.gitignore`).
- Re-run benchmarks after provider changes to validate success rates.
- Language coverage: English, Chinese, Japanese, Korean, Spanish, Portuguese, Russian (7 core languages; literature acquisition extends to 12).
