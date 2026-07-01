# Core 核心模块

> 平台核心配置与业务流程编排层，提供全局配置管理及各业务阶段的入口。

## 概述

`core` 是 ACMG Lingua 后端的核心包，包含全局配置管理（`config.py`）和四个业务阶段子模块。配置系统基于 Pydantic Settings，从 YAML 文件和环境变量加载，以单例模式提供全局访问。

## 结构

```
core/
├── __init__.py                  # 空包标识
├── config.py                    # 全局配置（Settings 单例、Provider 配置模型）
├── config_loader.py             # 向后兼容 shim，委托给 acmg_config_loader
└── ingest_and_digitize_data/    # 阶段 1：文献采集与解析
```

## 核心组件

### config.py — 全局配置中心

- **`Settings`**：根配置模型（Pydantic `BaseSettings`），包含所有子系统配置
- **Provider 配置**：`LLMConfig`、`ReasoningConfig`、`ChatLLMConfig`、`TranslationLLMConfig`、`EmbeddingConfig`、`RerankConfig`
- **基础设施配置**：`RedisConfig`、`PostgreSQLConfig`、`NetworkConfig`（代理/直连）、`WebSearchConfig`
- **文档解析配置**：`ParseDocumentConfig`、`MinerUConfig`
- **常量**：`PGVECTOR_DIMENSION=1024`、`BACKEND_ROOT`、`REPO_ROOT`
- **`get_config()`**：`@lru_cache` 单例访问器，返回全局 `Settings` 实例
- **`load_backend_config_into_env()`**：模块导入时自动从 YAML 加载配置到环境变量

### 业务阶段子模块

| 子模块 | 说明 |
|--------|------|
| `ingest_and_digitize_data/` | 阶段 1 — 文献采集（本地上传/在线获取）与文档解析（MinerU） |
| `cross_lingual_process_and_extract_evidence/` | 阶段 2 — 跨语言处理与证据提取 |
| `standardize_entities_and_align_knowledge/` | 阶段 3 — 实体标准化与知识对齐 |
| `visualize_evidence_with_expert_in_loop/` | 阶段 4 — 证据可视化与专家审核 |

## 数据流

```
YAML 配置 → load_backend_config_into_env() → Settings 实例
                                              ↓
                                    get_config() 单例
                                              ↓
                              各业务模块按需读取配置
```

## 使用

```python
from src.core.config import get_config

cfg = get_config()
# 访问 LLM 配置
print(cfg.llm.base_url, cfg.llm.model)
# 访问数据库连接串
print(cfg.get_postgresql_url("acmg_db"))
```
