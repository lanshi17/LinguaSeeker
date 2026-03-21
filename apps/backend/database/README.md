# Database Management

`database/` 目录统一由一个入口管理：`database/scripts/dbctl.sh`。

## Directory Layout

```text
database/
├── alembic/                     # PostgreSQL migration scripts
├── alembic.ini
├── config/
│   ├── .env                     # database stack env (for containers)
│   ├── .env.example
│   ├── containers.conf
│   └── qdrant_config.json
├── init-scripts/                # optional PostgreSQL init mount directory
├── minio/
│   ├── certs/
│   ├── data/
│   └── minio.license
├── podman-compose.yml
├── qdrant/
│   └── certs/
├── scripts/
│   ├── dbctl.sh                 # unified management entrypoint
│   └── qdrant/
│       └── qdrant_init.sh       # container runtime init hook (mounted by compose)
└── sql/
    ├── cleanup_orphan_records.sql
    ├── init_database_schema.sql
    ├── seed_data.sql
    └── README.md
```

## Unified Entry

```bash
./database/scripts/dbctl.sh <command> [args]
```

Env loading order:
1. `database/config/.env`
2. `.env.local` (if exists)
3. `ENV_FILE` (if set, highest priority)

## Commands

```bash
# lifecycle
./database/scripts/dbctl.sh up [service...]
./database/scripts/dbctl.sh down [compose-down-args...]
./database/scripts/dbctl.sh restart [service...]
./database/scripts/dbctl.sh ps
./database/scripts/dbctl.sh logs [service...]

# initialization and health
./database/scripts/dbctl.sh init
./database/scripts/dbctl.sh check

# maintenance
./database/scripts/dbctl.sh backup [output_dir]
./database/scripts/dbctl.sh cleanup

# destructive reset (requires explicit confirmation)
./database/scripts/dbctl.sh reset --yes
```

## Recommended Workflow

```bash
# 1) start stack
./database/scripts/dbctl.sh up

# 2) initialize/upgrade schema and seed
./database/scripts/dbctl.sh init

# 3) verify services and credentials
./database/scripts/dbctl.sh check
```

## Notes

- `reset --yes` will remove compose volumes and clear `database/minio/data`.
- `init` uses the backend ORM initializer and then applies `sql/seed_data.sql` if present.
- Keep `database/config/.env` values as plain `KEY=VALUE` lines (no inline comments in value lines).
