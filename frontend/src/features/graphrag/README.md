# GraphRAG 前端模块

> 基于 `@antv/g6` 的知识图谱可视化工作台。自然语言问答已整合进 Chat 特性。

## 快速开始

```tsx
import { GraphRagView } from "@/features/graphrag";

export function GraphRagPage() {
  return <GraphRagView />;
}
```

## 定位

`/graphrag`（导航名「知识图谱 / Knowledge Graph」）是「基因—疾病—变异」三元关系的
**可视化探索**工作台（`EntityGraphExplorer`）。首次进入无检索/深链参数时，默认展示一个
示例图谱（`EXAMPLE_GENE = EGFR`，携带完整「基因—疾病—变异」三元关系），工作台不会空白。
自然语言问答不再在此页重复：用户在 Chat 中提问，聊天编排器 (`chat` 特性)
会分发 `graph-qa` 动作，在对话内联渲染知识图谱的**有据回答 + 子图**。
Chat 的「在图谱中查看」深链会带 URL 参数跳转到本页（如 `/graphrag?gene=EGFR`）。

## 架构

```text
GraphRagPage
    │
    ▼
GraphRagView
    └── EntityGraphExplorer ──► useKnowledgeGraph ──► services/graphRag.fetchKnowledgeGraph()
             └── KnowledgeGraphCanvas ──► @antv/g6

Chat 特性（graph-qa 动作）
    └── queryGraphRag() ──► services/graphRag.queryGraphRag()
             └── ChatGraphResultCard ──► KnowledgeGraphCanvas
```

`EntityGraphExplorer` 支持从 URL 查询参数（`gene`/`disease`/`variant`/`phenotype`）
初始化，便于 Chat 深链直达。

## 公共 API

### 组件

| 组件 | 说明 |
|---|---|
| `GraphRagView` | 页面级容器，渲染实体探索工作台 |
| `EntityGraphExplorer` | 按实体浏览「基因—疾病—变异」证据三元关系 |
| `KnowledgeGraphCanvas` | `@antv/g6` 图渲染器（Chat 内联结果也复用） |

### Hooks

| Hook | 说明 |
|---|---|
| `useKnowledgeGraph` | 按实体查询子图 |

### Services

| 函数 | 说明 |
|---|---|
| `queryGraphRag` | `POST /api/v1/graphrag/query`（供 Chat 的 graph-qa 动作调用） |
| `fetchKnowledgeGraph` | `GET /api/v1/graphrag/graph` |

## 扩展指南

- 新增图节点样式：修改 `KnowledgeGraphCanvas.tsx` 中的 `NODE_THEMES`。
- 新增浏览实体维度：扩展 `EntityGraphExplorer` 表单与 `useKnowledgeGraph` 选项。
- 自定义布局：替换 `KnowledgeGraphCanvas` 中的 `layout.type`。

## 测试

```bash
bun run test tests/features/graphrag/ tests/pages/GraphRagPage.test.tsx
```
