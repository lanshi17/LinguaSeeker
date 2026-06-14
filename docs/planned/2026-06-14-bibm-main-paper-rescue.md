# BIBM Main Paper Rescue Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 CrossEvidence 从“有工程系统、但论文信号不稳定”拉回到“能用严谨实验支撑的 BIBM Main Paper 候选”，优先证明跨语言证据抽取的 recall、traceability 和 citation validity 真的有增益。

**Architecture:** 采用诊断优先的研究路径。先修复当前最明确的 recall 瓶颈，再重新跑 worst-case ablation 和统计检验；只有当 signal 被重新拉起来后，才继续强化双轨调和、置信度评分、traceability 指标和论文材料。Phase 4 UI 只作为审查与标注基础设施，不作为 main paper novelty。

**Tech Stack:** Python 3.12 + `uv`、backend FastAPI/LangGraph、`pytest`、Ruff、`benchmark/layer3`、`benchmark/pipeline`、现有 Phase 2/3 backend slices、docs/progress 记录。

---

## 0. Current Diagnosis

最近一轮诊断的结论很明确：

- `benchmark/layer3/reports/reconcile_ablation_20260614_140733.json` 中，worst-5 ablation 对不同策略都卡在 `F1=0.75`，没有拉开差距。
- `benchmark/layer3/reports/g2_statistics_20260614_140800.json` 中，`delta_f1=0.0`，`sign_test_p=1.0`，`main_paper_ready=false`。
- `benchmark/layer3/reports/contextual_reconcile_diagnosis_20260614_140800.json` 显示主要错误来源是 `candidate_absent=2`、`wrong_relationship_semantics=3`、`disease_boundary_error=2`。
- 当前 benchmark context pack 只加载 `expected.json`，疾病别名也主要停留在 exact / casefold / 括号裁剪层面。
- 真实 source 文本里能看到更强的安全别名信号，例如 `clingen_020` 里的 `TOF`、`clingen_024` 里的 `SLE`，但 benchmark 没有把这些信号吃进去。
- 结论：**source-aware alias expansion** 是当前最值得先做的 rescue 点；如果它不能把 recall 和边界错误拉起来，Main Paper 就不该继续硬推。

## 1. Scope

### In scope

- 让 benchmark context pack 能从 `source.md` 安全提取 source-aware aliases。
- 重新跑 contextual diagnosis、worst-5 ablation 和 G2 statistics。
- 在 signal 回来后，强化 reconciliation、confidence、traceability metrics 和 evaluation package。
- 准备 Main Paper 级别的 baseline、ablation、统计检验和图表。

### Out of scope

- Phase 4 的 UI 美化、批量操作、NL-to-SQL、导出模板。
- 纯 Demo 包装，没有算法/实验支撑的功能扩展。
- 未经冻结的“边写边调”主实验数字。

## 2. Milestone 1: Patch the benchmark context pack first

目标：先把最明显的 recall bottleneck 修掉，避免后面的调和算法面对空候选集。

### Task 1.1: Write failing tests for source-aware alias expansion

**Files:**
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`

**Step 1: 写测试**

补两个最小测试：

- `source.md` 存在时，`TOF` / `SLE` 这类源文别名会进入 context pack 的 alias 集。
- `source.md` 不存在时，当前行为不变。
- 任何 source-derived alias 都不能泄漏 `expected.json` 里的分类/关系标签。

**Step 2: 先跑一次，确认失败**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py -q
```

Expected: fail，因为当前代码还不会从 `source.md` harvest aliases。

### Task 1.2: Implement safe source-aware alias harvesting

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`

**Step 1: 最小实现**

实现一个保守的 alias 扩展器：

- 读取同目录或固定 sibling 的 `source.md`
- 先保留现有 exact / casefold / parenthetical-strip aliases
- 再从 source 文本里 harvest 安全别名
- 只接受低风险模式，例如：
  - repeated uppercase disease abbreviations
  - 明确的括号缩写
  - 与 target gene/disease 直接共现的短别名
- 给 source-derived alias 打 provenance 标记，避免它们冒充 ground truth

**Step 2: 跑测试**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py \
  backend/tests/core/standardize_entities_and_align_knowledge/context_pack/test_core.py
```

Expected: tests pass, Ruff clean.

### Task 1.3: Rerun diagnosis and worst-5 ablation

**Files:**
- Read: `benchmark/layer3/reports/contextual_reconcile_diagnosis_20260614_140800.json`
- Read: `benchmark/layer3/reports/reconcile_ablation_20260614_140733.json`

**Step 1: 重新跑诊断**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync \
  python -m benchmark.layer3.analysis.contextual_reconcile_diagnosis
```

**Step 2: 重新跑 worst-5 ablation**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync \
  python -m benchmark.layer3.analysis.reconcile_ablation --write
```

**Step 3: 重新跑 G2**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync \
  python -m benchmark.layer3.analysis.g2_statistics --write
