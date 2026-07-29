# deploy

> Lingua Seeker 平台的部署配置，支持 Ansible 裸机部署和 Docker Compose 容器化部署。

## 概述

本目录包含所有部署相关的配置文件，支持多种部署拓扑：Ansible 裸机/systemd 部署（生产+预发布）、Docker Compose 容器化部署（跨主机/单机/开发环境）、以及 MinerU 文档解析服务部署。

## 目录结构

```
deploy/
├── ansible/                    # 裸机 / systemd 部署（生产 + 预发布）
│   ├── ansible.cfg             # Ansible 配置（inventory、vault、SSH）
│   ├── .vault_pass             # Vault 密码文件（git 忽略）
│   ├── inventories/            # production/、staging/
│   ├── playbooks/              # site.yml、healthcheck.yml
│   └── roles/                  # common、postgres、redis、backend、frontend、nginx
├── compose/                    # Docker Compose 部署变体
│   ├── dev-infra/              # 本地开发：仅 Postgres + Redis
│   ├── staging/                # 预发布：backend + Postgres + Redis
│   ├── backend-host/           # 跨主机：backend + Postgres + Redis（后端服务器）
│   └── frontend-host/          # 跨主机：nginx + SPA（前端服务器）
├── archive/                    # 已归档变体：single-server、debug-prod
├── mineru-api/                 # MinerU 文档解析部署说明
├── nginx/                      # Nginx 配置
│   └── linguaseeker.conf       # 站点配置
└── README.md
```

## 部署选项

| 模式 | 目录 | 用途 |
|------|------|------|
| Ansible 裸机 | `ansible/` | 生产和预发布服务器，systemd 服务管理 |
| 跨主机 Compose | `compose/backend-host/` + `compose/frontend-host/` | 前后端分离的 Docker 部署 |
| 预发布 Compose | `compose/staging/` | Docker 预发布验证 |
| 开发基础设施 | `compose/dev-infra/` | 本地开发（仅 Postgres + Redis，后端在主机运行） |

> 已归档变体见 `archive/`：`single-server/`（一体化 GPU 单机，被跨主机架构取代）、`debug-prod/`（生产配置本地调试）。

## 部署拓扑

```
Internet
    |
    v
+---------+
|  Nginx  |  TLS 终止、反向代理、X-API-Key 注入
|  :443   |
+----+----+
     |
     +---> Frontend (Vite + React SPA :3000)
     +---> Backend  (FastAPI :8000)
              |
              +---> PostgreSQL (:5432)
              +---> Redis (:6379)
              +---> External Inference Services（独立项目）
                     +-- Embedding (:8002)
                     +-- Rerank (:8003)
                     +-- Doc Parse (:44321)
```

## 系统要求

- Ubuntu 22.04+ / Debian 12+（Ansible 模式）或 CentOS 7.9+（单机 Compose）
- GPU 服务器需 NVIDIA 驱动 + CUDA（用于模型推理）
- Ansible：Ansible >= 2.14，需 `community.docker` collection
- Compose：Docker CE 20.10+，需 NVIDIA Container Toolkit

## 快速开始

**Ansible（生产环境）：**
```bash
cd deploy/ansible
ansible-playbook playbooks/site.yml
```

**Docker Compose（跨主机）：**
```bash
# 后端主机
docker compose -f deploy/compose/backend-host/docker-compose.yml \
               --env-file deploy/compose/backend-host/.env up -d
# 前端主机
docker compose -f deploy/compose/frontend-host/docker-compose.yml \
               --env-file deploy/compose/frontend-host/.env up -d
```

**仅开发基础设施：**
```bash
docker compose -f deploy/compose/dev-infra/docker-compose.yml up -d
```

详见各子目录 README。
