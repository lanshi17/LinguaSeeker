# BIBM Novelty 攻关 — 研究执行计划（诊断优先）

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> 本计划不是"写代码实现某功能"，而是"先用实验诊断突破点在哪，再决定投哪个 track"。每个 milestone 末尾有 **go/no-go 决策门**，必须由人（论文一作）拍板后才进入下一阶段。

**Goal:** 在 2-3 周内，用现有的 `benchmark/layer3` 与 `benchmark/pipeline` 评测设施，定量诊断出本系统**唯一一个能站得住学术 novelty 的点**，并产出支撑该点的核心实验数据，最终决定投 BIBM Main Full Paper 还是 Demo/Resource Track。

**Architecture（研究方法论，非软件架构）:** 三阶段——(1) 诊断：挖现有报告 + 跑最小 ablation，确定哪个方向有信号；(2) 加固：围绕有信号的方向补关键实验（ablation/baseline/增益量化）；(3) 定稿：根据数据强度选 track 并组织论文。每阶段之间有 go/no-go 门。

**Tech Stack:** Python 3 + `uv`、现有 `benchmark/layer3/evaluate.py`（P/R/F1、cross-lingual consistency、entity standardization）、`benchmark/pipeline/benchmark.py`（10 语种全流程）、matplotlib 可视化、pytest。

---

## 立论前提：代码逼出来的五条硬事实（不可绕过）

> 这些是我读代码与数据后**已验证**的事实，不是假设。论文的每一句 claim 都必须与它们一致，否则 BIBM 审稿人会当场拆穿。

| # | 事实 | 来源（已核） | 对 novelty 的后果 |
|---|------|------------|------------------|
| F1 | **不存在"交叉验证融合/仲裁"算法。** 两轨（`original_result` / `translated_result`）各自独立跑同一个 `EvidenceExtractionWorkflow`，结果并排存进 `DualEvidenceExtractionResult`。`track_consistency` 只**度量**一致性，没有任何代码用一轨去**纠正**另一轨。 | `extract_evidence/contracts.py:297` `DualEvidenceExtractionResult`；`extract_evidence/workflow.py` 单轨 graph；grep 无 fuse/arbitrate/reconcile 业务逻辑 | 助手原稿里"extract-twice-then-fuse"的 fuse 这一步**目前是空的**。要么先把它实现成真算法，要么不能拿它当 contribution。 |
| F2 | **ClinGen 30 例的非英文是"英文→X 机器翻译"。** | 用户确认 "clingen 是翻译,其余是原生" | "原语言保留母语语境"这一理论卖点**在 ClinGen 集上不成立**——那只是"机翻 vs 机翻回读"。ClinGen 集**只能**用于"结构化抽取 P/R/F1 vs ground truth"，不能用于"母语增益"。 |
| F3 | **rett 是真实母语原生多语种（zh/ja/ru/de/fr/it/ko/es/pt/tr）。** | `benchmark/literature_acquisition/downloads/rett/<lang>/` 实际文件名为母语标题 | rett 是"跨语言母语增益"唯一合法语料。 |
| F4 | **rett 没有 ground truth。** 该目录只有 download/cleanup/rename report JSON，无 `expected.json`。 | `find ... rett -name expected.json` 为空 | rett 上**无法算 precision**。只能算召回代理（evidence count）、track 一致性、或人工小样本标注。 |
| F5 | **`source_grounding` 是真实 pipeline stage，有 `SourceLinker` 做双语 span 绑定 + `grounding_rate` 指标。** | `extract_evidence/workflow.py:118` `_node_source_grounding`；`extract_evidence/stages/source_grounding.py`；layer3 `EntryMetrics.grounding_rate` | 可追溯性/grounding 是**已实现且已被度量**的真东西，是除"结构化抽取"外最实在的可写点。 |

**由 F1–F5 直接推出的三个候选 novelty 方向**（你选了"多语种翻译+结构化提取+可追溯"，下面把它拆成可证伪的三条）：

