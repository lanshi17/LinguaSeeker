# BIBM Main Paper 指标提升实施计划

**Status:** planned
**Created:** 2026-06-14
**Completed:** —
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以 BIBM Main Paper 为目标，把 CrossEvidence 从“端到端工程系统”推进为可被实验支撑的跨语言生物医学证据抽取方法，核心产出是可复现的算法增益、可审计的溯源指标、以及严谨的数据集和基线对比。

**Architecture:** 采用编排式垂直切片架构。Phase 2 聚焦候选证据召回、双轨证据图和源文一致性调和；Phase 3 聚焦实体标准化、外部知识上下文和证据矩阵；Phase 4 只服务专家标注、错误分析和可追溯审稿材料，不把 UI 功能包装成 Main Paper novelty。

**Tech Stack:** Python 3.12 via `uv`、FastAPI/LangGraph、pytest、Ruff、Next.js/React/TypeScript、现有 `benchmark/layer3` 和 `benchmark/pipeline` 评测设施、ClinGen N=30 ground truth、rett 原生多语种语料、PostgreSQL/Redis。

---

## 0. 结论先行

这些实现可以提升效果，但必须按 Main Paper 优先级筛选。

**P0 必做，直接影响论文指标和 novelty：**

- Phase 2.2 粗粒度证据块过滤器
- Phase 2.4 细粒度医学提示词
- Phase 2.8 跨轨调和算法
- Phase 2.9 证据置信度评分
- Phase 3.11 冲突消解 Agent
- Phase 3.13 证据矩阵构建器
- 评测侧的 baseline、ablation、traceability metrics、统计检验

**P1 可做，作为 P0 的知识增强或消融条件：**

- Phase 3.3 ClinGen 上下文加载器
- Phase 3.5 gnomAD 频率加载器
- Phase 3.9 频率匹配器
- 跨页表格拼接算法

**P2 只支撑标注、审查和 Demo，不应作为 Main Paper 核心贡献：**

- Phase 2.13 前端证据基础
- Phase 4.1 证据卡片
- Phase 4.2 自然语言修正
- Phase 4.8 证据工作台
- Phase 4.10 溯源抽屉
- Phase 4.18 前端端到端流程

**P3 暂缓，除非 Main Paper 指标已经通过：**

- Phase 4.5 批量操作
- Phase 4.6 资源监控面板
- Phase 4.13 NL-to-SQL
- Phase 4.14 设置页面
- Phase 4.15 ACMG 分类草稿生成
- Phase 4.16 批量处理模式
- Phase 4.17 PDF/DOCX 报告导出
- Phase 0.4/0.14/0.18 基础设施增强

## 1. Main Paper 目标定义

### 1.1 一句话 Novelty

本文提出 **Trace-Consistent Cross-lingual Evidence Graph Reconciliation, TC-CER**：一种面向医学遗传学证据抽取的跨语言双轨证据图调和方法，它把原文轨和译文轨候选证据绑定到可程序验证的源文 span，通过跨轨一致性、span 支持度、实体上下文和冲突惩罚联合评分，在保持 citation-valid-by-construction 的同时提升 ClinGen 证据字段抽取 F1 并降低幻觉引用率。

这句话有三个约束：

- 不能声称“100% 语义正确”。只能声称每条被采纳证据都必须带可校验源文 span，即 citation validity by construction。
- 不能把简单 prompt 拼接称作算法。算法贡献必须落在证据图、评分函数、冲突决策和可复现实验上。
- 不能把 UI 或工程流水线当成 Main Paper 核心。UI 只能作为专家审查和标注闭环。

### 1.2 论文主 claim

Main Paper 只允许写下列两类 claim：

1. **效果提升 claim:** TC-CER 在 ClinGen N=30 任务上相对最强 baseline 显著提升字段级 F1，且提升来自跨轨调和、证据块召回和源文验证，而不是单纯多调用 LLM。
2. **可追溯受约束 IE claim:** 在 F1 不低于强 LLM baseline 的同时，TC-CER 显著降低 Hallucinated Citation Rate，并提供更高的 Citation Validity Rate 和 Span Boundary F1。

