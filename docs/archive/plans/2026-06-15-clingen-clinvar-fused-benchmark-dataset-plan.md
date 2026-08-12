# ClinGen + ClinVar Fused Benchmark Dataset Plan

**Status:** completed (fused-75 数据集构建+翻译+评估全部完成；原 Phase 3/4 由 GIM ablation 实验取代，见 docs/nar-web-server/gim_working_file.md)
**Created:** 2026-06-15
**Updated:** 2026-08-12
**Completed:** 2026-08-12
**Scope:** Benchmark Layer 3 — 第二数据集（Dataset 2）
**Owner:** LinguaSeeker benchmark team

---

## Summary

在现有 ClinGen-30（Dataset 1，3 字段银标）基础上，构建 **ClinGen + ClinVar 融合金标数据集**（Dataset 2），将可评估字段从 3 个扩展到 ~10 个，覆盖 gene-disease 层全量 P/R/F1 + variant 层 precision + 实体标准化准确率。

Dataset 2 定位为 **主评估数据集**，Dataset 1 保留为冒烟测试 / 回归测试。

## Motivation

### Dataset 1 的局限

| 问题 | 影响 |
|------|------|
| 只有 3 个字段（gene/disease/relationship） | 无法评估 variant 提取、致病性判定、变异类型等核心能力 |
| 30 篇样本量 | 统计置信度不足 |
| 金标不来自文章内容 | 只测"能否提取已知事实"，不测"能否从文献中发现" |
| 无标准化验证 | HGNC/MONDO 标准化在预处理路径下无法评估 |

### ClinGen + ClinVar 融合的增量价值

| 数据源 | 提供的金标字段 | 对应管道字段 |
|--------|-------------|------------|
| ClinGen | gene_symbol, hgnc_id, disease_label, mondo_id, moi, classification, gcep | `A.gene_symbol`, `B.disease_diagnosis`, `A.gene_disease_relationship`, `B.mode_of_inheritance_reported`, `J.expert_panel_assertion` |
| ClinVar | variant_hgvs_c, variant_hgvs_p, variant_type, clinical_significance, review_status, variation_id, rsid | `A.variant_hgvs_c`, `A.variant_hgvs_p`, `A.variant_type`, `J.clinvar_assertion` |
| 融合 | variant 实体标准化目标 | `expected_standardization.variant` → `ClinVarVariation:{id}` |

**覆盖字段数：3 → 10（+233%）**，其中 variant 层是最大增量。

---

## 设计原则

1. **ClinGen 提供 gene-disease 骨架** — 专家共识，确定性高，可做 P/R/F1 全量评估。
2. **ClinVar 提供 variant 候选集** — 高置信度变异作为"文中可能出现的变异"候选，**只能测 precision，不能测 recall**（除非人工确认文中是否提到该变异）。
3. **文献必须同时匹配 gene + variant** — 避免 ClinGen 文献不包含 ClinVar 变体的错位问题。
4. **分层置信度** — ClinVar Review Status ≥ 2★ + ClinGen Definitive/Strong 为基线，可选扩展到 1★ / Moderate。
5. **评估指标分层** — gene-disease 层全量 P/R/F1，variant 层 precision-only，标准化层准确率。

---

## 融合金标 Schema

