# GitHub Actions — 跨主机前后端容器化 CI/CD

> 三条流水线：前后端独立构建到 GHCR,手工(或自动)触发 SSH 跨主机部署。

```
push to dev / master / release/**
        │
        ├──► build-frontend.yml ──► ghcr.io/<owner>/lingua-seeker-frontend:<tag>
        │                                      │
        ├──► build-backend.yml  ──► ghcr.io/<owner>/lingua-seeker-backend:<tag>
        │                                      │
        └──► (master only) workflow_run ──► deploy.yml ──► SSH 两台主机 pull + up -d
```

## 文件

| 文件 | 触发 | 作用 |
| ---- | ---- | ---- |
| `.github/workflows/build-frontend.yml` | push / PR / 手动 | bun 构建 SPA + nginx 镜像 → GHCR |
| `.github/workflows/build-backend.yml`  | push / PR / 手动 | uv + maturin + Python 运行时镜像 → GHCR |
| `.github/workflows/deploy.yml`         | 手动 / build-* 完成后(仅 master) | SSH 到两台主机执行 `docker compose pull && up -d` |

## 镜像标签策略

`docker/metadata-action` 一次性算出以下 tag,根据触发场景过滤推送：

| 来源 | tag 示例 |
| ---- | -------- |
| 任何分支 push | `dev`, `master`, `release-1.2.0` |
| PR 事件 | `pr-42`(构建但不推送) |
| 提交 SHA | `sha-abc1234` |
| master 分支 | 额外推送 `latest` |
| 手动 dispatch 输入 | 自定义 tag |

回滚就是把 `IMAGE_TAG` 切回旧的 SHA。

## 必备 Secrets / Environments

### Repo-level(自动可用)

- `GITHUB_TOKEN`：登录 GHCR 推镜像,workflow 自带,无需额外配置。
  - 仓库设置 → Actions → General → Workflow permissions → 勾选 **Read and write permissions**。
  - 首次推送后,Package 默认 private,记得到 GHCR Package settings 里把 frontend / backend 两个 package 链接到当前 repo,并按需公开或加 read-package PAT。

### Environment 级别(`production` / `staging`)

> 在仓库 Settings → Environments 中各建一个,把 secrets 放到环境里,而不是 repo 全局——这样部署到 production 时可以加 required reviewers。

| Secret | 含义 |
| ------ | ---- |
| `BACKEND_HOST`   | 后端主机的公网 / VPN 地址 |
| `BACKEND_USER`   | 后端主机 SSH 用户(需要 `docker compose` 权限) |
| `BACKEND_SSH_KEY` | 私钥(PEM,无口令)。建议为部署用户单独签发,`authorized_keys` 用 `command=` 锁死。 |
| `FRONTEND_HOST`  | 前端主机地址 |
| `FRONTEND_USER`  | 前端主机 SSH 用户 |
| `FRONTEND_SSH_KEY` | 私钥 |
| `GHCR_PULL_TOKEN` | 仅当 GHCR 镜像私有时填写：一个 `read:packages` 范围的 PAT,部署主机用它登录 GHCR。 |

> 端口默认是 22。如果是非标端口,可以在 `appleboy/ssh-action` 那一步加 `port: ${{ secrets.BACKEND_PORT }}`。

## 部署主机一次性准备

两台目标主机都需要：

```bash
# 1. 装 docker + compose v2(略)

# 2. 克隆仓库到固定路径(deploy.yml 默认 /opt/lingua-seeker;可改 DEPLOY_ROOT 环境变量)
sudo install -d -o "$USER" -g "$USER" /opt/lingua-seeker
git clone [redacted-email]:[redacted-user]/CrossEvidence.git /opt/lingua-seeker

# 3. 填好对应 .env(不进版本控制)
cd /opt/lingua-seeker/deploy/compose/backend-host    # 或 frontend-host
cp .env.example .env  &&  vim .env

# 4. 后端主机额外:挂载用配置文件
cd /opt/lingua-seeker/deploy/compose/backend-host
mkdir -p config/vault
cp ../../../backend/config/environments/production.yaml.example config/production.yaml
cp ../../../backend/config/vault/production.yaml.example         config/vault/production.yaml
chmod 600 config/vault/production.yaml

# 5. 允许 deploy 用户无 sudo 跑 docker(加入 docker 组并重新登录)
sudo usermod -aG docker $USER
```

> 自动 deploy 流水线只做 `git fetch && checkout origin/master && docker compose pull && up -d`,**不会改 `.env` 和挂载的密钥**。

## 触发方式

### 自动构建

- push 到 `dev` / `master` / `release/**` 且改了对应路径,自动构建镜像并推到 GHCR。
- PR 只构建不推(用作 dockerfile 语法回归)。

### 自动部署(master only)

- `master` 上 build 成功后,`workflow_run` 触发 `deploy.yml`：
  - build-backend 完成 → 只滚动后端容器；
  - build-frontend 完成 → 只滚动前端容器。
- 想要要求人工 review,在 Environment(production)上勾 *Required reviewers*。

### 手动部署 / 回滚

GitHub → Actions → **deploy** → Run workflow:

| 输入 | 取值 |
| ---- | ---- |
| environment | `production` / `staging` |
| image_tag   | 例如 `sha-abc1234`、`latest`、`v1.2.0` |
| target      | `both` / `backend` / `frontend` |

部署脚本里有迁移和健康检查：

- 后端：`docker compose exec backend uv run alembic upgrade head`,完成后 `docker image prune -f`。
- 前端：拉镜像后,本机循环 `curl http://127.0.0.1/health` 最长 60 秒；失败会 dump `docker compose logs --tail=80` 再退非零。

## 与 Ansible 的关系

- Ansible 部署链路(`deploy/ansible/`)不受影响,适用于直接拉源码 + systemd 的裸机部署。
- GitHub Actions 部署链路面向"两台 Docker 主机"形态,使用本仓库的 `deploy/compose/`。
- 两条链路共享 `backend/config/` 的配置契约和 `X-API-Key` 的注入点。**同一台机器只走一条链路**,不要混用。

## 验证

```
$ python3 -c "yaml.safe_load(...)"
OK .github/workflows/build-backend.yml
OK .github/workflows/build-frontend.yml
OK .github/workflows/deploy.yml
```

未做完整端到端构建(本机 docker CLI 不带 compose v2,且推 GHCR 需要真实仓库 token)。首次推送后请在 PR 上跑一遍 build-* 流水线确认 Dockerfile 在 ubuntu-latest 上构建通过,再走 deploy。