若两类 claim 都无法通过统计 gate，则转 Demo/Resource Track。

### 1.3 成功门槛

**最低 Main Paper gate:**

- ClinGen N=30 上，最终方法相对最强 baseline 的 F1 提升 `>= +0.05`，或相对 `grounded_hard_rule` 的 F1 提升 `>= +0.03` 且 traceability 指标显著更好。
- Paired bootstrap 95% CI 下界 `> 0`，或配对符号检验/Wilcoxon 通过预设阈值。
- Hallucinated Citation Rate 明显低于 naive LLM 引用 baseline。
- 没有任何测试条目同时丢失 target gene 和 target disease。
- 所有最终数字来自冻结 artifact 或明确记录的 pipeline rerun，不混用不同代码版本。

**拒绝继续 Main Paper 的 no-go 条件：**

- 与 `translate-then-extract` 或 `single-agent CoT` baseline 打平。
- 跨轨调和只等价于硬规则，无法超过 `grounded_hard_rule`。
- traceability 只能验证 span 存在，无法证明 span 支持字段值。
- N=30 样本上只有个案提升，没有 paired 统计支持。

---

## 2. 总体路线

### 阶段 A: 冻结基线和可诊断数据

目标：先证明当前缺陷在哪里，不先写大功能。

核心产物：

- 冻结的 N=30 Phase 2 artifacts
- `dual_union`、`grounded_hard_rule`、`source_grounded_reconcile` 三策略报告
- 错误分解报告
- oracle upper bound 报告
- Main Paper manifest

### 阶段 B: 候选生成提升

目标：解决“正确证据根本没进入候选集”的问题。

核心方法：

- recall-first block selector
- 细粒度医学 prompt
- 表格/跨页表格召回
- target-safe role routing

### 阶段 C: 证据图调和算法

目标：把“双向提取、交叉验证融合”从工程描述变成可发表算法。

核心方法：

- 双轨候选证据图
- source-grounded confidence scoring
- cross-track agreement scoring
- conflict-aware decision policy
- abstain/review 机制

### 阶段 D: 实体知识对齐和证据矩阵

目标：降低 gene/disease/variant 对齐歧义和长尾错误，让 Phase 3 成为算法支撑而不是后处理。

核心方法：

- ClinGen safe context pack
- HGNC/MONDO alias expansion
- gnomAD frequency lookup
- ambiguity disambiguation agent
- ACMG/ClinGen evidence matrix

### 阶段 E: 评测、基线、论文材料

目标：用 reviewer 可接受的实验设计证明增益。

核心产物：

- ClinGen N=30 主实验
- rett 原生多语种弱/人工标注实验
- B0-B4 baseline
- ablation table
- traceability metrics
- paper outline 和 figures

---

## 3. Milestone 0: 工作区和基线冻结

**目标：** 在任何新实现前固定实验输入、代码版本和现有 no-go 数字。

**Files:**

- Read: `benchmark/layer3/reports/*.json`
- Read: `benchmark/layer3/evaluate.py`
- Create: `benchmark/layer3/analysis/main_paper_manifest.py`
- Create: `backend/tests/benchmark/layer3/test_main_paper_manifest.py`
- Modify: `progress.txt`

### Task 0.1: 建立隔离工作树

Run:

```bash
git status --short --branch
git fetch origin dev
git worktree add ../01_ACMG_Lingua-bibm-main-paper -b feat/bibm-main-paper-effect origin/dev
```

Expected:

- 新工作树从最新 `origin/dev` 创建。
- canonical 工作区不被污染。

### Task 0.2: 复算当前 N=30 基线

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.g2_statistics --report <new_reconcile_report> --write
```

Expected:

- 新报告包含 N=30。
- `main_paper_ready=false` 或明确说明 drift 原因。

### Task 0.3: 写 manifest

实现 `benchmark/layer3/analysis/main_paper_manifest.py`：

- 记录 git commit hash
- 记录 report path
- 记录 artifact coverage
- 记录三策略 P/R/F1
- 记录 G2 statistics
- 记录运行命令和 pipeline root

类型要求：

- 使用 `@dataclass(frozen=True)` 或 `TypedDict`
- 不使用裸 `-> dict` 作为公开函数返回值

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_main_paper_manifest.py -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/main_paper_manifest.py backend/tests/benchmark/layer3/test_main_paper_manifest.py
```

