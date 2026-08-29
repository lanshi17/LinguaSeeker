# App

> FastAPI 应用入口——创建应用实例、管理生命周期、注册中间件和路由。

## Overview

`app/` 包含 FastAPI 应用的创建和生命周期管理。`main.py` 是整个后端的入口点，负责初始化所有基础设施（PostgreSQL、Redis、管线编排器）、注册中间件（安全头、请求体大小限制、请求监控、限流）和挂载 API 路由。

## Structure

```
app/
├── main.py            # FastAPI 应用创建和生命周期管理
├── main.py.jinja      # Jinja2 模板版本（用于项目脚手架）
├── __init__.py
└── README.md
```

## Key Components

### `create_app()`

构建并配置 FastAPI 实例：

1. 加载配置（`get_config()`）
2. 注册安全中间件（`SecurityHeadersMiddlewareHSTS` / `SecurityHeadersMiddleware`）
3. 注册请求体大小限制中间件（`BodySizeLimitMiddleware`）
4. 注册请求监控中间件（`RequestMonitorMiddleware`）
5. 初始化限流器（`init_limiter()`）
6. 挂载 V1 API 路由（`v1_router`）
7. 配置 CORS
8. 注册全局异常处理器

### `lifespan()`

应用生命周期管理（启动和关闭）：

**启动阶段：**
- 清除系统代理环境变量（避免干扰应用层代理路由）
- 初始化日志系统（`setup_logging()`）
- 调用 `wire_dependencies()` 组装完整服务依赖图
- 启动作业调度器（`SingleJobDispatcher.start()`）
- 创建独立表（`frontend_search_index`）——使用 PostgreSQL advisory lock 防止多 worker 竞争
- 恢复被中断的管线运行（`recover_orphaned_runs()`）
- 执行基础设施连接健康检查（`check_all_connections()`）

**关闭阶段：**
- 停止作业调度器（`dispatcher.stop()`）
- 等待活跃管线任务完成（`runner.shutdown()`）
- 关闭 Phase5ServiceFactory 资源
- 释放 Redis 和 PostgreSQL 连接池

### 错误处理

全局异常处理器统一返回结构化错误响应：

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "...",
    "details": [...]
  },
  "request_id": "uuid"
}
```

每个响应携带 `X-Request-ID` 头，错误时同时包含在响应体中。

### 模块级实例

```python
app: FastAPI = create_app()  # uvicorn app.main:app 入口
```

## Usage / Patterns

### 启动服务

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 测试中使用

```python
from app.main import create_app
app = create_app()  # 程序化创建，测试和自定义入口使用
```

## Dependencies

| 依赖 | 用途 |
|------|------|
| FastAPI | Web 框架 |
| uvicorn | ASGI 服务器 |
| `src.api.wiring` | 依赖注入和服务组装 |
| `src.api.v1.router` | V1 API 路由 |
| `src.utils.*` | 中间件、日志、健康检查 |
| `src.agents.*` | 管线运行器和作业调度器 |
