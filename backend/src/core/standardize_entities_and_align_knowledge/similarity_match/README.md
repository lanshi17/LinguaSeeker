# Similarity Match — 语义相似度匹配

> 通过 pgvector 嵌入检索和 rerank 评分，为精确匹配未命中的实体提及提供语义回退匹配。

## 概述

`similarity_match` 子模块实现了 Phase 3 的第二层匹配策略。当精确匹配返回 `UNMAPPED` 时，此模块通过嵌入模型将候选文本向量化，在 pgvector 索引中检索最近邻术语条目，再经 rerank 模型评分后选择最佳匹配。

### 关键特性

- **两阶段检索**：pgvector 余弦距离初筛 → rerank 模型精排
- **多 API 风格**：支持 `simple`（`/embed`）和 OpenAI 兼容（`/v1/embeddings`）两种嵌入端点
- **本地/远程回退**：`FallbackEmbeddingProvider` 和 `FallbackRerankProvider` 支持本地优先、远程回退策略
- **SAVEPOINT 事务**：向量查询失败不会中止外层事务
- **阈值过滤**：rerank 分数低于阈值或 margin 不足时返回 `UNMAPPED`

## 目录结构

```
similarity_match/
├── __init__.py       # 包声明
├── contracts.py      # 嵌入和 rerank 的类型化契约
├── core.py           # SimilarityTerminologyMatcher 主匹配逻辑
├── providers.py      # HTTP 嵌入和 rerank 提供者（含本地/远程回退）
├── indexer.py        # TerminologyEmbeddingIndexer：构建和持久化术语嵌入
└── repositories.py   # PgvectorTerminologyRepository：pgvector 向量检索
```

## 核心组件

### SimilarityTerminologyMatcher（`core.py`）

主匹配类，协调嵌入、检索和 rerank。

**配置（`SimilarityMatchConfig`）：**
- `embedding_model` — 嵌入模型名称
- `rerank_top_k` — 初筛返回的最大候选数
- `rerank_score_threshold` — rerank 分数最低阈值
- `min_rerank_margin` — 第一名与第二名的最小分差

**匹配流程：**
1. 嵌入候选文本 → 获取查询向量
2. pgvector 余弦检索 → 获取 top-k 最近邻
3. rerank 评分 → 精排候选
4. 阈值和 margin 检查 → 判定 `STANDARDIZED` 或 `UNMAPPED`

### EmbeddingHttpProvider / RerankHttpProvider（`providers.py`）

HTTP 客户端，支持：
- Round-robin API key 轮换
- `simple` / OpenAI 兼容两种 API 风格
- 嵌入和 rerank 批量请求

### FallbackEmbeddingProvider / FallbackRerankProvider（`providers.py`）

本地优先回退策略：先尝试本地服务，失败或未配置时回退到远程 HTTP 提供者。

### TerminologyEmbeddingIndexer（`indexer.py`）

构建术语嵌入索引：
1. 查询已导入的 `TerminologyEntry` 记录
2. 构建确定性嵌入文本（display_name + aliases + external_id + source_db）
3. 通过嵌入服务批量向量化
4. 清理过期嵌入 → 批量 upsert 新嵌入

### PgvectorTerminologyRepository（`repositories.py`）

pgvector 向量检索仓储：
- `find_nearest()` — 按余弦距离检索最近邻，使用 SAVEPOINT 保护事务
- 返回 `SimilarityCandidate` 列表（包含 `TerminologyCandidate` + 向量距离 + 嵌入文本）

## 数据流

```
StandardizationCandidate (UNMAPPED from precise match)
        │
        ▼
   EmbeddingHttpProvider.embed_texts() → 查询向量
        │
        ▼
   PgvectorTerminologyRepository.find_nearest() → top-k 最近邻
        │
        ▼
   RerankHttpProvider.rerank() → 精排评分
        │
        ▼
   阈值/margin 检查 → EntityMatch (STANDARDIZED / UNMAPPED)
```

## 使用方式

```python
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SimilarityTerminologyMatcher,
    SimilarityMatchConfig,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    FallbackEmbeddingProvider,
    FallbackRerankProvider,
)

config = SimilarityMatchConfig(
    embedding_model="text-embedding-3-small",
    rerank_top_k=10,
    rerank_score_threshold=0.5,
)

matcher = SimilarityTerminologyMatcher(
    embedding_provider=embedding_provider,
    rerank_provider=rerank_provider,
    repository=pgvector_repo,
    config=config,
)

result = await matcher.match(candidate)
```
