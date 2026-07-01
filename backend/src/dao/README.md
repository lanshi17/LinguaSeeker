# DAO — 数据访问层

> 按存储后端组织的统一数据访问层，为管道各阶段提供 PostgreSQL、Redis、Neo4j、MinIO 的持久化和缓存抽象。

## 概述

`dao` 包是 Lingua Seeker 的持久化基础设施层，按存储后端划分为四个子包。当前实际实现包括 PostgreSQL（主存储）和 Redis（读缓存），Neo4j 和 MinIO 为预留占位。

### 存储后端状态

| 后端 | 状态 | 用途 |
|------|------|------|
| **PostgreSQL** | ✅ 完整实现 | ORM 模型、连接管理、术语/证据/审查/任务队列仓储 |
| **Redis** | ✅ 完整实现 | 异步读缓存，事务性失效 |
| **Neo4j** | 📌 占位 | 图数据库（预留） |
| **MinIO** | 📌 占位 | S3 兼容对象存储（预留） |

## 目录结构

```
dao/
├── __init__.py           # 包声明：子包说明
├── postgresql/           # PostgreSQL 主存储
│   ├── __init__.py       # 懒加载导出（避免 eager pgvector 依赖）
│   ├── connection.py     # 异步 SQLAlchemy 引擎和会话工厂
│   ├── contracts.py      # DAO 基础设施契约
│   ├── models.py         # SQLAlchemy ORM 模型（20+ 表）
│   ├── job_queue.py      # 持久化任务队列（SELECT FOR UPDATE SKIP LOCKED）
│   ├── literature_profile_repo.py  # 文献档案聚合仓储
│   ├── search_index_repo.py        # 前端搜索索引仓储
│   └── document_annotation_repo.py # 文档标注 CRUD
├── redis/                # Redis 读缓存
│   ├── __init__.py       # 懒加载导出
│   ├── connection.py     # 异步 Redis 客户端构建
│   └── cache_repo.py     # CacheRepository：JSON 缓存 + 事务性失效
├── neo4j/                # 图数据库（占位）
│   └── __init__.py
└── minio/                # 对象存储（占位）
    └── __init__.py
```

## 核心设计模式

### 懒加载导出
PostgreSQL 和 Redis 子包使用 `__getattr__` 实现懒加载，避免在未使用时触发 pgvector 或 redis.asyncio 的导入开销。

### 连接构建器模式
`connection.py` 提供纯构建函数（`build_async_engine`、`build_redis_client`），不管理单例生命周期——单例由 `src.api.wiring` 控制。

### 会话管理
PostgreSQL 使用 `async_sessionmaker` + `@asynccontextmanager` 的 `get_async_session()` 模式，由调用方控制事务边界。

## 关键模型（PostgreSQL）

| 模型 | 表名 | 用途 |
|------|------|------|
| `SourceDocument` | `source_documents` | 稳定的源文档根，跨处理运行 |
| `ProcessingRun` | `processing_runs` | 管道执行的可复现性边界 |
| `NormalizedEntity` | `normalized_entities` | 标准化和未映射实体的统一字典 |
| `RunEvidenceItem` | `run_evidence_items` | 单次运行产生的版本化证据项 |
| `CanonicalEvidenceItem` | `canonical_evidence_items` | 跨运行的当前最佳规范证据 |
| `EvidenceEntityBinding` | `evidence_entity_bindings` | 证据与实体的超边关系 |
| `TerminologyEntry` | `terminology_entries` | 从术语数据库导入的统一参考实体 |
| `TerminologyAlias` | `terminology_aliases` | 术语匹配的索引查找别名 |
| `TerminologyEmbedding` | `terminology_embeddings` | pgvector 语义嵌入 |
| `LiteratureProfile` | `literature_profiles` | 每文档聚合的证据概览 |
| `ReviewAuditEvent` | `review_audit_events` | 证据审查操作的审计追踪 |
| `ChatSession` / `ChatMessage` | `chat_sessions` / `chat_messages` | LLM 对话会话和消息 |
| `PipelineJob` | `pipeline_jobs` | 持久化任务队列 |
| `PipelineRunState` | `pipeline_run_states` | 管道编排器检查点 |
| `DocumentAnnotation` | `document_annotations` | 用户创建的文档标注 |

## 使用方式

```python
from src.dao.postgresql import build_async_engine, async_session_factory, get_async_session
from src.dao.postgresql.models import TerminologyEntry, CanonicalEvidenceItem
from src.dao.redis import CacheRepository, build_redis_client

# PostgreSQL
engine = build_async_engine(settings)
factory = async_session_factory(engine)
async with get_async_session(factory) as session:
    result = await session.execute(select(TerminologyEntry).limit(10))

# Redis
redis = build_redis_client(settings)
cache = CacheRepository(redis)
await cache.set("doc", "key", {"data": "value"})
```
