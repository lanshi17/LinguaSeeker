# ClinVar Fused Benchmark（数据集 2）

> ClinGen 提供基因-疾病金标签，ClinVar 提供变异级候选金标签。融合数据集在 GeneSymbol + MONDO ID 上连接两个来源，生成包含基因-疾病字段（P/R/F1）和变异字段（precision-only）的条目。

## 概述

本数据集通过融合 ClinGen 基因-疾病有效性和 ClinVar 变异数据构建基准条目。每个融合条目包含基因-疾病评估层（完整 P/R/F1）和变异评估层（仅精确率）。支持多语言翻译和 PDF 生成。

## 文件列表

| 文件 | 用途 |
|------|------|
| `select_fused_entries.py` | 选择条目：ClinGen Definitive/Strong × ClinVar ≥2-star Pathogenic/LP |
| `fetch_variant_literature.py` | EuropePMC 搜索每个融合条目的开放获取文献 |
| `download_articles.py` | 通过 NCBI efetch 下载 PMC 全文，JATS XML 转 Markdown |
| `translate_to_multilingual.py` | 使用 LLM 将 source.md 翻译为 zh/ja/ko |
| `generate_pdfs.py` | 从源 Markdown 生成 PDF（支持 CJK，使用 Noto Sans CJK） |
| `evaluate_fused.py` | 对预处理 Phase 2 提取数据的三层评估 |
| `hgvs_normalize.py` | HGVS 标准化：转录本前缀移除、三字母氨基酸转换、终止密码子标准化 |

## 快速开始

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua

# 1. 选择条目
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.select_fused_entries

# 2. 获取文献
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.fetch_variant_literature

# 3. 下载 PMC 全文
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.download_articles

# 4. 翻译为多语言（zh/ja/ko）
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.translate_to_multilingual --langs zh ja ko

# 5. 生成 PDF
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.generate_pdfs --langs en zh ja ko

# 6. 评估
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.evaluate_fused --write
```

所有脚本支持 `--limit N` 和 `--entries fused_000 fused_001` 进行子集运行。

## 评估层

### 层 1：基因-疾病（完整 P/R/F1）

| 字段 | 匹配方式 |
|------|---------|
| `A.gene_symbol` | 精确匹配 |
| `B.disease_diagnosis` | 多策略：精确 → 子串 → 词重叠（≥60%）→ 字段标准化 |
| `A.gene_disease_relationship` | 枚举匹配 |
| `B.mode_of_inheritance_reported` | 枚举匹配 + 字段特定标准化 |

### 层 2：变异（仅精确率）

| 字段 | 匹配方式 |
|------|---------|
| `A.variant_hgvs_c` | 标准化候选匹配 |
| `A.variant_hgvs_p` | 标准化候选匹配 |
| `A.variant_type` | 枚举匹配 |
| `J.clinvar_assertion` | 枚举匹配 |

### 层 3：实体标准化

| 目标 | 标准 ID | 匹配方式 |
|------|---------|---------|
| Gene → HGNC | `HGNC:XXXXX` | 精确 |
| Disease → MONDO | `MONDO:XXXXXXX` | 精确 / 祖先 |
| Variant → ClinVar | `ClinVarVariation:XXXXX` | 候选集匹配 |

## 选择策略

1. 解析 ClinGen CSV，保留 Definitive + Strong 条目
2. 解析 ClinVar `variant_summary.txt`，保留 germline Pathogenic/LP 且 ≥2 审查星
3. 在 GeneSymbol + MONDO ID 上连接
4. 每个融合组保留按审查星排序的 top-3 变异
5. 按多样性评分（MOI、GCEP、变异数量）选择 top N（默认 75）

## 已知限制

- 变异层仅评估精确率；无人工完整标注无法测量召回率
- 文献可能不包含 ClinVar 目标变异
- 仅英文源文章；翻译由 LLM 生成
