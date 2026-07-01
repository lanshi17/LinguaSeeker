# Precise Match — 精确术语匹配

> 基于别名优先级的确定性术语匹配，通过数据库精确查找将实体提及映射到标准术语条目。

## 概述

`precise_match` 子模块实现了 Phase 3 的第一层匹配策略。它通过 `StandardizationRepository` 查询术语别名表，对返回的候选按实体类型和别名类型进行确定性排序，产出 `STANDARDIZED`、`AMBIGUOUS` 或 `UNMAPPED` 三种结果之一。

### 关键特性

- **别名类型优先级**：`primary` > `alias` > `previous_symbol` > `name` > `rsid`
- **源库排序**：基因按 HGNC 优先、变异按 ClinVar 优先、疾病按 OMIM > ClinGen 优先
- **HGVS 别名展开**：变异匹配时将一个 HGVS 表达式展开为多个别名形式（三字母→单字母、`p.R243X` → `p.R243*`）
- **基因上下文过滤**：变异匹配利用候选基因符号消歧 ClinVar 多基因命中的变异
- **确定性平局打破**：多个等优先级候选时取 `entry_id` 最小值

## 目录结构

```
precise_match/
├── __init__.py     # 导出 PreciseTerminologyMatcher
└── core.py         # 精确匹配实现
```

## 核心组件

### PreciseTerminologyMatcher（`core.py`）

主匹配类，依赖 `StandardizationRepository` 进行数据库查询。

**公共方法：**
- `match(candidate)` — 匹配单个 `StandardizationCandidate`，返回 `EntityMatch`

**内部流程：**
1. `_match_variant()` — 变异专用：展开 HGVS 别名 → 批量查询 → 合并去重 → 基因上下文过滤
2. `_finalize()` — 通用：排序候选 → 判定结果状态
3. `_rank()` — 按实体类型选择排序策略（基因→HGNC 优先，变异→ClinVar 优先，疾病→OMIM 优先）
4. `_apply_alias_type_priority()` — 仅保留最高优先级别名类型的候选
5. `_filter_variant_candidates_by_gene_context()` — 利用基因符号上下文过滤变异候选
6. `_pick_deterministic_winner()` — 平局时取 `entry_id` 最小值

### 别名类型优先级（`ALIAS_TYPE_PRIORITY`）

```python
{"primary": 0, "alias": 1, "previous_symbol": 2, "name": 3, "rsid": 4}
```

## 数据流

```
StandardizationCandidate
        │
        ├─ 基因/疾病/表型 → repository.find_candidates()
        │
        └─ 变异 → expand_hgvs_aliases() → repository.find_variant_candidates()
        │
        ▼
   _rank() → 按实体类型排序（源库优先级）
        │
        ▼
   _apply_alias_type_priority() → 过滤低优先级别名
        │
        ▼
   _filter_variant_candidates_by_gene_context() → 基因消歧
        │
        ▼
   _finalize() → EntityMatch (STANDARDIZED / AMBIGUOUS / UNMAPPED)
```

## 使用方式

```python
from src.core.standardize_entities_and_align_knowledge.precise_match import PreciseTerminologyMatcher

matcher = PreciseTerminologyMatcher(repository=standardization_repo)
result = await matcher.match(candidate)

if result.status == MatchStatus.STANDARDIZED:
    print(f"Matched: {result.external_id} ({result.display_name})")
```
