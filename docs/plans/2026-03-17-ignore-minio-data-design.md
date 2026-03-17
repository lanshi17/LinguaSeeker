# Ignore MinIO Local Data Directory

## Context
Git is currently tracking MinIO runtime data under `apps/backend/database/minio/data/` (for example `.minio.sys/.../xl.meta` and `stats.bin`). These files change frequently and are not source code.

## Goals
- Stop Git from tracking anything under `apps/backend/database/minio/data/`.
- Keep the local data on disk for development (do not delete local files).

## Non-Goals
- Rewriting git history to remove previously committed blobs.
- Changing MinIO/runtime configuration.

## Approach
- Add an ignore rule to the repository root `.gitignore`:
  - `/apps/backend/database/minio/data/`
- Remove already-tracked files from the index (keep working tree files):
  - `git rm -r --cached apps/backend/database/minio/data`

## Verification
- After committing, `git status` should show no changes under `apps/backend/database/minio/data/`.
- Running local services may recreate/update MinIO files, but they should remain ignored.

## Rollback
- Remove the ignore rule and re-add files with `git add -f` (not recommended).
