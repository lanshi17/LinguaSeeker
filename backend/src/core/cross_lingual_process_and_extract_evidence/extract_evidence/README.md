# Extract Evidence 证据提取模块

> 双轨 ACMG/GDV 证据提取、交叉校验和源文本溯源

## 概述

`extract_evidence` 模块实现医学遗传学文献的结构化证据提取。基于 166 字段 A-K 类目的 ACMG/GDV 证据目录，支持双轨提取（原文轨 + 译文轨）、交叉校验和源文本溯源。管线基于 LangGraph 构建，采用 `broad`（高召回初筛 + 审校验证）和 `catalog`（直接目录提取）两种工作模式。

## 结构

```
extract_evidence/
├── __init__.py              # 模块入口
├── contracts.py             # 数据契约（EvidenceItem, TrackDocument 等 30+ 类型）
├── core.py                  # 源文本定位、质量验证、证据链构建
├── api.py                   # EvidenceExtractionService — 公共 API 门面
├── workflow.py              # EvidenceExtractionWorkflow — LangGraph 工作流
├── config_context.py        # EvidenceExtractionConfigContext — 多 tier LLM 配置
├── catalog.py               # 166 字段 A-K 类目静态目录
├── channel_contracts.py     # 文档通道分类与字段资格
├── chunking.py              # Token 预算提示分块
├── prompts.py               # 各阶段 LLM 提示模板
├── providers.py             # LangChainEvidenceProvider — 多 tier LLM 提供者
├── normalization.py         # ACMG 证据值规范化
├── field_eligibility.py     # 目标作用域字段资格策略
├── field_profile.py         # 评估配置文件与字段过滤
├── target_span_recovery.py  # 高信号字段确定性恢复
├── translation_traceback.py # 英文→原文溯源
├── _normalization.py        # 证据项规范化（字段目录对齐）
├── _grouping.py             # 变异中心分组
├── _quality.py              # 质量验证与目标实体守护
├── stages/                  # LangGraph 流水线阶段
├── reconcile/               # 双轨交叉校验
└── verify/                  # 证据验证
```

## 核心组件

### 数据契约 (`contracts.py`)

| 类型 | 说明 |
|------|------|
| `TrackDocument` | 单轨文档，含文档 ID、格式化文本、内容块、提取目标 |
| `ExtractionTarget` | 基因-疾病假设目标（gene_symbol、disease_name、variant_hgvs_p） |
| `EvidenceItem` | 单字段提取结果，含 field_id、value、status、source、confidence |
| `EvidenceStatus` | 枚举：FOUND / NOT_FOUND / NOT_APPLICABLE / NOT_ATTEMPTED / CONTEXT_CONTAMINATION |
| `EvidenceRole` | 枚举：PRIMARY / PHENOTYPE / CONTEXT |
| `SourceLocation` | 源文本定位，含 span_id、text_snippet、offsets、page、source_precision |
| `EvidenceChain` | 变异中心证据链 |
| `SpecialEvidenceRecord` | 特殊证据记录（functional / case_control / authority / contradiction） |
| `QualityReport` | 质量门报告 |
| `DualTrackDocuments` | 双轨文档对 |
| `EvidenceExtractionResult` | 提取最终结果 |
| `EvidenceExtractionState` | LangGraph 工作流状态 |

### 公共 API (`api.py`)

`EvidenceExtractionService` 是证据提取的公共门面：

- **提取模式**：`dual`（双轨）、`original_only`（仅原文）、`english_pivot`（英文中心）
- **工作流模式**：`broad`（高召回初筛 + 审校，默认）或 `catalog`（直接目录提取）
- **`extract(document, target, ...)`** — 执行提取并返回 `EvidenceExtractionResult`
- 内部处理：内容块过滤（移除元数据和参考文献）、页面跨度格式化、翻译对齐元数据解析

### 工作流 (`workflow.py`)

`EvidenceExtractionWorkflow` — LangGraph 状态图编排，两种模式共用大部分阶段：

