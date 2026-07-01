# backend-host/config — 后端容器配置

> Docker Compose 跨主机部署中后端容器的运行时配置文件。

## 概述

本目录存放挂载到后端容器的配置文件，通过 Docker Compose 的 `volumes` 以只读方式注入容器。配置通过 `acmg-config-loader` 库加载，按优先级从低到高合并。

## 文件列表

| 文件 | 容器路径 | 用途 |
|------|---------|------|
| `production.yaml` | `/app/config/environments/production.yaml`（只读） | 环境特定应用配置（LLM 端点、数据库主机、CORS 等） |
| `vault/production.yaml` | `/app/config/vault/production.yaml`（只读） | 密钥（API 密钥、数据库密码） |

## 设置

```bash
cd deploy/compose/backend-host

# 从模板创建配置
cp ../../../backend/config/environments/production.yaml.example config/production.yaml
cp ../../../backend/config/vault/production.yaml.example config/vault/production.yaml
chmod 600 config/vault/production.yaml
```

编辑 `config/production.yaml` 设置环境特定值（CORS 来源、推理服务 URL 等）。编辑 `config/vault/production.yaml` 填入真实密钥（数据库密码、LLM API 密钥）。

## 配置加载顺序

后端按以下优先级加载配置（最高优先级在后）：

1. `backend/config/defaults/main.yaml`（应用默认值）
2. `config/environments/production.yaml`（环境覆盖，此处挂载）
3. `config/vault/production.yaml`（密钥，此处挂载）
4. `docker-compose.yml` 中的环境变量（最高优先级）

## Git 忽略

- `config/production.yaml` — git 忽略（本地覆盖）
- `config/vault/*.yaml` — git 忽略（密钥）
- `config/vault/README.md` — 已提交（此文件豁免）
