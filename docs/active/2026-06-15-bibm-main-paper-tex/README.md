# BIBM Main Paper TeX Draft

**Status:** in-progress
**Created:** 2026-06-15
**Completed:** --
**PR:** --

This directory contains the IEEEtran-style TeX manuscript for the BIBM main paper: "LinguaSeeker: Citation-Valid Cross-Lingual Biomedical Evidence Reconciliation."

## Files

- `main.tex` -- anonymous double-column IEEE conference draft (315 lines). Includes abstract, introduction, related work, method, experiments, and results sections. Reports context-verifier reconciliation achieving P=0.9205, R=0.9759, F1=0.9474 on an N=30 ClinGen/ACMG benchmark.
- `refs.bib` -- BibTeX bibliography (153 lines, ~30 entries).
- `figures/method_figure.tex` -- TikZ vector method figure (25 lines) showing the dual-track evidence graph pipeline: original/translated track extraction, typed evidence graph, verifier-aware reconciliation, and audit trail.

## Build Notes

- Uses `\documentclass[conference]{IEEEtran}` for BIBM submission format.
- Method name macro: `\methodname` expands to `LinguaSeeker`.
- Tables are kept compact and scientific in tone.
- The method figure is intentionally schematic rather than decorative.
