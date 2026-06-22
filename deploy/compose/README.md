# 跨主机前后端分离部署 (Docker Compose)

> 部署目标：前端容器与后端容器分别运行在两台独立的服务器上，通过私有网络互联。

```
┌────────────────────────────────────────────────────────────────────┐
│                        浏览器 (公网/内网)                          │
└────────────────────────┬───────────────────────────────────────────┘
                         │ HTTPS  (域名 -> 前端主机)
                         ▼
        ┌──────────────────────────────────────────────┐
        │   前端主机  (deploy/compose/frontend-host)   │
        │   ┌────────────────────────────────────┐     │
        │   │ nginx:alpine                       │     │
        │   │  - 静态托管 /usr/share/nginx/html   │     │
        │   │  - /api/  → ${BACKEND_URL}         │     │
        │   │  - /health → ${BACKEND_URL}/health │     │
        │   │  - 注入 X-API-Key                  │     │
        │   └────────────────────────────────────┘     │
        └─────────────────────────┬────────────────────┘
                                  │ 内网 HTTP (建议私有 IP / VPC / WireGuard)
                                  ▼
        ┌──────────────────────────────────────────────┐
        │   后端主机  (deploy/compose/backend-host)    │
        │   ┌─────────────┐  ┌────────────┐ ┌────────┐ │
        │   │  backend    │  │ postgres   │ │ redis  │ │
        │   │  FastAPI    │◀▶│ pgvector   │ │  8.0   │ │
        │   │  :8000      │  │ :5432 内网 │ │ :6379  │ │
        │   └─────────────┘  └────────────┘ └────────┘ │
        └──────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌──────────────────────────────────────────────┐
        │   GPU 主机 (可选, services/model-server)     │
        │   embedding / rerank / VLM  :8001            │
        └──────────────────────────────────────────────┘
```

## 1. 目录速览

```
deploy/compose/
├── frontend-host/
│   ├── docker-compose.yml      # 单容器：nginx + 已构建的 SPA
│   └── .env.example            # BACKEND_URL / API_KEY / 端口
└── backend-host/
    ├── docker-compose.yml      # backend + postgres + redis
    ├── .env.example            # CORS / 密码 / 模型服务地址
    └── config/                 # 挂载到容器的 production.yaml + vault
```

镜像构建逻辑：

| 镜像 | Dockerfile | 构建上下文 |
| ---- | ---------- | ---------- |
| 前端 | `frontend/Dockerfile`  | `frontend/`（多阶段：bun 构建 → nginx 托管） |
| 后端 | `backend/Dockerfile`   | 仓库根（需要 `backend/` 与 `libs/config-loader/`） |

## 2. 关键设计

- **同源 SPA**：前端构建时把 `VITE_API_BASE_URL=/api/v1` 写入 bundle；浏览器永远向当前域发请求，CORS 由前端 nginx 在反代时统一携带 `Host`、`X-Forwarded-*` 头送达后端。
- **X-API-Key 注入点**：仅在前端容器 nginx 中通过 `proxy_set_header X-API-Key` 注入；浏览器不持有任何凭证，前端 bundle 不出现密钥。
- **后端外网暴露面**：后端容器 `:8000` 默认绑 `0.0.0.0`，请用系统防火墙 / 安全组只放行前端主机 IP。Postgres / Redis 仅绑 `127.0.0.1`，前端永远不直接访问。
- **配置注入**：`production.yaml` 与 `vault/production.yaml` 以只读卷挂入后端容器；环境变量优先级最高，可在 `.env` 中覆盖任何键。
- **跨容器 CORS**：`CORS_ORIGINS` 必须填浏览器实际访问的源（含 scheme + 端口），如 `https://app.example.com`。

## 3. 部署步骤

### 3.1 后端主机

```bash
# 0. 准备配置
cd deploy/compose/backend-host
cp .env.example .env                                 # 填密码、CORS、API_KEY、模型地址
mkdir -p config/vault
cp ../../../backend/config/environments/production.yaml.example  config/production.yaml
cp ../../../backend/config/vault/production.yaml.example         config/vault/production.yaml
chmod 600 config/vault/production.yaml

# 1. 构建并启动
docker compose --env-file .env up -d --build

# 2. 数据库迁移（首次或升级时）
docker compose exec backend uv run alembic upgrade head

# 3. 健康检查
curl -fsS http://127.0.0.1:8000/health
```

防火墙：

```bash
sudo ufw allow from <前端主机 IP> to any port 8000 proto tcp
```

### 3.2 前端主机

```bash
cd deploy/compose/frontend-host
cp .env.example .env
# 必填：
#   BACKEND_URL=http://<后端主机私有 IP>:8000
#   API_KEY=<与后端一致>
docker compose --env-file .env up -d --build

# 健康检查（容器内 nginx → 后端）
curl -fsS http://127.0.0.1/health
```

公网 TLS 推荐放在容器之外：宿主机用 Caddy / 系统 nginx 监听 443，把流量转发到本机 `:80`，证书续期独立于镜像生命周期。

### 3.3 GPU 模型服务（可选）

`services/model-server/docker-compose.model-server.yml` 已经支持独立部署，把它放到 GPU 主机上，再把 `EMBEDDING_BASE_URL` / `RERANK_BASE_URL` 等指向该主机即可。

## 4. 升级与回滚

```bash
# 升级（前端）
cd deploy/compose/frontend-host
git pull
IMAGE_TAG=$(date +%Y%m%d-%H%M) docker compose build
IMAGE_TAG=$(date +%Y%m%d-%H%M) docker compose up -d

# 回滚：把 IMAGE_TAG 改回旧值再 up -d，nginx 镜像支持秒级切换。
```

后端的回滚要小心数据库迁移：升级前先 `alembic revision history`，必要时使用 `alembic downgrade <rev>`。

## 5. 与 Ansible 部署的关系

- Ansible (`deploy/ansible/`) 仍是裸机 / systemd 部署的事实来源；
- 本目录是“同一份配置契约的容器化部署形态”，二者共用：
  - `backend/config/` 配置加载顺序；
  - `vault/production.yaml` 机密；
  - `cors_origins`、`api_key` 等结构化字段。
- 选择一种部署方式即可；不要同时在同一台机器上启用两套。
