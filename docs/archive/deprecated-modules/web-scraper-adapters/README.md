# Web Scraper Adapters (Archived)

**Archived:** 2026-06-16
**Status:** Deprecated, no longer in use
**Original path:** `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/`

## Overview

This module contained 9 browser-based web scraper adapters for academic sites that require JavaScript rendering. The adapters used crawl4ai + Playwright for automated UI interaction and structured data extraction.

### Reason for Deprecation

- **High maintenance cost:** Each site required independent XPath/CSS locators and UI interaction flows.
- **Poor stability:** Target site UI changes frequently broke locators.
- **Performance bottleneck:** Browser automation overhead made large-scale acquisition impractical.
- **Replacement:** Rust-based HTTP API providers (`net_io`) handle the same sites more reliably.

### Original Module Structure

```
web/
├── base.py           # Shared utilities (crawl4ai_search, PDF download, HTML parsing)
├── locators.py       # XPath/CSS selector constants
├── pubscholar.py     # PubScholar (Chinese, CNIC/CAS)
├── chinaxiv.py       # ChinaXiv (Chinese preprints)
├── hans_publishers.py # Hans Publishers (Chinese journals)
├── cyberleninka.py   # CyberLeninka (Russian open access)
├── koreascience.py   # KoreaScience (Korean journals)
├── redalyc.py        # Redalyc / La Referencia (Spanish/Portuguese)
└── __init__.py
```

### Technology Stack

- **crawl4ai** + **Playwright**: Browser automation
- **selectolax**: HTML parsing fallback
- **Rust net_io**: PDF link extraction acceleration
- **LLMExtractionStrategy**: LLM-assisted structured extraction

### Migration Guide

To restore these adapters, move the archived directory back to its original location:

```bash
mv docs/archive/deprecated-modules/web-scraper-adapters/web/ \
   backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/
```

However, prefer the existing Rust-based literature providers (Crossref, OpenAlex, EuropePMC, PMC, DOAJ, JStage, Unpaywall) instead.

## Related Documents

- Provider README: `web/README.md`
- Literature acquisition gateway: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/gateway.py`
- Rust I/O: `backend/libs/net-io/`