**Broad 模式（默认）**：
```
relevance_scan → block_selection → primary_broad_extraction → review_validation
→ special_evidence → clinical_context → group_assignment → source_grounding
→ target_span_recovery → normalization → quality_gate → finalize
```

**Catalog 模式**：
```
relevance_scan → block_selection → catalog_extraction
→ special_evidence → clinical_context → group_assignment → source_grounding
→ target_span_recovery → normalization → quality_gate → finalize
```

### 证据目录 (`catalog.py`)

166 字段 A-K 类目，分 3 组：
- **high_signal (62)**：A/B/D/E/J — 变异、病例、人群、预测、权威
- **supporting (81)**：C/F/G/H/I — 分离、功能、病例对照、矛盾、基因
- **curation (23)**：K — 跨论文 GDV 元数据（下游 GDV 管线填充，LLM 提取过滤）

### LLM 提供者 (`providers.py`)

`LangChainEvidenceProvider` — 多 tier LLM 提供者：
- **FAST** — 快速 tier，使用 `cfg.llm` 配置
- **STANDARD** — 标准 tier，使用 `cfg.reasoning` 配置
- **STRONG** — 强推理 tier，使用 `cfg.reasoning` 配置 + high effort
- 支持同步 `invoke_structured` 和异步 `ainvoke_structured`
- 内置 JSON 修复回退（LLM 修复 + Pydantic 重解析）

### 源文本定位 (`core.py`)

- `SourceGrounder` — 验证和修复源文本跨度，支持全角→半角转换、模糊省略号匹配
- `EvidenceChainBuilder` — 从已定位的分组证据构建变异中心身份链
- `SpecialEvidenceValidator` — 过滤不安全的特殊证据记录

### 其他关键模块

| 模块 | 说明 |
|------|------|
| `normalization.py` | `AcmgEvidenceValueNormalizer` — HGVS 校验、基因符号规范化、等位基因频率约束 |
| `field_eligibility.py` | `FieldEligibilityPolicy` — 基于提取目标和文档内容决定可提取字段集 |
| `field_profile.py` | 评估配置文件（`ExtractionProfile`）与文档通道字段资格交叉 |
| `target_span_recovery.py` | `TargetSpanFieldRecovery` — 从已选目标片段确定性恢复高价值字段 |
| `translation_traceback.py` | `apply_translation_traceback` — 将英文轨证据溯源到原文文本位置 |
| `_grouping.py` | `GroupAssigner` — 基因/变异中心的确定性分组 ID 分配 |
| `_quality.py` | `QualityValidator` — 规则质量验证；`TargetEntityGuard` — 主实体字段守护；`IntraTrackConflictChecker` — 轨内矛盾检测 |

## 数据流

```
CrossLingualOutput (原文 + 译文)
    │
    ▼
EvidenceExtractionService.extract()
    │
    ├── 构建 DualTrackDocuments
    │
    ▼
EvidenceExtractionWorkflow (每轨独立)
    │
    ├── relevance_scan → 关键词分类 + 通道分类
    ├── block_selection → 高召回块选择
    ├── primary_broad_extraction / catalog_extraction → LLM 证据提取
    ├── review_validation → 审校验证（broad 模式）
    ├── special_evidence → 功能/病例对照/权威/矛盾证据
    ├── clinical_context → 表型/性别/年龄/遗传模式补充
    ├── group_assignment → 变异中心分组
    ├── source_grounding → 源文本跨度验证
    ├── target_span_recovery → 高价值字段恢复
    ├── normalization → ACMG 值规范化
    ├── quality_gate → 质量门
    │
    ▼
EvidenceExtractionResult (每轨)
    │
    ▼
translation_traceback → 英文轨溯源到原文位置
    │
    ▼
reconcile → 双轨交叉校验 → 最终结果
```

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService

# 初始化
service = EvidenceExtractionService(cfg)

# 单轨提取
result = service.extract(document=track_doc, extraction_target=target)

# 双轨提取
result = service.extract_dual(
    documents=dual_docs,
    extraction_target=target,
    translation_alignment=alignment_chunks,
)
```
