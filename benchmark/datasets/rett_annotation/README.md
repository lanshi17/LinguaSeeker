# Rett Syndrome Benchmark Annotation Tool

第三基准数据集（Rett 综合征 / MECP2）的 AI 辅助标注工具，支持 LLM 生成标注 + 人工文件审核。

## 概述

本工具为 [Lingua Seeker](../../AGENTS.md) 项目的第三基准数据集提供端到端标注流水线：

1. **PDF 解析** — 通过 MinerU 云 API 将 PDF 转为结构化 Markdown
2. **AI 标注生成** — LLM 提取基因、变异、临床特征等证据字段
3. **人工审核** — 文件审核模式，直接编辑 JSON 后通过 CLI 管理状态
4. **基准数据集** — 审核通过的条目进入 `ground_truth/` 供评估使用

**数据源**：`benchmark/literature_acquisition/downloads/rett/`，89 个 PDF，覆盖 11 种语言（en=25, fr=14, ja=14, zh=10, de=8, tr=7, es=4, ru=3, ko=2, it=1, pt=1）。

## 独立配置

本工具的配置**完全独立**于主项目的 `backend/config/` 体系，使用本地 `config.yaml` + `.env`：

```bash
cp .env.example .env
# 编辑 .env 填入 API key
```

- `config.yaml` — LLM 模型、MinerU API、路径等配置
- `.env` — API key（`ANNOTATION_LLM_API_KEY`、`ANNOTATION_MINERU_TOKEN`），不提交版本控制

## 安装

```bash
cd benchmark/datasets/rett_annotation
uv sync
```

## 使用

### 1. PDF 解析

```bash
# 全量（89 PDF，11 语言，MinerU 分批解析）
uv run python cli/parse_pdfs.py

# 指定语言和数量
uv run python cli/parse_pdfs.py --lang en zh --limit 10

# MinerU 失败时 fallback 到 pymupdf
uv run python cli/parse_pdfs.py --fallback

# 强制重新解析
uv run python cli/parse_pdfs.py --force
```

输出：`draft/rett_NNN/source.md` + `source.pdf` + `meta.json`

### 2. AI 标注生成

```bash
# 全量（所有未生成的 draft 条目，concurrency=3）
uv run python cli/generate_drafts.py

# 指定条目
uv run python cli/generate_drafts.py --entries rett_000 rett_005

# 调整并发数
uv run python cli/generate_drafts.py --concurrency 5

# 强制重新生成
uv run python cli/generate_drafts.py --force
```

输出：`draft/rett_NNN/expected.json`（标注草稿）

### 2.1 Catalog 驱动重新标注

主项目字段目录更新后，使用 `cli/catalog_reannotate.py` 按当前 `knowledges/evidence-field-catalog.json` 重新生成标注。该脚本只抽取 A-J 单篇文献字段，自动排除 K 类跨论文 GDV curation 字段。

```bash
# 快速字段覆盖扫描（不写入 expected.json）
uv run python cli/catalog_reannotate.py \
  --model gpt-5-nano \
  --limit 5 \
  --concurrency 2 \
  --report reports/gpt5_nano_field_scan_sample.json

# 真实 ground_truth 重标注（写入 ground_truth/approved/draft 中已有条目）
uv run python cli/catalog_reannotate.py \
  --model claude-opus-4-8 \
  --concurrency 3 \
  --write \
  --report reports/claude_opus_4_8_reannotation.json

# 429 或长文失败时，缩小输入块并降低输出上限后重跑指定条目
uv run python cli/catalog_reannotate.py \
  --model claude-opus-4-8 \
  --entries rett_020 rett_030 \
  --concurrency 1 \
  --max-tokens 16384 \
  --chunk-size 6000 \
  --write \
  --report reports/claude_opus_4_8_reannotation_retry_compact.json
```

输出：`ground_truth/rett_NNN/expected.json`、同步的 `approved/` 和 `draft/` 现有条目、`ground_truth/selection.json`、以及 `reports/*.json` 运行报告。空 `expected_evidence` 会被视为失败，不会覆盖现有标注。

### 3. 人工审核

审核人直接编辑 `draft/rett_NNN/expected.json`，然后通过 CLI 管理状态：

