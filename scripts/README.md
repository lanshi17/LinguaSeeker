# Scripts

> LinguaSeeker 项目级运维脚本——数据管理、清理、生成和开发服务器。从项目根目录运行。

## 概述

本目录包含项目级操作脚本，涵盖数据导入/清理/分析/生成、开发服务器启动、以及 Docker 镜像构建推送。所有 Python 脚本通过 `uv run` 使用后端虚拟环境，Shell 脚本自动切换到正确目录。

## 目录结构

```
scripts/
├── data/
│   ├── import/                           数据导入脚本
│   │   ├── import_benchmark_ground_truth.py   导入基准真值（双轨可追溯性）
│   │   ├── import_terminology.py              导入术语数据库到 PostgreSQL
│   │   ├── backfill_variant_ids.py            回填变异标识符
│   │   └── reindex_clinvar_aliases.py         重建 ClinVar 别名索引
│   ├── cleanup/                          数据清理和重构脚本
│   │   ├── delete_unmapped_entities.py        删除未映射的基因和变异
│   │   ├── delete_incomplete_gene_variant_groups.py  删除不完整的基因-变异组
│   │   ├── refactor_benchmark_imports.py      重构基准模块导入
│   │   └── refactor_benchmark_reports.py      重构基准报告文件路径
│   ├── analyze/                          日志/数据分析脚本
│   │   └── analyze_logs.py                   drain3 日志模板聚类挖掘
│   └── generate/                         数据生成脚本
│       └── generate_ground_truth_pdfs.py     翻译真值文献并生成 PDF
├── dev/                                开发服务器脚本
│   ├── start_backend_dev.sh                启动 FastAPI 后端（热重载 + 可选基础设施）
│   └── start_frontend_dev.sh               启动 Vite 前端开发服务器
├── deploy/                             部署镜像脚本
│   └── build_push_backend_image.sh        构建、冒烟测试和推送后端 Docker 镜像
├── reconstruct_phase1_metadata.py        重建 Phase 1 元数据
├── refresh_business_read_models.py       刷新业务读模型
├── rerun_phase2_phase3.py                重跑 Phase 2 + Phase 3
├── rerun_phase3.py                       重跑 Phase 3
├── reset_lingua_seeker_business_results.sql  重置业务结果 SQL
├── run_all_shards.sh                     运行所有分片
├── run_benchmark_b8.sh                   运行 Benchmark B8
├── run_benchmark_shard.sh                运行基准分片
└── README.md
```

## 脚本清单

### 数据导入

| 脚本 | 语言 | 用途 |
|------|------|------|
| `import_benchmark_ground_truth.py` | Python | 导入基准真值，支持双轨可追溯性（原文+译文） |
| `import_terminology.py` | Python | 导入本地术语文件（hgnc、omim、hpo、clingen、clinvar）到 PostgreSQL |
| `backfill_variant_ids.py` | Python | 回填已有数据的变异标识符 |
| `reindex_clinvar_aliases.py` | Python | 重建 ClinVar 别名索引以优化搜索 |

### 数据清理

| 脚本 | 语言 | 用途 |
|------|------|------|
| `delete_unmapped_entities.py` | Python | 删除数据库中未映射的基因和变异 |
| `delete_incomplete_gene_variant_groups.py` | Python | 删除缺少基因或变异字段的证据项 |
| `refactor_benchmark_imports.py` | Python | 目录重组后重构基准模块导入 |
| `refactor_benchmark_reports.py` | Python | 目录重组后重构基准报告路径 |

### 数据分析

| 脚本 | 语言 | 用途 |
|------|------|------|
| `analyze_logs.py` | Python | 使用 drain3 模板挖掘聚类后端日志中的 WARNING/ERROR 模式 |

```bash
# 挖掘所有 WARNING/ERROR 模式
cd backend && uv run python ../scripts/data/analyze/analyze_logs.py

# 限制最近日志，显示更多详情
cd backend && uv run python ../scripts/data/analyze/analyze_logs.py --since 2026-06-23 --top 40

# 输出 JSON 报告
cd backend && uv run python ../scripts/data/analyze/analyze_logs.py --json reports/log-analysis.json
```

### 数据生成

| 脚本 | 语言 | 用途 |
|------|------|------|
| `generate_ground_truth_pdfs.py` | Python | 通过 LLM API 将真值文献翻译为 zh/ja/ko/fr/de/es，使用 weasyprint 生成 PDF |

### 开发服务器

| 脚本 | 语言 | 用途 |
|------|------|------|
| `start_backend_dev.sh` | Shell | 启动 uvicorn 热重载，支持 `--with-infra` 启动 Postgres + Redis 容器 |
| `start_frontend_dev.sh` | Shell | 启动 Vite 前端开发服务器 |

```bash
# 后端（默认端口 8000）
./scripts/dev/start_backend_dev.sh
./scripts/dev/start_backend_dev.sh --port 8001          # 自定义端口
./scripts/dev/start_backend_dev.sh --with-infra          # 先启动 Postgres + Redis

# 仅基础设施管理
./scripts/dev/start_backend_dev.sh --infra up -d
./scripts/dev/start_backend_dev.sh --infra down

# 前端
./scripts/dev/start_frontend_dev.sh
```

### 部署脚本

| 脚本 | 语言 | 用途 |
|------|------|------|
| `deploy/build_push_backend_image.sh` | Shell | 构建 `backend/Dockerfile`、验证运行时镜像、推送到 Docker Hub |

```bash
# 默认：docker.io/[redacted-user]47/lingua-seeker-backend:latest
./scripts/deploy/build_push_backend_image.sh

# 自定义标签
./scripts/deploy/build_push_backend_image.sh --tag 20260629

# 构建和冒烟测试，不推送
./scripts/deploy/build_push_backend_image.sh --no-push
```

### 管线重跑脚本

| 脚本 | 用途 |
|------|------|
| `reconstruct_phase1_metadata.py` | 重建 Phase 1 元数据 |
| `refresh_business_read_models.py` | 刷新业务 CQRS 读模型 |
| `rerun_phase2_phase3.py` | 重跑 Phase 2 + Phase 3 |
| `rerun_phase3.py` | 仅重跑 Phase 3 |
| `reset_lingua_seeker_business_results.sql` | 重置业务结果的 SQL 脚本 |
| `run_all_shards.sh` | 运行所有基准分片 |
| `run_benchmark_b8.sh` | 运行 Benchmark B8 |
| `run_benchmark_shard.sh` | 运行单个基准分片 |

## 前置条件

- **uv** — Python 依赖管理
- **bun** — 前端依赖管理
- **PostgreSQL** — 数据脚本需运行中且已迁移
- **推理服务** — 嵌入生成需运行中
- **LLM API** — `generate_ground_truth_pdfs.py` 需已配置
- **weasyprint** — PDF 生成需要（通过后端依赖安装）

## 注意事项

- 所有 Python 脚本通过 `uv run` 使用后端虚拟环境，无需单独安装依赖
- Shell 脚本自动 `cd` 到相对于自身位置的正确目录
- `start_backend_dev.sh` 监听 `src/` 和 `app/` 变更，排除日志、pycache 和迁移以避免管线执行期间的虚假重载
- `import_terminology.py` 和 `delete_unmapped_entities.py` 使用 `loguru` 结构化日志输出到 stderr