```json
{
  "entry_id": "fused_001",
  "source": "clingen_clinvar_fused",

  "clingen": {
    "gene_symbol": "BRCA1",
    "hgnc_id": "HGNC:1100",
    "disease_label": "Hereditary breast and ovarian cancer syndrome",
    "mondo_id": "MONDO:0003582",
    "moi": "AD",
    "classification": "Definitive",
    "gcep": "Hereditary Cancer Predisposition Gene Curation Expert Panel",
    "classification_date": "2024-01-15T00:00:00.000Z",
    "report_url": "https://search.clinicalgenome.org/kb/gene-validity/..."
  },

  "clinvar_variants": [
    {
      "variation_id": 17695,
      "hgvs_name": "NM_007294.4(BRCA1):c.5266dupC (p.Gln1756ProfsTer74)",
      "hgvs_c": "c.5266dupC",
      "hgvs_p": "p.Gln1756ProfsTer74",
      "variant_type": "dup",
      "clinical_significance": "Pathogenic",
      "review_status": "criteria provided, multiple submitters, no conflicts",
      "review_stars": 2,
      "rsid": "80357906",
      "phenotype_ids": "MONDO:MONDO:0003582,OMIM:604370",
      "phenotype_list": "Hereditary breast and ovarian cancer syndrome"
    }
  ],

  "expected_evidence": [
    {
      "field_id": "A.gene_symbol",
      "value": "BRCA1",
      "source": "clingen",
      "evaluation_type": "precision_recall"
    },
    {
      "field_id": "B.disease_diagnosis",
      "value": "Hereditary breast and ovarian cancer syndrome",
      "source": "clingen",
      "evaluation_type": "precision_recall"
    },
    {
      "field_id": "A.gene_disease_relationship",
      "value": "causative",
      "source": "clingen",
      "evaluation_type": "precision_recall"
    },
    {
      "field_id": "B.mode_of_inheritance_reported",
      "value": "AD",
      "source": "clingen",
      "evaluation_type": "precision_recall"
    },
    {
      "field_id": "A.variant_hgvs_c",
      "value": "c.5266dupC",
      "candidates": ["c.5266dupC"],
      "source": "clinvar",
      "evaluation_type": "precision_only"
    },
    {
      "field_id": "A.variant_hgvs_p",
      "value": "p.Gln1756ProfsTer74",
      "candidates": ["p.Gln1756ProfsTer74"],
      "source": "clinvar",
      "evaluation_type": "precision_only"
    },
    {
      "field_id": "A.variant_type",
      "value": "dup",
      "source": "clinvar",
      "evaluation_type": "precision_only"
    },
    {
      "field_id": "J.clinvar_assertion",
      "value": "Pathogenic",
      "source": "clinvar",
      "evaluation_type": "precision_only"
    }
  ],

  "expected_standardization": {
    "gene": "HGNC:1100",
    "disease": "MONDO:0003582",
    "variant_candidates": ["ClinVarVariation:17695"]
  },

  "expected_entities": {
    "gene": {"text": "BRCA1", "hgnc_id": "HGNC:1100"},
    "disease": {"text": "Hereditary breast and ovarian cancer syndrome", "mondo_id": "MONDO:0003582"},
    "variants": [
      {"text": "c.5266dupC", "variation_id": "ClinVarVariation:17695", "rsid": "rs80357906"}
    ]
  },

  "literature": {
    "source_pmid": "...",
    "source_pmc": "PMC...",
    "source_pdf_url": "...",
    "source_title": "...",
    "source_journal": "...",
    "source_year": "..."
  },

  "evaluation_config": {
    "gene_disease_fields": ["A.gene_symbol", "B.disease_diagnosis", "A.gene_disease_relationship", "B.mode_of_inheritance_reported"],
    "variant_fields": ["A.variant_hgvs_c", "A.variant_hgvs_p", "A.variant_type", "J.clinvar_assertion"],
    "standardization_fields": ["gene", "disease", "variant"]
  }
}
```

### Schema 设计说明

- `evaluation_type: "precision_recall"` — gene-disease 层，文中必定有（因为文献就是搜 gene+disease 关键词来的），可算完整 P/R/F1。
- `evaluation_type: "precision_only"` — variant 层，提取到的值 ∈ candidates 算 TP，提取到的值 ∉ candidates 算 FP，但不能说文中没有某个 variant 就是 FN。
- `candidates` 数组 — 一个基因在 ClinVar 可能有几十个高置信度变异，文献可能提到其中任意几个。只要提取到的值命中任意一个 candidate 就算 TP。
- `expected_standardization.variant_candidates` — 列表形式，因为文献可能提到多个变异，每个都应标准化到对应的 ClinVar ID。

---

## 选样策略

### Step 1: ClinGen 端筛选

```python
# 筛选条件
CLINGEN_FILTER = {
    "CLASSIFICATION": ["Definitive", "Strong"],  # 只选高置信度
    # 总计约 800-1000 条
}
```

理由：Definitive + Strong 的 gene-disease 关系有充分专家共识支持，避免 Moderate/Limited 的边界争议。

### Step 2: ClinVar 端筛选

```python
# 筛选条件（从 variant_summary.txt 43 字段）
CLINVAR_FILTER = {
    "ReviewStatus": [
        "practice guideline",           # 4★
        "reviewed by expert panel",     # 3★
        "criteria provided, multiple submitters, no conflicts",  # 2★
    ],
    "ClinicalSignificance": [
        "Pathogenic",
        "Likely pathogenic",
        "Pathogenic/Likely pathogenic",
    ],
    # 排除 somatic / oncogenicity 条目
    "OriginSimple": "germline",
}
```