Gate G0:

- manifest 生成成功
- 基线可复现
- 不通过则停止，不进入算法实现

---

## 4. Milestone 1: 数据集和标注方案

**目标：** 解决 BIBM reviewer 最关心的 dataset/ground truth 问题。

**Files:**

- Read: `benchmark/layer3/ground_truth/selection.json`
- Read: `benchmark/layer3/ground_truth/*/expected.json`
- Create: `benchmark/layer3/analysis/dataset_card.py`
- Create: `benchmark/rett/annotation/README.md`
- Create: `benchmark/rett/annotation/agreement.py`
- Create: `backend/tests/benchmark/layer3/test_dataset_card.py`
- Create: `backend/tests/benchmark/rett/test_agreement.py`

### Task 1.1: ClinGen N=30 dataset card

写 `dataset_card.py`，输出：

- entry id
- PMID/PMCID/DOI
- gene
- disease
- MOI
- classification
- source length
- field coverage
- 是否有 table/figure cue

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.dataset_card --write
```

Expected:

- `benchmark/layer3/reports/dataset_card_<timestamp>.json`
- 能回答“这个 30 例集是否覆盖不同疾病、不同 MOI、不同证据类型”。

### Task 1.2: rett 原生多语种标注协议

写 `benchmark/rett/annotation/README.md`，定义：

- 选样标准：zh/ja/ru/de/fr/es 等原生文献，每语种至少 2 篇，优先覆盖同一 schema 字段。
- 标注 schema：复用 `benchmark/layer3/ground_truth/*/expected.json`。
- 双人独立标注流程。
- 仲裁流程。
- 不能把机器翻译 ClinGen 用作母语优势实验。

### Task 1.3: Cohen's kappa 计算

实现 `agreement.py`：

- 输入两个 annotator 目录
- 按 field_id 计算 agreement
- 对 disease/gene 使用现有 fuzzy 或 ontology-aware comparator
- 输出每字段 kappa 和总体 kappa

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/rett/test_agreement.py -q
```

Gate G1:

- ClinGen N=30 作为主实验 ground truth。
- rett 只有完成人工标注且 kappa 合格后，才能写“原生多语种”实验。
- 若 rett 标注来不及，Main Paper 主 claim 不依赖母语优势，只把 rett 放入附录或 limitation。

---

## 5. Milestone 2: Phase 2 候选生成提升

**目标：** 提高候选证据召回，避免调和算法面对空候选集。

对应当前问题：

- 2.2 粗粒度过滤器
- 2.4 细粒度原生提示词
- 跨页表格解析

**Files:**

- Search first: `backend/.old_version/src/`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/table_reconstruction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_table_reconstruction.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

### Task 2.1: 先查旧代码可复用实现

Run:

```bash
rg -n "block|chunk|table|caption|evidence_map|source_ground" backend/.old_version/src backend/.old_version/utils || true
```

Expected:

- 记录可复用逻辑。
- 不直接复制旧代码，按当前垂直切片适配。

### Task 2.2: 实现 recall-first block selector

数据契约：

```python
@dataclass(frozen=True)
class SelectedBlock:
    index: int
    score: float
    reasons: tuple[str, ...]
```

评分特征：

- target gene exact match
- target disease exact/alias match
- variant/HGVS cue
- relationship cue
- table/caption cue
- section cue: title, abstract, result, discussion, case report
- contamination penalty: unrelated gene/disease list

测试必须覆盖：

- target gene + disease 同块时必须入选
- 只有 unrelated disease list 时降权
- table caption 和跨页 table continuation 不被丢弃
- 空块忽略
- top K 截断不丢 target gene block

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_block_selection.py -q
```

### Task 2.3: 接入 catalog extraction

修改 `catalog_extraction.py`：

- 当 `TrackDocument.extraction_target` 存在时，用 selector 限制 prompt chunks。
- 保留原始 block index，避免 source grounding 无法回指原文。
- 没有 target 时保持现有行为。

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages_async.py -q
```

### Task 2.4: 细粒度医学 prompt

在 `prompts.py` 中拆出 helper：

- `relationship_decision_guidance()`
- `disease_boundary_guidance()`
- `method_result_guidance()`
- `phenotype_vs_disease_guidance()`
- `functional_evidence_guidance()`

提示词必须明确：

- causative vs associated vs susceptibility vs uncertain vs disputed vs refuted
- disease diagnosis 不等于 phenotype
- variant VUS 不自动降级 gene-disease relationship
- review/background context 默认低置信
- table 中字段必须保留 table source

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -q
```

### Task 2.5: 跨页表格拼接

实现 `table_reconstruction.py`：

- 识别同一 caption 或相邻 page 的 table continuation
- 规范化 markdown table
- 为合并后单元格保留原始 page/block/span provenance
- 合并失败时标记 review，不伪造 source span

测试覆盖：

- 两页同一表格拼接
- caption 缺失但 header 相同的 continuation
- header 不同不能拼接
- 合并后 provenance 可回到原 block

Gate G2:

- worst-5 Phase 2 rerun F1 提升 `>= +0.05`
- 不出现 target gene 和 target disease 同时丢失的 entry
- 通过后才跑 N=30 rerun

---

## 6. Milestone 3: 证据图和跨轨调和算法

**目标：** 把“交叉验证融合”变成算法贡献。

对应当前问题：

- 2.8 跨轨调和算法
- 2.9 证据置信度评分
- “100% 可追溯”的算法化表述

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/contracts.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/core.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/providers.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/__init__.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py`

### Task 3.1: 定义证据图合同

核心类型：

```python
@dataclass(frozen=True)
class EvidenceGraphNode:
    node_id: str
    field_id: str
    value: str
    track: str
    source_text: str
    source_start: int
    source_end: int
    confidence: float
    status: str

@dataclass(frozen=True)
class EvidenceGraphEdge:
    source_node_id: str
    target_node_id: str
    relation: str
    score: float

@dataclass(frozen=True)
class ReconciledEvidenceDecision:
    field_id: str
    selected_node_id: str | None
    selected_value: str | None
    support_score: float
    conflict_score: float
    traceability_score: float
    decision: str
    reasons: tuple[str, ...]
```

不允许使用：

- `classification`
- `expected_evidence`
- ground truth relationship label

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile/test_contracts.py -q
```

### Task 3.2: 构建双轨 evidence graph

节点：

- original candidate
- translated candidate
- source span
- normalized entity
- target context

边：

- same_field
- same_value
- synonym_or_alias
- source_overlap
- contradiction
- target_match
- table_continuation

验证：

- 同 field 同 value 的双轨证据产生 agreement edge
- 同 field 不同 value 产生 conflict edge
- source span 无法定位时 traceability edge score 为 0
- context contamination 节点不能被默认选中

### Task 3.3: 置信度评分函数

定义：

```text
s(node) =
  w1 * source_validity
+ w2 * span_boundary_tightness
+ w3 * track_agreement
+ w4 * target_specificity
+ w5 * entity_alignment_confidence
+ w6 * llm_confidence
- w7 * conflict_penalty
- w8 * context_contamination_penalty
```

初始权重必须固定在配置或 dataclass 中，不能边看 N=30 结果边手调。

推荐初始值：

- source_validity: 0.25
- span_boundary_tightness: 0.15
- track_agreement: 0.20
- target_specificity: 0.15
- entity_alignment_confidence: 0.10
- llm_confidence: 0.10
- conflict_penalty: 0.20
- context_contamination_penalty: 0.25

验证：

- grounded 双轨一致候选胜过单轨低置信候选
- source invalid 候选即使 LLM confidence 高也不能胜出
- conflict score 差距小于阈值时输出 `requires_review`
- no candidate 时输出 `not_found`，不得编造

### Task 3.4: 冲突决策逻辑

决策策略：

- `accept`: top1 分数足够高，且与 top2 margin 足够大
- `review`: top1/top2 冲突且 margin 小
- `abstain`: 没有有效 source span 或 target specificity 不足
- `reject`: source invalid 或 context contamination

关键参数：

```python
score_accept_threshold = 0.65
score_margin_threshold = 0.12
traceability_min_threshold = 0.70
```

验证：

- 两轨冲突且都 grounded 时不靠固定轨道优先级，靠 score 和 margin。
- 两轨都未 grounded 时不能 accept。
- 原文和译文 value 是同义 disease alias 时合并。

### Task 3.5: 接入 dual extraction API

修改 `DualEvidenceExtractionResult`，新增：

- `reconciled_items`
- `reconciliation_report`

保持向后兼容：

- 旧 JSON 没有新字段也能 `model_validate`
- Phase 3 若未使用新字段，仍可读取 original/translated

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/reconcile \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api_contracts.py \
  backend/tests/agents/test_phase_2_adapter.py -q
```

Gate G3:

- offline reconcile ablation 中 `graph_reconcile` > `grounded_hard_rule`
- HCR 不高于 `grounded_hard_rule`
- 若打平，则调和算法不作为 Main Paper 核心，只作为系统方法细节

---

## 7. Milestone 4: 溯源准确率和抗幻觉指标

**目标：** 把“100% 可追溯”改写为可验证指标。

**Files:**

- Create: `benchmark/layer3/analysis/traceability_metrics.py`
- Create: `backend/tests/benchmark/layer3/test_traceability_metrics.py`
- Modify: `benchmark/layer3/analysis/g2_statistics.py`
- Modify: `benchmark/layer3/analysis/reconcile_ablation.py`

### Task 4.1: 定义指标

实现以下指标：

- **CVR, Citation Validity Rate:** 被采纳证据中 source span 在原文中可程序验证存在的比例。
- **HCR, Hallucinated Citation Rate:** 被采纳证据中 citation 无法在原文中定位的比例。
- **ESR, Evidence Support Rate:** source span 语义支持字段值的比例。诊断阶段可用人工小样本或 reasoning LLM 复核，最终论文需标明判定方式。
- **Span Boundary F1:** 预测 span 与标注 span 的 token overlap F1。
- **Traceability Accuracy:** citation valid 且 field value 被 comparator 判定正确的比例。

### Task 4.2: 程序校验 CVR/HCR

实现：

- 对每条 selected item 读取 `source.start_offset/end_offset/text_snippet`
- 在 `source.md` 或 formatted text 中验证 snippet
- offset 不可靠时退化为 normalized exact snippet search
- table provenance 使用 table cell/block ref 验证

测试：

- exact offset valid
- offset invalid but snippet exists
- snippet missing
- table span valid
- source null

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_traceability_metrics.py -q
```

### Task 4.3: 加入统计报告

在 `g2_statistics.py` 中加入：

- F1 paired bootstrap
- CVR/HCR paired bootstrap
- HCR sign test
- per-entry traceability deltas

Gate G4:

- 最终方法 HCR 显著低于 naive LLM citation baseline
- CVR 接近 1.0，但论文表述为“valid citation rate”，不表述为语义 100% 正确

---

## 8. Milestone 5: Phase 3 实体标准化和知识对齐

**目标：** 解决实体对齐歧义、长尾 disease alias、频率证据和证据矩阵缺口。

对应当前问题：

- 3.3 ClinGen 上下文加载器
- 3.5 gnomAD 频率加载器
- 3.9 频率匹配器
- 3.11 冲突消解 Agent
- 3.13 证据矩阵构建器
- 3.14 Supervisor 集成

**Files:**

- Search first: `backend/.old_version/src/`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/context_pack/core.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/knowledge_sources/clingen.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/knowledge_sources/gnomad.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/disambiguation/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/disambiguation/core.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/evidence_matrix/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/evidence_matrix/core.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/api.py`
- Modify: `backend/src/agents/phase_3_adapter.py`
- Tests under: `backend/tests/core/standardize_entities_and_align_knowledge/`

### Task 5.1: target-safe context pack

允许输入：

- target gene
- target disease
- HGNC/MONDO IDs
- known aliases
- MOI
- source identifiers

禁止输入：

- ClinGen classification
- expected relationship
- expected evidence field values

测试：

- 从 `expected.json` 构建 context pack 时不泄漏 `classification`
- 不出现 `causative/refuted/disputed/uncertain` 等 expected relationship 标签

### Task 5.2: ClinGen context loader

实现本地文件加载，不默认实时网络请求。

输出：

- gene validity context
- disease aliases
- known inheritance terms
- source version metadata

验证：

- loader 可读取 fixture
- 缺失项返回 typed empty result，不抛裸异常
- 版本号进入 result metadata

### Task 5.3: gnomAD frequency loader and matcher

实现：

- 本地 TSV/JSON fixture loader
- variant key normalization
- ancestry frequency lookup
- threshold flags for ACMG BA1/BS1/PM2 supporting evidence

验证：

- exact variant match
- transcript mismatch review
- missing frequency returns `not_available`
- version metadata 被持久化

### Task 5.4: 冲突消解 Agent

规则：

- deterministic resolver 先行
- reasoning LLM 只用于无法规则消解的歧义
- 使用 `REASONING_LLM_MODEL`
- prompt 必须包含 source span，不允许外部猜测

歧义类型：

- gene alias collision
- disease subtype vs umbrella term
- phenotype vs diagnosis
- variant transcript mismatch
- population frequency conflict

验证：

- fake provider 单测
- disease subtype 可通过 MONDO ancestry 归一
- 无 source support 时输出 review，不自动采纳

### Task 5.5: 证据矩阵构建器

矩阵维度：

- row: ACMG/ClinGen evidence field or module
- column: extracted value, normalized entity, source span, track support, confidence, conflict state, review state

输出：

- typed `EvidenceMatrix`
- per-field completeness
- per-field traceability
- per-field conflict flags

接入：

- Phase 3 API 返回 matrix
- Phase 4 可读取 matrix 展示
- benchmark 可从 matrix 计算 field-level metrics

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/core/standardize_entities_and_align_knowledge -q
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check backend/src/core/standardize_entities_and_align_knowledge backend/tests/core/standardize_entities_and_align_knowledge
```

Gate G5:

- entity standardization accuracy 有提升
- disease boundary error 降低
- evidence matrix 能驱动 Phase 4 审查，不影响 Phase 2 artifacts 兼容性

---

## 9. Milestone 6: 前端专家审查闭环

**目标：** 服务标注、错误分析和可追溯展示，不抢 Main Paper 算法优先级。

对应当前问题：

- 2.13 前端证据基础
- 4.1 证据卡片
- 4.2 自然语言修正
- 4.7 Delta 审计面板
- 4.8 证据工作台
- 4.9 快捷键
- 4.10 溯源抽屉
- 4.18 前端端到端流程

**Files:**

- Existing: `frontend/src/features/evidence-search/`
- Create: `frontend/src/features/evidence-workbench/`
- Create: `frontend/src/features/evidence-workbench/components/EvidenceWorkbenchView.tsx`
- Create: `frontend/src/features/evidence-workbench/components/EvidenceCard.tsx`
- Create: `frontend/src/features/evidence-workbench/components/TraceabilityDrawer.tsx`
- Create: `frontend/src/features/evidence-workbench/components/ConflictBadge.tsx`
- Create: `frontend/src/features/evidence-workbench/hooks/useEvidenceWorkbench.ts`
- Create: `frontend/app/(dashboard)/evidence/workbench/page.tsx`
- Tests: `frontend/tests/evidence-workbench/`

### Task 6.1: 证据卡片

卡片显示：

- field name
- selected value
- original/translated support
- confidence
- conflict state
- source link
- review action

要求：

- 卡片只用于单个证据项，不嵌套卡片
- 字段和值必须能换行，不溢出
- 冲突状态使用图标或 badge

### Task 6.2: 左右分栏 workbench

布局：

- 左侧原文/译文文档视图
- 右侧证据卡片列表
- 点击卡片高亮 source span
- 支持 filter: conflict/review/low confidence/source invalid

### Task 6.3: 溯源抽屉

抽屉显示：

- exact source snippet
- surrounding context
- page/block/table metadata
- original vs translated span alignment
- traceability metric status

### Task 6.4: 自然语言修正

只实现最小闭环：

- “把这个 disease 改成 X”
- “标记为 source invalid”
- “这个证据需要人工复核”

所有修正必须进入 delta audit，不直接覆盖原始 extraction artifact。

Run:

```bash
cd frontend
nvm use
npm run lint
npm run type-check
npm test -- evidence-workbench
```

Gate G6:

- workbench 能支持人工 ESR/Span Boundary 标注
- 能导出 review deltas 给 benchmark 使用
- 不把 UI 作为 Main Paper 主实验增益来源

---

## 10. Milestone 7: Baselines、Ablation 和统计实验

**目标：** 给 BIBM reviewer 一个完整实验闭环。

**Files:**

- Create: `benchmark/layer3/baselines/naive_llm.py`
- Create: `benchmark/layer3/baselines/translate_then_extract.py`
- Create: `benchmark/layer3/baselines/original_only.py`
- Create: `benchmark/layer3/baselines/rag_llm.py`
- Create: `benchmark/layer3/baselines/single_agent_cot.py`
- Create: `benchmark/layer3/analysis/ablation_runner.py`
- Create: `benchmark/layer3/analysis/paired_statistics.py`
- Modify: `benchmark/layer3/visualize.py`
- Tests: `backend/tests/benchmark/layer3/`

### Task 7.1: Baseline B0-B4

Baselines:

- B0: naive single-prompt LLM
- B1: translate-then-extract
- B2: original-only
- B3: RAG + LLM
- B4: single-agent CoT

要求：

- 所有 baseline 复用 `benchmark/layer3/evaluate.py` comparator
- 不重写 field matching 逻辑
- 每个 baseline 输出同构 JSON report
- 记录模型、prompt、temperature、timestamp

### Task 7.2: Ablation

消融项：

- no recall-first selector
- no field-specific prompt repair
- no table reconstruction
- no evidence graph
- no cross-track agreement
- no source validity feature
- no entity context
- hard rule reconcile
- full TC-CER

输出：

- Precision/Recall/F1
- CVR/HCR
- Traceability Accuracy
- cross-lingual consistency
- over-extraction count
- per-field deltas

### Task 7.3: 统计检验

实现：

- paired bootstrap CI
- paired sign test
- Wilcoxon optional
- effect size
- per-entry delta table

Run:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3 -q
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.ablation_runner --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.paired_statistics --report <final_ablation_report> --write
```

Gate G7:

- full TC-CER 明确优于 B1/B4 或 traceability 指标显著优于强 baseline
- 若只优于 naive baseline，不够 Main Paper

---

## 11. Milestone 8: 全量 rerun 和论文材料

**目标：** 形成可提交 Main Paper 的结果包。

**Files:**

- Create: `docs/paper/bibm_main_outline.md`
- Create: `docs/paper/experiment_manifest.md`
- Modify: `benchmark/layer3/visualize.py`
- Modify: `progress.txt`
- Modify: `lesson.md`

### Task 8.1: worst-5 rerun gate

先跑 worst-5：

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.run_phase2_artifact_batch \
  --base-url http://localhost:8002 \
  --entries clingen_004 clingen_020 clingen_021 clingen_024 clingen_028 \
  --pipeline-root <worktree_backend_data_pipeline> \
  --poll-interval-s 10 \
  --max-poll-attempts 360 \
  --write
```

Expected:

- 5/5 completed
- materialized artifacts 写入对应 `preprocessed/phase_2/extraction_result.json`
- ablation F1 比历史 worst-5 至少提升 `+0.05`

### Task 8.2: N=30 rerun gate

仅在 worst-5 通过后运行：

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.run_phase2_artifact_batch \
  --base-url http://localhost:8002 \
  --pipeline-root <worktree_backend_data_pipeline> \
  --poll-interval-s 10 \
  --max-poll-attempts 360 \
  --write
```

Expected:

- N=30 completed
- no failed entries
- artifacts 可 materialize

### Task 8.3: 最终表格和图

生成：

- Table 1: dataset statistics
- Table 2: baseline comparison
- Table 3: ablation
- Table 4: traceability metrics
- Figure 1: method overview
- Figure 2: evidence graph scoring
- Figure 3: per-field F1/traceability heatmap
- Figure 4: error reduction

### Task 8.4: 论文大纲

`docs/paper/bibm_main_outline.md` 必须包含：

- Abstract claim 和对应 report path
- Method formalization
- Dataset section
- Baseline section
- Metrics section
- Results section
- Limitations
- Ethics and clinical disclaimer

每个数字后写报告路径，例如：

```text
F1 = 0.xxxx, source: benchmark/layer3/reports/final_ablation_<timestamp>.json
```

Gate G8:

- 所有 paper 数字可追溯到 report JSON
- 不引用手工截图数字
- 不写“100% 准确溯源”，只写 citation validity by construction

---

## 12. 任务优先级和排期

### Week 1: 证明问题和候选生成

1. Milestone 0: 冻结基线和 manifest
2. Milestone 1.1: ClinGen dataset card
3. Milestone 2.1-2.4: block selector + prompt repair
4. worst-5 Phase 2 rerun

验收：

- worst-5 gate 通过
- 错误类型清楚
- 不通过则只投 Demo/Resource，不继续大改

### Week 2: 证据图调和和溯源指标

1. Milestone 3: evidence graph reconcile
2. Milestone 4: traceability metrics
3. offline ablation
4. N=30 rerun gate

验收：

- `graph_reconcile` 超过 hard rule
- HCR/CVR 指标可复现

### Week 3: Phase 3 对齐和主实验

1. Milestone 5: context pack + disambiguation + evidence matrix
2. Milestone 7: baselines + statistics
3. final N=30 report

验收：

- B0-B4 都有报告
- full method 有统计支持

### Week 4: UI 审查和论文材料

1. Milestone 6: 最小 evidence workbench
2. Milestone 8: figures/tables/outline
3. code review
4. docs organize

验收：

- paper package 完整
- Demo 备选材料完整

---

## 13. Review Checklist

实现完成后逐项检查：

- [ ] 没有把 ground truth label 输入 runtime method
- [ ] 所有新 backend 公开函数没有裸 `-> dict`
- [ ] 所有 LLM verifier 使用 `REASONING_LLM_MODEL`
- [ ] 所有新增业务代码在 `backend/src/`
- [ ] 所有测试在 `backend/tests/` 或 `frontend/tests/`
- [ ] 所有 Python 命令使用 `uv`
- [ ] 所有 frontend 命令使用 `nvm use` 后的 npm
- [ ] 所有 source citation 都有 programmatic validity check
- [ ] 所有论文数字都有 report path
- [ ] `progress.txt` 已记录
- [ ] 调试试错写入 `lesson.md`
- [ ] docs 更新后运行 doc organize 流程
- [ ] 模块实现并测试通过后生成对应 README/module guide

---

## 14. 最终 Go/No-Go

### Main Paper Go

满足任一条：

- F1 相对最强 baseline 显著提升，且 traceability 不下降。
- F1 与最强 baseline 非劣，但 CVR/HCR/Traceability Accuracy 显著更优，形成“traceability-constrained IE”贡献。

### Main Paper No-Go

满足任一条：

- 只超过 naive LLM，不超过 translate-then-extract 或 single-agent CoT。
- graph reconcile 与 hard rule 打平。
- 统计 CI 包含 0，且无明确机制解释。
- rett 无人工标注却试图写原生多语种优势。

### Demo/Resource Pivot

如果 Main Paper no-go，则论文定位改为：

```text
CrossEvidence: A citation-valid-by-construction bilingual workbench and benchmark resource for ACMG/ClinGen evidence extraction.
```

此时保留：

- 30-entry ClinGen benchmark
- bilingual traceability workbench
- evidence matrix
- system demonstration
- limited ablation

不再强行包装算法 novelty。
