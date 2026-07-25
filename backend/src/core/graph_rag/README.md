# GraphRAG 模块

> 构建、查询和利用 Neo4j 知识图谱，增强证据抽取并提供自然语言问答能力。

## 快速开始

```python
from src.core.config import get_config
from src.dao.neo4j.connection import build_neo4j_driver
from src.dao.neo4j.repository import Neo4jRepository
from src.core.graph_rag.api import GraphRagService

cfg = get_config()
driver = build_neo4j_driver(cfg)
repo = Neo4jRepository(driver)
service = GraphRagService(repo)

# 为抽取目标检索图上下文
context = await service.retrieve_context_for_target(
    target=extraction_target, hops=2, mode="full"
)
```

## 架构

```text
EvidenceExtractionWorkflow
    │
    ▼
GraphContextRetrievalStage ──► GraphRagService.retrieve_context_for_target()
    │                              │
    ▼                              ▼
EvidenceExtractionState   SubgraphRetriever + ContextFormatter
                                   │
                                   ▼
                           Neo4jRepository.get_subgraph()

EntityStandardizationService.run()
    │
    ▼
GraphRagService.write_literature_graph()
    │
    ▼
EvidenceGraphBuilder ──► Neo4jGraphProvider ──► Neo4jRepository
```

## 公共 API

### `GraphRagService`

| 方法 | 签名 | 说明 |
|---|---|---|
| `retrieve_context_for_target` | `(target, hops=2, mode="full") -> str` | 为抽取目标返回格式化图上下文 |
| `write_literature_graph` | `(input_data, matches, dual_result) -> dict` | 将标准化结果写入 Neo4j |
| `write_standardization_graph` | `(input_data, matches) -> dict` | 仅写标准化实体 |
| `write_evidence_chains_graph` | `(doc_id, run_id, chains) -> dict` | 写证据链关系 |

### `GraphRagQaEngine`

| 方法 | 签名 | 说明 |
|---|---|---|
| `query` | `(question, hops=None, mode=None) -> GraphRagQueryResponse` | 自然语言问答 |

## 图模型

- **节点**：`:Gene`、`:Variant`、`:Disease`、`:Phenotype`、`:Evidence`、`:Document`、`:ProcessingRun`
- **关系**：`ASSOCIATED_WITH`、`HAS_DOSAGE_SENSITIVITY`、`HAS_CLINICAL_SIGNIFICANCE`、`IS_A`、`MENTIONS`、`SUPPORTS`、`CONTRADICTS`、`HAS_PHENOTYPE`、`FROM_DOCUMENT`、`FROM_RUN`

## 扩展指南

- 新增节点类型：在 `contracts.py` 添加 `GraphEntityType`，在 `builder.py` 添加构建逻辑。
- 新增检索模式：在 `SubgraphRetriever.retrieve_for_target()` 中添加过滤分支。
- 新增关系类型：在 `contracts.py` 添加 `GraphRelationType`，在 `providers.py` 确保 Cypher 安全。

## 测试

```bash
uv run pytest tests/core/graph_rag/ tests/dao/neo4j/ -v
```