筛选后预计 50,000-100,000 条变异。

### Step 3: 融合（JOIN）

```python
# JOIN 条件：ClinVar.PhenotypeIDS 包含 ClinGen.DISEASE ID (MONDO)
# 例：ClinVar PhenotypeIDS = "MONDO:MONDO:0003582,OMIM:604370"
#      ClinGen DISEASE ID  = "MONDO:0003582"
#      → 匹配

def join_clingen_clinvar(clingen_rows, clinvar_rows):
    """按 MONDO ID 融合，生成候选条目池。"""
    fused = []
    for cg in clingen_rows:
        mondo_id = cg["DISEASE ID (MONDO)"]  # e.g. "MONDO:0003582"
        gene = cg["GENE SYMBOL"]
        # ClinVar 的 PhenotypeIDS 格式：MONDO:MONDO:0003582,...
        matching_variants = [
            cv for cv in clinvar_rows
            if cv["GeneSymbol"] == gene
            and mondo_id in cv["PhenotypeIDS"]
        ]
        if matching_variants:
            fused.append({
                "clingen": cg,
                "clinvar_variants": matching_variants,
            })
    return fused
```

### Step 4: 文献获取

对每条融合条目，搜索 PMC 文献：

```python
# 搜索策略：gene_symbol + variant_hgvs (或 variant_legacy_name) + OPEN_ACCESS
# 优先选择同时命中 gene + variant 的文章
# 如果搜不到同时命中的，退化为 gene + disease 搜索（与 Dataset 1 一致）

def fetch_literature(fused_entry):
    gene = fused_entry["clingen"]["GENE SYMBOL"]
    variants = fused_entry["clinvar_variants"]
    disease = fused_entry["clingen"]["DISEASE LABEL"]

    # 优先尝试：gene + top variant
    for v in variants[:3]:  # 取前 3 个高置信度变异尝试
        query = f'"{gene}" AND "{v["Name"]}" AND OPEN_ACCESS:y'
        result = search_europepmc(query)
        if result:
            return result

    # 退化：gene + disease（与 Dataset 1 策略一致）
    query = f'"{gene}" AND "{disease}" AND OPEN_ACCESS:y'
    return search_europepmc(query)
```

### Step 5: 规模控制

| 阶段 | 样本数 | 说明 |
|------|--------|------|
| Pilot | 50 | 手动验证融合质量，调整评估逻辑 |
| 主集 | 200 | 论文主评估数据集 |
| 扩展（可选） | 500 | 如果需要更大规模的统计显著性 |

选样分布目标（主集 200）：

| ClinGen Classification | 数量 | 说明 |
|----------------------|------|------|
| Definitive | 80 | 基线 |
| Strong | 120 | 主力 |

每条融合条目取 ClinVar 中 review_stars 最高的 1-3 个变异作为 gold candidates，避免候选集过大导致 precision 虚高。

---

## 评估逻辑

### 指标体系

#### Layer 1: Gene-Disease 层（全量 P/R/F1）

| 字段 | 匹配策略 | 评估类型 |
|------|---------|---------|
| `A.gene_symbol` | 精确匹配（case-insensitive） | P/R/F1 |
| `B.disease_diagnosis` | 多策略：精确 → 子串 → 词重叠 → MONDO 祖先 | P/R/F1 |
| `A.gene_disease_relationship` | 枚举匹配（causative/associated/uncertain/disputed/refuted） | P/R/F1 |
| `B.mode_of_inheritance_reported` | 枚举匹配（AD/AR/XL/MT/SD/UD） | Accuracy |

这一层与 Dataset 1 评估逻辑一致，可复用 `evaluate.py` 的 `compare_evidence()` 函数。

#### Layer 2: Variant 层（Precision-only）

| 字段 | 匹配策略 | 评估类型 |
|------|---------|---------|
| `A.variant_hgvs_c` | HGVS 归一化后精确匹配，或包含关系 | Precision |
| `A.variant_hgvs_p` | HGVS 归一化后精确匹配，或包含关系 | Precision |
| `A.variant_type` | 枚举匹配（missense/nonsense/frameshift/splice_site/deletion/insertion/dup/cnv/synonymous/other） | Precision |
| `J.clinvar_assertion` | 枚举匹配（Pathogenic/Likely_pathogenic/VUS/Likely_benign/Benign） | Precision |

