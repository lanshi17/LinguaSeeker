# database/seeds

> 数据库种子脚本预留目录，用于填充初始参考数据。

## 概述

本目录当前为空（仅 `.gitkeep`）。种子数据通过运行时脚本加载，而非静态 SQL 文件。

## 当前状态

种子数据通过术语导入脚本加载：

```bash
# 导入术语数据库文件到 PostgreSQL
uv run python scripts/data/import/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05

# 导入特定来源
uv run python scripts/data/import/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --sources hgnc clinvar

# 导入并生成 pgvector 嵌入
uv run python scripts/data/import/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --generate-embeddings
```

## 用途

本目录计划存放 SQL 或 Python 种子脚本，用于填充：
- 默认系统配置
- 初始用户账户（仅开发环境）
- 参考/查找数据

种子脚本应为幂等操作（可安全重复运行）。
