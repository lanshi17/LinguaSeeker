# benchmark/config — 基准测试集中配置

> 基准测试套件的集中配置管理。Ansible 渲染可调/密钥配置文件，`defaults.py` 是运行时代码常量的单一来源。

## 概述

本目录提供两种互补的配置机制：Ansible 渲染文件配置（模板+密钥）到消费者位置，以及 Python 运行时常量（`defaults.py`）供运行器代码导入。所有路径从 `BENCHMARK_ROOT` 解析，确保无论运行器 CWD 如何都正确。

## 快速开始

```bash
# 1. 安装 ansible-core
uv tool install ansible-core

# 2. 初始化密钥和 vault 密码（仅首次）
cd benchmark/config
openssl rand -base64 48 > .vault_pass && chmod 600 .vault_pass
cp vault/secrets.example.yml vault/secrets.yml
# ...编辑 vault/secrets.yml 填入真实值...
ansible-vault encrypt vault/secrets.yml

# 3. 渲染所有管理的配置文件到消费者位置
ansible-playbook playbooks/deploy-config.yml
```

重新运行 playbook 时，如果没有变更会报告 `changed=0`（幂等操作）。

运行时常量无需渲染——直接导入：

```python
from benchmark.config.defaults import DEFAULT_PIPELINE_BASE_URL, RETT_CONFIG_PATH
```

## 目录结构

```
benchmark/config/
├── __init__.py                       # 包标记 + 范围文档
├── defaults.py                       # 运行时代码常量（单一来源）
├── ansible.cfg                       # Inventory、roles_path、vault pass
├── inventories/local/
│   ├── hosts.yml                     # localhost 在 `benchmark` 分组
│   └── group_vars/benchmark.yml      # 渲染文件配置的非密钥变量
├── playbooks/deploy-config.yml       # 渲染所有文件配置
├── roles/
│   ├── rett_annotation_config/       # 渲染 config.yaml + .env（密钥通过 vault）
│   │   ├── tasks/main.yml
│   │   └── templates/{config.yaml.j2, .env.j2}
│   └── rett_acquisition_config/      # 部署静态 rett_config*.json（复制，非模板）
│       ├── tasks/main.yml
│       └── files/literature_acquisition/{rett_config.json, rett_config_02.json}
└── vault/
    ├── secrets.example.yml           # 占位符（已提交）
    └── secrets.yml                   # 真实密钥，ansible-vault 加密（git 忽略）
```

## 架构

### 流程 1：Ansible 渲染文件配置

```
group_vars/benchmark.yml（非密钥）   vault/secrets.yml（加密）
        rett_annotation_*                       rett_annotation_secrets
                |                                      |
        +-------+--------+                         （仅 .env）
        | deploy-config.yml |
        |  roles:           |
        |   rett_annotation_config   -> template -> config.yaml (0644) + .env (0600)
        |   rett_acquisition_config  -> copy     -> rett_config.json + rett_config_02.json
        +-----------+-------+
                    v
   benchmark/datasets/rett_annotation/         <- 由 src/config.py 读取
   benchmark/data/inputs/literature_acquisition/  <- 由 runners/literature_rett.py 读取
```

### 流程 2：运行时代码常量（`defaults.py`）

```python
from benchmark.config.defaults import (
    DEFAULT_PIPELINE_BASE_URL,   # "http://localhost:8000"
    PHASE2_TERMINAL_STATUSES,    # {"completed", "failed", "skipped"}
    FILTER_TIER1_KEEP_THRESHOLD, # 3
    DEFAULT_SEED_QUERIES,        # 25 个 Rett/MECP2 查询
    RETT_CONFIG_PATH,            # data/inputs/literature_acquisition/rett_config.json
)
```

## 管理的配置

### 文件配置（Ansible 渲染）

| 渲染文件 | 机制 | 消费者 |
|---------|------|--------|
| `benchmark/datasets/rett_annotation/config.yaml` | 模板 (0644) | `rett_annotation/src/config.py` |
| `benchmark/datasets/rett_annotation/.env` | 模板 (0600, no_log) | `rett_annotation/src/config.py` |
| `benchmark/data/inputs/literature_acquisition/rett_config.json` | 复制 (0644) | `runners/literature_rett.py` |
| `benchmark/data/inputs/literature_acquisition/rett_config_02.json` | 复制 (0644) | `runners/literature_rett.py` |

### 运行时常量（`defaults.py`）

| 常量 | 值 | 描述 |
|------|-----|------|
| `DEFAULT_PIPELINE_BASE_URL` | `http://localhost:8000` | 后端 API 端点 |
| `PHASE2_TERMINAL_STATUSES` | `{completed, failed, skipped}` | 终态集合 |
| `FILTER_TIER1_KEEP_THRESHOLD` | `3` | 变异过滤保留阈值 |
| `DEFAULT_SEED_QUERIES` | 25 个 Rett/MECP2 查询 | 文献获取种子查询 |
| `RETT_CONFIG_PATH` | `data/inputs/literature_acquisition/rett_config.json` | 规范配置路径 |

## 使用模式

```bash
# 更改 LLM 模型/端点
# 编辑 inventories/local/group_vars/benchmark.yml: rett_annotation_llm.model
ansible-playbook playbooks/deploy-config.yml

# 调整过滤阈值或管线 URL
# 直接编辑 benchmark/config/defaults.py——无需 playbook

# 轮换密钥
ansible-vault edit vault/secrets.yml
ansible-playbook playbooks/deploy-config.yml
```

## 测试

```bash
# Playbook 语法检查
ansible-playbook playbooks/deploy-config.yml --syntax-check

# 渲染 + 幂等性验证
ansible-playbook playbooks/deploy-config.yml
ansible-playbook playbooks/deploy-config.yml | tail -1   # changed=0

# 完整基准测试套件
cd backend && uv run pytest tests/benchmark/ -q
```
