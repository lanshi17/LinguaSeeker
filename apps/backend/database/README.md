# database/ 管理说明（代码对齐版）

`database/` 通过统一脚本 `database/scripts/dbctl.sh` 管理容器生命周期、初始化、检查与维护。

## 目录结构

```text
database/
├── podman-compose.yml
├── alembic/
├── alembic.ini
├── config/
│   ├── .env
│   ├── .env.example
│   ├── containers.conf
│   └── qdrant_config.json
├── scripts/
│   ├── dbctl.sh
│   └── qdrant/qdrant_init.sh
├── sql/
│   ├── init_database_schema.sql
│   ├── seed_data.sql
│   ├── cleanup_orphan_records.sql
│   └── 其他历史修复脚本
├── minio/
│   ├── certs/
│   ├── data/
│   └── minio.license
└── qdrant/
    └── certs/
```

## 统一入口

```bash
./database/scripts/dbctl.sh <command>
```

支持命令（来自脚本实装）：

- `up [service...]`
- `down [args...]`
- `restart [service...]`
- `ps`
- `logs [service...]`
- `init`
- `check`
- `backup [dir]`
- `cleanup`
- `reset --yes`（破坏性操作）

## 环境变量加载顺序

1. `database/config/.env`
2. 根目录 `.env.local`
3. `ENV_FILE` 指定文件（最高优先级）

## 一次完整初始化

```bash
./database/scripts/dbctl.sh up
./database/scripts/dbctl.sh init
./database/scripts/dbctl.sh check
```

## 说明

- `init` 会调用 `src.infrastructure.postgres.initialize_schema()` 并执行 `sql/seed_data.sql`。
- `cleanup` 仅执行 `sql/cleanup_orphan_records.sql`。
- `reset --yes` 会清理卷并清空 `database/minio/data`。

## 配置契约

- `database/config/.env` 与 `.env.example` 必须使用纯 `KEY=VALUE` 格式，不要在值后追加行内注释。
- Neo4j 使用单个 `NEO4J_AUTH=user/password` 变量，不能再拆成 `NEO4J_USER` / `NEO4J_PASSWORD`。
