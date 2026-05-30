# Benchmark

> Benchmarking and evaluation datasets for the ACMG Lingua backend. Contains literature acquisition test data across multiple languages and literature types.

## Directory Map

```
benchmark/
└── literature_acquisition/
    ├── README.md          # Detailed benchmark methodology and results
    ├── log/               # Benchmark execution logs
    └── downloads/         # Downloaded test papers organized by language
        ├── en/            # English papers
        ├── ja/            # Japanese papers
        ├── ko/            # Korean papers
        ├── es/            # Spanish papers
        ├── pt/            # Portuguese papers
        ├── ru/            # Russian papers
        └── zh/            # Chinese papers
```

Each language directory contains papers categorized by literature type:
- `sequencing/` — NGS/WES/WGS studies
- `functional/` — Functional studies (in vitro, knockout, etc.)
- `unclassified/` — Unclassified papers
- `case_report/` — Case reports and case series

## Quick Start

```bash
cd backend

# View benchmark data structure
tree benchmark/literature_acquisition/downloads/ -L 2

# Check benchmark logs
ls benchmark/literature_acquisition/log/
```

## Sub-module Reference

- **[literature_acquisition/](./literature_acquisition/README.md)** — Literature acquisition benchmark methodology, provider coverage, and evaluation metrics

## Notes

- Benchmark data is not committed to git (downloaded PDFs are in `.gitignore`).
- Re-run benchmarks after provider changes to validate search/download success rates.
- Language coverage: English, Chinese, Japanese, Korean, Spanish, Portuguese, Russian.