- **方向 A（结构化抽取，领域贡献）**：面向 ACMG/ClinGen 证据分类体系的细粒度结构化抽取 + 实体标准化（gene→HGNC、disease→MONDO、classification、MOI），用 ClinGen 30 例 ground truth 做 P/R/F1。✅ 数据合法（F2 允许）、设施已有。⚠️ 单独看 novelty 偏弱（助手原稿已指出 LLM-IE 不新）。
- **方向 B（跨语言母语增益）**：用 rett 原生多语种证明"母语轨比机翻轨多召回证据"。✅ 语料合法（F3）。❌ 无 ground truth（F4）——必须先解决标注，否则只能做弱实验。
- **方向 C（可追溯性 / 双语 grounding 形式化）**：把 evidence↔source span 双向绑定形式化为 **citation validity by construction**（每条采纳证据附带可程序验证的源文 span 引用），用 CVR/ESR/Span-Boundary-F1/HCR 四指标量化"可验证、抗幻觉"。✅ 已实现（F5）。⚠️ 需论证它比"让 LLM 自己引用"更强（要有反例/消融），且 claim 限定在"引用有效性"而非"语义 100% 正确"。

> **本计划不预设哪个方向赢。** Milestone 1 的诊断实验决定 A/B/C 哪个有信号，再投入 Milestone 2 加固。

---

## Milestone 0：环境就绪 + 诚实基线复算（0.5 天）

**目标：** 确认评测设施能跑通，并拿到**当前全 30 例**的真实 P/R/F1。注意：最新报告 `eval_20260611_221547.json` 的 `total_entries=3`（`config.limit=None`、concurrency=1，只实际跑了 3 例），其 overall F1=0.8（TP=4/FP=1/FN=1）、entity_std=0.25 **只是 3 例的数字，绝不能写进论文**。

**验证标准：** 拿到一份 `total_entries=30` 的 layer3 报告 JSON，overall 块字段齐全。

### Task 0.1：确认服务依赖可用

**Files:** 无（只读检查）

**Step 1:** 确认后端与依赖服务状态。

Run:
```bash
cd backend
uv run python -m benchmark.layer3.evaluate --help
```
Expected: 打印 CLI 帮助，含 `--base-url --concurrency --entries --limit`。若 import 失败，先 `uv pip install -e ".[dev]"`。

