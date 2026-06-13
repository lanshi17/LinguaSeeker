# Data

> Sample and test PDF files used for pipeline testing. Organized by ISO 639-1 language code.

## Directory Structure

```
downloads/
├── en/                                    English (1 PDF)
│   └── 10.3389_fimmu.2025.1655475.pdf
├── ja/                                    Japanese (3 PDFs)
│   ├── 32_2015-0041.pdf
│   ├── 33_2017-0026.pdf
│   └── 52_26.pdf
├── ru/                                    Russian (1 PDF)
│   └── elibrary_53981733_40074746.pdf
├── zh/                                    Chinese (4 PDFs)
│   ├── GLA基因c.92C_A突变法布雷病家系1例.pdf
│   ├── 法布雷病1例.pdf
│   ├── 一个15例患病的法布雷病家系分析.pdf
│   └── 一例极早发型炎症性肠病患儿的临床及IL10RA基因变异分析.pdf
└── v1.1/                                  Revised versions
    ├── en/
    │   └── 10.1186_s13256-023-03889-y.pdf
    └── ja/
        └── ATP2A2.pdf
```

## Usage

These files are used for:

- **Parser testing** -- Validating PDF text extraction across languages (en, ja, ru, zh)
- **Pipeline integration testing** -- End-to-end document processing with real literature
- **Cross-lingual extraction** -- Bilingual evidence extraction and translation validation

The `v1.1/` directory contains revised or updated versions of documents for testing version-aware processing.