**Precision 计算规则：**

```
TP = 管道提取的值 ∈ gold candidates（归一化后匹配）
FP = 管道提取的值 ∉ gold candidates
FN = 不计算（因为不知道文中是否提到了该变异）

Precision = TP / (TP + FP)
```

**HGVS 归一化规则：**
- 去除前缀 `NM_xxxxx.x(...):` 和空格
- Unicode NFKC 归一化
- 统一 delins/del/ins 大小写
- 蛋白变异：统一三字母/一字母编码（p.Arg27Ter → p.R27*）

#### Layer 3: 实体标准化准确率

| 目标实体 | 标准化目标 | 匹配策略 |
|---------|-----------|---------|
| Gene → HGNC ID | `HGNC:XXXXX` | 精确匹配 |
| Disease → MONDO ID | `MONDO:XXXXXXX` | 精确匹配（允许 MONDO 祖先匹配） |
| Variant → ClinVar ID | `ClinVarVariation:XXXXX` | 精确匹配（候选集匹配） |

**Variant 标准化准确率计算：**

```
# 对于管道提取到的每个变异：
# 1. 查 Phase 3 标准化结果，获取 ClinVarVariation ID
# 2. 检查该 ID 是否在 gold candidate_ids 中
# 3. 精确命中 → correct，未命中 → incorrect，未解析 → unresolved
```

#### Layer 4: 综合指标

| 指标 | 公式 | 说明 |
|------|------|------|
| Overall Gene-Disease F1 | 各字段 F1 的 micro-average | 主指标 |
| Variant Extraction Precision | 各 variant 字段 precision 的 average | 只有 precision |
| Standardization Accuracy | (gene_hit + disease_hit + variant_hit) / (gene_total + disease_total + variant_total) | 综合标准化能力 |
| Over-extraction Rate | FP / (TP + FP) | 管道过度提取的程度 |

### 评估脚本设计

```python
# evaluate_fused.py 核心流程

def evaluate_entry(entry: dict, extraction_result: dict) -> EntryResult:
    results = {}

    # Layer 1: Gene-Disease P/R/F1
    for field_cfg in entry["evaluation_config"]["gene_disease_fields"]:
        gold = get_gold_value(entry, field_cfg)
        extracted = find_extracted_value(extraction_result, field_cfg)
        match = multi_strategy_match(gold, extracted, field_cfg)
        results[field_cfg] = match

    # Layer 2: Variant Precision
    for field_cfg in entry["evaluation_config"]["variant_fields"]:
        candidates = get_gold_candidates(entry, field_cfg)
        extracted_values = find_all_extracted_values(extraction_result, field_cfg)
        for ev in extracted_values:
            if normalized_match(ev, candidates):
                tp += 1
            else:
                fp += 1
        # no FN counting
        results[field_cfg] = {"precision": tp / (tp + fp) if (tp + fp) > 0 else None}

    # Layer 3: Standardization
    for entity_type in ["gene", "disease", "variant"]:
        gold_ids = get_gold_standardization(entry, entity_type)
        predicted_ids = get_predicted_standardization(extraction_result, entity_type)
        results[f"std_{entity_type}"] = exact_id_match(gold_ids, predicted_ids)

    return EntryResult(entry_id=entry["entry_id"], results=results)
```

---

## 文件结构

```
benchmark/layer3/
├── clinvar_fused/
│   ├── select_fused_entries.py        # 选样：ClinGen × ClinVar 融合
│   ├── fetch_variant_literature.py    # 文献获取：gene + variant 关键词搜索
│   ├── build_fused_gold.py            # 生成融合金标 JSON
│   ├── evaluate_fused.py              # 评估脚本
│   ├── visualize_fused.py             # 可视化报告
│   ├── hgvs_normalize.py              # HGVS 归一化工具
│   ├── ground_truth/                  # 融合金标 + 文献 markdown
│   │   ├── fused_000/
│   │   │   ├── expected.json          # 融合金标
│   │   │   ├── source.md              # PMC 文献 markdown
│   │   │   └── preprocessed/          # Phase 2 缓存
│   │   ├── fused_001/
│   │   │   └── ...
│   │   └── selection.json             # 选样元数据
│   ├── reports/                       # 评估报告
│   └── README.md
│
├── ground_truth/                      # Dataset 1: ClinGen-30（保留）
│   └── ...（不变）
│
├── evaluate.py                        # Dataset 1 评估（保留）
└── ...
```

