# 前端 API 状态总结

## 当前状态

### ✅ 当前前端路由与后端挂载面一致

前端当前围绕以下稳定入口工作：

- `/tasks/new`：任务澄清、确认、分支选择
- `/tasks/pubmed/candidates`：PubMed 候选检索与选择
- `/requests/:requestId`：请求级监控
- `/documents/:documentId`：文档证据查看
- `/graph`：图谱检索、统计与文档重同步

### ✅ 当前前端依赖的 API 路径

| 功能 | 前端调用路径 | 状态 |
|---|---|---|
| 任务澄清开始 | `/api/v1/tasks/interaction/start` | ✅ 已对齐 |
| 任务澄清续问 | `/api/v1/tasks/interaction/respond` | ✅ 已对齐 |
| 任务单确认 | `/api/v1/tasks/interaction/confirm` | ✅ 已对齐 |
| 上传分支提交 | `/api/v1/tasks/requests/upload` | ✅ 已对齐 |
| PubMed 候选检索 | `/api/v1/tasks/requests/pubmed/candidates` | ✅ 已对齐 |
| PubMed 候选提交 | `/api/v1/tasks/requests/pubmed/submit` | ✅ 已对齐 |
| Web crawl 分支提交 | `/api/v1/tasks/requests/web/crawl` | ✅ 已对齐 |
| 请求状态 | `/api/v1/tasks/requests/{request_id}` | ✅ 已对齐 |
| 请求来源统计 | `/api/v1/tasks/requests/{request_id}/source-stats` | ✅ 已对齐 |
| Paper task 详情 | `/api/v1/tasks/papers/{paper_task_id}` | ✅ 已对齐 |
| 请求流式状态 | `/api/v1/stream/requests/{request_id}` | ✅ 已对齐 |
| 文档证据 | `/api/v1/evidence/document/{document_id}` | ✅ 已对齐 |
| 图谱搜索 | `/api/v1/evidence/search` | ✅ 已对齐 |
| 图谱统计 | `/api/v1/evidence/graph/stats` | ✅ 已对齐 |
| 文档图谱重同步 | `/api/v1/evidence/sync/document/{document_id}` | ✅ 已对齐 |

## 已移除的旧路径说明

以下历史描述不再应被当作当前前端主路径：

- 旧分析页路由
- 旧任务状态页路由
- 旧文档页重定向说明
- 旧 PDF PMID/DOI 获取接口说明

这些历史描述如果继续保留，会与当前 request-centric 流程冲突。

## 当前判断

1. 前端主流程已经以 `request_id` 为中心，而不是 `task_id` 或旧分析页。
2. `/tasks/new` 是统一入口，并承担 upload / PubMed / web crawl 三路分支。
3. `/graph` 对应的是 evidence API，而不是仅用于只读统计控制台。
4. 文档应统一描述 `/api/v1` 前缀下的当前挂载接口。