```bash
# 查看所有条目
uv run python cli/review_status.py --list

# 按状态筛选
uv run python cli/review_status.py --list --status draft

# 查看统计
uv run python cli/review_status.py --stats

# 审核通过
uv run python cli/review_status.py --approve rett_005 --reviewer "张三" --notes "变异位点已核实"

# 审核拒绝
uv run python cli/review_status.py --reject rett_010 --reason "PDF 不可读"

# 提升到 ground_truth（单条）
uv run python cli/review_status.py --promote rett_005

# 批量提升所有已审核条目
uv run python cli/review_status.py --promote-all
```

状态流转：`parsed → draft → approved → ground_truth`（或 `draft → rejected`）

## 目录结构

```
benchmark/annotation/
├── pyproject.toml          # 独立 uv 项目
├── config.yaml             # LLM / MinerU / 路径配置
├── .env.example            # API key 模板
├── src/
│   ├── config.py           # 独立配置加载器（Pydantic）
│   ├── models.py           # 数据模型（field_id 与主项目 catalog 一致）
│   ├── pdf_parser.py       # MinerU 云 API + pymupdf fallback
│   ├── annotator.py        # LLM 结构化标注生成
│   ├── manifest.py         # 状态追踪 manifest
│   ├── review.py           # 审核工作流
│   └── utils.py            # HGVS / MECP2 变异 / HPO 常量
├── cli/
│   ├── parse_pdfs.py       # PDF 解析
│   ├── generate_drafts.py  # AI 标注生成
│   └── review_status.py    # 审核管理
├── draft/                  # AI 生成的标注草稿
├── approved/               # 人工审核通过
├── rejected/               # 审核拒绝（审计留存）
└── ground_truth/           # 最终基准数据集
    ├── manifest.json       # 主清单
    ├── selection.json      # 条目索引
    └── rett_NNN/           # 每条数据
```

## Schema 兼容性

`expected.json` 的证据字段（`expected_evidence`）使用主项目当前字段目录中的 A-J 单篇文献字段：`knowledges/evidence-field-catalog.json` schema `2.0.0`，共 143 个 literature-extractable 字段。K 类 Gene-Disease Validity Curation 字段是跨论文 curation 字段，不进入 Rett 单篇文献标注。

每条 `expected_evidence` 记录对应文章中实际出现的一个字段，包含 `field_id`、`value`、`evaluation_type`（`precision_recall` 或 `precision_only`）、`candidates`（多变体时可选值列表）。不同文章提取到的字段数量和种类各不相同，不强制固定字段集；空字段不写入 `expected_evidence`。

**Rett 数据集特征**：
- 基因通常为 **MECP2**（HGNC:6992），非典型 Rett 可见 CDKL5/FOXG1
- 疾病为 **Rett syndrome**（MONDO:0010726），遗传方式 **XD**（X 连锁显性）
- 常见变异：p.R255X, p.R270X, p.R306C, p.T158M, p.R168X, p.R133C
- 蛋白结构域：MBD（aa 78–162）、TRD（aa 201–310）
- 临床特征：发育退化、手部刻板动作、癫痫、呼吸异常、小头畸形等

## 完整工作流示例

```bash
# 1. 环境准备
cd benchmark/datasets/rett_annotation
cp .env.example .env && $EDITOR .env
uv sync

# 2. 解析全部 PDF（MinerU API，约 10-30 分钟）
uv run python cli/parse_pdfs.py

# 3. AI 生成标注草稿（旧 55 字段 prompt；字段目录更新后优先使用 catalog_reannotate.py）
uv run python cli/generate_drafts.py

# 3b. 使用当前主项目字段目录重新标注 ground_truth
uv run python cli/catalog_reannotate.py --model claude-opus-4-8 --write

# 4. 人工审核（循环执行）
uv run python cli/review_status.py --list --status draft
# → 编辑 draft/rett_NNN/expected.json
uv run python cli/review_status.py --approve rett_000
uv run python cli/review_status.py --stats

# 5. 批量提升到 ground_truth
uv run python cli/review_status.py --promote-all

# 6. 验证结果
cat ground_truth/selection.json
```

## 依赖

| 依赖 | 用途 |
|------|------|
| `pydantic` + `pydantic-settings` | 数据模型 + 配置加载 |
| `pyyaml` | config.yaml 解析 |
| `loguru` | 日志 |
| `pymupdf` | PDF 解析 fallback |
| `langchain-core` + `langchain-openai` | LLM 调用 |
| `httpx` | MinerU API HTTP 客户端 |

通过 `uv` 独立管理，不影响主项目依赖。
