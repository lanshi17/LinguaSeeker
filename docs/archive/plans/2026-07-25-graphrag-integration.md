# GraphRAG 集成方案

日期：2026-07-25
状态：已完成
作者：AI Agent（feature/graphrag）

---

## 1. 目标

在 LinguaSeeker 的证据抽取流程中集成 GraphRAG：

1. **抽取增强**：在 Phase 2 证据抽取的 `broad` 模式下，于 `relevance_scan` 之后注入来自 Neo4j 知识图谱的上下文，降低幻觉并提升召回。
2. **知识图谱构建**：在 Phase 3 实体标准化完成后，将标准化实体、证据链与特殊证据写入 Neo4j。
3. **问答与可视化**：提供 `/graphrag` 页面与后端 API，支持自然语言问答和交互式知识图谱浏览。

---

## 2. 关键决策

- **图数据库**：Neo4j 5.x + `neo4j` Python 异步驱动。
- **前端可视化**：`@antv/g6`（专项图渲染库，非通用 UI 组件库）。
- **Feature Flag**：`graph_rag.enabled` 默认 `false`，需手动开启并确保 Neo4j 已灌入数据。
- **数据来源**：
  - 术语基线：复用 `terminology_relationships`。
  - 文献实例：`EvidenceChain` 三元组、`A.gene_disease_relationship`、`B.clinical_phenotypes`/`B.hpo_terms`、`SpecialEvidenceRecord.contradiction`。

---

## 3. 架构变更

### 3.1 后端

```
backend/src/core/graph_rag/
├── contracts.py                  # 领域契约 + API 响应模型
├── api.py                        # GraphRagService 公共接口
├── providers.py                  # Neo4jGraphProvider
└── core/
    ├── builder.py                # EvidenceGraphBuilder
    ├── retrieval.py              # SubgraphRetriever
    ├── context_formatter.py      # ContextFormatter
    └── qa_engine.py              # GraphRagQaEngine

backend/src/dao/neo4j/
├── connection.py                 # build_neo4j_driver
├── contracts.py                  # GraphNode / GraphEdge / SubgraphContext
└── repository.py                 # Neo4jRepository

backend/src/core/evidence_extraction/
├── config_context.py             # graph_rag_enabled / hops / mode
├── contracts.py                  # EvidenceExtractionState.graph_context
├── workflow.py                   # 插入 graph_context_retrieval 节点
├── stages/graph_context_retrieval.py
├── stages/primary_broad_extraction.py  # 接收 graph_context
├── stages/catalog_extraction.py        # 接收 graph_context
└── prompts/catalog.py            # 可选 graph_context 块

backend/src/api/v1/graph_rag.py   # POST /query, GET /graph
backend/src/api/v1/router.py      # 注册 /graphrag 路由
backend/src/api/wiring.py         # 注入 GraphRagService
backend/src/core/config.py        # GraphRagConfig + 扁平字段
```

### 3.2 前端

```
frontend/src/features/graphrag/
├── types/graphRag.ts
├── services/graphRag.ts
├── hooks/useGraphRagQuery.ts
├── hooks/useKnowledgeGraph.ts
├── components/GraphRagView.tsx
└── components/KnowledgeGraphCanvas.tsx

frontend/src/pages/GraphRagPage.tsx
frontend/src/App.tsx              # /graphrag 路由
frontend/src/components/layout/Sidebar.tsx  # 导航入口
frontend/src/lib/i18n/locales/*   # graphRag.* 翻译键
```

### 3.3 部署与脚本

```
deploy/compose/*/docker-compose.yml  # Neo4j 服务
scripts/seed_neo4j_terminology.py    # 术语基线导入
scripts/backfill_neo4j_literature.py # 历史文献回灌
```

---

## 4. 配置

`backend/config/defaults/main.yaml`：

```yaml
graph_rag:
  enabled: false
  hops: 2
  mode: "full"  # "terminology_only" 或 "full"
```

环境变量覆盖：`GRAPHRAG_ENABLED`、`GRAPHRAG_HOPS`、`GRAPHRAG_MODE`。

---

## 5. 工作流拓扑

`broad` 模式：

```
relevance_scan
    |
    v
graph_context_retrieval  (新增，feature flag 控制)
    |
    v
primary_broad_extraction
    |
    v
language_metadata -> group_assignment -> role_routing -> review_validation -> ...
```

`catalog` 模式同样会接收 `graph_context`，通过 `catalog_extraction` 注入 prompt。

---

## 6. API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/graphrag/query` | 自然语言问答 |
| GET | `/api/v1/graphrag/graph` | 按基因/疾病/变异/表型返回子图 |

---

## 7. 测试

后端：

- `backend/tests/dao/neo4j/test_repository.py`
- `backend/tests/core/graph_rag/test_builder.py`
- `backend/tests/core/graph_rag/test_retrieval.py`
- `backend/tests/core/graph_rag/test_qa_engine.py`

前端：

- `frontend/tests/features/graphrag/GraphRagView.test.tsx`
- `frontend/tests/pages/GraphRagPage.test.tsx`

---

## 8. 后续工作

- 在 staging 环境运行 `scripts/seed_neo4j_terminology.py` 与 `scripts/backfill_neo4j_literature.py`。
- 评估开启 `graph_rag.enabled=true` 后的抽取质量差异。
- 根据反馈优化 prompt 中的 graph context 格式与长度控制。
