# acmg-config-loader

> 纯 Python 分层 YAML 配置加载器，供后端服务和推理服务共享使用。

## 概览

`acmg-config-loader` 从 `backend/config` 目录按层级加载 YAML 配置文件，合并后将缺失的键注入环境变量。加载顺序为：

1. `defaults/main.yaml` — 全局默认值
2. `environments/<env>.yaml` — 环境特定覆盖（`env` 取自 `ENVIRONMENT` 环境变量，默认 `development`）
3. `vault/<env>.yaml` — 敏感配置覆盖

已存在的环境变量**不会被覆盖**（环境变量优先级最高）。

## 公开 API

| 函数/类型 | 签名 | 说明 |
|-----------|------|------|
| `load_backend_config_into_env` | `(backend_root: Path, environ: MutableMapping[str, str] \| None = None) -> None` | 加载分层 YAML 配置并注入环境变量 |
| `ConfigData` | `TypeAlias = dict[str, Any]` | 配置数据类型别名 |

### 内部函数

| 函数 | 说明 |
|------|------|
| `_deep_merge(base, override)` | 递归合并嵌套字典，override 覆盖 base |
| `_flatten_and_set_env(data, environ, prefix)` | 将嵌套键展平为大写环境变量名（`SECTION_KEY`），仅设置不存在的键 |

## 架构

```
acmg_config_loader/
├── __init__.py     # 导出 ConfigData、load_backend_config_into_env
└── loader.py       # 核心加载逻辑
```

- 使用 `yaml.safe_load` 安全解析 YAML
- 嵌套键通过 `_` 连接并转大写（如 `database.host` → `DATABASE_HOST`）
- 列表值自动序列化为 JSON 字符串
- 依赖 `pyyaml`，导入失败时静默返回

## 使用示例

```python
from pathlib import Path
from acmg_config_loader import load_backend_config_into_env

# 加载配置到 os.environ
load_backend_config_into_env(Path("/path/to/backend"))

import os
print(os.environ.get("DATABASE_HOST"))
```

## 依赖

| 依赖 | 版本 | 说明 |
|------|------|------|
| `pyyaml` | `>=6.0.0` | YAML 解析 |
| `pytest` | `>=8.2.0` | 开发依赖（dev） |
