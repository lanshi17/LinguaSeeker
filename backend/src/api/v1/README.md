# API V1

> V1 REST API 路由——管线编排、证据审核、聊天、标注、审计和溯源接口。

## Overview

`v1/` 包含 Lingua Seeker 后端 V1 版本的所有 REST API 路由。路由前缀为 `/api/v1`，通过 `router.py` 聚合后注册到主应用。每个路由模块对应一个业务域。

## Structure

```
v1/
├── router.py            # 路由聚合器（注册所有子路由到 /api/v1）
├── pipeline.py          # 管线编排路由（/api/v1/pipeline/*）
├── evidence.py          # 证据审核路由（/api/v1/evidence/*）
├── chat.py              # 聊天路由（/api/v1/chat/*）
├── annotations.py       # 文档标注 CRUD（/api/v1/documents/*）
├── delta_audit.py       # 审计事件查询（/api/v1/delta-audit/*）
├── source_link.py       # 证据溯源路由（/api/v1/source-link/*）
├── auth.py              # 会话认证路由（/api/v1/auth/*）
├── contracts.py         # Pydantic 请求/响应模型
└── __init__.py
```

## Key Components

### `router.py` — 路由聚合

```python
router = APIRouter(prefix="/api/v1")
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
router.include_router(delta_audit.router, prefix="/delta-audit", tags=["delta-audit"])
router.include_router(source_link.router, prefix="/source-link", tags=["source-link"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(annotations.router, prefix="/documents", tags=["annotations"])
```

### `pipeline.py` — 管线编排路由

| 端点 | 方法 | 说明 | 限流 |
|------|------|------|------|
| `/pipeline/run` | POST | 提交管线运行任务（入队到 job queue） | 10/分钟 |
| `/pipeline/runs` | GET | 列出所有运行摘要（分页） | — |
| `/pipeline/runs/{id}/status` | GET | 查询运行状态和各阶段详情 | — |
| `/pipeline/runs/{id}/state` | GET | 获取完整管线状态 | — |
| `/pipeline/runs/{id}/cancel` | POST | 取消运行中的管线 | 5/分钟 |
| `/pipeline/runs/{id}/rerun` | POST | 重跑指定阶段 | 5/分钟 |

支持 `PipelineRunRequest` 配置：文档来源（本地文件/在线标识符）、运行模式（全流程/单阶段）、提取目标、文献类型等。

### `evidence.py` — 证据审核路由

| 端点 | 方法 | 说明 |
|------|------|------|
| `/evidence/groups/detail` | GET | 分组证据详情（含分布和溯源） |
| `/evidence/{id}` | PATCH | 更新证据卡片并记录审计事件 |
| `/evidence/search` | GET | 证据搜索（字段级透视和分页） |
| `/evidence/literature/search` | GET | 文献档案搜索（按文章聚合） |
| `/evidence/literature/{id}` | GET | 文献档案详情 |
| `/evidence/literature/refresh` | POST | 刷新所有文献档案（管理员） |

### `chat.py` — 聊天路由

| 端点 | 方法 | 说明 |
|------|------|------|
| `/chat/sessions` | POST | 创建聊天会话 |
| `/chat/sessions/{id}` | GET | 列出处理运行的所有会话 |
| `/chat/sessions/{id}/messages` | GET | 列出会话消息 |
| `/chat/sessions/{id}/messages` | POST | 追加消息（支持自动回复） |
| `/chat/sessions/{id}/stream` | GET | SSE 流式 AI 回复（15 秒心跳） |
| `/chat/files/parse` | POST | 解析上传的 PDF（聊天上下文） |

### `annotations.py` — 文档标注 CRUD

| 端点 | 方法 | 说明 |
|------|------|------|
| `/documents/{id}/annotations` | GET | 列出文档标注（可按 track 过滤） |
| `/documents/{id}/annotations` | POST | 创建标注 |
| `/documents/{id}/annotations/{id}` | PATCH | 更新标注（颜色、备注） |
| `/documents/{id}/annotations/{id}` | DELETE | 删除标注 |
| `/documents/{id}/images/{name}` | GET | 提供文档提取的图片 |

### `delta_audit.py` — 审计事件

| 端点 | 方法 | 说明 |
|------|------|------|
| `/delta-audit/` | GET | 列出审核审计事件（可按证据/文档/审核人过滤） |

### `source_link.py` — 证据溯源

| 端点 | 方法 | 说明 |
|------|------|------|
| `/source-link/{id}/bilingual` | GET | 双语溯源文本跨度 |
| `/source-link/{id}/{track}` | GET | 单轨道溯源（原文/译文） |

### `auth.py` — 会话认证

| 端点 | 方法 | 说明 |
|------|------|------|
| `/auth/login` | POST | 密码登录，设置签名会话 Cookie |
| `/auth/logout` | POST | 删除会话 Cookie |
| `/auth/me` | GET | 查询当前认证状态 |

### `contracts.py` — 请求/响应模型

核心 Pydantic 模型：

| 模型 | 用途 |
|------|------|
| `PipelineRunRequest` | 管线运行请求（文档来源、模式、提取目标） |
| `PipelineRunResponse` | 运行提交响应（run_id、status_url） |
| `PipelineStatusResponse` | 状态查询响应（含各阶段详情） |
| `PipelineRunListResponse` | 运行列表响应（分页） |
| `PhaseStatusResponse` | 单阶段状态详情 |
| `PhaseNodeResponse` | 细粒度子节点进度 |

## Usage / Patterns

### 认证

所有写操作和状态查询需要认证（API Key 或会话 Cookie）：

```bash
# API Key 方式
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/pipeline/runs

# 会话 Cookie 方式
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -d '{"password": "your-password"}'
curl -b cookies.txt http://localhost:8000/api/v1/pipeline/runs
```

### 提交管线运行

```bash
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"local_path": "/path/to/paper.pdf"}' \
  http://localhost:8000/api/v1/pipeline/run
```

### 查询状态

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/runs/{run_id}/status
```

## Dependencies

| 依赖 | 用途 |
|------|------|
| FastAPI | 路由和依赖注入 |
| `src.api.auth` | 认证依赖 |
| `src.api.deps` | 数据库会话和 Phase4 工厂 |
| `src.api.rate_limit` | 限流装饰器 |
| `src.agents.*` | 管线运行器和作业队列 |
| `src.dao.postgresql.*` | 数据库仓储 |
| `src.core.*` | 业务逻辑服务 |
