# Benchmark Framework Refactor Plan

> 重构 `benchmark/` 顶层框架。当前 4 个并列子目录 + `analysis/` 散落在两层、35+ analysis 脚本扁平堆放、reports 目录混杂 ~300 个文件、命名层(`layer3` vs `pipeline` vs `literature_acquisition`)语义混乱、跨目录 import 互相绑死。这份计划给出**一次性切换**的目标布局、迁移步骤、回归门槛。

**Tech Stack:** Python 3.12 + `uv`, `pytest`, Ruff;  保持 `from benchmark.*` 包路径稳定可消费;  ground truth/reports/PDF 资产搬迁但不改内容。

---

## 1. 现状审计 (Why Refactor)

### 1.1 体量

| 路径 | 文件数 | LOC | 备注 |
|------|--------|-----|------|
| `benchmark/layer3/` (root) | 9 .py | 2,900 | `evaluate.py` 单文件 1,124 行,既做 PDF 生成又做评分还做 pipeline 客户端 |
| `benchmark/layer3/analysis/` | 34 .py | 12,756 | 真正的"分析层";扁平堆放,无主题分组 |
| `benchmark/layer3/baselines/` | 11 .py | 1,140 | LLM baseline B0–B10 |
| `benchmark/layer3/clinvar_fused/` | 7 .py | 2,161 | 与 layer3 主流程并列的另一份 dataset |
| `benchmark/literature_acquisition/` | 2 .py | ~1,856 | 文献下载器 (general + rett) |
| `benchmark/pipeline/` | 2 .py | 911 | HTTP 端到端 benchmark |
| `benchmark/annotation/` | src+cli | ~1,700 (+ .venv) | 独立 uv 项目,自带依赖 |
| `benchmark/analysis/` (顶层) | 2 .py | 400 | `diagnose_grounding`, `diagnose_native_gain` |

### 1.2 问题

1. **顶层语义不一致**。`layer3` 是按"评估层级"命名,`pipeline` 是按"被测对象"命名,`literature_acquisition` 是按"业务阶段"命名,`annotation` 是按"工作流"命名,`analysis` 是按"动作"命名。读者无法一眼分辨是 dataset、runner 还是 reporter。
2. **`layer3/evaluate.py` 是一个 1,124 行的瑞士军刀**:同时承担
   - PDF 生成 (`markdown_to_pdf_bytes`,`_sanitize_for_pdf`)
   - 文本归一化与 fuzzy matching (`normalize_comparison_text`, `fuzzy_match_value`)
   - Pipeline HTTP 客户端 (`submit_and_poll`, `evaluate_one`)
   - DB 直查实体绑定 (`compare_entity_standardization`, `compare_track_consistency`)
   - 聚合指标 (`compute_aggregate_metrics`)
   - CLI 入口 (`run_evaluation`)
   全部以"模块路径"作为外部稳定 API,任何 analysis 脚本都 `from benchmark.layer3.evaluate import GROUND_TRUTH_DIR, REPORTS_DIR, FieldMatch, EntryMetrics, compare_evidence`。这把 `evaluate.py` 钉成了事实上的"benchmark/contracts.py"+"benchmark/runner.py"+"benchmark/utils.py"。
3. **`analysis/` 扁平 35 文件**,主题至少 7 类(reconcile ablation、traceability、g1/g2 决策、benchmark B 队列、源清单、phase2 物化、诊断、main paper 表格、套利模型)却没有目录分组。`reconcile_*.py` 4 份、`diagnose_*.py` 5 份、`benchmark_b_*.py` 3 份、`main_paper_*.py` 3 份散在同一层。
4. **`benchmark/analysis/` (顶层) 只有 2 个 diagnose 脚本**,被 `benchmark/layer3/analysis/g1_decision.py` 反向引用。这条目录与 `benchmark/layer3/analysis/` 重名只差一层,容易误导;实质是被遗忘的早期 refactor 残留。
5. **数据资产与代码混在同一目录**。`benchmark/layer3/ground_truth/` 35 项 + `benchmark/layer3/clinvar_fused/ground_truth/` 76 项 + `benchmark/layer3/reports/` 305 文件,与 .py 模块平级,gitignore/打包/搜索都受拖累。
6. **reports 目录无组织**。305 个 timestamped JSON,文件名前缀已经隐含 50+ 种 "report kind" (`reconcile_ablation_*`, `g2_statistics_*`, `traceability_*`, `baseline_*`, `main_paper_tables_*`, `benchmark_b_phase2_*` ...) 但全部平铺。最新一份 `main_paper_tables_*.csv/.md` 出现 14 次重复。
7. **跨目录隐式耦合**:
   - `benchmark/pipeline/evidence_metrics.py` 被 `benchmark/layer3/evaluate.py` 反向 import (`from benchmark.pipeline.evidence_metrics import query_evidence_metrics`)。`layer3` 评测器依赖名为 "pipeline" 的兄弟目录,只为复用一个 DB 查询函数。
   - `benchmark/analysis/diagnose_*` 被 `benchmark/layer3/analysis/g1_decision.py` import,但本身不在 `layer3/` 之下。
   - `benchmark/annotation/` 自带 `.venv/` 与 `pyproject.toml`,与项目主 uv 工作区脱钩,加大 CI 与依赖审计成本。
8. **命名前缀与论文阶段绑死**。`benchmark_b_phase2_*`、`main_paper_*`、`g1_decision`、`g2_statistics`、`bibm_*` 这些名字编码的是 BIBM 论文里的 milestone,不是评测能力。论文换 venue 之后这些名字会成为僵尸前缀。
9. **`pipeline/manifest.json.bak`、`__pycache__/` 多份残留**。基本卫生缺失。
10. **测试目录已就位** (`backend/tests/benchmark/layer3/...`),但跟随源码扁平结构,任何分组迁移都要同步重命名 `from benchmark.layer3.analysis.* import ...`。