**Step 2:** 确认后端在线（layer3 需要 `http://localhost:8000` + PostgreSQL + 模型服务）。
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health || echo "BACKEND DOWN"
```
Expected: `200`。若 DOWN，按 `CLAUDE.md` 启动后端 + model-server + PostgreSQL，再继续。这是**外部环境依赖**，若起不来，停下来告诉一作，不要伪造数据。

### Task 0.2：全 30 例基线复算（这是论文的真基线）

**Files:**
- Read: `benchmark/layer3/evaluate.py`
- Create: 新报告写入 `benchmark/layer3/reports/eval_<timestamp>.json`（脚本自动命名）

**Step 1:** 先用 preprocessed 快路径试 3 例，确认链路通。
```bash
cd backend
uv run python -m benchmark.layer3.evaluate --entries clingen_000 clingen_001 clingen_002
```
Expected: 退出码 0，报告含这 3 例的 `per_entry`。

**Step 2:** 跑全 30 例。
```bash
cd backend
uv run python -m benchmark.layer3.evaluate --base-url http://localhost:8000 --concurrency 2
```
Expected: 生成 `total_entries=30` 的报告，耗时取决于是否有 preprocessed 缓存。

**Step 3:** 提取真基线数字（用于后续所有对比的锚点）。
```bash
cd backend
uv run python -c "
import json, glob, os
f=max(glob.glob('benchmark/layer3/reports/eval_*.json'), key=os.path.getmtime)
d=json.load(open(f)); o=d['aggregates']['overall']
print('REPORT:', f, 'N=', d['total_entries'])
print('overall:', {k:o.get(k) for k in ('precision','recall','f1','entity_standardization_accuracy','cross_lingual_consistency','over_extractions')})
print('by_field:', json.dumps(d['aggregates']['by_field'], indent=2))
"
```
Expected: 打印 N=30 的 overall 与 by_field。**记下这组数字**——它是真基线。

**Step 4（决策门 G0）：** 把 N=30 真基线贴给一作。
- 若 overall F1 ≥ ~0.85 且 entity_std 合理 → 方向 A 有 ground、可作为论文的"系统能力"底座。
- 若 entity_std 仍很低（如 <0.5）→ 这本身是个待修问题，记入 lesson，但不阻塞诊断。
- **不写代码改进，先看清现状。**

**Step 5:** Commit（只提交新报告，不改源码）。
```bash
git add benchmark/layer3/reports/eval_*.json
git commit -m "test: full 30-entry layer3 baseline for BIBM novelty diagnosis"
```

---

## Milestone 1：诊断三方向的信号强度（3-5 天）

**目标：** 用最小实验分别给 A/B/C 一个"有没有信号"的判据，**避免在没信号的方向上投实验工作量**。三个诊断可并行交给子代理。

### Task 1.A：方向 A 诊断 —— 结构化抽取是否已达可发表水平

**Files:**
- Read: `benchmark/layer3/reports/eval_<latest>.json`、`benchmark/layer3/evaluate.py`（看 `compute_aggregate_metrics`）
- Create: `benchmark/layer3/analysis/diagnose_extraction.py`

**Step 1:** 写诊断脚本（纯读现有报告，不跑模型），输出按 classification / MOI / field 的短板表 + 错误类型分布（missing vs wrong_value vs over_extraction）。

> 注意（项目规则 22 — 禁止裸 dict 返回值）：诊断脚本读取的是**外部第三方报告 JSON**（无固定结构），按例外条款可用 `dict`，但**必须**加 `# noqa: dict-return` 注释说明理由；或更优——为报告定义 `@dataclass EvalReport`。下例用例外写法。

```python
"""诊断方向 A：从最新 layer3 报告中提取结构化抽取的强弱项。"""
from __future__ import annotations
import glob
import json
import os
from typing import Any


def load_latest() -> dict[str, Any]:  # noqa: dict-return — 解析外部 layer3 报告 JSON，无固定结构
    f = max(glob.glob("benchmark/layer3/reports/eval_*.json"), key=os.path.getmtime)
    return json.load(open(f))


def main() -> None:
    d = load_latest()
    agg = d["aggregates"]
    print(f"N={d['total_entries']}  overall={agg['overall']}")
    for axis in ("by_field", "by_classification", "by_moi"):
        print(f"\n== {axis} ==")
        for k, v in agg[axis].items():
            print(f"  {k:30s} P={v.get('precision')} R={v.get('recall')} F1={v.get('f1')} over={v.get('over_extractions')}")
    # 错误类型分布
    from collections import Counter
    mt = Counter()
    for e in d["per_entry"]:
        for fm in e.get("field_matches", []):
            mt[fm.get("match_type", "?")] += 1
    print("\n== match_type distribution ==", dict(mt))


if __name__ == "__main__":
    main()
```

**Step 2:** 运行。
```bash
cd backend && uv run python -m benchmark.layer3.analysis.diagnose_extraction
```
Expected: 打印各维度 P/R/F1 + match_type 分布。

**Step 3（判据）：** 方向 A "有信号"的条件 = 在某个**有医学意义的细分维度**上系统显著优于"朴素 LLM 直抽"（这需要 Task 1.D 的 baseline 才能确认增益；本步先标记 A 的绝对水平与短板）。

### Task 1.B：方向 B 诊断 —— rett 母语增益是否存在（无 GT 的弱实验）

**Files:**
- Read: `benchmark/pipeline/benchmark.py`、`benchmark/pipeline/evidence_metrics.py`
- Create: `benchmark/analysis/diagnose_native_gain.py`

**Step 1:** 选 rett 中**同一篇文献存在多个母语版本**或**同一疾病多语种**的子集，分别只跑"原语言轨"与"译文轨"，统计两轨各自的 evidence count、unique evidence、以及一轨独有/两轨共有的证据数。**这是召回代理，不是 precision**（F4 限制，必须在论文里诚实标注）。

