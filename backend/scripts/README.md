# Scripts

> 后端独立脚本——端到端管线测试、配置渲染、元数据回填和术语嵌入构建。

## Overview

`scripts/` 包含独立运行的 Python 脚本，不属于 FastAPI 应用的一部分。主要用于端到端集成测试、配置管理和数据维护。

## Structure

```
scripts/
├── e2e_full.py                    # 完整端到端管线（5 阶段可组合）
├── e2e_translate.py               # Phase 2 翻译端到端测试
├── e2e_extract_evidence.py        # Phase 2 证据提取端到端测试
├── e2e_standardize_entities.py    # Phase 3 实体标准化端到端测试
├── e2e_visualize_feedback.py      # Phase 4 专家审核端到端测试
├── render_config.py               # 分层 YAML 配置渲染
├── backfill_metadata.py           # 源文献元数据回填
└── build_terminology_embeddings.py # pgvector 术语嵌入构建
```

## Key Components

### `e2e_full.py`

完整管线端到端测试，支持 5 个可组合阶段：

| 阶段 | 功能 |
|------|------|
| `parse` | PDF 解析（MinerU 远程 API） |
| `translate` | 跨语言翻译 |
| `extract` | 双轨证据提取 |
| `standardize` | 实体标准化 + 知识对齐 |
| `visualize` | 专家审核反馈循环 |

```bash
cd backend
uv run python scripts/e2e_full.py --stages parse,translate,extract downloads/paper.pdf
```

### `e2e_*.py` 单阶段脚本

每个 `e2e_` 脚本对应管线的一个阶段，可独立运行用于调试：

```bash
uv run python scripts/e2e_translate.py downloads/paper.pdf
uv run python scripts/e2e_extract_evidence.py
uv run python scripts/e2e_standardize_entities.py
uv run python scripts/e2e_visualize_feedback.py --document-id <id>
```

### `render_config.py`

从分层 YAML 文件渲染配置模板，用于调试和导出：

```bash
uv run python scripts/render_config.py --env development
uv run python scripts/render_config.py --env production --output /tmp/config.yaml
```

加载顺序：`defaults/main.yaml` → `environments/<env>.yaml` → `vault/<env>.yaml`，通过 Jinja2 模板渲染为最终配置。

### `backfill_metadata.py`

从 ground truth 源文件回填 `source_documents.raw_metadata` 和 `literature_profiles.title`：

```bash
uv run python scripts/backfill_metadata.py
```

### `build_terminology_embeddings.py`

为术语子集构建 pgvector 嵌入向量：

```bash
uv run python scripts/build_terminology_embeddings.py
uv run python scripts/build_terminology_embeddings.py --entity-types disease phenotype
uv run python scripts/build_terminology_embeddings.py --source-dbs OMIM HPO MONDO
```

## Dependencies

| 依赖 | 用途 |
|------|------|
| `src.core.config` | 配置加载 |
| `src.core.*` | 核心业务逻辑（各阶段服务） |
| `src.dao.postgresql.*` | 数据库操作（回填脚本） |
| PyYAML / Jinja2 | 配置渲染 |