### 1.3 跨目录引用矩阵 (search 结果)

```
benchmark/layer3/analysis/* ──> benchmark/layer3/evaluate (54 处)
benchmark/layer3/analysis/g1_decision ──> benchmark/analysis/diagnose_grounding
                                       ──> benchmark/analysis/diagnose_native_gain
benchmark/layer3/evaluate ──> benchmark/pipeline/evidence_metrics
benchmark/layer3/baselines/runner ──> benchmark/layer3/evaluate
benchmark/layer3/clinvar_fused/* ──> benchmark/layer3/evaluate (mondo, fuzzy, FieldMatch)
backend/tests/benchmark/layer3/* ──> benchmark/layer3/...  (41 文件)
docs/active/2026-06-1*-bibm-* ──> benchmark/layer3/...     (高频引用路径)
```

**结论**: `benchmark/layer3/evaluate.py` + `ground_truth/` + `reports/` 是事实上的项目级共享层,但被关在 `layer3/` 子目录里。重构必须把它们提到顶层。

---

## 2. 重构目标 (What Good Looks Like)

1. **顶层语义单一维度**:子目录命名沿"评测对象 / 数据集 / 工具 / 资产"四类轴,任何新读者一眼分辨。
2. **`evaluate.py` 拆解**为独立的 `contracts` / `matching` / `aggregate` / `runner` / `pdf` 模块,各自可单测。
3. **共享数据资产**(`ground_truth/`、`reports/`、PDF 输入)上提到顶层,与代码隔离。
4. **`analysis/` 按主题分组**:reconcile / traceability / baselines / benchmark_b / dataset_curation / paper_artifacts / diagnostics。
5. **`benchmark/analysis/`(顶层 2 文件)合并进 `analysis/diagnostics/`**,移除"两层同名 analysis"的歧义。
6. **`pipeline/evidence_metrics.py` 上提到 `benchmark/common/`**,切断 layer3 → pipeline 反向依赖。
7. **paper-specific 命名脱壳**:`g1_decision`、`g2_statistics`、`main_paper_*`、`benchmark_b_*` 落入 `analysis/paper_artifacts/`,保留语义但不再霸占 root。
8. **`benchmark/annotation/` 维持独立 uv 子项目** (这是它的设计意图,标注流程与主依赖隔离),但**所在路径改名 + 输出目录迁出**,`.venv/` 加入 .gitignore 验证。
9. **`reports/` 二级分桶** (`reports/<category>/<timestamp>.json`),保留时间戳但按报告种类归档。
10. **公共 API 通过 `benchmark/__init__.py` re-export 关键 symbol**,允许 `from benchmark import GROUND_TRUTH_DIR, FieldMatch, EntryMetrics`,降低长 import 痛感。

## 3. 目标布局 (Target Tree)