**Step 2:** 运行小样本（先 2-3 篇 zh + 2-3 篇 ja）。
```bash
cd backend && uv run python -m benchmark.analysis.diagnose_native_gain --langs zh ja --limit 3
```
Expected: 输出每篇 `original_only / translated_only / shared` 证据计数。

**Step 3（判据 + go/no-go）：** 若"原语言轨独有证据"在母语文献上系统性 > 0（且抽样人工 spot-check 确认这些证据是真的、不是幻觉）→ 方向 B 有信号，**值得投入 Task 2.B 做人工小样本标注**。若两轨证据几乎完全重合 → 方向 B 信号弱，**放弃 B**，不浪费标注成本。

### Task 1.C：方向 C 诊断 —— grounding 是否抗幻觉（可证伪）

**Files:**
- Read: `extract_evidence/stages/source_grounding.py`、`SourceLinker`
- Create: `benchmark/analysis/diagnose_grounding.py`

> **Claim 精确化（必须遵守）：** 不要写"100% 可追溯"或"100% 准确"。本系统能保证的是 **citation validity by construction**——即每条被采纳的 evidence 都**附带一个指向源文 span 的引用，且该 span 可被程序验证存在于原文**；这与"该证据语义正确"是两回事。语义正确性仍由 P/R/F1 衡量，可能 < 100%。论文必须把这两层分开陈述。

**四个可追溯性指标（在 diagnose_grounding.py 中实现，复用 layer3 `per_entry` 字段）：**

| 指标 | 定义 | 衡量什么 |
|------|------|---------|
| **Citation Validity Rate (CVR)** | 被采纳 evidence 中，其 source span **确实存在于原文**（程序可校验，offset/文本对得上）的比例 | "引用不是编的" — by construction 的核心 |
| **Evidence Support Rate (ESR)** | 被采纳 evidence 中，其 span 文本**确实支持该字段值**（人工/LLM 判定语义支持）的比例 | 引用存在 ≠ 引用支持，捕捉"引对地方但解读错" |
| **Span Boundary F1** | 抽取 span 与（人工标注）正确证据 span 的 token 级边界重叠 F1 | 引用精度，过宽/过窄都扣分 |
| **Hallucinated Citation Rate (HCR)** | 被采纳 evidence 中，source span **在原文找不到**（凭空捏造引用）的比例 = 1 − CVR 的子集（仅计有 citation 却无效者） | 幻觉引用率，越低越好，是抗幻觉的直接证据 |

**Step 1:** 从已有 layer3 `per_entry` 取每条 evidence 的 `grounding_rate`、`source`/`raw_source` span 与 `match_type`，计算 CVR / HCR（程序可算），并检验假设：**未 grounded（HCR 命中）的 evidence 是否更可能是 wrong_value/over-extraction**。ESR 与 Span Boundary F1 需少量人工/LLM 判定（先在诊断阶段做小样本）。

**Step 2:** 运行，输出 grounded vs ungrounded 两组 precision 对比 + CVR/HCR + 相关性。
```bash
cd backend && uv run python -m benchmark.analysis.diagnose_grounding
```
Expected: 两组 precision 差值 + CVR/HCR 数字 + 一个简单 χ²/相关数。

**Step 3（判据）：** 若 grounded 组 precision 显著高于 ungrounded **且 HCR 低**（接近 0，by construction）→ 方向 C 有"可验证抗幻觉"信号。否则 grounding 只是工程特性、非学术贡献。

### Task 1.D：共用 baseline 套件 —— A/C 都需要，BIBM Main 的必备对照

> 单一 naive baseline 会被 reviewer 直接质疑。Main Paper 至少需要下面这组**梯度 baseline**，以隔离"是 pipeline 结构带来的增益、还是单纯多调了几次 LLM"。

