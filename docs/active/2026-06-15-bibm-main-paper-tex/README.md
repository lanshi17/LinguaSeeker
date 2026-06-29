# BIBM Main Paper TeX Draft

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** --
**PR:** --

This directory contains the IEEEtran-style TeX manuscript for the BIBM main paper: "LinguaSeeker: Source-Grounded Cross-Lingual Evidence Extraction for Clinical Genetics Literature."

## Files

- `main.tex` -- anonymous double-column IEEE conference draft. Includes abstract, introduction, related work, method, experiments, and results sections. Reports the default broad workflow on the unified 150-entry benchmark: P=65.5%, R=33.6%, F1=44.4%, 150/150 completed. Also includes the external system positioning table and scope-sensitivity analysis.
- `refs.bib` -- BibTeX bibliography.
- `figures/method_figure.tex` -- TikZ vector method figure showing the broad workflow with source-document and translation input branches, primary extraction, review validation, normalization/source grounding, entity standardization, and read models.
- `figures/source_dataset_metrics.tex` -- TikZ grouped bar chart showing precision, recall, and F1 by source dataset.

## Build Notes

- Uses `\documentclass[conference]{IEEEtran}` for BIBM submission format.
- Method name macro: `\methodname` expands to `LinguaSeeker`; `\bmode` expands to `broad`.
- Tables are kept compact and scientific in tone.
- The figures are intentionally schematic and grayscale-friendly rather than decorative.
- Scope sensitivity numbers are generated from `benchmark/analysis/paper_artifacts/summarize_unified_b8_scope.py`, which writes `benchmark/data/reports/unified_b8_scope_sensitivity_20260629.json` and `.md`.
