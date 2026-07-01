# database/

> 数据库基础设施层：PostgreSQL 模式迁移、容器配置、种子数据、参考术语和备份。

## 概述

本目录管理 Lingua Seeker 的数据库基础设施，包括 Alembic 异步迁移系统、PostgreSQL/Redis/Qdrant/Neo4j 的容器环境配置、以及生物医学参考术语数据。数据库配置通过 `backend/src/core/config.py` 的 pydantic-settings 加载，迁移脚本使用 SQLAlchemy 2.0 异步引擎。

## 目录结构

```
database/
├── alembic.ini                        Alembic 启动配置（script_location、日志、文件模板）
├── alembic.ini.jinja                  alembic.ini 的 Jinja2 模板
├── config/
│   ├── .env                           容器环境变量（PostgreSQL、Redis、Neo4j、Qdrant）
│   ├── .env.example                   带内联文档的完整模板
│   ├── .env.example.jinja             .env.example 的 Jinja2 模板
│   ├── .env.neo4j                     Neo4j 认证字符串
│   ├── containers.conf                Podman 运行时配置：代理绕过、cgroup v2、子网保留
│   └── qdrant_config.json             Qdrant TLS 配置（默认禁用）
├── migrations/
│   ├── env.py                         异步迁移环境（离线/在线模式，导入 Base.metadata）
│   ├── env.py.jinja                   env.py 的 Jinja 模板
│   ├── script.py.mako                 新迁移脚本的 Mako 模板
│   └── versions/                      23 个迁移文件（从 init schema 到 document annotations）
├── seeds/
│   └── .gitkeep                       种子数据占位符
└── terminology_database/              生物医学参考数据（详见 terminology_database/README.md）
```

## 核心组件

### Alembic 迁移系统

- **异步引擎**：使用 `create_async_engine` 配合 `asyncpg` 驱动和 `NullPool`
- **Schema 感知**：迁移目标为可配置的 PostgreSQL schema（来自 `cfg.postgresql.schema_`），非 `public`
- **配置来源**：通过 `get_config()` 从 `backend/src/core/config.py` 读取数据库连接
- **离线模式**：生成 SQL 到 stdout，无需连接数据库，适合代码审查

### 迁移历史

共 23 个迁移文件，涵盖：

| 迁移 | 用途 |
|------|------|
| `init_mvp_schema` | 初始 MVP 模式（9 个核心表） |
| `add_terminology_reference_tables` | HGNC、OMIM、HPO、ClinVar、ClinGen、MONDO 参考表 |
| `add_terminology_embeddings_pgvector` | pgvector 术语嵌入 |
| `add_review_and_chat_tables` | 专家审查和 AI 聊天表 |
| `add_literature_profiles` | CQRS 读模型文献配置表 |
| `add_performance_indexes` | 搜索性能索引 |
| `add_pipeline_run_leases` | 流水线运行租约/锁机制 |
| `add_critical_indexes` | 热路径性能索引（P0/P1/P2 优先级） |
| `add_document_processing_cache` | L2 PostgreSQL 流水线结果缓存（JSONB） |
| `add_document_full_text` | 存储原文/译文全文 |
| `add_content_blocks` | 结构化内容块（JSONB） |
| `add_document_annotations` | 双语阅读器的段落级字符偏移注释 |

### 配置加载链

```
database/config/.env ──► podman-compose.yml（容器环境变量）
                         注入 PostgreSQL、Redis、Neo4j、Qdrant

backend/.env / .env.local ──► backend/src/core/config.py（pydantic-settings）
                              │
                              ├──► database/migrations/env.py（迁移时的 Alembic）
                              └──► backend/src/dao/postgresql/connection.py（运行时引擎）
```

## 使用方法

```bash
# 复制并自定义环境配置
cp database/config/.env.example database/config/.env

# 运行迁移（需要 PostgreSQL 运行中）
uv run alembic -c database/alembic.ini upgrade head

# 创建新的自动生成迁移
uv run alembic -c database/alembic.ini revision --autogenerate -m "add_foo_table"

# 离线模式生成 SQL（不连接数据库）
uv run alembic -c database/alembic.ini upgrade head --sql

# 查看当前版本
uv run alembic -c database/alembic.ini current
```

## 测试

```bash
cd backend
uv run pytest tests/dao/test_alembic_migration.py -v    # 迁移结构测试
uv run pytest tests/dao/test_models.py -v                # ORM 模型测试
uv run pytest tests/core/test_database_config.py -v      # DSN 配置测试
uv run pytest tests/dao/ -v                              # 完整 DAO 套件
```
