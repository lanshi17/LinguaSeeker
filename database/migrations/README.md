# database/migrations

> Lingua Seeker PostgreSQL 模式的 Alembic 异步迁移环境。

## 概述

本目录包含 Alembic 迁移框架的核心配置和所有迁移版本文件。迁移使用异步 PostgreSQL 引擎（`asyncpg`），支持离线 SQL 生成和在线异步执行。模式目标为可配置的 PostgreSQL schema（非 `public`）。

## 目录结构

```
migrations/
├── env.py              # 异步 Alembic 环境（从 src.core.config 读取 DSN）
├── env.py.jinja        # env.py 生成的 Jinja 模板
├── script.py.mako      # 新迁移脚本的 Mako 模板
└── versions/           # 迁移版本文件（23 个迁移）
    ├── 2026-05-18_4a82b5793055_init_mvp_schema.py
    ├── 2026-05-25_add_terminology_embeddings_pgvector.py
    ├── 2026-05-25_add_terminology_reference_tables.py
    ├── ...
    └── 2026-06-23_add_document_annotations.py
```

## 核心设计

- **异步引擎**：使用 `create_async_engine` 配合 `asyncpg` 驱动和 `NullPool`
- **Schema 感知**：迁移目标为可配置的 PostgreSQL schema（来自 `cfg.postgresql.schema_`），`search_path` 设置为 `<schema>,public`
- **配置来源**：通过 `backend/src/core/config.py` 的 `get_config()` 读取数据库连接
- **路径处理**：`env.py` 在运行时将 `backend/` 插入 `sys.path`，使 `src.*` 导入从仓库根目录解析
- **离线模式**：生成 SQL 到 stdout，无需连接数据库

## 快速开始

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua

# 应用所有待处理迁移
uv run alembic -c database/alembic.ini upgrade head

# 创建新迁移
uv run alembic -c database/alembic.ini revision --autogenerate -m "add_feature_table"

# 回滚一个版本
uv run alembic -c database/alembic.ini downgrade -1

# 查看当前版本
uv run alembic -c database/alembic.ini current

# 离线 SQL 生成
uv run alembic -c database/alembic.ini upgrade head --sql
```

## 迁移历史

| 日期 | 迁移 | 描述 |
|------|------|------|
| 2026-05-18 | `init_mvp_schema` | 初始 MVP 模式（9 个核心表） |
| 2026-05-25 | `add_terminology_embeddings_pgvector` | pgvector 扩展用于术语嵌入 |
| 2026-05-25 | `add_terminology_reference_tables` | 术语参考表（hgnc、omim、hpo 等） |
| 2026-05-27 | `add_nulls_not_distinct_relationship_constraint` | NULLS NOT DISTINCT 约束 |
| 2026-05-28 | `add_review_and_chat_tables` | 审查/反馈和聊天会话表 |
| 2026-05-30 | `initial_schema` | 模式重置/重组 |
| 2026-06-01 | `add_fk_chat_message_evidence_entity` | 聊天消息到证据实体的外键 |
| 2026-06-08 | `add_literature_profiles` | CQRS 读模型文献配置表 |
| 2026-06-08 | `add_performance_indexes` | 搜索性能索引 |
| 2026-06-08 | `add_reviewed_unmappable_status` | 实体审查状态 |
| 2026-06-08 | `extract_pipeline_status_column` | 流水线状态列提取 |
| 2026-06-08 | `remove_run_evidence_canonical_fk` | 移除外键约束 |
| 2026-06-10 | `add_created_at_to_search_index` | 搜索索引的 created_at |
| 2026-06-11 | `add_pipeline_run_leases` | 流水线运行租约管理 |
| 2026-06-11 | `allow_standalone_chat_sessions` | 支持独立聊天会话 |
| 2026-06-13 | `add_chat_message_action` | 聊天消息操作字段（JSONB） |
| 2026-06-21 | `add_critical_indexes` | 热路径索引：P0（pipeline_run_states.created_at 等）、P1（run_evidence_items 复合等）、P2（source_document_identifiers 复合等） |
| 2026-06-21 | `add_variant_internal_id_index` | 合成 variant 外部 ID 的部分唯一索引 |
| 2026-06-22 | `add_document_processing_cache` | L2 PostgreSQL 流水线结果缓存（JSONB，按内容哈希键控） |
| 2026-06-23 | `repair_phase3_schema` | 修复缺失的 Phase 3 运行时表（terminology_embeddings、frontend_search_index），幂等检查 |
| 2026-06-23 | `add_document_full_text` | source_documents 添加 original_text 和 translated_text 列 |
| 2026-06-23 | `add_content_blocks` | source_documents 添加 original_blocks 和 translated_blocks JSONB 列 |
| 2026-06-23 | `add_document_annotations` | 双语阅读器的段落级字符偏移注释表 |