**Files:**
- Create: `benchmark/layer3/baselines/naive_llm.py`（B0）、`benchmark/layer3/baselines/translate_then_extract.py`（B1）、`benchmark/layer3/baselines/original_only.py`（B2）、`benchmark/layer3/baselines/rag_llm.py`（B3）、`benchmark/layer3/baselines/single_agent_cot.py`（B4）
- Reuse: `benchmark/layer3/evaluate.py` 的 `compare_evidence` / `compute_aggregate_metrics`（**不重写比较器**，DRY）

**Baseline 梯度与目的：**

| ID | Baseline | 隔离的变量 | 数据 |
|----|----------|-----------|------|
| B0 | Naive single-prompt LLM 直抽三字段 | 完全无 pipeline 的下界 | ClinGen 30 |
| B1 | **Translate-then-extract**（先翻英、再单次抽） | 经典跨语言范式，证明本系统 ≠ 它 | ClinGen 30 |
| B2 | **Original-only**（仅原语言单次抽，不翻译） | 翻译这一步本身的贡献 | ClinGen 30 |
| B3 | **RAG + LLM**（检索相关段落再抽） | 检索增强 vs 全文结构化 | ClinGen 30 |
| B4 | **Single-agent CoT**（一个 agent 链式思考抽全部字段） | 多 stage pipeline vs 单 agent | ClinGen 30 |

**外部工具参考基线（写进 Related Work / 讨论，非直接同任务对比）：**
- **PubTator 3.0 / BERN2** — 生物医学实体识别+标准化（gene/disease/variant）。可作为 entity standardization 的参考，但它们**不做 ACMG/ClinGen 证据字段级抽取**，需在论文明确划清任务边界。
- **SemRep** — 语义关系抽取（subject-predicate-object）。可参考 gene-disease relationship 抽取，但其谓词体系与 ClinGen relationship（causative/uncertain/disputed/refuted）不同，属于**任务不完全重叠**，须解释。
- 论文表述：用这三者**对照实体/关系抽取的成熟度**，而非声称在同一任务上击败它们——否则会被指为不公平比较。

**Step 1:** 实现 B0–B4，全部复用 `compare_evidence` 算 P/R/F1。每个 baseline 一个文件，共享一个 `_run_against_ground_truth(extract_fn)` 辅助（DRY，避免 5 份重复的评测循环）。

**Step 2:** 跑全套。
```bash
cd backend
for b in naive_llm translate_then_extract original_only rag_llm single_agent_cot; do
  uv run python -m benchmark.layer3.baselines.$b
done
```
Expected: 5 份 baseline 报告，各含 overall P/R/F1。

**Step 3（决策门 G1 —— 关键）：** 三方向诊断 + 5 梯度 baseline 全部就绪后，把下表填满给一作：

| 方向 | 有无信号 | 关键数字 | 数据是否合法 | 还缺什么 |
|------|---------|---------|------------|---------|
| A 结构化抽取 | ? | 系统 F1 vs B0/B1/B4 最强 baseline = ?/? | ✅ ClinGen GT | 看 Δ 是否显著 |
| B 母语增益 | ? | original_only 证据数（rett） | ⚠️ 无 GT | 双人标注 |
| C grounding 抗幻觉 | ? | grounded/ungrounded precision Δ + Hallucinated Citation Rate | ✅ | 形式化 + 反例 |

**关键判据：系统必须显著优于 B1（translate-then-extract）和 B4（single-agent CoT）**，否则"多 stage 跨语言"相对经典范式没有可辩护的增量。一作据此拍板主攻 1 个方向（至多 2 个组合）。

**Step 4:** Commit 诊断脚本与结果。
```bash
git add benchmark/layer3/analysis benchmark/analysis benchmark/layer3/baselines
git commit -m "test: diagnostics (A/B/C) + 5-tier baseline suite for BIBM novelty"
```

---

## Milestone 2：加固选中方向（5-8 天，分支按 G1 结果二选一）

> 只执行 G1 选中的分支。下面给出三套，**不要全做**。

### 分支 2.A（若选结构化抽取）：完整 ablation + baseline 对比