```text
benchmark/
├── README.md                              # 顶层导览,指向各子模块 README
├── __init__.py                            # re-export contracts + paths
│
├── core/                                  # 跨数据集共享: contracts, matching, runner
│   ├── __init__.py
│   ├── contracts.py                       # FieldMatch, EntryMetrics, EntryStatus
│   ├── matching.py                        # normalize_comparison_text, fuzzy_match_value, compare_evidence
│   ├── aggregate.py                       # compute_aggregate_metrics, _false_positive_count, _over_extraction_count
│   ├── pdf.py                             # markdown_to_pdf_bytes, _sanitize_for_pdf
│   ├── pipeline_client.py                 # submit_and_poll, evaluate_one, run_evaluation, load_proxy
│   ├── evidence_metrics.py                # 移自 pipeline/evidence_metrics.py (DB 查询)
│   ├── mondo_hierarchy.py                 # 从 layer3/ 上移
│   ├── paths.py                           # GROUND_TRUTH_ROOT, REPORTS_ROOT, RAW_PDF_ROOT (集中常量)
│   └── README.md
│
├── datasets/                              # 数据集层:每个 dataset 一个垂直切片
│   ├── README.md
│   ├── clingen/                           # 原 layer3 root (除 evaluate 等已上移外的内容)
│   │   ├── __init__.py
│   │   ├── select_entries.py
│   │   ├── fetch_literature.py
│   │   ├── download_pdfs.py
│   │   ├── generate_ground_truth.py
│   │   ├── preprocess.py
│   │   ├── visualize.py
│   │   └── README.md
│   ├── clinvar_fused/                     # 原 layer3/clinvar_fused/
│   │   ├── select_fused_entries.py
│   │   ├── fetch_variant_literature.py
│   │   ├── download_articles.py
│   │   ├── generate_pdfs.py
│   │   ├── translate_to_multilingual.py
│   │   ├── hgvs_normalize.py
│   │   ├── evaluate_fused.py              # 仅 dataset-specific 评分逻辑;复用 core.matching
│   │   └── README.md
│   └── rett_annotation/                   # 原 benchmark/annotation/
│       ├── pyproject.toml                 # 保留独立 uv 项目
│       ├── src/, cli/, config.yaml, ...
│       └── README.md
│
├── runners/                               # 真正"跑测"的入口
│   ├── README.md
│   ├── pipeline_e2e.py                    # 原 pipeline/benchmark.py
│   ├── literature_acquisition.py          # 原 literature_acquisition/benchmark.py (general)
│   ├── literature_rett.py                 # 原 literature_acquisition/rett_download.py
│   └── clingen_eval.py                    # 原 layer3/evaluate.py 的 CLI 部分(仅 main + arg parsing)
│
├── analysis/                              # 报告生成器,按主题分组
│   ├── README.md
│   ├── reconcile/
│   │   ├── ablation.py                    # reconcile_ablation
│   │   ├── case_studies.py                # reconcile_case_studies
│   │   ├── oracle_upper_bound.py          # reconcile_oracle_upper_bound
│   │   └── contextual_diagnosis.py        # contextual_reconcile_diagnosis
│   ├── traceability/
│   │   └── metrics.py                     # traceability_metrics
│   ├── baselines/
│   │   ├── llm_common.py
│   │   ├── runner.py
│   │   ├── naive_llm.py
│   │   ├── translate_then_extract.py
│   │   ├── original_only.py
│   │   ├── rag_llm.py
│   │   ├── single_agent_cot.py
│   │   ├── prompt_model_sweep.py
│   │   ├── model_sweep_contracts.py
│   │   └── prompt_model_baseline_tables.py
│   ├── arbitrator/
│   │   ├── dataset.py                     # arbitrator_dataset
│   │   └── policy_eval.py                 # arbitrator_policy_eval
│   ├── benchmark_b/                       # multilingual pilot
│   │   ├── pilot_selection.py             # select_benchmark_b_pilot
│   │   ├── phase2_queue.py                # benchmark_b_phase2_queue
│   │   ├── phase2_runtime_metrics.py
│   │   └── phase2_sample_runner.py
│   ├── dataset_curation/
│   │   ├── readiness.py                   # benchmark_readiness
│   │   ├── source_inventory.py
│   │   ├── select_expansion.py            # select_expansion_entries
│   │   ├── expansion_artifact_coverage.py
│   │   ├── alignment_annotation_protocol.py
│   │   ├── generate_alignment_annotations.py
│   │   ├── alignment_metrics.py
│   │   ├── evidence_augmentation_metrics.py
│   │   ├── leakage_check.py
│   │   ├── inventory_system_runs.py
│   │   ├── phase2_artifact_coverage.py
│   │   ├── materialize_phase2_artifacts.py
│   │   ├── run_phase2_artifact_batch.py
│   │   └── report_from_system_runs.py
│   ├── paper_artifacts/                   # 论文专属:命名保留,但隔离掉
│   │   ├── g1_decision.py
│   │   ├── g2_statistics.py
│   │   ├── main_paper_tables.py
│   │   └── main_paper_rescue_manifest.py
│   └── diagnostics/                       # 合并 benchmark/analysis/* + layer3/analysis/diagnose_*
│       ├── grounding.py                   # diagnose_grounding
│       ├── native_gain.py                 # diagnose_native_gain
│       ├── extraction.py                  # diagnose_extraction
│       ├── baselines.py                   # diagnose_baselines
│       ├── block_recall.py                # diagnose_block_recall
│       └── reconcile_errors.py            # diagnose_reconcile_errors
│
├── data/                                  # 资产层 (.gitignore 全部 PDF/中间产物;ground_truth 选择性入库)
│   ├── ground_truth/
│   │   ├── clingen/                       # 原 layer3/ground_truth/clingen_NNN/
│   │   ├── clinvar_fused/                 # 原 layer3/clinvar_fused/ground_truth/
│   │   └── rett/                          # 原 layer3/ground_truth/rett/
│   ├── inputs/
│   │   ├── pipeline/                      # 原 pipeline/input/  (case_report PDFs)
│   │   └── literature/                    # 原 literature_acquisition/downloads/
│   └── reports/                           # 原 layer3/reports/, 二级分桶
│       ├── eval/
│       ├── reconcile/
│       ├── baseline/
│       ├── traceability/
│       ├── benchmark_b/
│       ├── paper/
│       └── diagnostics/
│
└── tests/                                 # (可选) 顶层 smoke tests; 主测试仍在 backend/tests/benchmark/

```

### 3.1 关键决策注脚

- **`benchmark/data/`** 是新增物理目录。`ground_truth/clingen_*/` 等子目录文件本体不动,只换路径前缀。`reports/` 进入按报告 kind 的二级分桶,这是真正的清洁工作,后文有迁移脚本。
- **`runners/`** 与 **`analysis/`** 区分**"跑实验产生 report"** vs **"读取 report 出报表"**。前者会发起 HTTP/LLM 调用,后者纯离线。当前两者混在一起,`analysis/run_phase2_artifact_batch.py` 实际是 runner,要随之上移到 `runners/phase2_batch.py`。
- **`paper_artifacts/`** 故意单列,允许在论文 milestone 结束后 **整体归档**到 `archive/`,不会影响其他模块。
- **`rett_annotation/`** 保留独立 `pyproject.toml`(确实独立工具链,主项目无 `MinerU` SDK 依赖),但放进 `datasets/` 后 `.venv` 通过 `.gitignore` 全局排除,`logs/`、`draft/`、`approved/`、`rejected/`、`ground_truth/` 一律迁到 `benchmark/data/ground_truth/rett/` 与 `benchmark/data/inputs/rett_annotation/`。


---

## 4. `evaluate.py` 拆分蓝图

`benchmark/layer3/evaluate.py` (1,124 行) 切成 6 个目标模块。映射表如下:

