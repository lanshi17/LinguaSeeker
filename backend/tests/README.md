# Tests

> 后端测试套件——单元测试、集成测试、基准测试和端到端脚本测试。

## Overview

`tests/` 包含 Lingua Seeker 后端的完整测试套件。使用 pytest + pytest-asyncio，单元测试使用 SQLite 内存数据库（快速、无外部依赖），集成测试使用 PostgreSQL 测试数据库。

## Structure

```
tests/
├── conftest.py                      # 共享测试夹具（SQLite/PG 会话、清理）
├── test_download_phase.py           # 下载阶段测试
├── test_health.py                   # 健康检查测试
├── test_startup_lock.py             # 启动 advisory lock 测试

├── agents/                          # 管线编排器测试
│   ├── test_state_persistence_layer.py
│   ├── test_phase2_retry.py
│   ├── test_phase_2_adapter.py
│   ├── test_processing_cache.py
│   ├── test_state_transition_guard.py
│   ├── test_concurrency.py
│   ├── test_contracts.py
│   ├── test_integration.py
│   ├── test_job_queue.py
│   └── ...
├── api/                             # API 路由测试
│   ├── conftest.py                  #   API 测试夹具（TestClient）
│   ├── test_pipeline_api.py
│   ├── test_annotations_api.py
│   ├── test_auth.py
│   ├── test_body_size_limit.py
│   ├── test_chat_api.py
│   ├── test_delta_audit_api.py
│   ├── test_wiring_config.py
│   └── ...
├── core/                            # 核心业务逻辑测试
│   ├── test_config.py
│   ├── test_config_loader.py
│   ├── test_contracts.py
│   ├── test_database_config.py
│   ├── test_formatter.py
│   ├── test_grounding.py
│   ├── test_search_service.py
│   ├── test_parse_document_config.py
│   ├── cross_lingual_process_and_extract_evidence/  # Phase 2 子模块测试
│   └── standardize_entities_and_align_knowledge/    # Phase 3 子模块测试
├── benchmark/                       # 基准和评估测试
│   ├── test_build_unified_dataset.py
│   ├── test_case_studies.py
│   ├── test_diagnose_grounding.py
│   ├── test_field_normalize.py
│   ├── test_gold_standard_filter.py
│   ├── test_statistical_significance.py
│   └── ...
├── dao/                             # 数据访问层测试
│   ├── postgresql/
│   ├── redis/
│   └── test_chat_message_fk.py
├── integration/                     # 集成测试
│   ├── test_app_startup.py
│   └── test_literature_profile_e2e.py
├── scripts/                         # 端到端脚本测试
│   ├── test_e2e_extract_evidence.py
│   └── test_e2e_standardize_entities.py
├── services/                        # 服务层测试（预留）
├── utils/                           # 工具函数测试
│   ├── test_exceptions.py
│   ├── test_health.py
│   ├── test_logger.py
│   ├── test_middleware.py
│   ├── test_observability.py
│   └── test_text.py
└── output/                          # 测试输出目录（git-ignored）
```

## Key Components

### `conftest.py` — 共享夹具

| 夹具 | 说明 |
|------|------|
| `db_session` | SQLite 内存数据库会话（每个测试独立创建和销毁） |
| `postgresql_db_session` | PostgreSQL 测试数据库会话（需要预创建 `lingua_seeker_test` 数据库） |
| `_cleanup_test_artifacts` | 会话级自动清理 `data/pipeline/` 测试产物 |
| `event_loop` | pytest-asyncio 事件循环 |

SQLite 夹具自动将 `JSONB` 列替换为 `JSON` 类型，测试结束后恢复原始类型。

### 测试分类

| 目录 | 类型 | 外部依赖 |
|------|------|----------|
| `agents/` | 管线编排器测试 | SQLite（内存） |
| `api/` | API 路由测试 | SQLite + TestClient |
| `core/` | 核心业务逻辑测试 | 视具体模块 |
| `utils/` | 工具函数测试 | 无 |
| `dao/` | 数据访问层测试 | SQLite/PostgreSQL |
| `integration/` | 集成测试 | PostgreSQL |
| `benchmark/` | 基准/评估测试 | 视具体测试 |
| `scripts/` | 脚本端到端测试 | PostgreSQL + 外部服务 |

## Usage / Patterns

### 运行全部测试

```bash
cd backend
uv run pytest tests/ -v
```

### 运行特定目录

```bash
uv run pytest tests/agents/ -v
uv run pytest tests/api/ -v
uv run pytest tests/utils/ -v
```

### 运行集成测试

```bash
# 需要运行中的 PostgreSQL
uv run pytest tests/integration/ -v
```

### 跳过需要外部服务的测试

```bash
uv run pytest tests/ -v -m "not integration"
```

### 运行基准测试

```bash
uv run pytest tests/benchmark/ -v
```

## Dependencies

| 依赖 | 用途 |
|------|------|
| pytest | 测试框架 |
| pytest-asyncio | 异步测试支持 |
| aiosqlite | SQLite 异步驱动（单元测试） |
| httpx | HTTP 测试客户端 |
| SQLAlchemy | 测试数据库管理 |
