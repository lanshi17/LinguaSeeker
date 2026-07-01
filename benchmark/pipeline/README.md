# Pipeline Benchmark

> **状态：已弃用垫片。** 本包（`benchmark/pipeline/`）仅包含 2026-06-18 框架重构后的向后兼容导入垫片。运行器已移至 `benchmark.runners.pipeline_e2e`，证据指标已移至 `benchmark.core.evidence_metrics`。垫片将在重构 Phase 6 移除。

## 概述

完整管线基准测试（Phase 1-3），通过 HTTP API 提交病例报告 PDF，模拟前端上传流程。测量每阶段计时、成功率、证据质量指标和跨语言可靠性。Phase 4 不参与测试——管线在 `COMPLETED` 状态停止。

## 文件

| 文件 | 用途 |
|------|------|
| `benchmark.py` | 已弃用垫片 → `benchmark.runners.pipeline_e2e` |
| `evidence_metrics.py` | 已弃用垫片 → `benchmark.core.evidence_metrics` |
| `__init__.py` | 已弃用垫片，`__getattr__` 重定向 |
| `manifest.json.bak` | 遗留清单备份（不再是主要输入源） |
| `input/` | 按语言和文献类型组织的测试 PDF |
| `reports/` | 带时间戳的 JSON 报告（纳入 git） |

## 新模块位置

| 旧路径 | 新路径 | 用途 |
|--------|--------|------|
| `benchmark.pipeline.benchmark` | `benchmark.runners.pipeline_e2e` | 管线基准 HTTP 客户端 + 编排器 |
| `benchmark.pipeline.evidence_metrics` | `benchmark.core.evidence_metrics` | PG 证据指标采集 |

## 输入语言

`input/` 目录包含语言子目录，每种语言有文献类型文件夹：

| 语言 | 路径 |
|------|------|
| English | `input/en/` |
| Chinese | `input/zh/` |
| Japanese | `input/ja/` |
| Korean | `input/ko/` |
| Spanish | `input/es/` |
| Portuguese | `input/pt/` |
| Russian | `input/ru/` |
| French | `input/fr/` |
| German | `input/de/` |

每种语言目录包含：`case_report/`、`functional/`、`sequencing/`、`unclassified/`。

## 前置条件

以下服务必须运行：

| 服务 | 用途 |
|------|------|
| FastAPI server | HTTP API |
| PostgreSQL + pgvector | Phase 1 状态、Phase 3 术语 |
| Redis | 缓存层 |
| MinerU Cloud API | Phase 1 PDF 解析 |
| LLM（OpenAI 兼容） | Phase 2 翻译 + 提取 |
| Model Server（本地） | Phase 3 嵌入 + 重排序 |

## 快速开始

```bash
cd backend

# 干运行——列出输入 PDF 不执行
uv run python -m benchmark.runners.pipeline_e2e --dry-run

# 运行所有输入 PDF（默认并发：2）
uv run python -m benchmark.runners.pipeline_e2e

# 自定义设置
uv run python -m benchmark.runners.pipeline_e2e --base-url http://localhost:8000 --concurrency 1

# 按语言过滤
uv run python -m benchmark.runners.pipeline_e2e --lang en

# 限制前 N 个 PDF
uv run python -m benchmark.runners.pipeline_e2e --limit 3

# 使用 manifest.json
uv run python -m benchmark.runners.pipeline_e2e --source manifest

# 恢复：跳过最近报告中已通过的 PDF
uv run python -m benchmark.runners.pipeline_e2e --resume
```

## CLI 参数

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--base-url` | `http://localhost:8000` | 后端 API 基础 URL |
| `--concurrency` | `2` | 最大并发管线运行数（1-10） |
| `--dry-run` | 关闭 | 仅显示 PDF 列表 |
| `--resume` | 关闭 | 跳过最近报告中已通过的 PDF |
| `--limit N` | 全部 | 仅处理前 N 个 PDF |
| `--source` | `input` | PDF 来源：`input` 或 `manifest` |
| `--lang` | 全部 | 过滤到单语言 |

## 报告结构

报告写入 `reports/report_{timestamp}.json`，包含：

- `config`：运行配置
- `summary`：总计、通过、失败、跳过、耗时
- `by_language`：按语言统计
- `by_phase`：按阶段统计（phase_1/2/3 平均耗时和失败数）
- `by_evidence`：证据质量指标（数量和质量两层）
- `results`：每 PDF 详细结果

## 证据质量指标

### 层 1：数量

| 指标 | 描述 |
|------|------|
| `run_evidence_count` | `run_evidence_items` 中的总证据项 |
| `canonical_evidence_count` | 关联到本次运行的去重规范证据 |
| `avg_confidence` | 所有证据项的平均置信度 |
| `field_coverage` | 有证据的不同字段 ID 数 |

### 层 2：质量

| 指标 | 描述 |
|------|------|
| `found_rate` | found / 总证据项 |
| `source_grounding` | source_precision 分布：exact / corrected / ambiguous / no_source |
| `category_coverage` | 按类别（A-J）的字段覆盖 |
| `key_field_found` | 关键字段是否找到 |
