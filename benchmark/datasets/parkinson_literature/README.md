# Parkinson Literature Dataset

> Utilities for converting the Parkinson literature collection workbook into auditable JSON artifacts.

## Quick Start

```bash
uv run --project backend python -m benchmark.datasets.parkinson_literature.export_dataset \
  --input 'tmp/test_liter_collect(1).xlsx' \
  --output-dir benchmark/data/processed/parkinson_literature
```

The command writes:

- `benchmark/data/processed/parkinson_literature/audit_report.json`
- one normalized `.jsonl` file per workbook sheet

Fetch available PMC PDFs for publication rows:

```bash
uv run --project backend python -m benchmark.datasets.parkinson_literature.fetch_pdfs \
  --publication-jsonl benchmark/data/processed/parkinson_literature/table7_publication_info.jsonl \
  --output-dir benchmark/data/processed/parkinson_literature/publications \
  --limit 5
```

The fetcher reuses the backend PubMed acquisition service to resolve PMID metadata and PMCID values, then downloads open-access PMC PDFs when available.

## Architecture

```text
XLSX workbook
  -> xlsx_dataset.load_workbook_tables()
  -> normalized WorkbookTable objects
  -> build_audit_report()
  -> export_dataset()
  -> audit_report.json + sheet-level JSONL files
```

The module intentionally uses only Python standard library APIs. This avoids adding `openpyxl` or `pandas` just to inspect and normalize the workbook.

## Public API

### `load_workbook_tables(path: Path) -> Mapping[str, WorkbookTable]`

Reads all sheets from an `.xlsx` archive and returns normalized rows keyed by sheet name.

### `build_audit_report(tables: Mapping[str, WorkbookTable]) -> DatasetAuditReport`

Computes structural dataset-readiness metrics:

- sheet count
- row and column counts
- non-empty counts per column
- identifier coverage for columns such as `Pubmed_id`, `Var_id`, `Fam_sample_id`
- duplicate composite identifier counts

### `export_dataset(input_path: Path, output_dir: Path) -> DatasetExportPaths`

Writes normalized JSONL files and the audit report.

### `fetch_publication_pdfs(publication_jsonl: Path, output_dir: Path, limit: int | None) -> PublicationPdfFetchReport`

Reads normalized publication rows, resolves PubMed metadata through `OnlineAcquisitionPubMedService`, and writes a PDF manifest plus downloaded PDF files.

## Normalization Rules

- `""`, `/`, and `\` are normalized to JSON `null`.
- Strings are trimmed.
- PubMed IDs like `16643317.0` are normalized to `16643317`.
- Output rows preserve traceability with `_sheet` and `_row_number`.
- Sheet filenames are made filesystem-safe, for example `table2_seq_study&var` becomes `table2_seq_study_var.jsonl`.
- PDF manifests preserve `pmid`, source workbook row number, resolved `pmcid`, DOI, PDF URL, local path, and fetch status.

## Current Export Summary

The current workbook export contains 7 sheets and 6291 data rows:

| Sheet | Rows | Columns | Role |
|---|---:|---:|---|
| `table1_seq_study_info` | 1580 | 17 | sequencing study cohort metadata |
| `table2_seq_study&var` | 1033 | 9 | variant-level case/control counts |
| `table3_sample&var` | 1150 | 9 | sample-variant genotype relationships |
| `tabel4_family_info` | 456 | 12 | family segregation information |
| `table5_samp_info` | 859 | 15 | individual sample phenotype metadata |
| `Table6_func_study_info` | 506 | 26 | functional assay evidence |
| `table7_publication_info` | 707 | 8 | publication metadata |

## Extension Guide

To convert this source into a full benchmark ground truth dataset:

1. Define entry identity, likely `Pubmed_id + Var_id` for variant-centric entries and `Pubmed_id` for publication-centric entries.
2. Map workbook fields to the existing benchmark `expected.json` structure.
3. Add source text acquisition from `table7_publication_info.Pubmed_id`.
4. Preserve workbook traceability by carrying `_sheet`, `_row_number`, `Pubmed_id`, and `Var_id` into every generated expected evidence item.
5. Add validation for duplicate keys and inconsistent sample/family links before using the data as gold labels.

## Limitations

- The current export is structural, not a biological correctness audit.
- Duplicate composite keys are reported but not resolved.
- The workbook has mixed Chinese/English notes and typo-preserved sheet names such as `tabel4_family_info`.
- Some columns, including `OR` and `CI`, are mostly empty and need domain review before benchmark use.
- PDF downloading is limited to open-access PMC records discoverable from PubMed metadata; paywalled or non-PMC records are recorded but not downloaded.

## Testing

Run:

```bash
uv run --project backend pytest backend/tests/benchmark/layer3/test_parkinson_literature_dataset.py -q
uv run --project backend ruff check benchmark/datasets/parkinson_literature backend/tests/benchmark/layer3/test_parkinson_literature_dataset.py
```
