# vault — Compose 后端密钥配置

> 挂载到后端容器的加密密钥文件目录。

## 概述

本目录存放后端容器运行时所需的密钥配置文件，以只读方式挂载到容器中。文件已 git 忽略（`*.yaml` 排除，本 README 豁免）。

## 文件

| 文件 | 容器路径 | 权限 |
|------|---------|------|
| `production.yaml` | `/app/config/vault/production.yaml`（只读） | 0600 |

## 必需密钥

从项目模板创建 `production.yaml`：

```bash
cp ../../../backend/config/vault/production.yaml.example production.yaml
chmod 600 production.yaml
```

vault 文件必须至少包含：

- `postgres.password` — PostgreSQL 密码
- `redis.password` — Redis 密码（如已配置）
- `fast_llm.api_key` — Fast LLM API 密钥
- `reasoning_llm.api_key` — Reasoning LLM API 密钥

## 安全

- 本目录已 git 忽略（`*.yaml` 排除，本 README 豁免）
- 文件以只读方式挂载到容器
- 绝不将真实密钥提交到版本控制
- Ansible 部署路径的等效文件为 `deploy/ansible/inventories/<env>/group_vars/vault.yml`（使用 `ansible-vault` 加密）
