# Rett Syndrome Benchmark Annotation Tool

> Rett 综合征 / MECP2 第三基准数据集的 AI 辅助标注工具。支持 LLM 生成标注和基于文件的人工审查工作流。

## 概述

端到端的 Rett 综合征文献标注管线：PDF 解析（MinerU Cloud API）→ AI 标注（LLM 提取基因、变异、临床特征等证据字段）→ 人工审查（直接编辑 JSON，CLI 管理状态）→ 基准数据集（批准条目进入 `ground_truth/`）。

**数据来源**：`benchmark/literature_acquisition/downloads/rett/`，89 篇 PDF，覆盖 11 种语言（en=25、fr=14、ja=14、zh=10、de=8、tr=7、es=4、ru=3、ko=2、it=1、pt=1）。

## 独立配置

本工具的配置**完全独立**于主项目的 `backend/config/` 系统，使用本地 `config.yaml` + `.env`：

- `config.yaml` — LLM 模型、MinerU API、路径
- `.env` — API 密钥（`ANNOTATION_LLM_API_KEY`、`ANNOTATION_MINERU_TOKEN`），不纳入版本控制

配置通过 `benchmark/config/` 的 Ansible 管理。

## 源码布局

```
src/
  config.py              # 独立配置加载器（Pydantic + YAML + .env）
  models.py              # Pydantic 模式：RettExpectedJson、ExpectedEvidenceField 等
  pdf_parser.py          # MinerU Cloud API + pymupdf 备选
  annotator.py           # LLM 驱动的标注生成（langchain-core + langchain-openai）
  catalog_annotation.py  # 目录感知的 prompt 构建和 expected.json 构造
  manifest.py            # 状态跟踪清单
  review.py              # 审查工作流逻辑
  utils.py               # HGVS / MECP2 变异 / HPO 常量
```

## 目录结构

```
rett_annotation/
  pyproject.toml          # 独立 uv 项目
  config.yaml             # LLM / MinerU / 路径配置
  .env.example            # API 密钥模板
  src/                    # 核心库代码
  cli/                    # CLI 入口点
  tests/                  # 单元测试
  draft/                  # AI 生成的标注草稿
  approved/               # 人工审查通过
  rejected/               # 已拒绝（审计跟踪）
  ground_truth/           # 最终基准数据集
    manifest.json         # 主清单
    selection.json        # 条目索引
    rett_NNN/             # 每条目数据
  reports/                # 运行报告
```

## 使用方法

### 1. PDF 解析

```bash
uv run python cli/parse_pdfs.py                    # 全部 89 篇
uv run python cli/parse_pdfs.py --lang en zh --limit 10
uv run python cli/parse_pdfs.py --fallback         # MinerU 失败时用 pymupdf
```

### 2. AI 标注生成

```bash
uv run python cli/generate_drafts.py               # 所有未草拟条目
uv run python cli/generate_drafts.py --entries rett_000 rett_005
```

### 2.1 目录驱动重新标注

```bash
uv run python cli/catalog_reannotate.py \
  --model claude-opus-4-8 --concurrency 3 --write \
  --report reports/claude_opus_4_8_reannotation.json
```

### 3. 人工审查

```bash
uv run python cli/review_status.py --list                    # 列出所有条目
uv run python cli/review_status.py --stats                   # 统计信息
uv run python cli/review_status.py --approve rett_005 --reviewer "Name"
uv run python cli/review_status.py --reject rett_010 --reason "Unreadable PDF"
uv run python cli/review_status.py --promote rett_005        # 提升到 ground_truth
uv run python cli/review_status.py --promote-all             # 批量提升
```

状态流：`parsed -> draft -> approved -> ground_truth`（或 `draft -> rejected`）

### 额外 CLI 工具

| 脚本 | 用途 |
|------|------|
| `cli/filter_entries.py` | 按条件过滤条目 |
| `cli/review_backfill.py` | 回填审查元数据 |
| `cli/catalog_reannotate.py` | 使用当前字段目录重新标注 |

## Schema 兼容性

`expected.json` 证据字段使用主项目的字段目录（`knowledges/evidence-field-catalog.json` schema 2.0.0）：A-J 类 143 个文献可提取字段。K 类基因-疾病有效性审查字段为跨论文字段，已排除。

## Rett 数据集特征

- 基因：**MECP2**（HGNC:6992）；非典型 Rett 可能显示 CDKL5/FOXG1
- 疾病：**Rett 综合征**（MONDO:0010726），遗传方式：**XD**（X 连锁显性）
- 常见变异：p.R255X、p.R270X、p.R306C、p.T158M、p.R168X、p.R133C
- 蛋白结构域：MBD（aa 78-162）、TRD（d aa 201-310）

## 测试

```bash
uv run pytest tests/ -v
```
