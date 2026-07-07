# Phase 3 — 标准化实体与知识对齐

> 将提取的生物医学实体（基因、变异、疾病、表型）确定性地映射到标准化术语库，为下游 ACMG 评分和证据整合提供对齐后的规范实体。

## 概述

Phase 3 是 Lingua Seeker 管道的核心标准化阶段。它接收 Phase 2 输出的双轨证据提取结果（`DualEvidenceExtractionResult`），通过混合匹配策略将实体提及映射到统一术语库（HGNC、ClinVar、OMIM、HPO、ClinGen），然后持久化标准化结果并生成 ACMG-ready 证据集。

### 关键特性

- **混合匹配**：先执行精确匹配（别名优先级排序），未命中时回退到语义相似度匹配
- **跨语言疾病解析**：支持中文疾病名称通过 token-ILIKE 匹配回退到英文术语
- **HGVS 规范化**：支持三字母→单字母蛋白质变异转换、ClinVar 别名扩展
- **确定性内部变异 ID**：未匹配变异通过 `sha256` 摘要生成稳定标识符
- **流式 ClinVar 导入**：分块处理避免单次内存溢出
- **ACMG 投影**：将标准化表型（HPO）投影为下游规则引擎消费的紧凑键值对

## 目录结构

```
standardize_entities_and_align_knowledge/
├── __init__.py              # 包声明
├── api.py                   # 公共门面：EntityStandardizationService、术语导入/嵌入构建
├── core.py                  # StandardizationService：编排匹配与持久化
├── contracts.py             # 类型化数据契约（EntityType, EntityMatch, StandardizationResult 等）
├── adapters.py              # DualResultAdapter：Phase 2 输出 → Phase 3 输入
├── matchers.py              # HybridTerminologyMatcher：精确 + 语义混合匹配门面
├── normalizers.py           # 共享规范化工具（文本折叠、基因符号、疾病跨语言映射）
├── repositories.py          # StandardizationRepository：PostgreSQL 持久化（术语、匹配、绑定、规范证据）
├── importers.py             # 术语导入解析器（HGNC、OMIM、HPO、ClinGen、ClinVar）
├── variant_id.py            # 未匹配变异的确定性内部 ID 生成
├── hgvs_normalizer.py       # HGVS 变异规范化与别名扩展
├── acmg_projection.py       # AcmgReadyProjector：标准化实体 → ACMG-ready 证据事实
├── cross_lingual_disease.py # CrossLingualDiseaseResolver：非英文疾病名 token 模糊匹配
├── db_ready_gate/           # DB-ready 候选证据准入门控（纯函数 + 审计原因）
├── precise_match/           # 精确术语匹配子模块
├── similarity_match/        # 语义相似度匹配子模块
└── context_pack/            # 目标安全上下文包子模块
```

## 核心组件

### EntityStandardizationService（`api.py`）
公共门面，负责组装依赖链（适配器→匹配器→仓储→服务），提供：
- `standardize()` — 处理一次标准化运行
- `import_terminology()` — 导入本地术语源
- `build_terminology_embeddings()` — 构建 pgvector 嵌入索引

### StandardizationService（`core.py`）
内部编排层，依次执行：
1. 确保运行父记录存在
2. 对每个候选执行匹配
3. 上规范化实体
4. 持久化运行证据、绑定、规范证据
5. 刷新文献档案和搜索索引
6. 投影 ACMG-ready 证据集

### HybridTerminologyMatcher（`matchers.py`）
混合匹配策略：
- 优先 `PreciseTerminologyMatcher`（别名类型优先级 + 源库排序）
- 未映射时尝试 `CrossLingualDiseaseResolver`（仅疾病类型）
- 最终回退 `SimilarityTerminologyMatcher`（pgvector 嵌入检索 + rerank）

### DualResultAdapter（`adapters.py`）
将 Phase 2 的 `DualEvidenceExtractionResult` 转换为 `StandardizationInput`，处理：
- 原始/翻译/审计轨的证据字段映射
- 表型字段拆分（中文分号/逗号分隔）
- 实体类型 → 绑定角色的推断

### AcmgReadyProjector（`acmg_projection.py`）
将标准化匹配结果投影为 ACMG 消费者可直接使用的证据事实：
- 提取已标准化的 HPO 表型 ID
- 关联原始证据值和置信度

### DB-ready Gate（`db_ready_gate/`）
候选准入层，用于判断证据是否具备进入 DB-ready/export 边界的最低条件：
- 检查 run/document/field/group 基础边界
- 检查 source span 或显式 expert override
- 按字段要求 gene/variant/disease 标准化绑定
- 输出 `DbReadyRejectReason` 聚合，供后续审计报告使用

`db_ready_gate` 本身保持纯函数；`repositories.py` 在 `upsert_canonical_evidence()` 前将 `RunItemSpec`、`EntityMatch` 和 normalized entity 外部 ID 适配为 `DbReadyCandidate`，只把通过 gate 的业务 track row 写入 canonical evidence。兼容性的 match fallback row 仍保留旧行为。

## 数据流

```
Phase 2 DualEvidenceExtractionResult
        │
        ▼
   DualResultAdapter ──→ StandardizationInput
        │                    (candidates + evidence_items)
        ▼
   HybridTerminologyMatcher
        │
        ├─→ PreciseTerminologyMatcher (精确匹配)
        │       └─→ HGNC/ClinVar/OMIM/HPO/ClinGen 别名查找
        ├─→ CrossLingualDiseaseResolver (跨语言疾病)
        └─→ SimilarityTerminologyMatcher (语义匹配)
                └─→ pgvector 嵌入检索 + rerank
        │
        ▼
   EntityMatch[] ──→ StandardizationRepository
        │                ├─ upsert_normalized_entity
        │                ├─ persist_run_evidence
        │                ├─ persist_bindings
        │                ├─ DB-ready gate
        │                ├─ upsert_canonical_evidence
        │                ├─ refresh_literature_profile
        │                └─ refresh_search_index
        ▼
   AcmgReadyProjector ──→ StandardizationResult
```

## 使用方式

```python
from src.core.standardize_entities_and_align_knowledge.api import (
    EntityStandardizationService,
    import_terminology,
    build_terminology_embeddings,
)

# 标准化一次运行的证据
service = EntityStandardizationService(settings)
result = await service.standardize(dual_extraction_result)

# 导入术语数据
await import_terminology(settings, sources=("hgnc", "omim", "hpo", "clingen", "clinvar"))

# 构建语义嵌入
count = await build_terminology_embeddings(settings, entity_type="gene")
```
