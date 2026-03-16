# Agent Mode Choice + Graph Console (MVP) — Design

## Goal
在 `/tasks/new` 的 agent 交互里，**先让 agent 询问用户**“解析文档 / 检索图谱”二选一；当用户选择“检索图谱”时，提供一个新的 `/graph` 入口页，用于对齐后端 OpenAPI 中暴露的图谱相关能力。

## Non-Goals
- 不做 Neo4j 图可视化（ForceGraph / D3）
- 不做复杂图谱检索 DSL / Cypher 编辑器
- 不做权限/鉴权改造

## Constraints / Source of Truth
- 以 `api_docs/openapi.json` 为准。
- 图谱相关接口（Evidence tag）：
  - `GET /evidence/graph/stats`：Neo4j 图数据库统计
  - `POST /evidence/sync/document/{document_id}`：将某文档证据重同步到 Neo4j
- 现有任务创建流程在 `/tasks/new`；agent 澄清最多 2 轮（已实现）。

## UX / Flow
### 1) `/tasks/new` 里 agent 首问（入口选择）
在 Clarification Chat transcript 顶部（消息列表为空时）展示一条 assistant bubble：

> 在开始之前，你想进行哪种工作？

并提供两枚 quick replies（chips）：
- **解析文档**（documents）
- **检索图谱**（graph）

行为：
- 用户点选后，将选择作为一条 user message 写入 transcript。
- 在未选择入口前，Start 按钮不可用（确保“agent 先询问”这一产品意图）。
- 选择 **检索图谱**：立即跳转到 `/graph`。
- 选择 **解析文档**：留在 `/tasks/new`，继续原有澄清/上传/检索流程。

### 2) 新增 `/graph` 页面（Graph Console — MVP）
页面分区：
1. **Graph Stats**
   - 刷新按钮：调用 `GET /evidence/graph/stats`
   - 将响应（`EvidenceSearchResponse`：`code/message/data`）以 JSON 形式展示
2. **Resync Document**
   - 输入 `document_id`（uuid）
   - “Resync” 按钮：调用 `POST /evidence/sync/document/{document_id}`
   - 将响应 JSON 或错误提示展示

说明：该页以“后端能力可用性 + 最小可操作入口”为优先，不依赖前端图渲染。

## Data / State
- Zustand `useTaskFlowStore` 增加 `entryMode: 'documents' | 'graph' | null`，用于控制首问是否完成，并在 Restart 时清空。
- Graph Console 页内部用本地 `useState` 管理 `loading/stats/resyncResponse/error`。

## Error Handling
- API 层沿用 `ApiError`（`detail` 优先）
- `/graph` 页面错误以 Toast + inline error 文本展示
- chat 中错误写入 transcript（role=error），并 Toast

## Verification
- `npm run lint`
- `npx tsc --noEmit`
- `npm run build`
- 手动：
  - `/tasks/new` 首次进入必须先选入口
  - 选择“检索图谱”可跳转 `/graph`
  - `/graph` 的 stats/resync 按钮能发起请求、展示 JSON 或显示错误
