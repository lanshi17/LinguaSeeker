# Benchmark Framework

> Lingua Seeker 证据提取管线的基准测试套件。覆盖文献获取、跨语言证据提取、实体标准化和端到端管线评估。

## 概述

本目录是 Lingua Seeker 的统一基准测试框架，包含共享原语（contracts、matching、aggregate、paths）、数据集组装器、实验运行器、离线分析工具和配置管理。2026-06-18 重构后，所有代码通过 `benchmark.core`、`benchmark.datasets`、`benchmark.runners`、`benchmark.analysis` 四个规范包访问。

## 目录结构

```
benchmark/
├── core/              共享原语：contracts、matching、aggregate、paths、pdf、pipeline_client、evidence_metrics、field_normalize、mondo_hierarchy
├── config/            集中配置：Ansible 管理的文件配置 + 运行时默认值
├── datasets/          数据集特定组装器和评估器
│   ├── clingen/       ClinGen 条目 + Rett 审查
│   ├── clinvar_fused/ ClinVar 融合变异（数据集 2）
│   ├── parkinson_literature/  帕金森 XLSX 工作簿管理 + PDF 获取
│   └── rett_annotation/       MinerU 驱动的标注工具（独立 uv 项目）
├── runners/           实验入口点（调用管线/提供商/LLM）
├── analysis/          按主题组织的离线报告生成器
│   ├── reconcile/     消融实验、案例研究、Oracle 上界、上下文诊断
│   ├── traceability/  引用有效性 / 跨度边界 / 可追溯 F1
│   ├── baselines/     B0..B10 LLM 基线 + prompt-only 扫描 + 汇总表
│   ├── arbitrator/    仲裁器数据集 + 策略评估器
│   ├── benchmark_b/   多语言试点选择 + Phase 2 指标
│   ├── dataset_curation/  就绪度、来源清单、扩展、对齐、泄露检测
│   ├── paper_artifacts/   论文专用表格（G1/G2/main paper/rescue）
│   └── diagnostics/   Grounding、native gain、extraction、baselines、block recall、reconcile errors
├── layer3/            已弃用垫片：重定向到 core/datasets/runners/analysis（Phase 6 移除）
├── literature_acquisition/  已弃用垫片：重定向到 runners（Phase 6 移除）
├── pipeline/          已弃用垫片 + 测试 PDF + 报告（运行器已移至 runners/）
├── annotation/        遗留标注数据（源 PDF + markdown）
├── optimization/      Prompt 优化实验（fused75 消融、裁决）
├── scripts/           基准工具脚本
├── data/              所有数据产物（适当位置 git 忽略）
│   ├── ground_truth/  {unified, clingen, clinvar_fused, rett, parkinson}
│   ├── inputs/        {pipeline, literature_acquisition}
│   └── reports/       {eval, reconcile, traceability, baseline, benchmark_b,
│                       curation, paper, diagnostics, clinvar_fused, pipeline_e2e}
└── README.md
```

## 规范导入

跨切面原语位于 `benchmark.core`：

```python
from benchmark.core import (
    FieldMatch, EntryMetrics,
    compare_evidence, fuzzy_match_value, normalize_comparison_text,
    compute_aggregate_metrics,
    GROUND_TRUTH_ROOT, GROUND_TRUTH_UNIFIED_ROOT, GROUND_TRUTH_CLINGEN_ROOT,
    REPORTS_ROOT, RAW_PDF_ROOT,
    submit_and_poll, evaluate_one, run_evaluation,
)
```

`GROUND_TRUTH_ROOT` 默认指向**统一**数据集（150 条目）。

## 常用入口点

| 目标 | 命令 |
|------|------|
| 运行统一基准（默认） | `python -m benchmark.layer3.evaluate --help` |
| 运行分片 | `python -m benchmark.layer3.evaluate --shard-index 0 --shard-size 10` |
| 运行子集 | `python -m benchmark.layer3.evaluate --entries gs_000 gs_001` |
| 运行管线基准 | `python -m benchmark.runners.pipeline_e2e --help` |
| 下载文献 | `python -m benchmark.runners.literature_acquisition download --help` |
| Rett 文献管线 | `python -m benchmark.runners.literature_rett --help` |
| ClinVar 融合评估 | `python -m benchmark.datasets.clinvar_fused.evaluate_fused --write` |
| 构建论文表格 | `python -m benchmark.analysis.paper_artifacts.main_paper_tables --help` |

## 统一金标准数据集（默认）

**2026-06-25 起的默认基准数据集。** 四个来源数据集的 schema 统一超集，150 条目位于 `benchmark/data/ground_truth/unified/gs_NNN/`。

每个 `gs_NNN/` 目录完全自包含：`expected.json`（统一 schema）、`source.md`（+ 多语言 `source_*.md`）、`source.pdf`。所有条目共享一个扁平、字段完整的 schema。

### 来源溯源

每个统一条目携带到原始数据集的溯源信息。权威来源为 `unified/manifest.json`（schema 版本 1.1.0）。

### 分层评估

报告统一数据集的基准指标时，**按 `source_dataset` 分层**。聚合数字会掩盖每个数据集的性能差异。

### 批量/分片执行

```bash
# 完整数据集（150 条目）
cd backend && uv run python -m benchmark.layer3.evaluate

# 单个分片（每分片 10 条目）
uv run python -m benchmark.layer3.evaluate --shard-index 0 --shard-size 10

# 特定条目
uv run python -m benchmark.layer3.evaluate --entries gs_000 gs_001 gs_002

# 带并发
uv run python -m benchmark.layer3.evaluate --shard-index 0 --shard-size 20 --concurrency 4
```

## 配置

`benchmark/config/` 中的两种互补机制：

- **Ansible** 渲染可调/密钥配置文件到消费者位置
- **`defaults.py`** 是运行时代码常量的规范来源

详见 `benchmark/config/README.md`。

## 弃用垫片

2026-06-18 重构保留了所有遗留点分路径。以下前缀的导入仍然有效但会发出 `DeprecationWarning`，计划在 Phase 6 移除：

| 遗留前缀 | 新位置 |
|----------|--------|
| `benchmark.layer3.evaluate` | `benchmark.core` |
| `benchmark.layer3.mondo_hierarchy` | `benchmark.core.mondo_hierarchy` |
| `benchmark.layer3.analysis.<x>` | `benchmark.analysis.<group>.<module>` |
| `benchmark.pipeline.benchmark` | `benchmark.runners.pipeline_e2e` |
| `benchmark.literature_acquisition.*` | `benchmark.runners.*` |

## 测试

```bash
cd backend && uv run pytest tests/benchmark/ -q
```
