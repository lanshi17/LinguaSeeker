# src/api 说明（代码对齐版）

`src/api` 负责 HTTP / WebSocket 接口契约、错误响应封装，以及对外暴露的 `/api/v1` 路由面。

## 路由挂载

全局前缀来自 `main.py`，当前挂载方式为：

- `app.include_router(api_routers, prefix=cfg.api_prefix)`
- `app.include_router(task_api_routers, prefix=cfg.api_prefix)`
- `app.include_router(evidence_api_routers, prefix=cfg.api_prefix)`
- `app.include_router(stream_api_routers, prefix=cfg.api_prefix)`

当前默认前缀是 `cfg.api_prefix = /api/v1`。

## 路由组织

```text
api/
├── dependencies.py
└── routes/
    ├── core.py
    ├── task.py
    ├── evidence.py
    └── stream.py
```

## 已挂载接口清单

### `routes/core.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 服务健康检查 |
| GET | `/api/v1/pdf/check_hash` | PDF hash 查询 |
| POST | `/api/v1/pdf/upload` | 单 PDF 上传 |
| GET | `/api/v1/results/{document_id}/{object_path}` | 结果对象访问 |
| GET | `/api/v1/logs/reissue` | 日志链接重签发 |

### `routes/task.py`（router prefix: `/tasks`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/tasks/interaction/start` | 启动任务澄清 |
| POST | `/api/v1/tasks/interaction/respond` | 响应澄清问题 |
| POST | `/api/v1/tasks/interaction/confirm` | 确认任务单并生成 `request_id` |
| POST | `/api/v1/tasks` | 直接创建 Celery 任务 |
| GET | `/api/v1/tasks` | 列出任务 |
| POST | `/api/v1/tasks/requests/pubmed/candidates` | PubMed 候选检索 |
| POST | `/api/v1/tasks/requests/pubmed/submit` | 提交选中的 PubMed 候选 |
| POST | `/api/v1/tasks/requests/web/crawl` | Web crawl 请求创建 |
| POST | `/api/v1/tasks/requests/upload` | 上传分支请求创建 |
| GET | `/api/v1/tasks/requests/{request_id}` | 请求级状态查询 |
| GET | `/api/v1/tasks/requests/{request_id}/source-stats` | 请求级来源统计 |
| POST | `/api/v1/tasks/papers/{paper_task_id}/resume` | 重新排队 paper task |
| GET | `/api/v1/tasks/papers/{paper_task_id}` | 读取 paper task 详情 |
| GET | `/api/v1/tasks/{task_id}` | 读取单个 Celery 任务状态 |

### `routes/evidence.py`（router prefix: `/evidence`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/evidence/search` | 多文档图谱检索 |
| GET | `/api/v1/evidence/search/gene/{gene_symbol}` | 按基因检索 |
| GET | `/api/v1/evidence/search/variant/{variant}` | 按变异检索 |
| GET | `/api/v1/evidence/document/{document_id}` | 文档证据读取 |
| GET | `/api/v1/evidence/association/gene/{gene_symbol}` | 基因关联分析 |
| GET | `/api/v1/evidence/association/variant/{variant}` | 变异关联分析 |
| GET | `/api/v1/evidence/co-occurrence/{gene_symbol}` | 共现矩阵 |
| GET | `/api/v1/evidence/evidence-chains/{gene_symbol}` | 证据链检测 |
| POST | `/api/v1/evidence/aggregate` | 聚合检索 |
| GET | `/api/v1/evidence/aggregate/gene/{gene_symbol}` | 按基因聚合 |
| GET | `/api/v1/evidence/aggregate/variant` | 按变异聚合 |
| GET | `/api/v1/evidence/quality` | 质量概览（当前返回移除语义） |
| GET | `/api/v1/evidence/graph/stats` | 图数据库统计 |
| POST | `/api/v1/evidence/sync/document/{document_id}` | 文档图谱重同步 |

### `routes/stream.py`（router prefix: `/stream`）

| 方法 | 路径 | 说明 |
|---|---|---|
| WS | `/api/v1/stream/{task_id}` | Celery 任务状态流 |
| WS | `/api/v1/stream/requests/{request_id}` | 请求级状态流 |

## 对齐说明

1. 当前公开前缀是 `/api/v1`，不是 `/api`。
2. 前端 request-centric 流程依赖的关键入口集中在 `/tasks/interaction/confirm`、`/tasks/requests/*`、`/evidence/*`、`/stream/requests/{request_id}`。
3. `routes/task.py` 同时保留直接 Celery 任务接口（`POST /api/v1/tasks`、`GET /api/v1/tasks`、`GET /api/v1/tasks/{task_id}`）与 request/paper 级接口。
4. README 以准确的挂载面为目标，不再描述未挂载或已过时的旧前缀。