# GitHub Actions

> CI pipeline for lint/test plus a build-and-deploy pipeline for the backend image to GHCR.

```
push to dev / master / release/**
        │
        ├──► ci.yml            ──► backend ruff lint, frontend lint + type-check + test, rust test
        │
        ├──► build-backend.yml ──► ghcr.io/<owner>/lingua-seeker-backend:<tag>
        │                                      │
        ├──► config-validation.yml ──► cross-service config consistency check
        │
        └──► (master only) workflow_run ──► deploy.yml ──► SSH to backend host pull + up -d
```

## Workflows

| File | Trigger | Purpose |
|------|---------|---------|
| `.github/workflows/ci.yml` | push / PR | Backend lint (ruff), frontend lint + type-check + test (vitest), rust test |
| `.github/workflows/build-backend.yml` | push / PR / manual | uv + maturin + Python runtime image to GHCR |
| `.github/workflows/config-validation.yml` | push / PR touching config files | Cross-service configuration consistency validation across environments |
| `.github/workflows/deploy.yml` | manual / build-backend completion | SSH to backend host, `docker compose pull && up -d` |

## Image Tag Strategy

`docker/metadata-action` computes the following tags; filtering rules control which are actually pushed:

| Source | Example Tag |
|--------|-------------|
| Any branch push | `dev`, `master`, `release-1.2.0` |
| PR event | `pr-42` (build only, not pushed) |
| Commit SHA | `sha-abc1234` |
| Master branch | additionally pushes `latest` |
| Manual dispatch input | custom tag |

Rollback: switch `IMAGE_TAG` back to a previous SHA.

## Required Secrets / Environments

### Repo-level (auto-available)

- `GITHUB_TOKEN`: logs into GHCR to push images. Provided automatically by the workflow.
  - Repo Settings > Actions > General > Workflow permissions > select **Read and write permissions**.

### Environment-level (`production` / `staging`)

> Create each in repo Settings > Environments. Place secrets in the environment, not at repo level, so you can add required reviewers for production deploys.

| Secret | Description |
|--------|-------------|
| `BACKEND_HOST` | Public / VPN address of the backend host |
| `BACKEND_USER` | SSH user on the backend host (needs `docker compose` permission) |
| `BACKEND_SSH_KEY` | Private key (PEM, no passphrase). Issue a dedicated deploy key; lock `authorized_keys` with `command=`. |
| `GHCR_PULL_TOKEN` | Only needed when GHCR images are private: a PAT with `read:packages` scope for the deploy host to log into GHCR. |

> Default SSH port is 22. For non-standard ports, add `port: ${{ secrets.BACKEND_PORT }}` to the `appleboy/ssh-action` step.

## Deploy Host Preparation

```bash
# 1. Install docker + compose v2 (omitted)

# 2. Clone repo to a fixed path (deploy.yml defaults to /opt/lingua-seeker; change via DEPLOY_ROOT)
sudo install -d -o "$USER" -g "$USER" /opt/lingua-seeker
git clone git@github.com:lanshi17/CrossEvidence.git /opt/lingua-seeker

# 3. Fill in the .env for this host (not version-controlled)
cd /opt/lingua-seeker/deploy/compose/backend-host
cp .env.example .env  &&  vim .env

# 4. Mount config files
mkdir -p config/vault
cp ../../../backend/config/environments/production.yaml.example config/production.yaml
cp ../../../backend/config/vault/production.yaml.example         config/vault/production.yaml
chmod 600 config/vault/production.yaml

# 5. Allow the deploy user to run docker without sudo (add to docker group, re-login)
sudo usermod -aG docker $USER
```

> The automated deploy pipeline only does `git fetch && checkout origin/master && docker compose pull && up -d`. It does **not** modify `.env` or mounted secrets.

## Trigger Modes

### CI (every push / PR)

- `ci.yml` runs ruff lint on the backend, ESLint + TypeScript type-check + vitest on the frontend, and `cargo test` on all three Rust crates.

### Automatic Build

- Push to `dev` / `master` / `release/**` that touches backend paths automatically builds and pushes the image to GHCR.
- PRs build but do not push (serves as Dockerfile syntax regression check).

### Automatic Deploy (master only)

- After a successful `build-backend` on `master`, `workflow_run` triggers `deploy.yml` to roll the backend containers.
- To require manual review, enable *Required reviewers* on the Environment (production).

### Manual Deploy / Rollback

GitHub > Actions > **deploy** > Run workflow:

| Input | Values |
|-------|--------|
| environment | `production` / `staging` |
| image_tag | e.g. `sha-abc1234`, `latest`, `v1.2.0` |

The deploy script includes migration and health checks:
- `docker compose exec backend uv run alembic upgrade head`, then `docker image prune -f`.

## Config Validation

`config-validation.yml` runs on PRs and pushes that touch configuration files. It validates configuration consistency across all environments, checking that backend config, Docker Compose, and Ansible inventories are aligned.

## Relationship with Ansible

- The Ansible deployment path (`deploy/ansible/`) is unaffected and is used for source-code + systemd bare-metal deployments.
- The GitHub Actions deployment path targets the Docker host topology using `deploy/compose/`.
- Both paths share the `backend/config/` configuration contract and the `X-API-Key` injection point. **Use only one path per machine** -- do not mix them.
