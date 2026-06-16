# Rett Syndrome Benchmark Annotation Tool

第三基准数据集（Rett 综合征 / MECP2）的 AI 辅助标注工具，支持 LLM 生成标注 + 人工文件审核。

## 概述

本工具为 [Cross Evidence](../../AGENTS.md) 项目的第三基准数据集提供端到端标注流水线：

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
cd benchmark/annotation
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

`expected.json` 的 `expected_evidence` 字段完全使用主项目 `EVIDENCE_FIELD_SPECS` 目录（A–J 类别，138 字段），与 fused dataset 格式兼容：

| field_id | 类别 | 说明 | evaluation_type |
|----------|------|------|-----------------|
| `A.gene_symbol` | A. 变异信息 | MECP2 | precision_recall |
| `A.gene_disease_relationship` | A. 变异信息 | causative | precision_recall |
| `A.variant_hgvs_c` | A. 变异信息 | c. 编码变异 | precision_only |
| `A.variant_hgvs_p` | A. 变异信息 | p. 蛋白变异 | precision_only |
| `A.variant_type` | A. 变异信息 | missense/nonsense/frameshift 等 | precision_only |
| `A.functional_domain_or_hotspot` | A. 变异信息 | MBD/TRD | precision_only |
| `B.disease_diagnosis` | B. 病例/表型 | Rett syndrome | precision_recall |
| `B.mode_of_inheritance_reported` | B. 病例/表型 | XD | precision_recall |
| `B.hpo_terms` | B. 病例/表型 | HPO 术语 | precision_recall |
| `B.clinical_phenotypes` | B. 病例/表型 | 临床表型 | precision_recall |
| `B.sex` | B. 病例/表型 | 患者性别 | precision_recall |
| `B.age_of_onset` | B. 病例/表型 | 发病年龄 | precision_recall |
| `C.de_novo_status` | C. 家系/遗传 | de novo 状态 | precision_recall |

Rett 综合征特有字段：
- 基因固定为 **MECP2**（HGNC:6992），偶见 CDKL5/FOXG1（非典型 Rett）
- 疾病固定为 **Rett syndrome**（MONDO:0010726）
- 遗传方式 **XD**（X 连锁显性）
- 常见变异：p.R255X, p.R270X, p.R306C, p.T158M, p.R168X, p.R133C
- 蛋白结构域：MBD（aa 78–162）、TRD（aa 201–310）

## 完整工作流示例

```bash
# 1. 环境准备
cd benchmark/annotation
cp .env.example .env && $EDITOR .env
uv sync

# 2. 解析全部 PDF（MinerU API，约 10-30 分钟）
uv run python cli/parse_pdfs.py

# 3. AI 生成标注草稿（约 10-20 分钟）
uv run python cli/generate_drafts.py

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
