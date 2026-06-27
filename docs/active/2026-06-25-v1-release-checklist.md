# Lingua Seeker v1.0.0 Release Checklist

**Status:** in-progress
**Created:** 2026-06-25
**Release:** v1.0.0

## Goal

Freeze the current `dev` branch state, publish the first stable `v1.0.0` release, and deploy matching frontend/backend images with a consistent environment contract.

## Release Scope

- Backend package version: `1.0.0`
- Frontend package version: `1.0.0`
- API prefix: `/api/v1/`
- Database contract:
  - Development: `dev_lingua_seeker`, schema `lingua_seeker`
  - Staging: `staging_lingua_seeker`, schema `lingua_seeker`
  - Production: `lingua_seeker`, schema `lingua_seeker`
- External inference services remain out of repository lifecycle:
  - Embedding: `BAAI/bge-m3`
  - Rerank: `BAAI/bge-reranker-v2-m3`
  - Doc Parse: `opendatalab/MinerU2.5-Pro-2604-1.2B`

## Code Freeze Rules

- Only release-blocking fixes may land after this checklist starts.
- Do not change public API routes except for release-blocking defects.
- Do not modify real `backend/config/vault/*.yaml` secrets in release commits.
- Keep frontend and backend image tags identical for release rollout.

## Pre-Tag Verification

Run from a clean worktree on `dev`:

```bash
git status --short --branch
(cd backend && uv run ruff check)
(cd backend && uv run pytest)
(cd frontend && bun run lint)
(cd frontend && bun run type-check)
(cd frontend && bun run build)
(cd backend/libs/rust-io && cargo test)
(cd backend/libs/files-io && cargo test)
(cd backend/libs/net-io && cargo test)
```

Expected result: all commands pass. If any command fails, fix the issue before creating the release tag.

## Tag And Build

After verification passes:

```bash
git checkout dev
git pull --ff-only origin dev
git status --short
git tag -a v1.0.0 -m "release: v1.0.0"
git push origin v1.0.0
```

Build both images from GitHub Actions:

1. Run `build-backend` with `tag=v1.0.0`.
2. Run `build-frontend` with `tag=v1.0.0`.
3. Confirm both images exist in GHCR:
   - `ghcr.io/lanshi17/lingua-seeker-backend:v1.0.0`
   - `ghcr.io/lanshi17/lingua-seeker-frontend:v1.0.0`

## Staging Rollout

Deploy both sides to staging with `image_tag=v1.0.0`:

```bash
# GitHub Actions > deploy > Run workflow
# environment=staging
# image_tag=v1.0.0
# target=both
```

Verify:

```bash
curl -fsS https://staging.furong.genemed.tech/health
curl -fsS https://staging.furong.genemed.tech/api/v1/health
```

Also run one controlled pipeline smoke test with a known small input before production rollout.

## Production Rollout

Deploy after staging passes:

```bash
# GitHub Actions > deploy > Run workflow
# environment=production
# image_tag=v1.0.0
# target=both
```

Verify:

```bash
curl -fsS https://furong.genemed.tech/health
curl -fsS https://furong.genemed.tech/api/v1/health
```

Check backend logs and database migration status:

```bash
cd /opt/lingua-seeker/deploy/compose/backend-host
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=120 backend
docker compose --env-file .env exec -T backend uv run alembic current
```

## Rollback

Rollback uses the previous known-good image tag:

```bash
# GitHub Actions > deploy > Run workflow
# environment=production
# image_tag=<previous-sha-or-tag>
# target=both
```

If a database migration was applied, confirm whether it is backward-compatible before rolling back application images.

## Release Completion

After production verification:

- Update this checklist status to `completed`.
- Record the final production image digests.
- Move this document to `docs/archive/plans/`.
- Add a final `progress.txt` entry with the deployed tag and verification result.
