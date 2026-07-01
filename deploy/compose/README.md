# deploy/compose — Docker Compose 部署

> Lingua Seeker 各种拓扑的 Docker Compose 部署配置。

## 概述

本目录包含多种 Docker Compose 部署变体，覆盖开发、预发布、跨主机和单机场景。所有变体共享相同的配置契约（`backend/config/` 加载顺序、`vault/production.yaml` 密钥结构）。

## 部署变体

```
deploy/compose/
├── dev-infra/               # 本地开发：仅 Postgres + Redis（后端在主机运行）
│   └── docker-compose.yml
├── staging/                 # 预发布：backend + Postgres + Redis
│   └── docker-compose.yml
├── backend-host/            # 跨主机：backend + Postgres + Redis（后端服务器）
│   ├── docker-compose.yml
│   ├── .env.example
│   └── config/              # 挂载的 production.yaml + vault/
├── frontend-host/           # 跨主机：nginx + SPA（前端服务器）
│   ├── docker-compose.yml
│   └── .env.example
├── single-server/           # 一体化：backend + Postgres + Redis（推理服务外部）
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── deploy.sh            # 初始部署脚本
│   ├── update.sh            # 增量代码更新脚本
│   └── patch-backend.Dockerfile
├── debug-prod/              # 生产调试配置
└── README.md
```

| 变体 | 服务 | 用途 |
|------|------|------|
| `dev-infra/` | Postgres + Redis | 本地开发，后端通过 `uv run uvicorn` 在主机启动 |
| `staging/` | Backend + Postgres + Redis | 预发布验证，推理服务外部 |
| `backend-host/` | Backend + Postgres + Redis | 跨主机部署的后端部分 |
| `frontend-host/` | Nginx + SPA | 跨主机部署的前端部分 |
| `single-server/` | Backend + Postgres + Redis | 一体化服务器（推理服务外部） |

## 跨主机部署（backend-host + frontend-host）

```
Browser
    | HTTPS (domain -> frontend-host)
    v
+---------------------------------------+
|  frontend-host (nginx:alpine)         |
|  - Static SPA /usr/share/nginx/html   |
|  - /api/ -> ${BACKEND_URL}            |
|  - /health -> ${BACKEND_URL}/health   |
|  - Injects X-API-Key header           |
+-----------------+---------------------+
                  | Internal HTTP (private IP / VPC / WireGuard)
                  v
+---------------------------------------+
|  backend-host                         |
|  +----------+ +----------+ +--------+ |
|  | backend  | | postgres | | redis  | |
|  | FastAPI  | | pgvector | | 8.0    | |
|  | :8000    | | :5432    | | :6379  | |
|  +----------+ +----------+ +--------+ |
+---------------------------------------+
```

### 关键设计决策

- **SPA 来源** — 前端构建使用 `VITE_API_BASE_URL=/api/v1`，浏览器始终请求当前域名
- **X-API-Key 注入** — 由前端 Nginx 通过 `proxy_set_header` 注入，浏览器永远看不到凭证
- **后端暴露** — 后端端口默认绑定 `127.0.0.1`，设置 `BACKEND_BIND=0.0.0.0` 并配置防火墙
- **配置注入** — `production.yaml` 和 `vault/production.yaml` 以只读方式挂载到后端容器

## 单机部署

适用于 CentOS 7.9+ 服务器，本地运行 backend、Postgres 和 Redis。推理服务（embedding、rerank、doc-parse）为外部 Docker 容器。

### 前置条件

- Docker CE 20.10+
- 已加载后端镜像：`lingua-seeker-backend:local`
- 外部推理服务运行中（embedding :8002、rerank :8003、doc-parse :44321）

### 初始部署

```bash
cd deploy/compose/single-server
cp .env.example .env   # 编辑真实密钥
./deploy.sh            # 检查前置条件、复制文件、启动服务、健康检查
```

### 增量更新

```bash
./update.sh backend          # 仅更新后端
```

使用薄覆盖 Dockerfile（`patch-backend.Dockerfile`），仅复制变更的源文件到现有镜像。

## 开发基础设施

轻量级 Compose，仅 Postgres 和 Redis，后端通过 `uv run uvicorn` 在主机运行：

```bash
docker compose -f deploy/compose/dev-infra/docker-compose.yml up -d
```

## 镜像构建

| 服务 | Dockerfile | 构建上下文 |
|------|-----------|-----------|
| Frontend | `frontend/Dockerfile` | `frontend/`（多阶段：bun build -> nginx） |
| Backend | `backend/Dockerfile` | 仓库根目录（需要 `backend/` 和 `libs/config-loader/`） |

> **注意**：Embedding、Rerank 和 Doc-Parse 推理服务由独立项目构建和发布。

## 与 Ansible 的关系

- Ansible（`deploy/ansible/`）是裸机 / systemd 部署路径
- 本目录是容器化部署路径，使用相同的配置契约
- 两者共享：`backend/config/` 加载顺序、`vault/production.yaml` 密钥结构
- 每台服务器选择一种方式，不要在同一机器上同时运行
