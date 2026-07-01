# Layer 3 Analysis

> **状态：已弃用垫片。** 本包（`benchmark/layer3/analysis/`）仅包含 2026-06-18 框架重构后的向后兼容导入垫片。所有分析模块已移至 `benchmark.analysis.*` 主题子组。垫片将在重构 Phase 6 移除。

## 概述

BIBM Layer 3 基准表格、可追溯性检查、多语言证据增强、诊断和论文附件的离线报告生成器。遗留的扁平 `benchmark.layer3.analysis.<name>` 导入通过垫片保留，新代码必须从以下规范位置导入。

## 新模块位置

### 数据集管理（`benchmark.analysis.dataset_curation`）

| 旧名称 | 新路径 | 用途 |
|--------|--------|------|
| `alignment_metrics` | `benchmark.analysis.dataset_curation.alignment_metrics` | 对齐标注准确率 |
| `evidence_augmentation_metrics` | `benchmark.analysis.dataset_curation.evidence_augmentation_metrics` | 仅英文 vs 多语言证据矩阵 |
| `benchmark_readiness` | `benchmark.analysis.dataset_curation.readiness` | 冻结 Benchmark A 标注覆盖 |
| `source_inventory` | `benchmark.analysis.dataset_curation.source_inventory` | ClinVar 锚点 + 多语言 PDF 清单 |
| `select_expansion_entries` | `benchmark.analysis.dataset_curation.select_expansion` | Benchmark C 扩展切片选择 |
| `leakage_check` | `benchmark.analysis.dataset_curation.leakage_check` | 数据泄露检测 |
| `materialize_phase2_artifacts` | `benchmark.analysis.dataset_curation.materialize_phase2_artifacts` | 物化 Phase 2 产物 |

### Benchmark B（`benchmark.analysis.benchmark_b`）

| 旧名称 | 新路径 | 用途 |
|--------|--------|------|
| `select_benchmark_b_pilot` | `benchmark.analysis.benchmark_b.pilot_selection` | 冻结多语言 N=10 试点 |
| `benchmark_b_phase2_queue` | `benchmark.analysis.benchmark_b.phase2_queue` | 排队 zh/ja/ko Phase 2 条目 |
| `benchmark_b_phase2_runtime_metrics` | `benchmark.analysis.benchmark_b.phase2_runtime_metrics` | Phase 2 运行时性能指标 |

### Reconcile（`benchmark.analysis.reconcile`）

| 旧名称 | 新路径 | 用途 |
|--------|--------|------|
| `reconcile_ablation` | `benchmark.analysis.reconcile.ablation` | 消融实验调和 |
| `reconcile_case_studies` | `benchmark.analysis.reconcile.case_studies` | 案例研究调和 |
| `reconcile_oracle_upper_bound` | `benchmark.analysis.reconcile.oracle_upper_bound` | Oracle 上界分析 |
| `contextual_reconcile_diagnosis` | `benchmark.analysis.reconcile.contextual_diagnosis` | 上下文调和诊断 |

### Traceability（`benchmark.analysis.traceability`）

| 旧名称 | 新路径 | 用途 |
|--------|--------|------|
| `traceability_metrics` | `benchmark.analysis.traceability.metrics` | 可追溯性指标报告 |

### Arbitrator（`benchmark.analysis.arbitrator`）

| 旧名称 | 新路径 | 用途 |
|--------|--------|------|
| `arbitrator_dataset` | `benchmark.analysis.arbitrator.dataset` | 仲裁器数据集构建器 |
| `arbitrator_policy_eval` | `benchmark.analysis.arbitrator.policy_eval` | 仲裁器策略评估 |

### Diagnostics（`benchmark.analysis.diagnostics`）

| 旧名称 | 新路径 | 用途 |
|--------|--------|------|
| `diagnose_baselines` | `benchmark.analysis.diagnostics.baselines` | 基线诊断 |
| `diagnose_block_recall` | `benchmark.analysis.diagnostics.block_recall` | 块召回诊断 |
| `diagnose_extraction` | `benchmark.analysis.diagnostics.extraction` | 提取诊断 |

### Paper Artifacts（`benchmark.analysis.paper_artifacts`）

| 旧名称 | 新路径 | 用途 |
|--------|--------|------|
| `g1_decision` | `benchmark.analysis.paper_artifacts.g1_decision` | G1 决策表 |
| `g2_statistics` | `benchmark.analysis.paper_artifacts.g2_statistics` | G2 统计表 |
| `main_paper_tables` | `benchmark.analysis.paper_artifacts.main_paper_tables` | 主论文表格 |
| `main_paper_rescue_manifest` | `benchmark.analysis.paper_artifacts.main_paper_rescue_manifest` | Rescue 清单 |

## 快速开始

所有命令使用**规范**导入路径：

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.alignment_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.evidence_augmentation_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.benchmark_b.pilot_selection --write
```

## 架构

```text
data/ground_truth/clingen/selection.json
  -> 每条目期望文件和 phase_2/extraction_result.json
  -> 分析模块（benchmark.analysis.* 下）
  -> 类型化数据类报告
  -> data/reports/{group}/*.json
```

分析模块为离线设计：从 `benchmark/data/ground_truth` 读取冻结产物，计算确定性指标，可选写入 JSON 报告。

## 报告输出分组

| 报告组 | 路径 | 内容 |
|--------|------|------|
| `eval` | `data/reports/eval/` | 端到端评估报告 |
| `reconcile` | `data/reports/reconcile/` | 调和消融和案例研究 |
| `baseline` | `data/reports/baseline/` | LLM 基线报告和汇总表 |
| `traceability` | `data/reports/traceability/` | 可追溯性指标报告 |
| `benchmark_b` | `data/reports/benchmark_b/` | 多语言试点 Phase 2 输出 |
| `curation` | `data/reports/curation/` | 数据集管理/就绪度/清单 |
| `paper` | `data/reports/paper/` | 论文专用表格和 rescue 清单 |
| `diagnostics` | `data/reports/diagnostics/` | 诊断输出 |