---

## 实现步骤

### Phase 1: 数据准备（预计 1-2 天）

#### 1.1 实现 `select_fused_entries.py`

```
输入：
  - database/terminology_database/clingen/Clingen-Gene-Disease-Summary.csv
  - database/terminology_database/clinvar/variant_summary.txt (43 字段完整版)

输出：
  - clinvar_fused/ground_truth/selection.json

逻辑：
  1. 解析 ClinGen CSV，筛选 Classification ∈ {Definitive, Strong}
  2. 解析 ClinVar variant_summary.txt，筛选：
     - ReviewStatus ∈ {practice guideline, reviewed by expert panel, criteria provided, multiple submitters, no conflicts}
     - ClinicalSignificance ∈ {Pathogenic, Likely pathogenic, Pathogenic/Likely pathogenic}
     - OriginSimple = germline
  3. 按 GeneSymbol + MONDO ID JOIN
  4. 对每个融合组，取 review_stars 最高的前 3 个变异
  5. 按 (ClinGen classification, review_stars, 变异数量) 评分排序
  6. 选 top 50（pilot）/ 200（主集）

验证：selection.json 包含 50/200 条条目，每条有 clingen 元数据 + clinvar_variants 列表
```

#### 1.2 实现 `fetch_variant_literature.py`

```
输入：clinvar_fused/ground_truth/selection.json
输出：每条条目更新 source_pmid, source_pmc, source_pdf_url, source_md

逻辑：
  1. 对每条条目，构建搜索查询：
     a. 优先：gene_symbol + variant_hgvs_name + OPEN_ACCESS:y
     b. 退化：gene_symbol + disease_label + OPEN_ACCESS:y
  2. 搜索 EuropePMC API
  3. 选择最佳结果（有 PMC ID 优先）
  4. 下载 JATS XML → 转 markdown
  5. 保存 source.md

验证：≥80% 的条目有 source.md
```

#### 1.3 实现 `build_fused_gold.py`

```
输入：selection.json + 每条条目的文献信息
输出：每条条目的 expected.json（按上述 Schema）

逻辑：
  1. 从 ClinGen 元数据生成 gene-disease 层金标
  2. 从 ClinVar 变异列表生成 variant 层金标候选集
  3. 构建 expected_standardization（含 variant_candidates）
  4. 标注 evaluation_config（哪些字段 precision_recall，哪些 precision_only）

验证：每个 expected.json 包含 ≥8 个 expected_evidence 项，evaluation_config 正确标记
```

### Phase 2: 评估逻辑（预计 2-3 天）

#### 2.1 实现 `hgvs_normalize.py`

```python
def normalize_hgvs_c(hgvs: str) -> str:
    """归一化 HGVS 编码变异。

    规则：
    - 去除转录本前缀 NM_xxxxx.x(...):
    - 去除空格
    - Unicode NFKC
    - 统一 delins/del/ins/dup 大小写
    - c. 前缀保留
    """

def normalize_hgvs_p(hgvs: str) -> str:
    """归一化 HGVS 蛋白变异。

    规则：
    - 去除转录本前缀
    - 三字母 → 一字母氨基酸编码
    - 统一 Ter/stop/* 终止符
    - p. 前缀保留
    """

def normalize_variant_type(vt: str) -> str:
    """归一化变异类型到标准枚举。"""
```

单元测试：至少覆盖以下 case

```python
# 编码变异
assert normalize_hgvs_c("NM_007294.4(BRCA1):c.5266dupC") == "c.5266dupC"
assert normalize_hgvs_c("c.5266 dup C") == "c.5266dupC"
assert normalize_hgvs_c("c.1A>G") == "c.1a>g"  # 或保持原样，需确定策略

# 蛋白变异
assert normalize_hgvs_p("p.Arg27Ter") == "p.R27*"
assert normalize_hgvs_p("p.R27X") == "p.R27*"
assert normalize_hgvs_p("p.Gln1756ProfsTer74") == "p.Q1756Pfs*74"
```

