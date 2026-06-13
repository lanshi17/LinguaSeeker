# Knowledges

> Domain knowledge reference documents for ACMG variant interpretation. These documents serve as authoritative context for the system's LLM-based evidence extraction and classification pipelines.

## Contents

| File | Size | Source | Description |
|------|------|--------|-------------|
| `acmg-2015.md` | 125 KB | Richards et al., *Genetics in Medicine* (2015) | ACMG/AMP 2015 guidelines for sequence variant interpretation |
| `acmg-2019.md` | 67 KB | Brnich et al., *Human Mutation* (2019) | ClinGen SVI PS3/BS3 functional evidence evaluation criteria |
| `acmg-2021-2026-outline.md` | 17 KB | Multiple sources | Outline of ACMG guideline developments 2021-2026 (Chinese) |
| `gdv-12.md` | 166 KB | ClinGen (2020) | Gene-Disease Validity Curation Process SOP v12 |

## Usage

These documents are ingested by the backend as domain knowledge for:

- **Evidence extraction** -- LLM prompts reference ACMG criteria to classify evidence strength (PS1, PM1, BA1, etc.)
- **Gene-disease validity assessment** -- GDV SOP guides automated curation scoring
- **Variant classification** -- Structured rules from the 2015 guidelines map extracted evidence to classification tiers

They are not runtime dependencies; they are prompt/context resources loaded during pipeline processing.
