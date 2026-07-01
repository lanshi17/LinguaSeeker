# deploy/ansible — 生产部署

> Lingua Seeker 生产和预发布环境的 Ansible 自动化配置与部署。

## 概述

基于 Ansible 的裸机配置管理和部署系统，支持多服务器拓扑（web/app/db 分组）和单机部署。通过 systemd 管理服务生命周期，支持 Let's Encrypt TLS 自动证书、PostgreSQL 自动备份、以及 GPU 推理容器部署。

## 目录结构

```
deploy/ansible/
├── ansible.cfg                              Ansible 配置（inventory、vault、SSH）
├── .vault_pass                              Vault 密码文件（git 忽略）
├── .gitignore                               忽略 .vault_pass、*.retry
├── inventories/
│   ├── production/
│   │   ├── hosts.yml                        多服务器 inventory（web/app/db 分组）
│   │   ├── hosts-single-server.yml.example  单机 inventory 模板
│   │   └── group_vars/
│   │       ├── all.yml                      结构化配置（可提交）
│   │       ├── vault.yml.example            密钥模板
│   │       └── .gitignore                   排除 vault.yml
│   └── staging/
│       ├── hosts.yml                        预发布 inventory
│       └── group_vars/
│           ├── all.yml                      预发布结构化配置
│           └── vault.yml.example            预发布密钥模板
├── playbooks/
│   ├── site.yml                             主部署 playbook
│   └── healthcheck.yml                      部署后验证
└── roles/
    ├── common/                              基础包、deploy 用户、sysctl、logrotate
    ├── postgres/                            PostgreSQL 16 Docker + 每日备份
    ├── redis/                               Redis 8.0 Docker
    ├── backend/                             FastAPI 后端（uv + systemd）
    ├── frontend/                            Vite + React SPA（bun build + systemd）
    └── nginx/                               Nginx 反向代理 + Let's Encrypt TLS
```

每个角色遵循标准 Ansible 结构：`tasks/`、`handlers/`、`defaults/`、`templates/`。

## 前置条件

- 控制机安装 Ansible >= 2.14
- 目标主机：Ubuntu 22.04+ / Debian 12+，SSH 访问
- 所有主机需 `deploy` 用户且有 sudo 权限
- `community.docker` collection（`ansible-galaxy collection install community.docker`）
- GPU 主机需 NVIDIA 驱动 + CUDA

## 快速开始

### 1. 配置 Inventory

编辑 `inventories/production/hosts.yml` 替换占位 IP：

```yaml
web-01:
  ansible_host: "203.0.113.10"
app-01:
  ansible_host: "203.0.113.20"
db-01:
  ansible_host: "203.0.113.30"
```

单机部署：
```bash
cp inventories/production/hosts-single-server.yml.example inventories/production/hosts.yml
```

### 2. 配置密钥

```bash
cp inventories/production/group_vars/vault.yml.example inventories/production/group_vars/vault.yml
ansible-vault encrypt inventories/production/group_vars/vault.yml
echo "your-vault-password" > .vault_pass
chmod 600 .vault_pass
```

### 3. 部署

```bash
cd deploy/ansible
ansible-galaxy collection install community.docker

# 完整部署
ansible-playbook playbooks/site.yml

# 部署特定组件
ansible-playbook playbooks/site.yml --tags infra         # DB + Redis
ansible-playbook playbooks/site.yml --tags backend        # 仅后端
ansible-playbook playbooks/site.yml --tags frontend       # 前端 + Nginx
ansible-playbook playbooks/site.yml --tags model-server   # 仅推理服务

# 干运行
ansible-playbook playbooks/site.yml --check --diff

# 部署后健康检查
ansible-playbook playbooks/healthcheck.yml
```

## 主机拓扑

| 分组 | 主机 | 服务 | 端口 |
|------|------|------|------|
| `web` | web-01 | Nginx (:80/:443)、Frontend (:3000) | 80、443、3000 |
| `app` | app-01 | Backend (FastAPI :8000)、推理服务 (:8002-8003,:44321) | 8000、8002-8003、44321 |
| `db` | db-01 | PostgreSQL 16 (:5432)、Redis 8.0 (:6379) | 5432、6379 |

## 角色说明

| 角色 | 功能 |
|------|------|
| **common** | 安装基础包、创建 deploy 用户、配置 sysctl 和 logrotate |
| **postgres** | Docker 运行 PostgreSQL 16（pgvector），每日 03:00 自动备份，30 天保留 |
| **redis** | Docker 运行 Redis 8.0，AOF 持久化，512MB 内存限制 |
| **backend** | 安装 uv、rsync 同步代码、部署 systemd 服务（`acmg-backend`） |
| **frontend** | 安装 bun、构建 SPA、部署 systemd 服务（`acmg-frontend`） |
| **nginx** | Nginx + Certbot，Let's Encrypt TLS，安全头（HSTS、CSP 等） |
| **推理服务** | 独立 Docker 容器：embedding(:8002)、rerank(:8003)、doc-parse(:44321) |

## 关键特性

- **TLS / Let's Encrypt** — 首次部署仅 HTTP，certbot 获取证书后切换 TLS，自动续期
- **自动备份** — PostgreSQL 每日 03:00 cron 备份，存储于 `/opt/lingua-seeker-data/postgres-backups/`
- **安全性** — `vault.yml` 使用 `ansible-vault` 加密，systemd 服务运行于 `NoNewPrivileges` + `ProtectSystem=strict`
- **两种 Nginx 拓扑** — 单主机或分主机（独立前端/后端域名）

## 维护

```bash
# 检查服务状态
ansible app -m systemd -a "name=acmg-backend" --become
ansible web -m systemd -a "name=acmg-frontend" --become

# 查看日志
ansible app -m shell -a "journalctl -u acmg-backend -n 50 --no-pager" --become

# 健康检查
ansible-playbook playbooks/healthcheck.yml

# 滚动重启（仅后端）
ansible-playbook playbooks/site.yml --tags backend
```
