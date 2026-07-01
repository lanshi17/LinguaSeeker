# Alembic

> 数据库 schema 迁移管理——基于 Alembic 管理 PostgreSQL 表结构变更。

## Overview

Alembic 管理 `src.dao.postgresql.models.Base` 中定义的 ORM 模型对应的数据库 schema 迁移。迁移文件位于 `versions/` 目录，由 Alembic 自动生成和管理。

## Structure

```
alembic/
├── versions/          # 迁移版本文件（自动生成）
│   └── .gitkeep
└── README.md
```

## Key Components

| 组件 | 说明 |
|------|------|
| `versions/` | 存放自动生成的迁移脚本，文件名格式 `<revision>_<description>.py` |
| 目标 metadata | `src.dao.postgresql.models.Base.metadata`（Alembic autogenerate 的比较基准） |

## Usage / Patterns

### 生成迁移

```bash
cd backend
uv run alembic revision --autogenerate -m "description"
```

### 执行迁移

```bash
uv run alembic upgrade head
```

### 查看当前版本

```bash
uv run alembic current
```

### 注意事项

- `frontend_search_index` 表使用独立的 `MetaData`（`search_index_metadata`），不由 Alembic 管理——该表通过 `app.main.lifespan` 中的 `create_all` 自动创建。
- 测试使用 SQLite 内存数据库，`JSONB` 列会在测试创建表时自动替换为 `JSON` 类型。

## Dependencies

| 依赖 | 用途 |
|------|------|
| Alembic | 数据库迁移框架 |
| SQLAlchemy | ORM metadata 作为迁移基准 |
| asyncpg | PostgreSQL 异步驱动 |
