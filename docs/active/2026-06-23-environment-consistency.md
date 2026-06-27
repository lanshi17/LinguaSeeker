# 跨服务环境一致性规范

> 生效日期：2026-06-23 | 状态：Active | 关联规则：AGENTS.md §28

## 1. 概述

本文档定义了前端、后端、模型服务、数据库、容器部署之间在开发（development）、预发布（staging）、生产（production）三个环境中的配置一致性规范。

## 2. 三环境策略

| 维度 | Development | Staging | Production |
|---|---|---|---|
| **用途** | 本地开发调试 | 预发布验证，镜像生产结构 | 正式服务 |
| **部署方式** | 本地 host + Docker Compose (infra only) | Docker Compose (full stack) | Ansible bare-metal/systemd |
| **调试模式** | `true` | `false` | `false` |
| **CORS** | `*` | staging 域名 | 生产域名 |
| **网络代理** | `http://127.0.0.1:7890`（可配） | 无 | 无 |

### 2.1 部署路径选择

- **Dev / Staging**：使用 Docker Compose（`deploy/compose/<env>/docker-compose.yml`）
- **Production**：使用 Ansible（`deploy/ansible/`）
- 两条路径的配置值必须保持一致，通过共享 `backend/config/` 层实现

## 3. 数据库一致性

### 3.1 命名规范

| 环境 | 数据库名 | Schema | 用户 | 密码来源 |
|---|---|---|---|---|
| Development | `dev_lingua_seeker` | `lingua_seeker` | `lingua_seeker` | `.env` 文件（必须提供，无默认值） |
| Staging | `staging_lingua_seeker` | `lingua_seeker` | `lingua_seeker` | `.env` 文件（必须提供，无默认值） |
| Production | `lingua_seeker` | `lingua_seeker` | `lingua_seeker` | Ansible vault / `.env` 文件 |

**关键规则**：
- Schema 在所有环境中统一为 `lingua_seeker`
- 数据库名仅在不同环境间区分（`dev_` / `staging_` / 无前缀）
- **禁止**在 `docker-compose.yml` 中硬编码密码默认值
- `database/config/.env` 不得作为凭证来源，统一使用 `backend/config/vault/`

### 3.2 迁移策略

Alembic 迁移从 `backend/src/core/config.py` 读取连接信息和 schema，因此在所有环境中使用相同的 `alembic upgrade head` 命令即可：

```bash
# Dev
cd backend && uv run alembic -c ../database/alembic.ini upgrade head

# Staging / Production (在容器内)
docker compose exec -T backend uv run alembic -c ../database/alembic.ini upgrade head
```

### 3.3 生产环境 Schema 迁移

如果生产数据库中存在旧 schema 名 `acmg_app`，部署前需执行：

```sql
ALTER SCHEMA acmg_app RENAME TO lingua_seeker;
ALTER USER acmg_app RENAME TO lingua_seeker;
```

## 4. 配置层级架构

### 4.1 后端配置加载顺序

```
1. backend/config/defaults/main.yaml       ← 基础结构默认值
2. backend/config/environments/<env>.yaml  ← 环境覆盖
3. backend/config/vault/<env>.yaml         ← 密钥（git-ignored）
4. 环境变量                                 ← 最高优先级
```

嵌套字段自动扁平化为大写环境变量（如 `fast_llm.model` → `FAST_LLM_MODEL`）。

### 4.2 前端环境变量层级

```
1. frontend/.env                    ← 安全默认值（committed）
2. frontend/.env.<mode>             ← 环境覆盖（committed）
3. frontend/.env.<mode>.local       ← 密钥（git-ignored）
```

Vite 自动按 mode 加载对应文件。非 `VITE_` 前缀变量（如 `API_KEY`）仅在 `vite.config.ts` 中可用，不会暴露给客户端。

### 4.3 模型服务配置

模型服务**不维护自己的配置文件**，通过 `acmg_config_loader` 共享 `backend/config/` 层：

