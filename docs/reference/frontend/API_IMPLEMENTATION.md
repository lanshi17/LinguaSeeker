# 前端路由与 API 对齐说明

## 概述

当前前端采用以 `request_id` 为中心的用户流程：`/tasks/new` 负责任务澄清与分支选择，进入分支后统一回到 `/requests/:requestId` 监控请求级状态，再按需要跳转到 `/documents/:documentId` 查看文档证据；`/graph` 独立承担图谱检索、统计与重同步控制。

## 当前前端路由

| 路由 | 作用 | 主要后端依赖 |
|---|---|---|
| `/` | 重定向到任务创建入口 | 无 |
| `/tasks/new` | 任务澄清、任务单确认、上传/PubMed/Web crawl 三分支选择 | `POST /api/v1/tasks/interaction/start` `POST /api/v1/tasks/interaction/respond` `POST /api/v1/tasks/interaction/confirm` `POST /api/v1/tasks/requests/upload` `POST /api/v1/tasks/requests/web/crawl` |
| `/tasks/pubmed/candidates` | 基于已确认 request 进行 PubMed 候选检索与提交 | `POST /api/v1/tasks/requests/pubmed/candidates` `POST /api/v1/tasks/requests/pubmed/submit` |
| `/requests/:requestId` | 请求级监控页，展示请求状态、论文任务状态与跳转入口 | `GET /api/v1/tasks/requests/{request_id}` `GET /api/v1/tasks/requests/{request_id}/source-stats` `WS /api/v1/stream/requests/{request_id}` |
| `/requests/:requestId/export` | 请求结果导出页 | `GET /api/v1/tasks/requests/{request_id}` `GET /api/v1/tasks/papers/{paper_task_id}` |
| `/documents/:documentId` | 文档证据查看页，展示原文、译文、PS3/BS3 证据与图谱片段 | `GET /api/v1/evidence/document/{document_id}` |
| `/graph` | 图谱检索与控制页，保留 stats/resync 面板并新增搜索入口 | `POST /api/v1/evidence/search` `GET /api/v1/evidence/graph/stats` `POST /api/v1/evidence/sync/document/{document_id}` |

## 当前前端 API 类型与服务

前端当前维护的契约集中在：

- `TaskFormStructured`：澄清后的结构化任务单
- `ConfirmationContractResponse`：确认后返回 `request_id` 与可用分支
- `TaskRequestCreateResponse` / `TaskRequestStatusResponse`：请求级状态与论文任务摘要
- `WebLiteratureCrawlRequest`：Web crawl 分支提交 payload
- `GraphSearchRequest` / `EvidenceSearchResponse`：图谱检索请求与响应
- `DocumentEvidenceResponse`：文档证据页使用的数据载荷

服务层当前暴露的关键 helper：

- `confirmTaskForm()`
- `uploadTaskRequest()`
- `pubmedCandidateSearch()`
- `pubmedSelectionSubmit()`
- `webCrawlSubmit()`
- `getTaskRequestStatus()`
- `getPaperTaskDetail()`
- `getEvidenceDocument()`
- `searchEvidence()`
- `getEvidenceGraphStats()`
- `resyncEvidenceDocument()`

## 后端接口清单（前端当前依赖）

### 任务创建与请求监控

| 方法 | 路径 | 前端用途 |
|---|---|---|
| POST | `/api/v1/tasks/interaction/start` | 澄清对话开始 |
| POST | `/api/v1/tasks/interaction/respond` | 澄清对话续问 |
| POST | `/api/v1/tasks/interaction/confirm` | 任务单确认并生成 `request_id` |
| POST | `/api/v1/tasks/requests/upload` | 上传分支提交 |
| POST | `/api/v1/tasks/requests/pubmed/candidates` | PubMed 候选检索 |
| POST | `/api/v1/tasks/requests/pubmed/submit` | PubMed 候选提交 |
| POST | `/api/v1/tasks/requests/web/crawl` | Web crawl 分支提交 |
| GET | `/api/v1/tasks/requests/{request_id}` | 请求级状态查询 |
| GET | `/api/v1/tasks/requests/{request_id}/source-stats` | 请求级来源统计 |
| GET | `/api/v1/tasks/papers/{paper_task_id}` | 单篇 paper task 详情 |
| WS | `/api/v1/stream/requests/{request_id}` | 请求级实时状态流 |
| WS | `/api/v1/stream/{task_id}` | Celery 任务级实时状态流 |

### 证据与图谱

| 方法 | 路径 | 前端用途 |
|---|---|---|
| GET | `/api/v1/evidence/document/{document_id}` | 文档证据页 |
| POST | `/api/v1/evidence/search` | `/graph` 主搜索入口 |
| GET | `/api/v1/evidence/search/gene/{gene_symbol}` | 已挂载的按基因检索接口 |
| GET | `/api/v1/evidence/search/variant/{variant}` | 已挂载的按变异检索接口 |
| GET | `/api/v1/evidence/graph/stats` | `/graph` 统计面板 |
| POST | `/api/v1/evidence/sync/document/{document_id}` | `/graph` 文档重同步 |

## 当前规范结论

1. 当前用户入口是 `/tasks/new`，不是单独的上传页或分析页。
2. 上传、PubMed、Web crawl 是同一个确认后流程下的三条 intake 分支。
3. `request_id` 是前端的主导航锚点，`/requests/:requestId` 是统一监控页。
4. `document_id` 只在查看单文档证据时使用，对应 `/documents/:documentId`。
5. `/graph` 当前已经对齐到 evidence API：搜索、统计、文档重同步共存于一个页面。
6. 文档中应继续使用 `/api/v1` 作为后端前缀。