```

**Gate G1**

继续往下的条件只有两个：

- `candidate_absent` / `disease_boundary_error` 明显下降；
- worst-5 ablation 至少有一个策略相对当前 `F1=0.75` 出现可辩护的提升。

如果这一步仍然打平，就不要先写 paper claim，先扩大 alias strategy 或补更强的标注/上下文。

## 3. Milestone 2: Turn the signal into an algorithmic contribution

目标：把“双轨抽取 + 调和”从工程描述，变成可以写进 Main Paper 的算法对象。

### Task 2.1: Harden reconciliation logic around the new aliases

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contextual.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contextual.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/verify/test_core.py`

**Step 1: 补冲突场景测试**

覆盖这些情况：

- 原文/译文都 grounded，但 value 冲突
- 一条证据 traceability 很强，另一条 traceability 很弱
- 语义是 disease alias，但字符串不同
- 证据是 hedged / uncertain，而不是硬性肯定

**Step 2: 让决策规则保持可解释**

维持清晰的状态输出：

- `accept`
- `review`
- `abstain`
- `reject`

并确保决策依据来自 support / margin / traceability，而不是固定偏向某一轨。

### Task 2.2: Expose reconciliation evidence for the paper

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`

**Step 1: 记录论文需要的中间量**

确保调和结果能直接导出：

- track agreement
- conflict type
- traceability score
- support score
- review reason

**Step 2: 保持向后兼容**

旧 JSON 仍然能被 `model_validate`，不要因为加字段破坏已有报告。

**Gate G2**

如果 `graph_reconcile` 还不能超过 `grounded_hard_rule`，就把它降级为系统实现细节，不把它写成 main paper 核心贡献。

## 4. Milestone 3: Freeze evaluation and baselines

目标：补齐 reviewer 最在意的实验包，避免“只讲系统，不讲对比”的拒稿点。

### Task 3.1: Freeze a manifest for the paper numbers

**Files:**
- Create: `benchmark/layer3/analysis/main_paper_manifest.py`
- Create: `backend/tests/benchmark/layer3/test_main_paper_manifest.py`

**Step 1: 记录冻结信息**

至少保存：

- git commit hash
- report path
- N
- per-field metrics
- traceability metrics
- run command

**Step 2: 跑测试**

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/benchmark/layer3/test_main_paper_manifest.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check \
  benchmark/layer3/analysis/main_paper_manifest.py \
  backend/tests/benchmark/layer3/test_main_paper_manifest.py
```

### Task 3.2: Build the baseline ladder

**Files:**
- Create: `benchmark/layer3/baselines/naive_llm.py`
- Create: `benchmark/layer3/baselines/translate_then_extract.py`
- Create: `benchmark/layer3/baselines/original_only.py`
- Create: `benchmark/layer3/baselines/rag_llm.py`
- Create: `benchmark/layer3/baselines/single_agent_cot.py`

**Step 1: 统一比较器**

所有 baseline 复用同一个 ground-truth compare helper，不要复制评测逻辑。

**Step 2: 生成 baseline 报告**

至少保留这几条梯度：

- naive LLM
- translate-then-extract
- original-only
- RAG + LLM
- single-agent CoT

### Task 3.3: Define traceability metrics

**Files:**
- Create: `benchmark/layer3/analysis/traceability_metrics.py`
- Create: `backend/tests/benchmark/layer3/test_traceability_metrics.py`
- Modify: `benchmark/layer3/analysis/g2_statistics.py`

**Step 1: 固定指标定义**

输出这些量：

- `CVR` (Citation Validity Rate)
- `HCR` (Hallucinated Citation Rate)
- `ESR` (Evidence Support Rate)
- `Span Boundary F1`

**Step 2: 加统计检验**

至少包括：

- paired bootstrap
- sign test
- per-entry deltas

**Gate G3**

只有当 baseline、manifest、traceability metrics 都能复现时，才算进入论文写作阶段。

## 5. Milestone 4: Package the paper

目标：把实验信号转成 BIBM 能读懂的 story。

### Task 4.1: Produce the claim matrix

**Files:**
- Create: `docs/active/bibm-main-paper-claim-matrix.md`

**Step 1: 明确主张**

每条 claim 都要对应：

- 支持它的实验表
- 支持它的统计检验
- 支持它的失败案例

**Step 2: 明确不能说的话**

禁止写成：

- “100% semantic correctness”
- “all citations are always right”
- “UI 证明了方法有效”

### Task 4.2: Draft the paper outline

**Files:**
- Create: `docs/active/bibm-main-paper-outline.md`

**Step 1: 写出论文骨架**

至少包含：

- Problem
- Method
- Evaluation
- Ablation
- Traceability
- Limitations

**Step 2: 对齐图表**

每个 section 都要能挂上现有的实验结果，不允许空洞叙述。

## 6. Risks

- 如果 source-aware alias expansion 没有拉起 recall，Main Paper 的主线就应当收缩，不要硬写成算法突破。
- 如果调和算法和 grounded_hard_rule 打平，就不要把 reconcile 包装成主要创新。
- 如果 traceability 指标只能证明“引用存在”，不能证明“字段值被支撑”，论文必须把这层边界写清楚。
- 如果 main paper gate 失败，下一步应切到 Demo/Resource track，而不是继续堆功能。