1. **消融**：逐个关闭 pipeline stage（relevance_scan / special_evidence / grounding / chain_assembly / value_normalization），各跑 30 例，量化每个 stage 对 F1 的贡献 → 验证: 每关一个 stage 出一行 ΔF1。
2. **强 baseline**：除 naive LLM 外，加一个"PubMed + 单次强模型直抽"对照 → 验证: 三方 P/R/F1 表。
3. **细分增益**：证明系统在 Limited/Refuted/Disputed 这类**难分类**上比 baseline 强（这才是领域价值）→ 验证: by_classification 上的 Δ。

### 分支 2.B（若选母语增益）：双人标注 + 双轨 ablation

1. **标注（含信度保证）**：在 rett 上选 ~15-20 篇母语文献（覆盖 zh/ja/ru 等），按 ClinGen 三字段 schema 标 ground truth，存为 `benchmark/rett/ground_truth/<id>/expected.json`（复用 layer3 的 `expected.json` schema，DRY）。
   - **不可单人标注**（reviewer 必拒）。流程：(a) 一作 + 第二位领域标注者**独立**标注同一批；(b) 计算 **Cohen's κ**（字段值匹配用 `fuzzy_match_value` 判等，逐字段算 κ）；(c) 报告 κ 值，目标 κ ≥ 0.6（substantial）；(d) **冲突仲裁规则**：分歧条目由第三方裁定或两人协商，记录裁定依据到 `selection.json`。
   - 新建 `benchmark/rett/annotation/agreement.py` 计算 κ。→ 验证: ≥15 个 expected.json 通过 schema 校验 + 一份 κ 报告（按字段）。
2. **双轨 ablation**：在这批 GT 上跑"仅原语言轨 / 仅译文轨 / 两轨并集"三配置，算 P/R/F1 → 验证: 三配置对比表，重点看母语轨是否在召回上赢；做配对显著性检验（见 G2 统计要求）。
3. **诚实边界**：明确写出"机翻 ClinGen 集不参与此实验"（F2），只用 rett 原生集。

### 分支 2.C（若选 grounding 抗幻觉）：实现可学习的跨轨仲裁 + grounding 消融

> 注意：这条**需要写新代码**（实现 F1 缺失的融合/仲裁），工作量最大。仅在 G1 强烈指向 C 时选。
1. **实现跨轨仲裁（scoring/ranking，非硬规则）**：在 `DualEvidenceExtractionResult` 上加一个 `reconcile` 步骤。
   - **不要用"被 grounded 的一方胜出"这种硬规则**——作为 Main Paper novelty 太单薄，且无法处理"两轨都 grounded 但冲突"或"都未 grounded"。
   - 改为对每个候选 evidence 计算一个**支持度分数** `s = f(grounding_span_overlap, track_agreement, source_confidence, span_boundary_tightness)`，对同一 `field_id` 的多轨候选**排序**取 top，冲突时按分数差与阈值决定"采纳/标记需复核"。形式化为一个 ranking 函数 + 可调阈值，权重可在 dev 集上拟合（即使是简单 logistic / 线性加权也比硬规则可辩护）。
   - 新建 `extract_evidence/stages/cross_track_reconcile.py`：纯业务逻辑入 `core.py`，类型化契约入 `contracts.py`（`ReconcileResult` 用 dataclass、`ReconcileParams` 用 TypedDict，遵循规则 22），LLM/DB 调用入 `providers.py`，遵循垂直切片架构。
   - → 验证: 单元测试覆盖 (两轨一致 / 两轨冲突且一方 grounded / 两轨冲突且都 grounded / 单轨缺失 / 都未 grounded) 五种 case；ranking 函数有确定性输出。
2. **消融**：reconcile off（并集）/ 硬规则 / 打分排序 三档的 precision、over-extraction、Hallucinated Citation Rate 对比 → 验证: 30 例上三档 Δ，证明"打分排序 > 硬规则 > 并集"。
3. **反例库**：收集 reconcile 拦截掉的幻觉证据样例（论文 case study）。

