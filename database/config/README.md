# database/config

> Lingua Seeker 数据库基础设施的配置文件：PostgreSQL、Redis、Qdrant 和 Neo4j。

## 概述

本目录存放容器级环境变量和运行时配置文件，供 Podman/Docker Compose 服务使用。敏感文件（`.env`、`.env.neo4j`）已 git 忽略，绝不应提交到版本控制。

## 文件列表

| 文件 | 状态 | 描述 |
|------|------|------|
| `.env.example` | 已跟踪 | 包含所有必需环境变量和内联文档的模板 |
| `.env.example.jinja` | 已跟踪 | 生成 `.env.example` 的 Jinja2 模板 |
| `.env` | **git 忽略** | 本地活跃环境配置（含密钥） |
| `.env.neo4j` | **git 忽略** | Neo4j 认证字符串（`user/password` 格式） |
| `containers.conf` | 已跟踪 | Podman 容器运行时配置：代理绕过、cgroup v2、保留子网 `10.89.0.0/16` |
| `qdrant_config.json` | 已跟踪 | Qdrant 向量数据库 TLS 配置（默认禁用 TLS） |

## 环境变量

### PostgreSQL

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `POSTGRES_HOST` | `127.0.0.1` | 数据库主机 |
| `POSTGRES_PORT` | `5432` | 数据库端口 |
| `POSTGRES_DB` | `dev_lingua_seeker` | 数据库名称 |
| `POSTGRES_USER` | - | 超级用户 |
| `POSTGRES_PASSWORD` | - | 密码 |
| `POSTGRES_SCHEMA` | `lingua_seeker` | 应用 schema |
| `POSTGRES_POOL_SIZE` | `20` | 连接池大小 |
| `POSTGRES_MAX_OVERFLOW` | `30` | 最大溢出连接 |

### Redis

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_PASSWORD` | - | AUTH 密码 |
| `REDIS_DB` | `0` | 数据库编号 |

### Qdrant

| 变量 | 描述 |
|------|------|
| `QDRANT_HOST` | 主机地址 |
| `QDRANT_PORT` | HTTP 端口（默认 6333） |
| `QDRANT_GRPC_PORT` | gRPC 端口（默认 6334） |
| `QDRANT_API_KEY` | API 密钥 |
| `QDRANT_COLLECTION_NAME` | 集合名称（默认 `paper_chunks`） |
| `QDRANT_DIMENSION` | 向量维度（默认 1024） |

### 其他服务

| 变量 | 服务 | 描述 |
|------|------|------|
| `NEO4J_AUTH` | Neo4j | `user/password` 单变量格式 |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO | 对象存储凭证 |

## 设置

```bash
# 1. 复制模板
cp .env.example .env

# 2. 编辑本地凭证
vi .env

# 3. Neo4j（如使用图功能）
# 编辑 .env.neo4j，格式为 user/password
```

## 安全

- `.env` 和 `.env.neo4j` 已 git 忽略——**绝不提交密钥**
- 生产环境密钥应通过环境变量或 Ansible Vault 注入
- 生产密钥模板见 `deploy/ansible/inventories/production/group_vars/vault.yml.example`
