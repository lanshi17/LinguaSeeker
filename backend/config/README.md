# Config

> 分层配置管理系统——defaults → environment → vault 三层合并，敏感信息与结构配置分离。

## Overview

`config/` 管理 Lingua Seeker 后端的全部配置。采用三层合并策略：基础默认值 → 环境特定覆盖 → 敏感信息注入。配置通过 `src.core.config.Settings`（Pydantic Settings）在启动时加载，敏感信息（API keys、密码）与结构配置物理隔离。

## Structure

```
config/
├── defaults/                  # 基础默认值（所有环境共享，可提交）
│   └── main.yaml              #   LLM、数据库、网络、推理服务等默认配置
├── environments/              # 环境特定结构配置（可提交）
│   ├── development.yaml       #   开发环境覆盖（LLM 端点、数据库名、代理）
│   ├── production.yaml        #   生产环境覆盖
│   ├── production.yaml.example
│   └── staging.yaml           #   预发布环境覆盖
├── vault/                     # 敏感信息（git-ignored，不提交）
│   ├── development.yaml       #   开发环境密钥
│   ├── production.yaml        #   生产环境密钥
│   ├── development.yaml.example
│   ├── production.yaml.example
│   └── staging.yaml.example
├── templates/                 # 配置渲染模板（调试/导出用）
│   └── config.yaml.j2         #   Jinja2 模板，合并三层变量
└── README.md
```

## Key Components

### 加载顺序（优先级从低到高）

1. `defaults/main.yaml` — 基础默认值（模型、端口、连接池等）
2. `environments/<env>.yaml` — 环境覆盖（`development` / `staging` / `production`）
3. `vault/<env>.yaml` — 敏感信息（API keys、密码、签名密钥）
4. 环境变量 — 最高优先级，覆盖所有 YAML 配置

### `defaults/main.yaml`

定义全部配置项的结构化默认值：

| 配置块 | 说明 |
|--------|------|
| `fast_llm` / `reasoning_llm` / `chat_llm` / `translation_llm` | 四类 LLM 模型配置 |
| `embedding` / `rerank` | 向量嵌入和重排序模型（含远程 fallback） |
| `postgres` / `redis` | 数据库和缓存连接参数 |
| `mineru` | MinerU 文档解析服务配置 |
| `web_search` | 网络搜索服务（Firecrawl、Tavily、SerpAPI） |
| `network` | HTTP 代理和域名绕过规则 |
| `unpaywall` / `pubmed` / `base` / `core` | 文献采集服务提供商配置 |

### `vault/`

存放 API keys、数据库密码、session 签名密钥等敏感信息。每个环境有对应的 `.yaml` 文件和 `.yaml.example` 模板。`vault/*.yaml` 在 `.gitignore` 中排除。

关键敏感配置：
- `session_signing_key` — HMAC-SHA256 会话签名密钥（必须与 `api_key` 不同）
- `fast_llm.api_key` / `reasoning_llm.api_key` 等 — LLM 服务 API keys（支持 `api_keys` 列表用于密钥池轮转）
- `postgres.user` / `postgres.password` — 数据库凭证

### 字段命名约定

嵌套字段展平为环境变量：`fast_llm.model` → `FAST_LLM_MODEL`，`cors_origins` → `CORS_ORIGINS`。

## Usage / Patterns

### 运行时加载

配置在 `src.core.config` 模块导入时自动加载：

```python
from src.core.config import get_config
cfg = get_config()
print(cfg.fast_llm.model)
```

### 渲染完整配置（调试）

```bash
uv run python scripts/render_config.py --env development
```

### 新增配置项

1. 在 `defaults/main.yaml` 添加默认值
2. 在 `src.core.config.Settings` 中添加对应的 Pydantic 字段
3. 如需环境差异，在 `environments/<env>.yaml` 中覆盖

## Dependencies

| 依赖 | 用途 |
|------|------|
| `acmg-config-loader` (libs/config-loader) | 分层 YAML 加载和环境变量注入 |
| `pydantic-settings` | `Settings` 基类和环境变量绑定 |
| PyYAML | YAML 解析 |
| Jinja2 | 配置模板渲染（仅 `render_config.py`） |