> **若打分排序相对硬规则没有显著增量** → 仲裁不构成 Main novelty，方向 C 退回 Demo/Resource（强调 grounding 作为系统特性），不硬撑算法贡献。

**每个分支结束 = 决策门 G2：** 数据增益是否**统计显著**（经得起 reviewer 质疑）？
- **统计要求（必做）**：N=30 偏小，所有"系统 vs baseline"或"配置 A vs B"的对比必须配 **配对显著性检验**（配对 bootstrap 或 McNemar/Wilcoxon，视指标而定）+ **95% 置信区间**，而非只报点估计。差异不显著就不能写"显著优于"。
- 显著 → Milestone 3 投 Main；不显著但系统完整 → 投 Demo/Resource。

---

## Milestone 3：定 track + 组织论文（3-4 天）

**Files:**
- Create: `docs/paper/bibm_outline.md`（论文大纲，非代码）
- Create: `benchmark/.../visualize.py` 复用，产出论文图（已有 `visualize.py`，扩展即可，DRY）

### Task 3.1：根据 G2 数据强度选 track

**判据：**
- 选中方向有**显著且可复现**的 ablation/baseline 增益（Δ 经得起追问）→ **Main Full Paper**。论文结构：Intro → Related Work（点名 LLM-IE/translate-then-extract 已有，划清差异）→ Method（选中方向的形式化）→ Experiments（ablation + baseline + 选中方向的核心增益 + 30 例 ClinGen GT）→ Discussion（含 F2/F4 的诚实 limitation）。
- 增益不够但系统端到端完整、可演示 → **Demo/Resource Track**。强调"首个面向医学遗传学的端到端跨语言证据抽取与 **citation-valid-by-construction** 双语可追溯工作台 + 30 例 ClinGen 多语种 benchmark（含 10 语种 pipeline 设施）"，附至少 1 个核心 ablation。

### Task 3.2：产出论文图与表

**Step 1:** 复用并扩展 `benchmark/layer3/visualize.py` 生成最终图（overall、by_classification heatmap、ablation 柱状、baseline 对比）。
```bash
cd backend && uv run python -m benchmark.layer3.visualize
```
Expected: `reports/*.png` + `report.html` 更新。

**Step 2:** 写大纲 `docs/paper/bibm_outline.md`，每个 claim 后标注其支撑实验文件与报告 JSON 路径（可追溯）。

### Task 3.3：归档与记录

**Step 1:** 按 `CLAUDE.md` 规则归档：调用 `skill:doc-organize` 整理 `docs/`；在 `progress.txt` 记进度；把本次"诊断推翻了助手原稿的 fusion 假设（F1）"等复盘写入 `lesson.md`。

**Step 2:** Commit。
```bash
git add docs/paper progress.txt lesson.md
git commit -m "docs: BIBM paper outline + novelty diagnosis retrospective"
```

---

## 风险与诚实边界（写进论文 limitation，也提醒执行者）

| 风险 | 说明 | 处置 |
|------|------|------|
| F1 fusion 不存在 | 若选方向 C 需先实现，工作量被低估 | G1 若指向 C，重新评估排期 |
| F2 ClinGen 是机翻 | 不能用于母语增益 claim | 任何"母语优势"实验只用 rett |
| F4 rett 无 GT | 母语增益只能弱实验，除非补标注 | 分支 2.B 含标注成本 |
| 样本量 30 偏小 | reviewer 会质疑统计显著性 | 报告置信区间 / 考虑扩充 ClinGen 选样 |
| 后端环境 | layer3/pipeline 需全栈在线 | Milestone 0 起不来就停，不伪造 |

---

## 一句话总结给一作

代码已经否决了原稿里最性感的卖点（"交叉验证融合"根本没实现，且 ClinGen 母语数据是机翻的）。但你手里有**两套真实评测设施 + 30 例 ClinGen ground truth + 真实母语 rett 语料 + 已实现的双语 grounding**。**先跑 Milestone 0+1 的诊断（约 1 周），用 G1 决策门让数据告诉你 A/B/C 哪个有突破**，再决定投哪个 track——而不是现在就赌一个方向。