```python
# services/model-server/app/config.py
load_backend_config_into_env(_BACKEND_ROOT)  # 加载 backend/config/ 到 os.environ
```

`Settings` 类从环境变量读取值，定义模型服务特有的默认值（端口、缓存路径等）。

## 5. 模型标识符一致性

所有环境使用相同的模型标识符：

| 服务 | 模型 ID | 维度 | max_model_len |
|---|---|---|---|
| Embedding | `BAAI/bge-m3` | 1024 | 8192 |
| Rerank | `BAAI/bge-reranker-v2-m3` | — | 8192 |
| Doc Parse (VLM) | `opendatalab/MinerU2.5-Pro-2604-1.2B` | — | — |

### 5.1 GPU 内存分配

- **Monolith 模式**（dev，单进程共享 GPU）：由模型服务 `Settings` 默认值控制
- **Multi-container 模式**（staging/prod，每个服务独立 GPU）：所有服务 `gpu_memory_utilization: 0.90`

### 5.2 模型服务端口

| 模式 | Embedding | Rerank | VLM | Doc Parse |
|---|---|---|---|---|
| Monolith（dev） | `:8001` | `:8001` | `:8001` | `:8001` |
| Multi-container（staging/prod） | `:8002` | `:8003` | `:44321` | `:8005` |

后端配置通过 `embedding.base_url` 和 `rerank.base_url` 指向正确端口。

## 6. 配置文件完整性清单

新增环境时，必须创建以下完整文件集：

### 6.1 后端

- [ ] `backend/config/environments/<env>.yaml`
- [ ] `backend/config/vault/<env>.yaml.example`
- [ ] `backend/config/vault/<env>.yaml`（实际密钥，git-ignored）

### 6.2 前端

- [ ] `frontend/.env.<mode>`（非密钥覆盖）
- [ ] `frontend/.env.<mode>.local`（密钥，git-ignored）

### 6.3 部署

- [ ] Docker Compose（dev/staging）：`deploy/compose/<env>/docker-compose.yml`
- [ ] Ansible inventory（staging/production）：
  - `deploy/ansible/inventories/<env>/hosts.yml`
  - `deploy/ansible/inventories/<env>/group_vars/all.yml`
  - `deploy/ansible/inventories/<env>/group_vars/vault.yml.example`

### 6.4 CI/CD

- [ ] GitHub Actions workflow 中包含对应环境的分支触发器
- [ ] `config-validation` workflow 覆盖新环境

## 7. CI/CD 验证

`config-validation.yml` 工作流在每次 PR 和 push 时自动验证：

1. **密钥检查**：tracked 文件中不含硬编码密钥
2. **Compose 校验**：所有 `docker-compose.yml` 文件语法正确
3. **Ansible 语法检查**：所有 inventory 的 playbook 通过 `--syntax-check`
4. **配置完整性**：三个环境的 config 和 vault example 文件均存在
5. **模型名一致性**：不存在过时的模型名引用

### 7.1 自动部署

- `dev` 分支 push → 自动部署到 **staging**
- `master` 分支 push → 自动部署到 **production**
- 手动 `workflow_dispatch` → 选择环境和镜像标签

## 8. 变更检查表

修改以下配置时，必须同步更新所有相关文件：

| 变更类型 | 需同步更新的文件 |
|---|---|
| 模型名称 | `defaults/main.yaml`, `config.py` Settings, `all.yml` (all inventories) |
| 数据库 schema | `defaults/main.yaml`, `config.py` (2处), `all.yml` (all inventories), compose files, `.env.example` |
| 新增配置字段 | `defaults/main.yaml`, 对应 `environments/*.yaml`, vault examples, `config.py` Settings |
| GPU 内存设置 | `defaults/main.yaml`, `all.yml` (all inventories), `config.py` Settings |
| 端口变更 | `environments/*.yaml`, compose files, Ansible `all.yml`, nginx templates |
