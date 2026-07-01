# Context Pack — 目标安全上下文包

> 从基准或运行时元数据构建无泄漏的目标上下文包，为证据验证和一致性检查提供安全的基因/疾病/遗传模式上下文。

## 概述

`context_pack` 子模块负责构建 **TargetContextPack**——一个不包含待提取信息的安全上下文对象。它用于：
- 基准测试中防止数据泄漏（benchmark target context）
- 运行时为证据提取提供目标基因、疾病和遗传模式的先验知识

上下文包从两个来源构建：
1. **ClinGen expected.json** — 基准测试场景的标准答案文件
2. **运行时元数据** — 生产环境中从 `ExtractionTarget` 构建

## 目录结构

```
context_pack/
├── __init__.py     # 导出 TargetContextPack、GeneContext、DiseaseContext 及构建函数
├── contracts.py    # 类型化数据契约
└── core.py         # 上下文包构建逻辑
```

## 核心组件

### 数据契约（`contracts.py`）

- **`GeneContext`** — 目标基因上下文：`symbol`、`hgnc_id`、`aliases`
- **`DiseaseContext`** — 目标疾病上下文：`label`、`mondo_id`、`aliases`、`ancestor_labels`
- **`TargetContextPack`** — 完整上下文包：`entry_id`、`gene`、`disease`、`moi`（遗传模式）、`source_pmid`、`source_pmc`

### 构建函数（`core.py`）

- **`build_context_pack_from_expected_json(path)`** — 从 ClinGen `expected.json` 构建无泄漏上下文包
- **`build_context_pack_from_runtime_target(target, pmid, pmc)`** — 从生产运行时 `ExtractionTarget` 构建上下文包

### 辅助功能

- **疾病别名扩展** — 通过缩写提取、括号展开、stopword 过滤生成疾病名称的同义词
- **MONDO 层级缓存** — 从本地 MONDO 缓存文件加载祖先标签，扩展疾病上下文
- **源文本感知** — 从 `source.md` 提取观察到的缩写和短语匹配，增强别名覆盖
- **防泄漏措施** — stopword 过滤、最小 token 长度检查、括号内容剥离

## 数据流

```
ClinGen expected.json / ExtractionTarget
        │
        ▼
   _disease_aliases() ──→ 基础别名（括号展开、缩写提取）
        │
        ▼
   _source_aware_disease_aliases() ──→ 源文本观察别名
        │
        ▼
   _source_observed_mondo_aliases() ──→ MONDO 层级祖先标签
        │
        ▼
   TargetContextPack (gene + disease + moi)
```

## 使用方式

```python
from src.core.standardize_entities_and_align_knowledge.context_pack import (
    build_context_pack_from_expected_json,
    build_context_pack_from_runtime_target,
    TargetContextPack,
)

# 基准测试：从 expected.json 构建
pack = build_context_pack_from_expected_json(Path("clingen/expected.json"))

# 生产运行时：从 ExtractionTarget 构建
pack = build_context_pack_from_runtime_target(
    target=extraction_target, source_pmid="12345678", source_pmc="PMC123456"
)
```
