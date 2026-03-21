2026-03-21 - env_file inline comments caused credential corruption and auth failures
- Symptom: backend startup failed with `Redis invalid username-password pair` and `MinIO InvalidAccessKeyId`; Neo4j previously flipped to unhealthy.
- Root cause: `database/config/.env` used inline comments on same line as values. With Podman `env_file`, those comments were injected literally into env values (e.g., passwords), causing service/runtime auth mismatch.
- Additional root cause: Neo4j container should not rely on separate `NEO4J_USER/NEO4J_PASSWORD` env keys; use `NEO4J_AUTH=user/password` and parse it in healthcheck.
- Fix: sanitized `.env`/`.env.example` to pure `KEY=VALUE`, kept single `.env` for database stack, switched Neo4j checks to `NEO4J_AUTH`, recreated services, and aligned app MinIO client credentials.
- Prevention: never place inline comments on env-value lines used by container `env_file`; keep comments on separate lines only.

2026-03-21 - Celery failed Redis auth because `.env.local` was not loaded for CLI entrypoints
- Symptom: `celery -A src.celery_app.celery_app worker -l info` showed broker URL without password and repeated `Authentication required` from Redis.
- Root cause: `src/config.AppConfig._load_dotenv()` loaded `.env` and `.env.<environment>` only; Celery CLI was started without `--env-file`, so `REDIS_PASSWORD` from `.env.local` was never loaded.
- Fix: load `.env.local` by default (override enabled), while keeping explicit `ENV_FILE` as highest priority.
- Prevention: for non-uvicorn processes, either rely on default `.env.local` loading or explicitly set `ENV_FILE=.env.local` in process startup scripts.

2026-03-21 - PostgreSQL `public` legacy table collision during SQLAlchemy auto-init
- Symptom: upload API returned 503; schema init failed with `psycopg2.errors.UndefinedColumn` on FK `tasks.document_id -> documents.document_id`.
- Root cause: database `acmg_ps3` already contained legacy `public.documents` table (PK `id`), while current ORM expects `documents.document_id`. `Base.metadata.create_all()` skipped creating `documents` but failed creating `tasks` FK against incompatible existing table.
- Fix: introduced configurable schema isolation (`POSTGRES_SCHEMA` + `search_path`) and automatic `CREATE SCHEMA IF NOT EXISTS` before metadata creation; local runtime set to `POSTGRES_SCHEMA=acmg_app`.
- Prevention: keep app ORM tables in a dedicated schema (or dedicated database) instead of sharing `public` with legacy structures.

2026-03-21 - Database management drift caused by fragmented scripts
- Symptom: database operations were split across many scripts with overlapping responsibilities and stale hardcoded paths, making startup/init/check behavior inconsistent.
- Root cause: no single command surface; historical setup scripts accumulated and diverged from current runtime (`podman-compose` + ORM init path).
- Fix: introduced one canonical CLI (`database/scripts/dbctl.sh`) and removed legacy scripts/directories not required at runtime.
- Prevention: new database operational commands must be added only through `dbctl.sh`, and docs must reference that single entrypoint.


2026-03-21 - CWD-dependent dotenv loading caused schema fallback and legacy FK collision
- Symptom: runtime intermittently logged `Failed to auto-initialize PostgreSQL schema` with `(psycopg2.errors.UndefinedColumn) ... FOREIGN KEY(document_id) REFERENCES documents (document_id)`.
- Root cause: config dotenv loading used `os.getcwd()`; when a process started outside project root, `.env.local` was not loaded, so `POSTGRES_SCHEMA` fell back to `public` and ORM DDL collided with legacy `public.documents` table shape.
- Fix: load dotenv files from project root (derived from `src/config.py`) independent of cwd; keep `ENV_FILE` override support.
- Hardening: `initialize_schema()` now applies explicit schema translation for non-public schemas even when caller does not pass `schema_name`; DB conninfo search_path includes `schema,public`.
- Prevention: avoid cwd-coupled config resolution for long-running services and workers; keep schema-targeting explicit during DDL operations.
