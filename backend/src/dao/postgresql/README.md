# PostgreSQL — 主存储数据访问层

> 基于 SQLAlchemy 异步引擎的 PostgreSQL 数据访问层，提供 ORM 模型、连接管理、任务队列和多种查询仓储。

## 概述

`postgresql` 子包是 Lingua Seeker 的主持久化层，管理从术语导入到证据审查的全生命周期数据。它使用 SQLAlchemy 2.0 异步 API + asyncpg 驱动，支持 pgvector 向量检索和 PostgreSQL app-schema 搜索路径。

### 关键特性

- **20+ ORM 模型**：覆盖源文档、处理运行、术语、证据、审查、对话、任务队列等全部实体
- **pgvector 集成**：术语嵌入的余弦距离检索，模块级注册 Vector 类型
- **持久化任务队列**：`SELECT FOR UPDATE SKIP LOCKED` 保证原子单领
- **前端搜索索引**：物化表 `frontend_search_index`，支持 GIN 索引的 JSONB 过滤
- **文献档案聚合**：per-document 证据分组、统计和审查状态管理
- **懒加载导出**：`__getattr__` 避免未使用时触发 pgvector 导入

## 目录结构

```
postgresql/
├── __init__.py                  # 懒加载导出（30+ 符号）
├── connection.py                # 异步引擎构建、会话工厂、pgvector 注册
├── contracts.py                 # DAO 基础设施契约（AsyncpgConnectArgs、CanonicalEvidencePayload 等）
├── models.py                    # SQLAlchemy ORM 模型定义
├── job_queue.py                 # JobQueueRepository：持久化任务队列
├── literature_profile_repo.py   # LiteratureProfileRepository：文献档案聚合
├── search_index_repo.py         # SearchIndexRepository：前端搜索索引
└── document_annotation_repo.py  # 文档标注 CRUD 函数
```

## 核心组件

### 连接管理（`connection.py`）

- **`build_async_engine(settings)`** — 从 Settings 构建异步 SQLAlchemy 引擎（连接池 + app-schema search_path）
- **`async_session_factory(engine)`** — 创建 `async_sessionmaker` 工厂
- **`get_async_session(factory)`** — 异步上下文管理器，控制事务边界
- **pgvector 注册** — 模块加载时注册 `Vector` 类型，支持原生 `<->`/`<=>` 操作符

### ORM 模型（`models.py`）

**核心实体：**
- `SourceDocument` — 源文档根，含 PMCID、PMC 本地路径、标题等
- `SourceDocumentIdentifier` — 外部标识符注册表（PMID/DOI 去重）
- `ProcessingRun` — 管道执行边界，含配置快照和状态追踪
- `NormalizedEntity` — 统一实体字典（gene/variant/disease/phenotype），含 external_id、display_name、规范状态
- `EntityMergeEvent` — 实体合并审计追踪

**证据模型：**
- `RunEvidenceItem` — 单次运行的版本化证据项，含 field_id、active_payload、源文本 span
- `EvidenceEntityBinding` — 证据-实体超边关系（subject/target/context/mention 角色）
- `CanonicalEvidenceItem` — 跨运行的当前最佳规范证据，含 review_status 和 current_best_run_evidence_id
- `LiteratureProfile` — per-document 聚合的 evidence_groups JSONB

**术语模型：**
- `TerminologyEntry` — 统一参考实体（HGNC/ClinVar/OMIM/HPO/ClinGen）
- `TerminologyAlias` — 索引查找别名（normalized_alias + alias_type + source_db）
- `TerminologyRelationship` — 术语间结构化关系
- `TerminologyEmbedding` — pgvector 语义嵌入（embedding_model + Vector 列）

**审查与对话：**
- `ReviewAuditEvent` — 证据审查操作审计（field_deltas JSONB）
- `ChatSession` / `ChatMessage` — LLM 对话会话和消息
- `DocumentAnnotation` — 用户文档标注（文本选择 + 颜色 + 笔记）

**基础设施：**
- `PipelineRunState` — 管道编排器检查点（stage、cursor、heartbeat）
- `PipelineJob` — 持久化任务队列（priority、claimed_by、retry_count）
- `DocumentProcessingCache` — L2 PostgreSQL 缓存

### 任务队列（`job_queue.py`）

**`JobQueueRepository`** — 原子任务队列操作：
- `enqueue()` — 插入排队状态任务
- `claim_next()` — `SELECT FOR UPDATE SKIP LOCKED` 原子领取最高优先级任务
- `complete()` / `fail()` — 标记任务完成/失败
- `get_status()` / `get_running_count()` — 状态查询

### 文献档案仓储（`literature_profile_repo.py`）

**`LiteratureProfileRepository`** — 文献档案聚合：
- `refresh_for_document()` — 从 canonical_evidence_items 重建 evidence_groups JSONB
- `get_by_document()` — 按文档 ID 获取完整档案
- `search()` — 多维过滤搜索（PMID/基因/变异/疾病/审查状态）

### 搜索索引仓储（`search_index_repo.py`）

**`SearchIndexRepository`** — 前端搜索索引：
- `refresh()` — 从 canonical_evidence_items + document_identifiers 重建物化表
- 支持 PMID/DOI、gene_ids（GIN）、variant_ids（GIN）、search_text 过滤
- `frontend_search_index` 表含 GIN 索引的 JSONB 列

### 文档标注仓储（`document_annotation_repo.py`）

异步 CRUD 函数：
- `list_annotations()` / `get_annotation()` — 查询标注
- `create_annotation()` / `update_annotation()` / `delete_annotation()` — 创建/修改/删除标注

## 数据流

```
应用层 (Service)
        │
        ▼
   get_async_session(factory) → AsyncSession
        │
        ├─→ ORM 查询 (select/insert/update)
        ├─→ JobQueueRepository (任务队列)
        ├─→ LiteratureProfileRepository (文献档案聚合)
        ├─→ SearchIndexRepository (搜索索引刷新)
        └─→ document_annotation_repo (标注 CRUD)
        │
        ▼
   PostgreSQL (asyncpg + pgvector)
```

## 使用方式

```python
from src.dao.postgresql import (
    build_async_engine,
    async_session_factory,
    get_async_session,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    TerminologyEntry,
    NormalizedEntity,
)
from src.dao.postgresql.job_queue import JobQueueRepository
from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository
from src.dao.postgresql.search_index_repo import SearchIndexRepository

# 构建引擎和会话工厂
engine = build_async_engine(settings)
factory = async_session_factory(engine)

# 使用会话
async with get_async_session(factory) as session:
    # ORM 查询
    result = await session.execute(select(TerminologyEntry).limit(10))

    # 任务队列
    queue = JobQueueRepository(factory)
    await queue.enqueue(processing_run_id, source_document_id, request_data)
    job = await queue.claim_next(worker_id="worker-1")

    # 文献档案
    profile_repo = LiteratureProfileRepository(session)
    await profile_repo.refresh_for_document(source_document_id)

    # 搜索索引
    search_repo = SearchIndexRepository(session)
    await search_repo.refresh()
```
