# ClinGen + ClinVar Fused Benchmark (Dataset 2)

主评估数据集。ClinGen 提供 gene-disease 层金标，ClinVar 提供 variant 层候选金标。

## Quick Start

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua

# 1. 选样（ClinGen Definitive/Strong × ClinVar ≥2★ Pathogenic/LP）
PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.select_fused_entries

# 2. 获取文献
PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.fetch_variant_literature

# 3. 下载文献全文（需要先跑 Dataset 1 的 download_pdfs.py 或手动添加 source.md）

# 4. 评估（需要预处理数据）
PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.evaluate_fused --write

# 5. 测试
cd backend
uv run pytest tests/benchmark/layer3/clinvar_fused/ -v
```

## 评估指标

### Layer 1: Gene-Disease（全量 P/R/F1）

| 字段 | 评估类型 | 说明 |
|------|---------|------|
| `A.gene_symbol` | P/R/F1 | 精确匹配 |
| `B.disease_diagnosis` | P/R/F1 | 多策略匹配（精确→子串→词重叠→MONDO） |
| `A.gene_disease_relationship` | P/R/F1 | 枚举匹配 |
| `B.mode_of_inheritance_reported` | Accuracy | 枚举匹配 |

### Layer 2: Variant（Precision-only）

| 字段 | 评估类型 | 说明 |
|------|---------|------|
| `A.variant_hgvs_c` | Precision | 归一化后匹配 gold candidates |
| `A.variant_hgvs_p` | Precision | 归一化后匹配 gold candidates |
| `A.variant_type` | Precision | 枚举匹配 |
| `J.clinvar_assertion` | Precision | 枚举匹配 |

**不能测 Recall** — 文中可能有 ClinVar 未收录的变异，提取到不算 FP。

### Layer 3: 实体标准化

| 目标 | 标准化 ID | 匹配 |
|------|----------|------|
| Gene → HGNC | `HGNC:XXXXX` | 精确 |
| Disease → MONDO | `MONDO:XXXXXXX` | 精确/祖先 |
| Variant → ClinVar | `ClinVarVariation:XXXXX` | 候选集匹配 |

## 已知局限

1. Variant 层只有 Precision，没有 Recall
2. 文献可能不包含 ClinVar 目标变异（退化为 gene+disease 搜索）
3. ClinVar ClinicalSignificance 是聚合值，文中表述可能不同
4. 只覆盖英文文献
5. HGVS 格式多样性可能影响匹配率

## 文件结构

```
clinvar_fused/
├── select_fused_entries.py        # 选样
├── fetch_variant_literature.py    # 文献获取
├── evaluate_fused.py              # 评估
├── hgvs_normalize.py              # HGVS 归一化
├── ground_truth/                  # 金标 + 文献
│   ├── selection.json
│   └── fused_NNN/
│       └── expected.json
├── reports/                       # 评估报告
└── README.md
```

## 与 Dataset 1 的关系

| | Dataset 1 (ClinGen-30) | Dataset 2 (Fused) |
|---|---|---|
| 字段数 | 3 | ~8-10 |
| 评估类型 | 全量 P/R/F1 | P/R/F1 + Precision-only |
| 样本量 | 30 | 50 (pilot) / 200 (main) |
| 定位 | 冒烟测试 | 主评估 |
