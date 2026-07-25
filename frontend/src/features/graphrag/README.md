# GraphRAG 前端模块

> 基于 `@antv/g6` 的知识图谱可视化与自然语言问答界面。

## 快速开始

```tsx
import { GraphRagView } from "@/features/graphrag";

export function GraphRagPage() {
  return <GraphRagView />;
}
```

## 架构

```text
GraphRagPage
    │
    ▼
GraphRagView
    ├── useGraphRagQuery ──► services/graphRag.queryGraphRag()
    └── KnowledgeGraphCanvas ──► @antv/g6
```

## 公共 API

### 组件

| 组件 | 说明 |
|---|---|
| `GraphRagView` | 问答输入、答案展示、子图可视化 |
| `KnowledgeGraphCanvas` | `@antv/g6` 图渲染器 |

### Hooks

| Hook | 说明 |
|---|---|
| `useGraphRagQuery` | 提交问题并获取回答 |
| `useKnowledgeGraph` | 按实体查询子图 |

### Services

| 函数 | 说明 |
|---|---|
| `queryGraphRag` | `POST /api/v1/graphrag/query` |
| `fetchKnowledgeGraph` | `GET /api/v1/graphrag/graph` |

## 扩展指南

- 新增图节点样式：修改 `KnowledgeGraphCanvas.tsx` 中的 `COLOR_MAP`。
- 新增问答参数：扩展 `GraphRagQueryRequest` 类型和 `GraphRagView` 表单。
- 自定义布局：替换 `KnowledgeGraphCanvas` 中的 `layout.type`。

## 测试

```bash
bun run test tests/features/graphrag/ tests/pages/GraphRagPage.test.tsx
```
