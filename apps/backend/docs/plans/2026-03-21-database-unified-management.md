# Database Unified Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide a single operational entrypoint for database stack lifecycle, initialization, health checks, reset, backup, and cleanup while removing fragmented legacy scripts.

**Architecture:** Introduce one Bash CLI (`database/scripts/dbctl.sh`) as the only operational interface. The script wraps podman-compose lifecycle actions and SQL/Python initialization checks using repository-relative paths and environment loading without any absolute hardcoded locations.

**Tech Stack:** Bash, podman-compose, psql/pg_dump, uv/python (existing app bootstrap), PostgreSQL, Redis, Neo4j, MinIO, Qdrant.

---

### Task 1: Add single entrypoint CLI

**Files:**
- Create: `database/scripts/dbctl.sh`

**Steps:**
1. Implement command parser with subcommands: `up/down/restart/ps/logs/init/check/reset/backup/cleanup`.
2. Use repository-relative root resolution and compose file `database/podman-compose.yml`.
3. Load env from `database/config/.env` and optional overrides (`.env.local`, `ENV_FILE`) without hardcoded absolute paths.
4. Add safety gate for `reset` requiring explicit `--yes`.

### Task 2: Remove fragmented legacy scripts

**Files:**
- Delete: `database/scripts/init_db.sh`
- Delete: `database/scripts/backup_db.sh`
- Delete: `database/scripts/run_cleanup_sql.sh`
- Delete: `database/scripts/setup/*`
- Delete: `database/scripts/qdrant/{deploy_https_qdrant.sh,generate_qdrant_certs.sh,setup_qdrant_tls.sh}`
- Keep: `database/scripts/qdrant/qdrant_init.sh` (runtime dependency in compose)

**Steps:**
1. Delete scripts replaced by `dbctl.sh`.
2. Keep runtime-critical script used by qdrant container startup.

### Task 3: Rewrite docs for unified management

**Files:**
- Modify: `database/README.md`
- Modify: `database/sql/README.md`
- Delete: `database/lesson.md`
- Delete: `database/leesons.md`

**Steps:**
1. Rewrite README around `dbctl.sh` commands and one canonical workflow.
2. Remove stale references to deleted scripts and hardcoded paths.
3. Keep SQL README focused on script purpose + invocation through dbctl.
4. Remove legacy troubleshooting notes from database directory (tracked in root `lesson.md`).

### Task 4: Verify and record

**Files:**
- Modify: `progress.txt`
- Modify: `lesson.md`

**Steps:**
1. Run shell syntax check for `dbctl.sh`.
2. Run `dbctl.sh ps` and `dbctl.sh check` to verify command path.
3. Record milestone in `progress.txt` and debugging lessons in root `lesson.md`.
