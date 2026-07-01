# Stages 证据提取流水线阶段

> LangGraph 工作流的各运行时阶段组件

## 概述

`stages` 模块包含证据提取 LangGraph 工作流的所有运行时阶段。每个阶段是一个独立的类，封装特定的提取/验证逻辑，由 `EvidenceExtractionWorkflow` 编排执行。

## 结构

```
stages/
├── __init__.py                  # 模块入口
├── preprocessing.py             # 证据预处理（规范化 + 截断）
├── role_routing.py              # 证据角色路由
├── evidence_map.py              # 相关性扫描与通道分类
├── block_selection.py           # 高召回块选择
├── primary_broad_extraction.py  # B8 高召回初筛提取
├── catalog_extraction.py        # 166 字段目录提取
├── review_validation.py         # 审校验证
├── special_evidence.py          # 特殊证据提取
├── clinical_context.py          # 临床上下文补充提取
├── group_assignment.py          # 变异中心分组
├── source_grounding.py          # 源文本定位验证
└── quality_validation.py        # 质量门验证
```

## 核心组件

### 预处理 (`preprocessing.py`)

`EvidencePreprocessor` — 规范化和截断证据字段：
- 空白规范化（多空格/换行→单空格）
- 分级截断：article_limit=3000、paragraph_limit=800、sentence_limit=400
- 处理字段：article_title、article_abstract、article_keywords、paragraph_text、figure_caption、table_caption、table_data、supplementary_info

### 角色路由 (`role_routing.py`)

`EvidenceRoleRouter` — 按证据角色分离提取结果：
- PRIMARY → 主证据列表
- PHENOTYPE → 表型证据列表
- CONTEXT → 判断是否为目标实体身份（gene_symbol/disease_name 匹配），匹配则提升为 PRIMARY
- 其他 → 丢弃并记录日志

### 相关性扫描 (`evidence_map.py`)

`RelevanceScanStage` — LLM 驱动的文档相关性评估：
- 支持同步 `run()` 和异步 `run_async()`（并发 chunk 处理，默认 5 并发）
- 按 token 预算分块 → 每块 LLM 评估 → 合并结果
- 输出 `RelevanceScanResult`（含 `DocumentEvidenceMap` + `DocumentChannelClassification`）
- 通道分类决定文档类型（case_report / functional_study / cohort_study 等）和可提取字段集

### 块选择 (`block_selection.py`)

`select_recall_first_blocks(blocks, target, ...)` — 高召回块选择：
- 基于目标基因/疾病关键词评分每个块
- 评分因子：基因符号匹配、疾病家族匹配、变异线索、关系线索、章节线索、表格/标题加分
- 邻域扩展：目标块前后各 1 块
- 返回 `SelectedBlock`（index、score、reasons）

### Broad 提取 (`primary_broad_extraction.py`)

`PrimaryBroadExtractionStage` — B8 高召回初筛：
- 使用简化提示，高召回率提取所有可能的证据候选项
- 输出 `PrimaryBroadEvidenceCandidate` 列表
- 包含 benchmark 字段别名兼容层（`_FIELD_ALIAS_MAP`）
- 后处理：consequence_class→variant_type 投影、稀疏项合并、值规范化

### 目录提取 (`catalog_extraction.py`)

`CatalogExtractionStage` — 166 字段结构化提取：
- 仅发送 LLM 可提取组（high_signal 62 字段 + supporting 81 字段），过滤 curation 组（23 字段 K）
- 按 token 预算分块 → 每块并发提取（默认 5 并发）
- 核心身份字段（A.gene_symbol、B.disease_diagnosis）缺失时触发聚焦重试
- 后处理：`RawSourceNormalizer`（未定位源移至 raw_source）、`FieldValueNormalizer`（枚举/格式约束）

### 审校验证 (`review_validation.py`)

`ReviewValidationStage` — 对初筛候选项进行审校：
- 仅验证已有候选项，不添加新候选项
- 支持 3 种拒绝策略：`hard_veto`（直接移除）、`soft_veto`（标记降级）、`tristate_review`（三态：approve/uncertain/reject/correct）
- 检测并保留非人类模型上下文的变异拒绝（避免误杀）

### 特殊证据 (`special_evidence.py`)

`SpecialEvidenceStage` — 提取 4 类特殊证据：
- **functional** — 功能实验数据
- **case_control** — 病例对照数据
- **authority** — 权威来源（ClinVar、HGMD）
- **contradiction** — 矛盾证据
- 通过 `SpecialEvidenceValidator` 过滤不安全记录

### 临床上下文 (`clinical_context.py`)

`ClinicalContextStage` — 补充提取 6 个临床上下文字段：
- `B.clinical_phenotypes`、`B.sex`、`B.age_of_onset`、`B.mode_of_inheritance_reported`
- `C.inheritance_source`、`C.de_novo_status`
- 使用聚焦提示（≤10 字段），解决主目录提取阶段因注意力稀释导致的 not_found 问题
- 智能合并：仅补充当前缺失的字段，不覆盖已有值

### 分组与定位

- `GroupAssignmentStage` (`group_assignment.py`) — 委托 `GroupAssigner` 为证据项和特殊记录分配变异中心 group_id
- `SourceGroundingStage` (`source_grounding.py`) — 委托 `SourceGrounder` 验证和修复源文本跨度

### 质量门 (`quality_validation.py`)

`QualityGateStage` — 委托 `QualityValidator` 执行规则质量验证，输出 `QualityReport`。

## 数据流（Broad 模式）

```
TrackDocument + ExtractionTarget
    │
    ▼
RelevanceScanStage.run()
    │  → RelevanceScanResult (evidence_map + channel_classification)
    ▼
select_recall_first_blocks()
    │  → SelectedBlock[]
    ▼
PrimaryBroadExtractionStage.run()
    │  → PrimaryBroadEvidenceCandidate[] → EvidenceItem[]
    ▼
ReviewValidationStage.run()
    │  → 审校后的 EvidenceItem[] (approve/reject/correct)
    ▼
SpecialEvidenceStage.run()
    │  → SpecialEvidenceRecord[]
    ▼
ClinicalContextStage.run()
    │  → 补充 EvidenceItem[]
    ▼
GroupAssignmentStage.run()
    │  → 分组后的 items + special_records
    ▼
SourceGroundingStage.run()
    │  → 定位后的 items + special_records
    ▼
TargetSpanFieldRecovery (在 workflow 中调用)
    │  → 恢复的高价值字段
    ▼
AcmgEvidenceValueNormalizer (在 workflow 中调用)
    │  → 规范化后的 items
    ▼
QualityGateStage.run()
    │  → QualityReport
    ▼
finalize → EvidenceExtractionResult
```

## 使用

各阶段由 `EvidenceExtractionWorkflow` 自动编排，通常无需直接调用。如需单独使用：

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import RelevanceScanStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.primary_broad_extraction import PrimaryBroadExtractionStage

# 相关性扫描
scan_stage = RelevanceScanStage(provider=llm_provider)
scan_result = scan_stage.run(track_document)

# Broad 提取
broad_stage = PrimaryBroadExtractionStage(provider=llm_provider)
candidates = broad_stage.run(track_document)
```
