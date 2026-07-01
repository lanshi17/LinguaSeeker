# Layer 3 Evaluation — ClinGen Ground Truth

> **状态：已弃用垫片。** 本包（`benchmark/layer3/`）仅包含 2026-06-18 框架重构后的向后兼容导入垫片。所有实质代码已移至 `benchmark.core`、`benchmark.datasets`、`benchmark.runners` 和 `benchmark.analysis`。垫片将在重构 Phase 6 移除。

## 概述

基于 ClinGen 基因-疾病有效性审查数据的管线证据提取准确率自动评估。原始代码已拆分到多个规范包中。

## 新模块位置

| 旧路径 | 新路径 | 角色 |
|--------|--------|------|
| `benchmark.layer3.evaluate` | `benchmark.core` | 匹配算法、contracts、聚合指标、管线客户端 |
| `benchmark.layer3.mondo_hierarchy` | `benchmark.core.mondo_hierarchy` | MONDO 本体层次用于祖先匹配 |
| `benchmark.layer3.select_entries` | `benchmark.datasets.clingen.select_entries` | ClinGen CSV 条目选择 |
| `benchmark.layer3.fetch_literature` | `benchmark.datasets.clingen.fetch_literature` | EuropePMC 文献搜索 |
| `benchmark.layer3.download_pdfs` | `benchmark.datasets.clingen.download_pdfs` | PMC 全文下载 + JATS-to-markdown |
| `benchmark.layer3.generate_ground_truth` | `benchmark.datasets.clingen.generate_ground_truth` | 真值 JSON 生成 |
| `benchmark.layer3.visualize` | `benchmark.datasets.clingen.visualize` | Matplotlib 图表和 HTML 报告 |
| `benchmark.layer3.preprocess` | `benchmark.runners.clingen_preprocess` | Phase 1+2 预处理 + 缓存 |
| `benchmark.layer3.baselines` | `benchmark.analysis.baselines` | LLM 基线策略和扫描 |
| `benchmark.layer3.clinvar_fused` | `benchmark.datasets.clinvar_fused` | ClinVar 融合数据集管线 |

## 文件

| 文件 | 用途 |
|------|------|
| `__init__.py` | 已弃用垫片：lazy `__getattr__` 重定向到新位置 |
| `evaluate.py` | 已弃用垫片：从 `benchmark.core` 重新导出所有公共符号 |
| `mondo_hierarchy.py` | 已弃用垫片：重定向到 `benchmark.core.mondo_hierarchy` |
| `analysis/` | 已弃用垫片包：重定向到 `benchmark.analysis.*` 子组 |
| `baselines/` | 包含 `__init__.py`（遗留包标记） |
| `clinvar_fused/` | 包含 `__init__.py` + 日志文件 |
| `ground_truth/` | 真值数据：`clingen_000..029` 条目 + `rett/` |

## 规范导入

```python
from benchmark.core import (
    FieldMatch, EntryMetrics,
    compare_evidence, fuzzy_match_value, normalize_comparison_text,
    compute_aggregate_metrics,
    GROUND_TRUTH_ROOT, REPORTS_ROOT,
)
```

已弃用的 `benchmark.layer3.*` 垫片仍然有效但会发出 `DeprecationWarning`。

## 核心 API

### `compare_evidence`（`benchmark.core.matching`）

核心比较逻辑。对每个期望字段：查找匹配 `field_id` 且 `status="found"` 的提取候选 → 模糊匹配每个候选 → 选择最佳（exact > fuzzy > ontology_ancestor）→ 疾病字段回退到 MONDO 祖先。

### `FieldMatch` / `EntryMetrics`（`benchmark.core.contracts`）

`FieldMatch`：`field_id`、`expected_value`、`matched`、`match_type`（exact/fuzzy/ontology_ancestor/missing/wrong_value）。
`EntryMetrics`：`entry_id`、`gene_symbol`、`classification`、`field_matches`、`found_rate`、`grounding_rate`。

### `compute_aggregate_metrics`（`benchmark.core.aggregate`）

返回嵌套字典：`overall`（P/R/F1 + 过度提取）、`by_field`、`by_classification`、`by_moi`、`by_entity_type`。

## 真值选择

30 条 ClinGen Gene-Disease Summary CSV 条目：

| 分类 | 数量 | MOI 覆盖 |
|------|------|---------|
| Definitive | 10 | AD、AR、XL、MT、SD |
| Strong | 5 | AD、AR、XL |
| Moderate | 5 | AD、AR、XL |
| Limited | 5 | AD、AR、XL |
| Refuted | 3 | AD、AR |
| Disputed | 2 | AD、XL |

## 使用方法

```bash
cd backend

# 评估所有 30 条目
uv run python -m benchmark.layer3.evaluate --base-url http://localhost:8000 --concurrency 2

# 特定条目
uv run python -m benchmark.layer3.evaluate --entries clingen_000 clingen_001

# 预处理以快速重新评估
uv run python -m benchmark.runners.clingen_preprocess --entries clingen_000 clingen_001
```

## 测试

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_evaluate_matching.py -v
```
