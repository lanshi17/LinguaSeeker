# Parkinson Literature Dataset

Utilities for converting a Parkinson disease literature collection XLSX workbook into auditable JSON artifacts, with optional PMC PDF downloading.

## Files

| File | Purpose |
|------|---------|
| `xlsx_dataset.py` | XLSX reader and structural audit (stdlib only, no `openpyxl`/`pandas`) |
| `export_dataset.py` | Export workbook sheets to JSONL + audit report |
| `fetch_pdfs.py` | Download open-access PMC PDFs for publication rows |

## Quick Start

```bash
# Export workbook to JSONL + audit report
uv run --project backend python -m benchmark.datasets.parkinson_literature.export_dataset \
  --input 'tmp/test_liter_collect(1).xlsx' \
  --output-dir benchmark/data/processed/parkinson_literature

# Fetch PMC PDFs for publication rows
uv run --project backend python -m benchmark.datasets.parkinson_literature.fetch_pdfs \
  --publication-jsonl benchmark/data/processed/parkinson_literature/table7_publication_info.jsonl \
  --output-dir benchmark/data/processed/parkinson_literature/publications \
  --limit 5
```

## Architecture

```text
XLSX workbook
  -> xlsx_dataset.load_workbook_tables()
  -> normalized WorkbookTable objects
  -> build_audit_report()
  -> export_dataset()
  -> audit_report.json + sheet-level JSONL files
```

The module uses only Python standard library APIs for XLSX parsing (via `ZipFile` + `xml.etree.ElementTree`), avoiding third-party dependencies.

## Public API

### `xlsx_dataset.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `WorkbookTable` | `dataclass` | Normalized rows from one sheet: `name`, `headers`, `rows`, `row_numbers` |
| `ColumnProfile` | `dataclass` | Completeness profile: `name`, `non_empty_count`, `sample_values` |
| `SheetAudit` | `dataclass` | Per-sheet audit: row/column counts, non-empty counts, identifier coverage, duplicate keys |
| `DatasetAuditReport` | `dataclass` | Top-level report: `sheet_count`, `total_data_rows`, per-sheet audits |
| `load_workbook_tables` | `(path: Path) -> Mapping[str, WorkbookTable]` | Read all sheets from `.xlsx` archive |
| `build_audit_report` | `(tables) -> DatasetAuditReport` | Compute structural quality metrics |

### `export_dataset.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `DatasetExportPaths` | `dataclass` | Paths written: `audit_report`, `jsonl_paths` |
| `export_dataset` | `(input_path, output_dir) -> DatasetExportPaths` | Write JSONL files + audit report |

### `fetch_pdfs.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `PublicationPdfRecord` | `dataclass` | Per-publication download status |
| `PublicationPdfFetchReport` | `dataclass` | Aggregate fetch summary |
| `fetch_publication_pdfs` | `async (publication_jsonl, output_dir, ...) -> PublicationPdfFetchReport` | Resolve PubMed metadata, download PMC PDFs |

## Normalization Rules

- `""`, `/`, `\` are normalized to JSON `null`
- Strings are trimmed
- PubMed IDs like `16643317.0` are normalized to `16643317`
- Output rows preserve traceability with `_sheet` and `_row_number`
- Sheet filenames are made filesystem-safe (e.g. `table2_seq_study&var` -> `table2_seq_study_var.jsonl`)

## Workbook Summary

7 sheets, 6291 data rows:

| Sheet | Rows | Columns | Role |
|-------|------|---------|------|
| `table1_seq_study_info` | 1580 | 17 | Sequencing study cohort metadata |
| `table2_seq_study&var` | 1033 | 9 | Variant-level case/control counts |
| `table3_sample&var` | 1150 | 9 | Sample-variant genotype relationships |
| `tabel4_family_info` | 456 | 12 | Family segregation information |
| `table5_samp_info` | 859 | 15 | Individual sample phenotype metadata |
| `Table6_func_study_info` | 506 | 26 | Functional assay evidence |
| `table7_publication_info` | 707 | 8 | Publication metadata |

## PDF Fetch Results

Full acquisition run stored under `benchmark/data/processed/parkinson_literature/publications_full/`:

| Metric | Count |
|--------|------:|
| Unique publication PMIDs requested | 598 |
| PubMed metadata resolved | 584 |
| PMCID/PDF candidates | 249 |
| PDFs downloaded | 176 |
| Not open access / no PMCID | 346 |
| Download failed | 73 |
| Metadata missing/error | 3 |

## Limitations

- The export is structural, not a biological correctness audit
- Duplicate composite keys are reported but not resolved
- The workbook has mixed Chinese/English notes and typo-preserved sheet names (e.g. `tabel4_family_info`)
- Some columns (`OR`, `CI`) are mostly empty and need domain review
- PDF downloading is limited to open-access PMC records; paywalled records are recorded but not downloaded

## Testing

```bash
uv run --project pytest backend/tests/benchmark/layer3/test_parkinson_literature_dataset.py -q
uv run --project ruff check benchmark/datasets/parkinson_literature backend/tests/benchmark/layer3/test_parkinson_literature_dataset.py
```
