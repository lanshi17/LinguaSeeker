# Parkinson Literature Dataset

> 将帕金森病文献集合 XLSX 工作簿转换为可审计 JSON 数据的工具集，支持可选的 PMC PDF 下载。

## 概述

本模块使用纯 Python 标准库（`ZipFile` + `xml.etree.ElementTree`）解析 XLSX 工作簿，无需 `openpyxl` 或 `pandas` 依赖。工作簿包含 7 个工作表、6291 行数据，涵盖测序研究、变异、家系、样本、功能实验和出版物元数据。

## 文件列表

| 文件 | 用途 |
|------|------|
| `xlsx_dataset.py` | XLSX 读取器和结构审计（纯标准库） |
| `export_dataset.py` | 导出工作表为 JSONL + 审计报告 |
| `fetch_pdfs.py` | 下载开放获取 PMC PDF |

## 快速开始

```bash
# 导出工作簿为 JSONL + 审计报告
uv run --project backend python -m benchmark.datasets.parkinson_literature.export_dataset \
  --input 'tmp/test_liter_collect(1).xlsx' \
  --output-dir benchmark/data/processed/parkinson_literature

# 获取 PMC PDF
uv run --project backend python -m benchmark.datasets.parkinson_literature.fetch_pdfs \
  --publication-jsonl benchmark/data/processed/parkinson_literature/table7_publication_info.jsonl \
  --output-dir benchmark/data/processed/parkinson_literature/publications \
  --limit 5
```

## 架构

```text
XLSX workbook
  -> xlsx_dataset.load_workbook_tables()
  -> normalized WorkbookTable objects
  -> build_audit_report()
  -> export_dataset()
  -> audit_report.json + sheet-level JSONL files
```

## 公共 API

### `xlsx_dataset.py`

| 符号 | 描述 |
|------|------|
| `WorkbookTable` | 归一化行数据：`name`、`headers`、`rows`、`row_numbers` |
| `ColumnProfile` | 完整性配置：`name`、`non_empty_count`、`sample_values` |
| `SheetAudit` | 每表审计：行列计数、非空计数、标识符覆盖、重复键 |
| `DatasetAuditReport` | 顶层报告：`sheet_count`、`total_data_rows`、每表审计 |
| `load_workbook_tables` | 读取 `.xlsx` 归档中的所有工作表 |
| `build_audit_report` | 计算结构质量指标 |

### `export_dataset.py`

| 符号 | 描述 |
|------|------|
| `DatasetExportPaths` | 输出路径：`audit_report`、`jsonl_paths` |
| `export_dataset` | 写入 JSONL 文件 + 审计报告 |

### `fetch_pdfs.py`

| 符号 | 描述 |
|------|------|
| `PublicationPdfRecord` | 每出版物下载状态 |
| `PublicationPdfFetchReport` | 聚合获取摘要 |
| `fetch_publication_pdfs` | 解析 PubMed 元数据，下载 PMC PDF |

## 工作簿概览

| 工作表 | 行数 | 列数 | 用途 |
|--------|------|------|------|
| `table1_seq_study_info` | 1580 | 17 | 测序研究队列元数据 |
| `table2_seq_study&var` | 1033 | 9 | 变异级病例/对照计数 |
| `table3_sample&var` | 1150 | 9 | 样本-变异基因型关系 |
| `tabel4_family_info` | 456 | 12 | 家系分离信息 |
| `table5_samp_info` | 859 | 15 | 个体样本表型元数据 |
| `Table6_func_study_info` | 506 | 26 | 功能实验证据 |
| `table7_publication_info` | 707 | 8 | 出版物元数据 |

## 标准化规则

- `""`、`/`、`\` 标准化为 JSON `null`
- 字符串去首尾空白
- PubMed ID 如 `16643317.0` 标准化为 `16643317`
- 输出行保留 `_sheet` 和 `_row_number` 可溯源

## 测试

```bash
uv run --project pytest backend/tests/benchmark/layer3/test_parkinson_literature_dataset.py -q
```
