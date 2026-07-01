# Src

> 后端核心源码——包含配置管理、业务逻辑、API 路由、数据访问和工具函数。

## Overview

`src/` 是 Lingua Seeker 后端的核心代码包，按职责分为 5 个子包：配置管理（`core/`）、管线编排（`agents/`）、HTTP API（`api/`）、数据访问（`dao/`）和通用工具（`utils/`）。

## Structure

```
src/
├── core/                # 核心业务逻辑和配置管理
│   ├── config.py                # Settings 单例（Pydantic Settings）
│   ├── config_loader.py         # 分层 YAML 配置加载（兼容性 shim）
│   ├── ingest_and_digitize_data/          # Phase 1: 文献采集和文档解析
│   ├── cross_lingual_process_and_extract_evidence/  # Phase 2: 翻译和证据提取
│   ├── standardize_entities_and_align_knowledge/    # Phase 3: 实体标准化
│   └── visualize_evidence_with_expert_in_loop/      # Phase 4: 专家审核反馈
├── agents/              # 管线编排和任务调度
│   ├── orchestrator.py          # LangGraph 管线编排器
│   ├── runner.py                # 后台管线运行器
│   ├── dispatcher.py            # 单任务作业调度器
│   ├── contracts.py             # 状态模型、错误层次、状态转换守卫
│   ├── state_persistence.py     # PostgreSQL 状态持久化
│   ├── processing_cache.py      # 两级缓存（L1 Redis + L2 PostgreSQL）
│   ├── content_hash.py          # 内容哈希去重
│   ├── concurrency.py           # 信号量和重试执行器
│   └── phase_*_adapter.py       # Phase 1-3 适配器
├── api/                 # HTTP API 层
│   ├── wiring.py                # 依赖注入和服务组装
│   ├── auth.py                  # API Key 和会话认证
│   ├── deps.py                  # FastAPI 依赖项
│   ├── body_size_limit.py       # 请求体大小限制中间件
│   ├── rate_limit.py            # Redis 限流
│   └── v1/                      # V1 API 路由
├── dao/                 # 数据访问层
│   ├── postgresql/              # SQLAlchemy ORM 和仓储
│   ├── redis/                   # Redis 缓存操作
│   ├── neo4j/                   # 图数据库（预留）
│   └── minio/                   # 对象存储（预留）
└── utils/               # 通用工具函数
    ├── logger.py                # 日志配置（loguru）
    ├── llm_adapter.py           # LLM 客户端适配器（密钥池轮转）
    ├── exceptions.py            # 统一异常层次
    ├── health.py                # 启动健康检查
    ├── middleware.py             # 请求监控中间件
    ├── security_headers.py      # 安全头中间件
    └── text.py                  # 文本处理工具
```

## Key Components

### 依赖关系图

```
app.main → src.api.wiring → src.agents.* → src.core.*
                ↓
           src.dao.* (PostgreSQL / Redis)
                ↓
           src.utils.* (日志、LLM 适配器、异常)
```

### 管线架构（Phase 1-4）

| Phase | 模块 | 职责 |
|-------|------|------|
| Phase 1 | `core/ingest_and_digitize_data/` | 文献采集 + MinerU 文档解析 |
| Phase 2 | `core/cross_lingual_process_and_extract_evidence/` | 跨语言翻译 + 双轨证据提取 |
| Phase 3 | `core/standardize_entities_and_align_knowledge/` | 实体标准化 + 术语知识对齐 |
| Phase 4 | `core/visualize_evidence_with_expert_in_loop/` | 专家审核、聊天、审计、溯源 |

Phase 1-3 由 `agents/orchestrator.py`（LangGraph）编排为有向图，Phase 4 是独立的请求-响应式交互服务。

## Usage / Patterns

### 获取配置

```python
from src.core.config import get_config
cfg = get_config()
```

### 导入异常

```python
from src.utils.exceptions import NotFoundException, ValidationException
```

### 创建 LLM 客户端

```python
from src.utils.llm_adapter import create_llm_client
client = create_llm_client(model="gpt-5", api_keys=["sk-1", "sk-2"], base_url="...")
```

## Dependencies

| 依赖 | 用途 |
|------|------|
| FastAPI | HTTP 框架 |
| SQLAlchemy 2.0 | 异步 ORM |
| LangGraph | 管线编排 |
| LangChain | LLM 客户端抽象 |
| loguru | 结构化日志 |
| Pydantic | 数据验证和 Settings |
