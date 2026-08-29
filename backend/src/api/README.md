# API

> HTTP API 层——依赖注入、认证、限流、中间件和路由注册。

## Overview

`api/` 是 Lingua Seeker 后端的 HTTP 接口层。负责应用级依赖组装（`wiring.py`）、请求认证（`auth.py`）、限流（`rate_limit.py`）、请求体大小限制（`body_size_limit.py`）和 V1 路由注册。所有路由定义在 `v1/` 子包中。

## Structure

```
api/
├── wiring.py              # 依赖注入和服务组装（应用启动时调用一次）
├── auth.py                # API Key + HMAC 会话认证
├── deps.py                # FastAPI 依赖项（数据库会话、Phase5ServiceFactory）
├── body_size_limit.py     # 请求体大小限制 ASGI 中间件
├── rate_limit.py          # Redis/内存限流器
├── v1/                    # V1 API 路由
│   ├── router.py          #   路由聚合器
│   ├── pipeline.py        #   管线编排路由
│   ├── evidence.py        #   证据审核路由
│   ├── chat.py            #   聊天路由
│   ├── annotations.py     #   文档标注 CRUD
│   ├── delta_audit.py     #   审计事件查询
│   ├── source_link.py     #   证据溯源路由
│   ├── auth.py            #   会话认证路由
│   └── contracts.py       #   Pydantic 请求/响应模型
└── __init__.py
```

## Key Components

### `wiring.py` — 依赖注入

`wire_dependencies()` 在应用启动时调用一次，组装完整服务依赖图：

```
cfg → engine → session_factory
  → Redis client → DocumentProcessingCacheService
  → DocumentAcquisitionService + ParseDocumentService
  → TranslationService + EvidenceExtractionService
  → EntityStandardizationService
  → Phase1Adapter + Phase2Adapter + Phase3Adapter
  → SessionBoundStatePersistence
  → PipelineOrchestrator → PipelineRunner
  → SingleJobDispatcher
  → Phase5ServiceFactory
  → JobQueueRepository
```

提供单例访问器：`get_engine()`、`get_session_factory()`、`get_redis_client()`、`get_local_parser()`、`get_dispatcher()`。

### `auth.py` — 认证

支持两种认证方式：

- **X-API-Key 头** — 直接与配置的 `api_key` 比较（HMAC 常量时间比较）
- **会话 Cookie** (`ce_session`) — HMAC-SHA256 签名的 JWT-like 令牌，8 小时有效期

```python
# 路由中使用
async def handler(_api_key: str | None = Depends(require_api_key)):
    ...
```

`require_api_key` 依赖项检查 API Key 或会话 Cookie，任一有效即可通过。

### `deps.py` — FastAPI 依赖项

| 依赖 | 说明 |
|------|------|
| `get_db_session()` | 提供异步数据库会话（自动 commit/rollback） |
| `get_phase5_factory()` | 返回全局 Phase5ServiceFactory 实例 |

### `body_size_limit.py` — 请求体限制

原始 ASGI 中间件（非 BaseHTTPMiddleware），避免缓冲流式响应：

- 检查 `Content-Length` 头（快速拒绝）
- 包装 `receive` 跟踪实际接收字节（处理 chunked 传输）
- 超限时返回 413 并排空剩余消息
- 默认限制 100MB

### `rate_limit.py` — 限流

基于 slowapi 的限流器：

- 生产环境使用 Redis 存储（跨 worker 共享）
- 本地开发自动降级为内存存储
- 模块级单例 `limiter`，`init_limiter()` 切换存储后端

```python
@router.post("/run")
@limiter.limit("10/minute")
async def handler(request: Request, ...):
    ...
```

## Usage / Patterns

### 应用启动流程

```python
# app/main.py lifespan
wire_dependencies()           # 组装依赖
dispatcher.start()            # 启动作业调度
check_all_connections()       # 健康检查
```

### 路由中访问数据库

```python
async def handler(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(Model))
```

### 路由中访问 Phase 4 服务

```python
async def handler(session: AsyncSession = Depends(get_db_session)):
    factory = get_phase5_factory()
    service = factory.create_feedback_service(session)
```

## Dependencies

| 依赖 | 用途 |
|------|------|
| FastAPI | 路由和依赖注入 |
| slowapi | 限流 |
| Starlette | ASGI 中间件 |
| SQLAlchemy | 数据库会话 |
| `src.agents.*` | 管线运行器、调度器、服务工厂 |
| `src.dao.*` | 数据访问 |
| `src.core.config` | 配置 |
