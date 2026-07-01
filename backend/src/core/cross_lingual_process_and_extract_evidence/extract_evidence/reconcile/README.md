# Reconcile 双轨证据交叉校验

> 确定性源文本定位交叉校验和上下文验证器驱动校验

## 概述

`reconcile` 模块实现原文轨和译文轨提取结果的交叉校验。通过对齐记录构建、候选评分和字段级决策，将双轨证据合并为单一源文本定位的最终结果。支持两种模式：纯确定性校验和上下文验证器增强校验。

## 结构

```
reconcile/
├── __init__.py        # 导出核心类型
├── api.py             # CrossTrackReconcileService — 公共 API
├── contracts.py       # ReconcileParams, CandidateScore, FieldDecision, ReconcileOutput
├── core.py            # 确定性源文本定位校验
├── contextual.py      # 上下文验证器增强校验
├── alignment.py       # 原文/译文对齐记录构建
└── features.py        # 候选特征向量提取（用于学习型仲裁）
```

## 核心组件

### 公共 API (`api.py`)

`CrossTrackReconcileService` — 双轨校验的公共门面：

```python
class CrossTrackReconcileService:
    def __init__(self, params: ReconcileParams = ReconcileParams())
    def run(original, translated, context_pack=None) -> EvidenceExtractionResult
    def run_with_output(original, translated, context_pack=None) -> ReconcileOutput
```

- `context_pack=None` 时使用纯确定性校验（`reconcile_results`）
- 提供 `context_pack` 时使用上下文验证器增强校验（`reconcile_with_context`）

### 数据契约 (`contracts.py`)

| 类型 | 说明 |
|------|------|
| `ReconcileParams` | 校验参数（`conflict_margin=0.15`） |
| `CandidateScore` | 候选评分分解：source_score、confidence_score、agreement_score、status_score、verifier_support_score、target_specificity_score、contradiction_penalty |
| `FieldDecision` | 字段级决策：accepted（接受项）、rejected（拒绝项）、requires_review、rationale |
| `ReconcileOutput` | 完整校验输出：result + decisions + alignment_records |

### 确定性校验 (`core.py`)

`reconcile_results(original, translated, params)` — 纯规则驱动的双轨校验：

- **候选构建** — 从两轨提取结果构建 `_Candidate`（含 track、normalized_value）
- **字段决策** — 对每个字段的候选评分排序，最高分接受，其余拒绝
- **评分体系**：
  - `source_score` — 有源文本 > 无源文本
  - `status_score` — FOUND > NOT_FOUND > 其他
  - `agreement_score` — 两轨值一致时加分
  - `conflict_margin` — 冲突边距阈值
- **注解** — 接受项添加 `inference_basis`（"source-grounded cross-track reconcile"），拒绝项记录拒绝理由
- **链去重** — 对结果中的 `EvidenceChain` 去重

### 上下文校验 (`contextual.py`)

`reconcile_with_context(original, translated, context_pack, params)` — 增强版校验：

在确定性校验基础上引入 `TargetContextPack`（来自标准化实体与知识对齐模块）：

- **验证器评分** (`score_candidate_support`) — 使用 `EvidenceVerificationInput` 评估候选与目标上下文的一致性
- **目标特异性评分** — 评估候选值与目标基因/疾病的匹配度
- **矛盾惩罚** — 验证器检测到矛盾时施加惩罚
- **关系覆盖** — 特定条件下允许验证器覆盖关系字段
- **疾病规范化** — 可将疾病名规范化为目标上下文的标准名称

### 对齐记录 (`alignment.py`)

构建字段级对齐记录，追踪原文轨和译文轨的证据一致性：

- `build_alignment_records` — 逐字段比较两轨最佳证据项
- **对齐标签** (`EvidenceAlignmentLabel`)：AGREES / PARTIAL / CONFLICT / MISSING
- **支持标签** (`EvidenceSupportLabel`)：SUPPORTS / PARTIAL_SUPPORT / CONTRADICTS / INSUFFICIENT
- **检测逻辑**：
  - 关系漂移（causative ↔ protective 等）
  - 冲突值（pathogenic ↔ benign 等）
  - 否定丢失（一侧有否定词另一侧无）
  - 数值漂移（定量医学值跨轨变化）

### 特征提取 (`features.py`)

`CandidateFeatureVector` — 为学习型仲裁器提取 21 维特征向量：

- 源文本特征（source_score、has_source、source_is_exact/corrected、span_length）
- 置信度与状态特征
- 一致性与验证器特征（agreement_score、verifier_support_score、target_specificity_score）
- 矛盾与字段特征
- 交互特征（source × agreement、verifier × no_contradiction 等）

## 数据流

```
EvidenceExtractionResult (原文轨)
    +
EvidenceExtractionResult (译文轨)
    │
    ▼
build_alignment_records()
    │  → 字段级对齐记录
    ▼
_decide_fields()
    │
    ├── 确定性模式：_score_candidate() → 源文本/状态/一致性评分
    └── 上下文模式：_score_candidate() + 验证器评分 + 目标特异性
    │
    ▼
FieldDecision (每字段: accepted + rejected)
    │
    ▼
组装 EvidenceExtractionResult
    │  → 合并接受项 + 注解 + 链去重
    ▼
ReconcileOutput
    ├── result: EvidenceExtractionResult
    ├── decisions: tuple[FieldDecision, ...]
    └── alignment_records: tuple[EvidenceAlignmentRecord, ...]
```

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile import (
    CrossTrackReconcileService, ReconcileParams,
)

# 确定性校验
service = CrossTrackReconcileService(params=ReconcileParams(conflict_margin=0.15))
result = service.run(original_result, translated_result)

# 上下文增强校验
output = service.run_with_output(
    original_result, translated_result,
    context_pack=target_context_pack,
)
# output.decisions 可审计每字段决策
```