#### 2.2 实现 `evaluate_fused.py`

```
输入：
  - clinvar_fused/ground_truth/*/expected.json
  - clinvar_fused/ground_truth/*/preprocessed/phase_2/extraction_result.json

输出：
  - clinvar_fused/reports/fused_report_{timestamp}.json

评估逻辑：
  1. 对每条条目，加载 expected.json + extraction_result.json
  2. Layer 1 (gene-disease): 复用 Dataset 1 的 compare_evidence()，计算 TP/FP/FN
  3. Layer 2 (variant precision): 遍历管道提取的 variant 字段值，
     归一化后检查是否 ∈ gold candidates，统计 TP/FP
  4. Layer 3 (standardization): 检查标准化结果中的 ID 是否匹配
  5. 汇总：各层指标 + 按 classification 分层 + 按 variant_type 分层

报告格式：
  {
    "timestamp": "...",
    "total_entries": 200,
    "evaluated_entries": 195,
    "layer1_gene_disease": {
      "overall": {"precision": 0.92, "recall": 0.85, "f1": 0.88},
      "by_field": {
        "A.gene_symbol": {"precision": 0.98, "recall": 0.95, "f1": 0.96},
        "B.disease_diagnosis": {"precision": 0.90, "recall": 0.82, "f1": 0.86},
        "A.gene_disease_relationship": {"precision": 0.88, "recall": 0.80, "f1": 0.84},
        "B.mode_of_inheritance_reported": {"accuracy": 0.92}
      }
    },
    "layer2_variant": {
      "overall_precision": 0.75,
      "by_field": {
        "A.variant_hgvs_c": {"precision": 0.72, "tp": 144, "fp": 56},
        "A.variant_hgvs_p": {"precision": 0.70, "tp": 140, "fp": 60},
        "A.variant_type": {"precision": 0.82, "tp": 164, "fp": 36},
        "J.clinvar_assertion": {"precision": 0.68, "tp": 136, "fp": 64}
      },
      "by_variant_type": {
        "missense": {"precision": 0.80},
        "nonsense": {"precision": 0.75},
        "frameshift": {"precision": 0.70}
      }
    },
    "layer3_standardization": {
      "gene": {"accuracy": 0.95, "correct": 190, "total": 200},
      "disease": {"accuracy": 0.88, "correct": 176, "total": 200},
      "variant": {"accuracy": 0.72, "correct": 144, "total": 200, "unresolved": 20}
    },
    "by_clingen_classification": {
      "Definitive": {"gene_disease_f1": 0.92, "variant_precision": 0.78},
      "Strong": {"gene_disease_f1": 0.85, "variant_precision": 0.72}
    }
  }
```

#### 2.3 实现 `visualize_fused.py`

生成图表：
1. **分层雷达图** — gene-disease F1 + variant precision + 标准化准确率
2. **字段级柱状图** — 各字段的 P/R/F1/Precision
3. **变异类型热力图** — variant_type × clinical_significance 的 precision
4. **标准化桑基图** — 提取值 → 标准化 ID 的流向
5. **Dataset 1 vs Dataset 2 对比表** — 相同字段的指标对比

### Phase 3: 预处理与集成（预计 1 天）

#### 3.1 预处理缓存

```bash
# 对 200 篇文献运行 Phase 1+2 管道，缓存结果
PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.preprocess \
    --dataset clinvar_fused \
    --ground-truth-dir benchmark/layer3/clinvar_fused/ground_truth
```

#### 3.2 集成到 CI / 回归测试

```bash
# 快速冒烟测试（5 篇）
PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.evaluate_fused --limit 5

# 完整评估
PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.evaluate_fused --write
```

#### 3.3 泄漏检查

复用 Dataset 1 的 `leakage_check.py` 逻辑，扩展检查：
- 融合金标中的 `variation_id` / `hgvs_c` / `hgvs_p` 不得出现在 extraction_result 的 prompt 或 context 中
- `expected_evidence` 不得出现在 LLM 的 input token 中

### Phase 4: 文档与报告（预计 0.5 天）

#### 4.1 README.md

记录数据集构成、选样策略、评估方法、已知局限。

#### 4.2 论文 Table 设计

