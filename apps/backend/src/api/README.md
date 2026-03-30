# src/api 说明（代码对齐版）

`src/api` 负责 HTTP/WebSocket 接口契约与错误响应封装。

## 目录结构

```text
api/
├── dependencies.py
└── routes/
    ├── core.py
    ├── task.py
    ├── evidence.py
    └── stream.py
```

## 路由组织

全局前缀来自 `main.py`：`app.include_router(..., prefix=cfg.api_prefix)`。
当前默认 `cfg.api_prefix=/api`。

### `routes/core.py`

- `GET /health`
- `GET /pdf/check_hash`
- `POST /pdf/upload`
- `GET /results/{document_id}/{object_path:path}`
- `GET /logs/reissue`

### `routes/task.py`（router prefix: `/tasks`）

- `POST /interaction/start`
- `POST /interaction/respond`
- `POST /requests/pubmed/candidates`
- `POST /requests/pubmed/submit`
- `POST /requests/web/crawl`
- `POST /requests/upload`
- `GET /requests/{request_id}`
- `POST /papers/{paper_task_id}/resume`
- `GET /{task_id}`

### `routes/evidence.py`（router prefix: `/evidence`）

包含检索、关联分析、聚合、质量与图同步接口，例如：

- `POST /search`
- `GET /search/gene/{gene_symbol}`
- `GET /search/variant/{variant:path}`
- `POST /aggregate`
- `GET /quality`
- `POST /sync/document/{document_id}`

### `routes/stream.py`（router prefix: `/stream`）

- `WS /{task_id}`
- `WS /requests/{request_id}`

## `dependencies.py` 作用

- 标准化错误码映射
- 构造失败响应契约
- 生成日志链接 `log_link`
