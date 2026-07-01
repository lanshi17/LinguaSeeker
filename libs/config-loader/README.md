# acmg-config-loader

> 后端服务和推理服务共享的分层 YAML 配置加载器。按优先级顺序加载配置文件，将嵌套键扁平化为大写环境变量。已有环境变量始终优先（永不覆盖）。

## 概述

纯标准库 + PyYAML 实现的配置加载库，无 FastAPI / Pydantic / vLLM 依赖。通过 `hatchling` 构建，被 `backend/`（FastAPI 应用）和 `services/`（推理微服务）共同使用。

## 加载顺序

1. `backend/config/defaults/main.yaml` — 基础默认值
2. `backend/config/environments/<env>.yaml` — 环境覆盖（`ENVIRONMENT` 环境变量，默认 `development`）
3. `backend/config/vault/<env>.yaml` — 密钥（git 忽略）

每层在前一层基础上深度合并。

## 使用方法

```python
from pathlib import Path
from acmg_config_loader import load_backend_config_into_env

load_backend_config_into_env(Path("/path/to/backend"))
# 现在所有配置值都可用作大写环境变量
```

函数接受可选的 `environ` 字典用于测试；默认使用 `os.environ`。

## 目录结构

```
libs/config-loader/
├── src/
│   └── acmg_config_loader/
│       ├── __init__.py          # 公共 API：ConfigData、load_backend_config_into_env
│       └── loader.py            # 实现：深度合并 + 环境变量扁平化
├── tests/
│   ├── conftest.py
│   └── test_loader_isolated.py
├── pyproject.toml
├── uv.lock
└── .gitignore
```

## 依赖

| 依赖 | 版本 |
|------|------|
| `pyyaml` | `>=6.0.0` |

## 消费者

- `backend/`（FastAPI 应用）
- `services/`（推理微服务）

## 开发

```bash
cd libs/config-loader
uv pip install -e ".[dev]"
uv run pytest
```
