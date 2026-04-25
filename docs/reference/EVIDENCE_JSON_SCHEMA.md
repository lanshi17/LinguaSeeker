# 证据 JSON 字段说明（EVIDENCE_JSON_SCHEMA）

本文档详细说明 ACMG-Lingua 项目中两种证据 JSON 格式的字段定义、数据类型与取值含义，供开发、评估和数据标注人员参考。

---

## 一、系统输出证据 JSON（`benchmark/evidence-json/*.evidence.json`）

系统处理管道针对每篇文献、每个变异输出一个 `EvidenceOutput` 对象，整篇文献的输出为该对象的数组（`List[EvidenceOutput]`）。

### 顶层字段

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ps3_evidence` | Object | ✅ | PS3/BS3 功能证据四步评估结果（见下节） |
| `arbitration_confidence` | float \| null | — | 专家仲裁置信度，取值范围 0–1 |
| `image_descriptions` | string[] | — | 文献图片的 AI 描述列表 |
| `evidence_sources` | string[] | — | 证据来源标识，如 `"PMID:21721555"` |
| `final_evidence_strength` | string \| null | — | 最终证据强度等级（见下方枚举值） |
| `status` | string | — | 处理状态：`pending` / `success` / `failed` |
| `origin_format_md` | string \| null | — | 原始语言排版后的 Markdown 内容 |
| `en_format_md` | string \| null | — | 翻译成英文的排版后 Markdown 内容 |
| `extracted_fields` | Object \| null | — | 11 个标准化结构化证据字段（见下节） |
| `field_confidence_scores` | Object \| null | — | 各字段置信度评分（0–100） |
| `overall_confidence` | float \| null | — | 总体置信度（0–100） |
| `evidence_classification` | string \| null | — | 证据分类，当前取值：`Pathogenic`；模型定义允许扩展 |
| `acmg_evidence_levels` | string[] \| null | — | ACMG 证据等级标签列表（见下方枚举值） |

#### `final_evidence_strength` / `acmg_evidence_levels` 枚举值

| 取值 | 含义 |
|---|---|
| `PS3_very_strong` | 功能证据—致病—非常强 |
| `PS3` | 功能证据—致病—强 |
| `PS3_moderate` | 功能证据—致病—中等 |
| `PS3_supporting` | 功能证据—致病—支持 |
| `BS3_supporting` | 功能证据—良性—支持 |
| `BS3_moderate` | 功能证据—良性—中等 |
| `BS3` | 功能证据—良性—强 |
| `BS3_very_strong` | 功能证据—良性—非常强 |
| `inconclusive` | 不确定 / 无法判断 |

---

### `ps3_evidence` 字段（PS3/BS3 四步评估）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `functional_evidence_aim` | string \| null | 功能证据方向：`pathogenic`（致病）或 `benign`（良性） |
| `ps3_step_1` | Object | 步骤1：定义疾病机制 |
| `ps3_step_1.score` | number | 步骤1得分 |
| `ps3_step_1.summary` | string \| null | 步骤1说明（可选，实际数据中常缺省） |
| `ps3_step_2` | Object | 步骤2：实验方法适用性 |
| `ps3_step_2.score` | number | 步骤2得分 |
| `ps3_step_2.summary` | string \| null | 步骤2说明（可选，实际数据中常缺省） |
| `ps3_step_3` | Object | 步骤3：实验有效性 |
| `ps3_step_3.score` | number | 步骤3得分 |
| `ps3_step_3.checkpoint_3a` | Object \| null | 检查点3a：基本对照与重复 |
| `ps3_step_3.checkpoint_3a.replicates_used` | boolean | 是否使用了重复实验 |
| `ps3_step_3.checkpoint_3a.positive_control_present` | boolean | 是否有阳性对照 |
| `ps3_step_3.checkpoint_3a.negative_control_present` | boolean | 是否有阴性对照 |
| `ps3_step_4` | Object | 步骤4：变异解释应用 |
| `ps3_step_4.score` | number | 步骤4得分 |
| `ps3_step_4.final_evidence_strength` | string | 步骤4判定的证据强度（同枚举值表） |
| `ps3_step_4.oddspath_data` | Object | OddsPath 计算数据 |
| `ps3_step_4.oddspath_data.computable` | boolean | OddsPath 是否可计算 |
| `ps3_step_4.oddspath_data.OddsPath` | number \| null | OddsPath 值（可计算时给出） |
| `ps3_step_4.oddspath_data.functional_evidence_aim` | string \| null | 方向性标注 |
| `overall_assessment` | Object | 综合评估 |
| `overall_assessment.total_score` | number | 综合总分 |
| `overall_assessment.reasoning` | string \| null | 综合推理说明（可选，实际数据中常缺省） |

---

### `extracted_fields` 字段（11个标准化证据字段）

每个子字段都包含 `confidence`（0–100 提取置信度）和 `evidence_quote`（原文引用，可为 `null`）两个通用属性。

#### 1. `gene`（基因信息）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 基因符号，如 `BRCA1`、`TP53` |
| `full_name` | string \| null | 基因全名 |
| `ncbi_gene_id` | string \| null | NCBI Gene ID |
| `ensembl_id` | string \| null | Ensembl Gene ID |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 2. `transcript_id`（转录本信息）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `transcript_id` | string | 转录本 ID，如 `NM_007294.4`、`ENST00000357654` |
| `source` | string \| null | 来源：`RefSeq` / `Ensembl` |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 3. `reference_genome_version`（参考基因组版本）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `version` | string | 版本标识，如 `GRCh37`、`GRCh38`、`hg19`、`hg38` |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 4. `experiment_data`（实验数据）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `assay_type` | string | 实验类型，如 `functional assay`、`splicing assay` |
| `method_description` | string \| null | 实验方法描述 |
| `key_findings` | string[] \| null | 关键发现列表 |
| `statistical_data` | Object \| null | 统计数据（p值、CI、效应量等） |
| `sample_size` | string \| null | 样本量 |
| `cell_line` | string \| null | 细胞系 |
| `model_organism` | string \| null | 模型生物 |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 5. `disease_chpo`（疾病信息—中文人类表型本体）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `disease_name` | string | 疾病名称 |
| `chpo_id` | string \| null | CHPO（中文人类表型本体）ID |
| `icd10_code` | string \| null | ICD-10 编码 |
| `omim_id` | string \| null | OMIM ID |
| `inheritance_pattern` | string \| null | 遗传模式：`AD`/`AR`/`XL`/`XD` 等 |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 6. `disease_icd10`（疾病信息—ICD-10）

与 `disease_chpo` 字段结构相同，侧重 ICD-10 编码维度的疾病提取。

#### 7. `species`（物种信息）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `species_name` | string | 物种名称，如 `Homo sapiens` |
| `is_human` | boolean | 是否为人类样本 |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 8. `phenotype`（表型信息）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `phenotype_description` | string | 表型描述 |
| `hpo_ids` | string[] \| null | HPO ID 列表，如 `["HP:0001250"]` |
| `severity` | string \| null | 严重程度：`mild`/`moderate`/`severe` |
| `onset_age` | string \| null | 发病年龄 |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 9. `variant`（变异信息）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `hgvs_c` | string \| null | cDNA 变异描述，如 `NM_000345.4:c.157G>A` |
| `hgvs_p` | string \| null | 蛋白变异描述，如 `p.Ala53Thr` |
| `hgvs_g` | string \| null | 基因组变异描述（g. 格式） |
| `chromosome` | string \| null | 染色体，如 `chr17` |
| `position` | integer \| null | 基因组坐标位置 |
| `ref_allele` | string \| null | 参考等位基因 |
| `alt_allele` | string \| null | 替代等位基因 |
| `variant_type` | string \| null | 变异类型：`missense`/`nonsense`/`frameshift` 等 |
| `rs_id` | string \| null | dbSNP rs ID |
| `clinvar_id` | string \| null | ClinVar 变异 ID |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 10. `negative_positive_control`（阴性/阳性对照）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `has_negative_control` | boolean | 是否存在阴性对照 |
| `has_positive_control` | boolean | 是否存在阳性对照 |
| `negative_control_description` | string \| null | 阴性对照描述 |
| `positive_control_description` | string \| null | 阳性对照描述 |
| `control_variants` | Object[] \| null | 对照变异列表 |
| `total_control_count` | integer | 对照变异总数 |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

#### 11. `pedigree_information`（家系信息）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `has_pedigree` | boolean | 是否有家系数据 |
| `family_size` | integer \| null | 家系规模（人数） |
| `affected_count` | integer \| null | 受累人数 |
| `segregation_data` | string \| null | 共分离数据描述 |
| `inheritance_pattern` | string \| null | 遗传模式 |
| `confidence` | float | 提取置信度（0–100） |
| `evidence_quote` | string \| null | 原文引用 |

---

### `field_confidence_scores` 字段

对 `extracted_fields` 中 11 个字段的置信度汇总，键名与子字段名一致：

```json
{
  "gene": 100.0,
  "transcript_id": 100.0,
  "reference_genome_version": 0.0,
  "experiment_data": 100.0,
  "disease_chpo": 0.0,
  "disease_icd10": 0.0,
  "species": 100.0,
  "phenotype": 100.0,
  "variant": 100.0,
  "negative_positive_control": 100.0,
  "pedigree_information": 0.0
}
```

> 置信度为 0.0 表示该字段在文献中未被提取到或不适用。

---

### 完整示例（单条 `EvidenceOutput`）

```json
{
  "ps3_evidence": {
    "functional_evidence_aim": "pathogenic",
    "ps3_step_1": { "score": 0 },
    "ps3_step_2": { "score": 20 },
    "ps3_step_3": {
      "score": 15,
      "checkpoint_3a": {
        "replicates_used": true,
        "positive_control_present": true,
        "negative_control_present": false
      }
    },
    "ps3_step_4": {
      "score": 20,
      "final_evidence_strength": "PS3_supporting",
      "oddspath_data": { "computable": false }
    },
    "overall_assessment": { "total_score": 55 }
  },
  "arbitration_confidence": null,
  "image_descriptions": [],
  "evidence_sources": ["PMID:21721555"],
  "final_evidence_strength": "PS3_supporting",
  "status": "success",
  "origin_format_md": null,
  "en_format_md": null,
  "extracted_fields": {
    "gene": {
      "symbol": "SNCA",
      "full_name": null,
      "ncbi_gene_id": null,
      "ensembl_id": null,
      "confidence": 100.0,
      "evidence_quote": null
    },
    "transcript_id": {
      "transcript_id": "NM_000345.4",
      "source": null,
      "confidence": 100.0,
      "evidence_quote": null
    },
    "reference_genome_version": null,
    "experiment_data": {
      "assay_type": "Fluorescence analysis",
      "method_description": "Fluorescence analysis shows A53T substitution dominates growth kinetics.",
      "key_findings": null,
      "statistical_data": null,
      "sample_size": null,
      "cell_line": "Human-mouse αSynuclein chimeras",
      "model_organism": null,
      "confidence": 100.0,
      "evidence_quote": null
    },
    "disease_chpo": null,
    "disease_icd10": null,
    "species": {
      "species_name": "Homo sapiens",
      "is_human": true,
      "confidence": 100.0,
      "evidence_quote": null
    },
    "phenotype": {
      "phenotype_description": "Abnormal",
      "hpo_ids": null,
      "severity": null,
      "onset_age": null,
      "confidence": 100.0,
      "evidence_quote": null
    },
    "variant": {
      "hgvs_c": "NM_000345.4:c.157G>A",
      "hgvs_p": "p.Ala53Thr",
      "hgvs_g": null,
      "chromosome": null,
      "position": null,
      "ref_allele": "G",
      "alt_allele": "A",
      "variant_type": null,
      "rs_id": null,
      "clinvar_id": null,
      "confidence": 100.0,
      "evidence_quote": null
    },
    "negative_positive_control": {
      "has_negative_control": false,
      "has_positive_control": true,
      "negative_control_description": null,
      "positive_control_description": "Wild-type α-synuclein serves as a positive control.",
      "control_variants": null,
      "total_control_count": 0,
      "confidence": 100.0,
      "evidence_quote": null
    },
    "pedigree_information": null
  },
  "field_confidence_scores": {
    "gene": 100.0,
    "transcript_id": 100.0,
    "reference_genome_version": 0.0,
    "experiment_data": 100.0,
    "disease_chpo": 0.0,
    "disease_icd10": 0.0,
    "species": 100.0,
    "phenotype": 100.0,
    "variant": 100.0,
    "negative_positive_control": 100.0,
    "pedigree_information": 0.0
  },
  "overall_confidence": 100.0,
  "evidence_classification": "Pathogenic",
  "acmg_evidence_levels": ["PS3_supporting"]
}
```

---

## 二、金标准基准 JSON（`benchmark/Gold-Standard-Json/*.json`）

金标准 JSON 由专家人工标注，用于评估系统输出质量。每个文件对应一篇文献，根对象为单一标注对象。

### 顶层字段

| 字段名 | 类型 | 说明 |
|---|---|---|
| `Variants Include` | Object[] | 文献涉及的变异列表 |
| `Described Disease` | Object | 文献描述的疾病信息 |
| `Experiment Method` | Object[] | 实验方法列表，每项对应一种实验设计 |

---

### `Variants Include`（变异列表）

每个元素包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `Gene` | string | 基因符号，如 `SNCA`、`BRCA1` |
| `variants` | Object[] | 该基因下的变异列表 |

每个 `variants` 元素包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `HGVS` | string | 完整 HGVS 字符串，如 `NM_000345.4:c.157G>A` |
| `cDNA Change` | Object | cDNA 层面变异详情 |
| `cDNA Change.transcript` | string | 转录本 ID |
| `cDNA Change.ref` | string | 参考碱基 |
| `cDNA Change.alt` | string | 替代碱基 |
| `cDNA Change.position` | string | cDNA 位置 |
| `Protein Change` | Object | 蛋白质层面变异详情 |
| `Protein Change.ref` | string | 参考氨基酸（单字母缩写） |
| `Protein Change.alt` | string | 替代氨基酸（单字母缩写） |
| `Protein Change.position` | string | 蛋白质位置 |
| `Description in input context` | string | 原文中的变异简短描述，如 `A53T` |

---

### `Described Disease`（疾病信息）

| 字段名 | 类型 | 说明 |
|---|---|---|
| `Described Disease` | string | 疾病名称，如 `Autosomal recessive juvenile parkinsonism` |
| `MONDO` | string | MONDO 本体 ID，如 `MONDO:0005180` |

---

### `Experiment Method`（实验方法列表）

每个实验方法对象包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `Assay Method` | string | 实验方法名称，如 `Fluorescence analysis`、`Thioflavin T (ThT) fluorescence` |
| `Material used` | Object | 实验材料信息 |
| `Material used.Material Source` | string | 材料来源 |
| `Material used.Material Name` | string | 材料名称 |
| `Material used.Description` | string | 材料使用描述 |
| `Readout type` | string | 读出类型：`Quantitative`（定量）/ `Qualitative`（定性） |
| `Readout description` | Object[] | 每个变异的实验读出结果 |
| `Biological replicates` | Object | 生物学重复信息 |
| `Biological replicates.Biological replicates` | string | `Yes` / `No` / `N.D.`（未报告） |
| `Biological replicates.Description` | string | 重复描述 |
| `Technical replicates` | Object | 技术重复信息（结构同生物学重复） |
| `Basic positive control` | Object | 基本阳性对照（结构同重复信息） |
| `Basic negative control` | Object | 基本阴性对照（结构同重复信息） |
| `Validation controls P/LP` | Object | 已知致病/可能致病变异验证对照 |
| `Validation controls P/LP.Validation controls P/LP` | string | `Yes` / `No` / `N.D.` |
| `Validation controls P/LP.Counts` | string | 对照数量或 `N.D.` |
| `Validation controls B/LB` | Object | 已知良性/可能良性变异验证对照（结构同上） |
| `Statistical analysis method` | Object | 统计分析方法 |
| `Statistical analysis method.Statistical analysis method` | string | 方法名称或 `N.D.` |
| `Threshold for normal readout` | Object | 正常读出阈值 |
| `Threshold for normal readout.Threshold for normal readout` | string | 阈值描述或 `N.D.` |
| `Threshold for normal readout.Source` | string | 阈值来源或 `N.D.` |
| `Threshold for abnormal readout` | Object | 异常读出阈值（结构同正常阈值） |
| `Approved assay` | Object | 该实验方法是否为已认可方法 |
| `Approved assay.Approved assay` | string | `Yes` / `No` / `N.D.` |

#### `Readout description` 元素字段

| 字段名 | 类型 | 说明 |
|---|---|---|
| `Variant` | string | 变异 HGVS 字符串 |
| `Conclusion` | string | 结论：`Abnormal`（异常）/ `Normal`（正常）/ `N.D.`（未判定）。个别标注存在非标准值（如 `Monoallelic expression`） |
| `Molecular Effect` | string | 分子效应。常见取值：`gain-of-function`（功能获得）/ `loss-of-function`（功能丧失）/ `partial loss-of-function`（部分功能丧失）/ `complete loss-of-function`（完全功能丧失）/ `dominant-negative`（显性负效应）/ `intermediate effect`（中间效应）/ `No Effect`（无效应）/ `N.D.`（未报告）。注意：大小写和连字符在标注中不完全统一 |
| `Result Description` | string | 实验结果详细描述 |

---

> **约定说明**：金标准 JSON 中 `N.D.` 表示该信息在原文中未报告（Not Determined / Not Described），非缺失数据。

---

## 三、字段对照关系

| 系统输出字段 | 金标准字段 | 说明 |
|---|---|---|
| `extracted_fields.gene.symbol` | `Variants Include[].Gene` | 基因符号 |
| `extracted_fields.variant.hgvs_c` | `Variants Include[].variants[].HGVS` | HGVS cDNA 变异 |
| `extracted_fields.variant.hgvs_p` | `Variants Include[].variants[].Protein Change` | HGVS 蛋白变异 |
| `extracted_fields.transcript_id.transcript_id` | `Variants Include[].variants[].cDNA Change.transcript` | 转录本 ID |
| `extracted_fields.experiment_data.assay_type` | `Experiment Method[].Assay Method` | 实验类型 |
| `extracted_fields.negative_positive_control.has_positive_control` | `Experiment Method[].Basic positive control` | 阳性对照 |
| `extracted_fields.negative_positive_control.has_negative_control` | `Experiment Method[].Basic negative control` | 阴性对照 |

---

**最后更新**：2026-04-25