| Table | 内容 | 数据源 |
|-------|------|--------|
| Table N | Dataset 2 构成（样本数、分类分布、变异类型分布） | selection.json |
| Table N+1 | Gene-Disease 层 P/R/F1（按字段 × 按分类） | evaluate_fused.py |
| Table N+2 | Variant 层 Precision（按字段 × 按变异类型） | evaluate_fused.py |
| Table N+3 | 实体标准化准确率（gene/disease/variant） | evaluate_fused.py |
| Table N+4 | Dataset 1 vs Dataset 2 交叉验证 | 两个数据集的报告 |

---

## 已知局限

| 局限 | 影响 | 缓解措施 |
|------|------|---------|
| Variant 层只有 Precision，没有 Recall | 无法评估"文中有的变异是否都提取了" | 论文中明确标注为 precision-only；未来可人工标注补充 |
| 文献可能不包含 ClinVar 目标变异 | 搜索到的文章可能只讨论 gene-disease 关系，不讨论具体变异 | 优先搜 gene+variant 关键词；退化为 gene+disease 时标记为 variant-naive |
| ClinVar ClinicalSignificance 是聚合值 | 文中表述可能与 ClinVar 聚合判定不同 | 评估时用宽松匹配（Pathogenic ≈ "pathogenic" ≈ "致病性"） |
| HGVS 格式多样 | 同一变异可能有多种 HGVS 表述 | 实现 HGVS 归一化模块，覆盖常见格式变体 |
| 融合 JOIN 的 MONDO ID 匹配 | ClinVar 的 PhenotypeIDS 中 MONDO ID 格式不统一（有 MONDO:MONDO: 前缀） | 归一化 MONDO ID 格式后匹配 |
| 只覆盖英文文献 | 不能测跨语言能力 | 与 Dataset 1 互补；Benchmark B（zh/ja/ko）单独覆盖 |

---

## 与现有 Benchmark 体系的关系

```
论文评估体系
├── Benchmark A: Cross-Lingual Evidence Transport
│   ├── Dataset 1: ClinGen-30（冒烟测试 + 回归）
│   │   └── 3 字段 P/R/F1 + alignment + traceability
│   └── Dataset 2: ClinGen+ClinVar Fused（主评估）  ← 本文档
│       └── 10 字段 P/R/F1 + variant precision + 标准化
│
├── Benchmark B: Multilingual Evidence Augmentation
│   ├── zh/ja/ko raw corpora
│   └── 10-case pilot
│
└── 辅助实验
    ├── Ablation study（reconcile 策略对比）
    ├── Model baseline（GPT-5 / Claude / DeepSeek / Qwen / GLM）
    └── Traceability metrics（CVR/HCR/ESR/TraceableF1）
```

---

## Acceptance Criteria

- [x] `select_fused_entries.py` 生成 ≥50 条融合条目（pilot）— 50 条已生成
- [x] 每条条目有 expected.json（≥8 个 expected_evidence 项）— 8 项（4 gene-disease + 4 variant）
- [x] ≥80% 的条目有 PMC 文献 — 38/50（76%，12 条 EuropePMC 限流，可重试）
- [x] `hgvs_normalize.py` 通过 ≥20 个 case 的单元测试 — 68 tests pass
- [x] `evaluate_fused.py` 输出完整报告（3 层指标 + 分层分析）— 已实现
- [ ] Dataset 2 的 gene/disease/relationship F1 与 Dataset 1 可比（差异 < 10%）— 需 Phase 3 预处理
- [ ] Variant precision 在 pilot 50 条上 > 0.5 — 需 Phase 3 预处理
- [ ] 泄漏检查通过 — 需 Phase 3
- [ ] `visualize_fused.py` 生成 ≥3 张图表 — 待实现
- [x] README.md 记录数据集构成和已知局限

---

## 进度记录

- [2026-06-15] 计划文档编写完成。[planned]
- [2026-06-16] Phase 1+2 实现完成。select_fused_entries.py 从 ClinGen(2321 Definitive/Strong) × ClinVar(190224 variants) 融合出 1476 条候选，选 50 条 pilot。fetch_variant_literature.py 获取 38/50 条 PMC 文献。evaluate_fused.py 实现 3 层评估（gene-disease P/R/F1 + variant precision + standardization）。hgvs_normalize.py 通过 68 个单元测试。已合并到 dev 分支。Phase 3（预处理缓存 + 管道运行）和 Phase 4（可视化）待执行。[completed]