| 现 evaluate.py 区间 | 目标模块 | 关键 symbol |
|----|----|----|
| L40–L45 (path/poll/terminal 常量) | `core/paths.py` + `core/pipeline_client.py` | `GROUND_TRUTH_DIR/REPORTS_DIR -> GROUND_TRUTH_ROOT/REPORTS_ROOT`、`POLL_INTERVAL_S`、`MAX_POLL_ATTEMPTS`、`TERMINAL_STATUSES` |
| L48–L67 (`_run_id_from_status_url`、`preflight_database_connection`) | `core/pipeline_client.py` | 内部工具 |
| L72–L130 (PDF 生成) | `core/pdf.py` | `_sanitize_for_pdf`、`markdown_to_pdf_bytes` |
| L135–L165 (Unicode 归一化常量与函数) | `core/matching.py` | `normalize_comparison_text` |
| L168–L214 (dataclasses) | `core/contracts.py` | `FieldMatch`、`EntryMetrics` |
| L217–L394 (匹配算法) | `core/matching.py` | `fuzzy_match_value`、`compare_evidence`、`mark_expected_fields_missing`、内部 `_score_components`、`_optional_*` |
| L409–L500 (DB 直查 std/track) | `core/pipeline_client.py` (短期);中期可拆 `core/db_metrics.py` | `compare_entity_standardization`、`compare_track_consistency` |
| L501–L808 (HTTP submit/poll/evaluate_one、proxy) | `core/pipeline_client.py` | `submit_and_poll`、`load_proxy`、`evaluate_one` |
| L808–L957 (聚合) | `core/aggregate.py` | `_false_positive_count`、`_over_extraction_count`、`compute_aggregate_metrics` |
| L959–end (`run_evaluation`+ CLI) | `runners/clingen_eval.py` | 仅保留 argparse + 顶层 `main()`,所有依赖通过 `core` import |

### 4.1 `core/__init__.py` re-export 规则

```python
# benchmark/core/__init__.py
from .contracts import FieldMatch, EntryMetrics
from .matching import (
    normalize_comparison_text,
    fuzzy_match_value,
    compare_evidence,
    mark_expected_fields_missing,
)
from .aggregate import compute_aggregate_metrics
from .paths import (
    GROUND_TRUTH_ROOT,
    REPORTS_ROOT,
    RAW_PDF_ROOT,
    # 兼容别名(过渡期):
    GROUND_TRUTH_ROOT as GROUND_TRUTH_DIR,
    REPORTS_ROOT as REPORTS_DIR,
)
from .pipeline_client import (
    POLL_INTERVAL_S,
    MAX_POLL_ATTEMPTS,
    TERMINAL_STATUSES,
    submit_and_poll,
    evaluate_one,
    run_evaluation,
    load_proxy,
)
```

并在 `benchmark/__init__.py` re-export 关键 symbol,使下列 import 都成立:

```python
from benchmark.core import FieldMatch, EntryMetrics, compare_evidence, GROUND_TRUTH_ROOT
from benchmark import GROUND_TRUTH_ROOT  # 顶层捷径
```

### 4.2 兼容期 shim (1 个 release)

保留 `benchmark/layer3/__init__.py` + `benchmark/layer3/evaluate.py` 作为 **stub**,内容只有:

```python
# benchmark/layer3/evaluate.py  (transitional shim, remove after v2 cutover)
import warnings
from benchmark.core.contracts import FieldMatch, EntryMetrics  # noqa: F401
from benchmark.core.matching import (  # noqa: F401
    normalize_comparison_text,
    fuzzy_match_value,
    compare_evidence,
    mark_expected_fields_missing,
)
from benchmark.core.aggregate import compute_aggregate_metrics  # noqa: F401
from benchmark.core.paths import (  # noqa: F401
    GROUND_TRUTH_ROOT as GROUND_TRUTH_DIR,
    REPORTS_ROOT as REPORTS_DIR,
)
from benchmark.core.pipeline_client import (  # noqa: F401
    POLL_INTERVAL_S,
    MAX_POLL_ATTEMPTS,
    TERMINAL_STATUSES,
    submit_and_poll,
    evaluate_one,
    run_evaluation,
    load_proxy,
)

warnings.warn(
    "benchmark.layer3.evaluate is deprecated; import from benchmark.core instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

这样 41 处 `backend/tests/benchmark/layer3/test_*.py` 与 14 篇 docs/active 论文计划文档**不需要立刻改路径**,迁移可分阶段。第 7 节给出何时拆除该 shim 的 gate。


---

## 5. analysis/ 主题分组细则

| 现 `benchmark/layer3/analysis/` | 新归属 |
|----|----|
| `reconcile_ablation.py` | `analysis/reconcile/ablation.py` |
| `reconcile_case_studies.py` | `analysis/reconcile/case_studies.py` |
| `reconcile_oracle_upper_bound.py` | `analysis/reconcile/oracle_upper_bound.py` |
| `contextual_reconcile_diagnosis.py` | `analysis/reconcile/contextual_diagnosis.py` |
| `traceability_metrics.py` | `analysis/traceability/metrics.py` |
| `arbitrator_dataset.py` | `analysis/arbitrator/dataset.py` |
| `arbitrator_policy_eval.py` | `analysis/arbitrator/policy_eval.py` |
| `select_benchmark_b_pilot.py` | `analysis/benchmark_b/pilot_selection.py` |
| `benchmark_b_phase2_queue.py` | `analysis/benchmark_b/phase2_queue.py` |
| `benchmark_b_phase2_runtime_metrics.py` | `analysis/benchmark_b/phase2_runtime_metrics.py` |
| `benchmark_b_phase2_sample_runner.py` | `runners/phase2_sample_runner.py` (这是 runner 不是 analyzer) |
| `benchmark_readiness.py` | `analysis/dataset_curation/readiness.py` |
| `source_inventory.py` | `analysis/dataset_curation/source_inventory.py` |
| `select_expansion_entries.py` | `analysis/dataset_curation/select_expansion.py` |
| `expansion_artifact_coverage.py` | `analysis/dataset_curation/expansion_artifact_coverage.py` |
| `alignment_annotation_protocol.py` | `analysis/dataset_curation/alignment_annotation_protocol.py` |
| `generate_alignment_annotations.py` | `analysis/dataset_curation/generate_alignment_annotations.py` |
| `alignment_metrics.py` | `analysis/dataset_curation/alignment_metrics.py` |
| `evidence_augmentation_metrics.py` | `analysis/dataset_curation/evidence_augmentation_metrics.py` |
| `leakage_check.py` | `analysis/dataset_curation/leakage_check.py` |
| `inventory_system_runs.py` | `analysis/dataset_curation/inventory_system_runs.py` |
| `phase2_artifact_coverage.py` | `analysis/dataset_curation/phase2_artifact_coverage.py` |
| `materialize_phase2_artifacts.py` | `analysis/dataset_curation/materialize_phase2_artifacts.py` |
| `run_phase2_artifact_batch.py` | `runners/phase2_batch.py` (这是 runner) |
| `report_from_system_runs.py` | `analysis/dataset_curation/report_from_system_runs.py` |
| `g1_decision.py` | `analysis/paper_artifacts/g1_decision.py` |
| `g2_statistics.py` | `analysis/paper_artifacts/g2_statistics.py` |
| `main_paper_tables.py` | `analysis/paper_artifacts/main_paper_tables.py` |
| `main_paper_rescue_manifest.py` | `analysis/paper_artifacts/main_paper_rescue_manifest.py` |
| `prompt_model_baseline_tables.py` | `analysis/baselines/prompt_model_baseline_tables.py` |
| `diagnose_baselines.py` | `analysis/diagnostics/baselines.py` |
| `diagnose_block_recall.py` | `analysis/diagnostics/block_recall.py` |
| `diagnose_extraction.py` | `analysis/diagnostics/extraction.py` |
| `diagnose_reconcile_errors.py` | `analysis/diagnostics/reconcile_errors.py` |
| `benchmark/analysis/diagnose_grounding.py` | `analysis/diagnostics/grounding.py` |
| `benchmark/analysis/diagnose_native_gain.py` | `analysis/diagnostics/native_gain.py` |

`benchmark/layer3/baselines/*` 整体上移到 `benchmark/analysis/baselines/`,内部 `runner.py` 的 `from benchmark.layer3.evaluate import ...` 改为 `from benchmark.core import ...`。

`benchmark/layer3/baselines/prompt_model_sweep_*.json`、`prompt_model_sweep.example.json` 这类 manifest 数据离开代码目录,移入 `benchmark/data/baselines/manifests/`。

## 6. reports/ 二级分桶规则

扫描已有 305 个 `reports/*.json/.md/.csv` 文件名前缀,按下列正则归桶。规则与归档脚本同时入库,后续新报告写入对应子目录。

| 子目录 | 文件名前缀 |
|----|----|
| `data/reports/eval/` | `eval_*`、`eval_db_inventory_*` |
| `data/reports/reconcile/` | `reconcile_ablation_*`、`reconcile_case_studies_*`、`reconcile_oracle_upper_bound_*`、`reconcile_error_diagnosis_*`、`contextual_reconcile_diagnosis_*` |
| `data/reports/traceability/` | `traceability_*` |
| `data/reports/baseline/` | `baseline_*`、`prompt_model_baseline_tables_*`、`baseline_comparison_*` |
| `data/reports/benchmark_b/` | `benchmark_b_phase2_*` |
| `data/reports/diagnostics/` | `block_recall_diagnosis_*`、`grounding_*`、`native_gain_*` (现位于顶层 reports/ 时已没有,但保留前缀) |
| `data/reports/curation/` | `benchmark_readiness_*`、`source_inventory_*`、`expansion_*`、`alignment_*`、`evidence_augmentation_metrics_*`、`leakage_*`、`phase2_artifact_*`、`report_from_system_runs_*` |
| `data/reports/paper/` | `g1_decision_*`、`g2_statistics_*`、`main_paper_*`、`arbitrator_*` |

迁移脚本 `scripts/refactor_benchmark_reports.py`(Phase 2 创建,见 §8 Step 4)读取上述映射表,执行 `git mv`,失败的文件名(无前缀匹配)写入 `_unmapped/` 等待人工归类。

迁移完成后,各 analysis/runner 模块写入路径常量统一改为 `from benchmark.core.paths import REPORTS_ROOT`,并以 `REPORTS_ROOT / "<category>" / f"{kind}_{ts}.json"` 拼接。


---

## 7. 执行 Phase 划分

所有 phase 在隔离 worktree `wt/benchmark-refactor` 上执行。每个 phase 结束运行 7.1 中"per-phase gate",才 merge 进 dev。

### Phase 0 — Freeze & Branch  (0.5 day)

- 创建 worktree `wt/benchmark-refactor`,从 `dev` 分出。
- 冻结一份当前的 ruff/pytest baseline:`backend/tests/benchmark/` 全部用例先跑一遍,记录 pass count 与 import warning 数,落入 `lesson.md`。
- 在 `progress.txt` 起一行: `[2026-06-18] benchmark refactor phase 0 baseline pinned`。
- **不动任何文件**,仅采集 baseline。

### Phase 1 — `core/` 抽出 + 兼容 shim  (1 day)

目标:`benchmark/layer3/evaluate.py` 拆分到 `benchmark/core/*`,layer3 仅留 shim。

步骤:

1. 创建 `benchmark/core/` 与子模块文件骨架(空 docstring + 典型 `__all__`)。
2. 按 §4 表格逐节点搬代码,**逐节点跑**对应单元测试 (`backend/tests/benchmark/layer3/test_evaluate_matching.py` 等)。
3. `benchmark/core/paths.py` 与 `benchmark/core/__init__.py` 提供 §4.1 中所列符号 + 兼容别名。
4. `benchmark/layer3/evaluate.py` 替换为 §4.2 shim,**保留所有公共 symbol 名称**。
5. 把 `benchmark/pipeline/evidence_metrics.py` 内容搬到 `benchmark/core/evidence_metrics.py`。原文件改为 shim:`from benchmark.core.evidence_metrics import *`。
6. `benchmark/layer3/mondo_hierarchy.py` 搬到 `benchmark/core/mondo_hierarchy.py`,原路径 shim。

Gate:

- `pytest backend/tests/benchmark -q` 通过率与 baseline 一致 (允许新出现 `DeprecationWarning`,但 0 失败)。
- `ruff check benchmark/core benchmark/layer3/evaluate.py benchmark/pipeline/evidence_metrics.py` 通过。
- 手工 import smoke:`python -c "from benchmark.core import FieldMatch, compare_evidence, GROUND_TRUTH_ROOT"`。

### Phase 2 — `analysis/` 主题分组  (1.5 day)

目标:35 个 analysis 模块按 §5 表迁入 `benchmark/analysis/<group>/`,层级保持。

步骤:

1. 一次性 `git mv` 全表执行(不允许跨主题重命名两次)。
2. 每个被移动文件内部把 `from benchmark.layer3.evaluate import ...` → `from benchmark.core import ...`,把 `from benchmark.layer3.analysis.* import ...` → `from benchmark.analysis.<group>.* import ...`。
3. 同步更新 `backend/tests/benchmark/layer3/test_*.py` 中的 import (用 `lsp rename_file` + 手工跟改)。
4. `benchmark/layer3/analysis/__init__.py` 替换为 shim,把所有旧路径 re-export 到新路径并打 `DeprecationWarning`。
5. `benchmark/analysis/__init__.py`(原 `benchmark/analysis/`)合并到 `benchmark/analysis/diagnostics/__init__.py`,从顶层移除空目录。

Gate:

- `pytest backend/tests/benchmark -q` 0 失败。
- `ruff check benchmark/analysis backend/tests/benchmark` 通过。
- 至少 1 个 paper-artifact 命令端到端能跑:`python -m benchmark.analysis.paper_artifacts.main_paper_tables --reports-dir benchmark/data/reports/paper --dry-run`。


### Phase 3 — `runners/` 提取  (0.5 day)

目标:把"跑实验"模块从 layer3/pipeline/literature_acquisition 三处汇入 `benchmark/runners/`。

步骤:

1. 移动:
   - `benchmark/pipeline/benchmark.py` → `benchmark/runners/pipeline_e2e.py`
   - `benchmark/literature_acquisition/benchmark.py` → `benchmark/runners/literature_acquisition.py`
   - `benchmark/literature_acquisition/rett_download.py` → `benchmark/runners/literature_rett.py`
   - `benchmark/layer3/preprocess.py` → `benchmark/runners/clingen_preprocess.py`
   - `benchmark/layer3/analysis/run_phase2_artifact_batch.py` → `benchmark/runners/phase2_batch.py`
   - `benchmark/layer3/analysis/benchmark_b_phase2_sample_runner.py` → `benchmark/runners/benchmark_b_phase2_sample.py`
2. `benchmark/layer3/evaluate.py` 中 `run_evaluation` + CLI 移到 `benchmark/runners/clingen_eval.py`。`benchmark/layer3/evaluate.py` shim 内仍然 re-export `run_evaluation`(为旧文档命令行 `python -m benchmark.layer3.evaluate` 兼容,直到 Phase 6 删除 layer3)。
3. 各 runner 内的 `manifest.json`、`rett_config*.json`、`rett_syndrome_queries.txt` 等数据资源搬到 `benchmark/data/inputs/`。
4. `benchmark/pipeline/manifest.json.bak` 直接删除(无价值备份)。

Gate:

- `python -m benchmark.runners.pipeline_e2e --dry-run` 输出现有 manifest 列表。
- `python -m benchmark.runners.literature_acquisition --help` 正常。
- 旧路径 `python -m benchmark.pipeline.benchmark --dry-run` 仍能跑(走 shim)并打印 1 条 deprecation。

### Phase 4 — 资产搬迁 (`data/`)  (1 day)

目标:把 ground_truth、PDF 输入、reports 全部搬到 `benchmark/data/`,与代码彻底分离。

步骤:

1. `git mv benchmark/layer3/ground_truth/clingen_*  benchmark/data/ground_truth/clingen/`。
2. `git mv benchmark/layer3/ground_truth/rett       benchmark/data/ground_truth/rett/`。
3. `git mv benchmark/layer3/clinvar_fused/ground_truth  benchmark/data/ground_truth/clinvar_fused`。
4. `git mv benchmark/pipeline/input  benchmark/data/inputs/pipeline`。
5. `git mv benchmark/literature_acquisition/downloads  benchmark/data/inputs/literature_acquisition`。
6. `git mv benchmark/annotation/{ground_truth,draft,approved,rejected,archive,logs,reports}  benchmark/data/...`(rett-annotation 工作流目录全部搬出)。
7. 跑 `scripts/refactor_benchmark_reports.py`(本 plan §6 描述)对 305 份 reports 二级分桶。失败项写入 `benchmark/data/reports/_unmapped/`,人工归档。
8. `benchmark/core/paths.py` 一次性切换:`GROUND_TRUTH_ROOT = Path(__file__).resolve().parents[2] / "benchmark/data/ground_truth/clingen"`,`REPORTS_ROOT = ... / "benchmark/data/reports"`。**保留旧别名 `GROUND_TRUTH_DIR/REPORTS_DIR` 仅指向新位置**。
9. 兼容期(直到 Phase 6 结束)在 `benchmark/layer3/ground_truth/__init__.py` 不放,改用 `.gitkeep` 占位 + `README.md` 写明已迁移。

Gate:

- `git status` 显示纯 `R` (rename) + `M` 配置常量。
- `pytest backend/tests/benchmark -q` 通过(测试 fixture 通过 `GROUND_TRUTH_ROOT` 间接定位,所以路径常量切换后即可)。
- `ls benchmark/data/reports/_unmapped/` 为空或 ≤ 5 个,人工逐一归档。
- `du -sh benchmark/layer3/ benchmark/data/` 验证体量从前者全部转移到后者。

### Phase 5 — `datasets/` 收敛  (0.5 day)

目标:`layer3/` 目录最终只剩 shim;按数据集名重新组织 dataset-specific 代码到 `benchmark/datasets/`。

步骤:

1. `git mv benchmark/layer3/select_entries.py            benchmark/datasets/clingen/select_entries.py`。
2. `git mv benchmark/layer3/fetch_literature.py          benchmark/datasets/clingen/fetch_literature.py`。
3. `git mv benchmark/layer3/download_pdfs.py             benchmark/datasets/clingen/download_pdfs.py`。
4. `git mv benchmark/layer3/generate_ground_truth.py     benchmark/datasets/clingen/generate_ground_truth.py`。
5. `git mv benchmark/layer3/generate_rett_ground_truth.py benchmark/datasets/clingen/generate_rett_ground_truth.py`(虽然名字带 rett,实际只是 ClinGen-Rett 流程,内容审核后再决定是否归 rett_annotation)。
6. `git mv benchmark/layer3/visualize.py                 benchmark/datasets/clingen/visualize.py`。
7. `git mv benchmark/layer3/clinvar_fused/*              benchmark/datasets/clinvar_fused/`。
8. `git mv benchmark/annotation                          benchmark/datasets/rett_annotation`,确认 `pyproject.toml`、`config.yaml`、`.env.example`、`src/`、`cli/`、`uv.lock` 同步迁移。`.venv/` **不**搬,由用户在新位置 `uv sync` 重建;.gitignore 已覆盖。
9. 每个被迁文件 update import:`from benchmark.layer3.evaluate` → `from benchmark.core`。
10. `benchmark/layer3/__init__.py` 留 stub,写明 "deprecated, see benchmark/datasets/clingen and benchmark/core";`benchmark/pipeline/__init__.py`、`benchmark/literature_acquisition/__init__.py`、`benchmark/analysis/__init__.py` (顶层) 同样 shim 化。

Gate:

- `pytest backend/tests/benchmark -q` 0 失败。
- `ruff check benchmark/datasets benchmark/runners benchmark/core benchmark/analysis backend/tests/benchmark` 通过。
- 关键 CLI smoke:
  - `python -m benchmark.runners.clingen_eval --entries clingen_000 --dry-run`
  - `python -m benchmark.runners.pipeline_e2e --dry-run`
  - `python -m benchmark.analysis.paper_artifacts.main_paper_tables --dry-run`
  - `python -m benchmark.analysis.diagnostics.grounding --help`

### Phase 6 — 移除兼容 shim  (0.5 day,可拖到下一 release)

触发条件:

- 至少 1 周内 0 处 `DeprecationWarning` 出现在 `pytest backend/tests/benchmark` 与 nightly run。
- `docs/active/` 中所有引用 `benchmark/layer3` 的活跃 plan 已经更新或归档(查询命令: `grep -rn "benchmark/layer3" docs/active`)。
- `progress.txt` 中迁移条目已归档。

步骤:

1. 删除 `benchmark/layer3/`、`benchmark/pipeline/`、`benchmark/literature_acquisition/`、`benchmark/annotation/`(已成纯 shim 的目录)。
2. 删除 `benchmark/__init__.py` 中"过渡期别名"`GROUND_TRUTH_DIR`、`REPORTS_DIR` (规则改名为 `_ROOT`)。
3. 更新所有 docs/active、`progress.txt`、`lesson.md` 引用。
4. `benchmark/README.md` 重写,反映最终布局。
5. 关闭本 plan,归档到 `docs/archive/plans/2026-06-18-benchmark-framework-refactor-plan.md`。

Gate:

- `grep -rn "benchmark.layer3\\|benchmark.pipeline\\|benchmark.literature_acquisition\\|benchmark.annotation" benchmark/ backend/ docs/active/ scripts/` 命中数为 0(允许 docs/archive 命中)。
- `pytest backend/tests/benchmark -q` 0 失败、0 deprecation warning。


---

## 8. 配套脚本

1. `scripts/refactor_benchmark_reports.py` — 读 §6 映射表,`git mv` 旧 reports 到 `benchmark/data/reports/<bucket>/`,失败项写入 `_unmapped/`。
2. `scripts/refactor_benchmark_imports.py` — 一次性把 `from benchmark.layer3.evaluate` 等旧路径改写成新路径(用 `ast_edit` 风格的脚本,但作为一次性工具留在 `scripts/` 而非 `benchmark/`)。
3. `scripts/check_benchmark_paths.py` — pre-commit hook,禁止新代码写入 `benchmark/layer3/...`、`benchmark/pipeline/...` 路径(白名单仅允许 shim 文件)。
4. `.gitignore` 增量:
   - `benchmark/datasets/rett_annotation/.venv/`(rename 之后)
   - `benchmark/data/inputs/**/*.pdf`
   - `benchmark/data/inputs/**/*.json` (大批 download 报告) — 但保留 `benchmark/data/inputs/**/manifest.json`
   - `benchmark/data/reports/_unmapped/`

## 9. 测试与回归

- **单元测试**: 所有 `backend/tests/benchmark/layer3/test_*.py` 重命名为对应新主题路径 (`backend/tests/benchmark/core/...`、`.../analysis/reconcile/...`)。Phase 2 完成时统一一次,测试文件位置随源代码主题。
- **集成测试**: 新增 `backend/tests/benchmark/test_imports.py`,断言:
  - `benchmark.core.{FieldMatch, EntryMetrics, compare_evidence, GROUND_TRUTH_ROOT}` 可导入。
  - `benchmark.layer3.evaluate` 仍可导入但**触发 1 条 DeprecationWarning**(过渡期间)。
  - `benchmark.analysis.paper_artifacts.main_paper_tables` 可执行 `--help`。
- **回归报告**: 选 1 份完整 reconcile_ablation + g2_statistics + traceability_metrics 链路,在重构前后各跑一次,diff JSON 应只在 timestamp/git hash 字段上变化。
- **CI**: 在 PR 检查中加 `python scripts/check_benchmark_paths.py`,阻断新代码引入旧前缀。

## 10. 风险与对策

| 风险 | 影响 | 对策 |
|----|----|----|
| 论文计划文档(`docs/active/2026-06-1*-bibm-*`)硬编码大量 `benchmark/layer3/...` 路径 | 论文复现命令断裂 | Phase 1–5 全程保留 layer3 shim 与 `benchmark/data/reports/<bucket>/` 同名重定向(下表),论文里命令仍可工作。Phase 6 删除前由作者批量 sed 更新 docs/active。 |
| 测试文件 41 份带 `from benchmark.layer3.*` import | 一次性大改易冲突 | Phase 2 用 `lsp rename_file` + 自动化脚本,单次原子提交;每搬一组源代码立刻搬对应测试,不留半迁移状态。 |
| `benchmark/annotation/` 自带 `.venv` 与独立依赖 | 改路径后用户需要 `uv sync` 重建 | `datasets/rett_annotation/README.md` 顶部标注重建步骤;CI 不依赖该 venv,所以无 CI 影响。 |
| `reports/main_paper_tables_*.csv/.md` 14 重复版本 | 二级分桶后历史可读性下降 | 全量保留(都进入 `paper/`),仅按时间戳排序,允许后续手工删除中间版本。 |
| reports 目录庞大,`git mv` 耗时 + 单 PR diff 巨大 | code review 难度高 | Phase 4 单独成 PR;PR 描述里贴脚本输出+前后体量对比;不混 code 改动。 |
| 跨 worktree 同时改 evaluate 的同事 | 冲突 | Phase 1 落地前在 `irc` 通知,在 `progress.txt` 标注 freeze 期。 |

### 10.1 论文路径兼容映射

在 `benchmark/data/reports/__init__.py` 之外,**额外**在 `benchmark/layer3/reports/` 留 symlink 列表(由 Phase 4 末尾自动生成),指向 `benchmark/data/reports/<bucket>/<file>`,确保论文 `jq` 命令仍能命中。Phase 6 删除时同步移除 symlink。

## 11. 时间预算

| Phase | 工作量 | Gate |
|----|----|----|
| 0 — Freeze & Branch | 0.5d | baseline 抓取 |
| 1 — `core/` 抽出 | 1d | `pytest backend/tests/benchmark` 等价 |
| 2 — `analysis/` 主题分组 | 1.5d | analysis 全测试 + ruff |
| 3 — `runners/` 提取 | 0.5d | runner CLI smoke |
| 4 — 资产搬迁 | 1d | reports 二级分桶完成 + 路径常量切换 |
| 5 — `datasets/` 收敛 | 0.5d | end-to-end CLI smoke |
| 6 — Shim 删除 | 0.5d (≥1 周后) | 0 deprecation + docs 更新 |
| **合计** | **5.5d 工程** + 1 周观察期 | |

## 12. 验收标准

- `tree benchmark/ -L 2` 输出与 §3 一致(允许 `__init__.py` 与 README.md)。
- `find benchmark -name "__pycache__" -type d` 无残留(.gitignore 已覆盖)。
- `wc -l benchmark/core/*.py` 单文件 ≤ 400 行,`evaluate.py` 不再存在为非 shim。
- `python -c "from benchmark.core import FieldMatch, EntryMetrics, compare_evidence, compute_aggregate_metrics, GROUND_TRUTH_ROOT, REPORTS_ROOT; print('ok')"` 输出 ok。
- `pytest backend/tests/benchmark -q` 全绿,且 deprecation warning 在 Phase 6 后为 0。
- `ruff check benchmark backend/tests/benchmark` 通过。
- `docs/README.md` 索引指向新 `benchmark/README.md`,后者反映目标布局。
- `progress.txt` 顶部追加 `[2026-06-XX] benchmark refactor merged to dev`。
- `lesson.md` 追加迁移期遇到的至少 3 条 lesson(如 reports 二级分桶失败项处理、shim 顺序调整、`uv sync` 在新 rett_annotation 路径下的注意事项)。

## 13. 不做的事 (Out of Scope)

- 不重写任何 ground truth/expected 内容。
- 不修改 `compare_evidence`、`fuzzy_match_value` 算法行为(只换文件位置)。
- 不引入新的依赖。
- 不重构 `benchmark/datasets/rett_annotation/` 内部结构(它已自洽)。
- 不改 backend 业务代码 import (`backend/src/`),仅 `backend/tests/benchmark/` 跟随源码迁移。
- 不重命名 `benchmark/data/ground_truth/clingen/clingen_NNN/` 内文件结构(只换上一级目录前缀)。

---

## 14. Acceptance Checklist (PR 描述模板)

```
- [ ] benchmark/core/* 创建,evaluate.py 拆解完成
- [ ] benchmark/analysis/<group>/ 35 个模块全部归位,测试同步迁移
- [ ] benchmark/runners/* 6 个 runner 就位,旧 CLI shim 工作
- [ ] benchmark/datasets/* 三个数据集子目录(clingen / clinvar_fused / rett_annotation)就位
- [ ] benchmark/data/{ground_truth,inputs,reports} 资产搬迁,reports 二级分桶
- [ ] backend/tests/benchmark 全绿,deprecation warning 仅在 layer3 shim 出现
- [ ] benchmark/README.md 重写,docs/README.md 索引同步
- [ ] progress.txt + lesson.md 更新
- [ ] (Phase 6) 所有 layer3/pipeline/literature_acquisition shim 删除
```
