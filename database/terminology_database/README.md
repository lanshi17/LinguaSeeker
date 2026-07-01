# Terminology Database

> Lingua Seeker Phase 3 实体标准化和知识对齐的生物医学参考术语数据。所有数据文件需单独下载，不纳入版本控制。

## 概述

本目录存放生物医学参考术语原始数据文件，涵盖基因（HGNC）、疾病（OMIM、MONDO）、表型（HPO）、变异（ClinVar、dbSNP）和基因-疾病关系（ClinGen）。这些数据是 Phase 3 实体标准化管线的核心参考源，通过 `scripts/data/import/import_terminology.py` 导入 PostgreSQL。

## 目录结构

```
terminology_database/
├── README.md
├── clingen/
│   ├── Clingen-Dosage-Sensitivity.csv       剂量敏感性评分
│   └── Clingen-Gene-Disease-Summary.csv     基因-疾病有效性审查
├── clinvar/
│   ├── variant_summary.txt                  完整 ClinVar 变异摘要（~3.7 GB）
│   ├── clinvar.vcf.gz                       ClinVar VCF 格式（GRCh38，~192 MB）
│   └── variant_summary.core.tsv             精简 TSV 用于导入（~700 MB）
├── dbSNP/
│   └── dbsnp_b157.sqlite                    dbSNP b157 SQLite 用于 rsID 查询（~1.2 GB）
├── hgnc/
│   └── hgnc_complete_set.txt                完整 HGNC 基因命名数据集
├── hpo/
│   ├── hp.obo                               HPO 本体（OBO 格式）
│   ├── hp.json                              HPO 本体（JSON 格式）
│   ├── phenotype.hpoa                       表型注释文件
│   ├── genes_to_phenotype.txt               基因-表型关联
│   └── phenotype_to_genes.txt               表型-基因关联
├── mondo/
│   ├── .gitignore                           忽略下载的本体文件
│   ├── mondo.json                           MONDO 疾病本体
│   └── mondo_hierarchy_cache.json           派生的层次查找（label_to_id、id_to_parents）
└── omim/
    ├── mimTitles.txt                        OMIM 标题条目
    ├── genemap2.txt                         OMIM 基因图谱
    └── morbidmap.txt                        OMIM 疾病图谱
```

**注意：** 仅 `README.md` 纳入 git 跟踪。所有数据文件已 git 忽略，需单独下载。

## 数据源概览

| 来源 | 实体类型 | 目录 | 关键文件 |
|------|---------|------|---------|
| ClinVar | 变异 | `clinvar/` | `variant_summary.txt`、`clinvar.vcf.gz`、`variant_summary.core.tsv` |
| ClinGen | 基因-疾病 | `clingen/` | `Clingen-Dosage-Sensitivity.csv`、`Clingen-Gene-Disease-Summary.csv` |
| dbSNP | 变异（rsID） | `dbSNP/` | `dbsnp_b157.sqlite` |
| HGNC | 基因 | `hgnc/` | `hgnc_complete_set.txt` |
| HPO | 表型 | `hpo/` | `hp.obo`、`hp.json`、`phenotype.hpoa`、`genes_to_phenotype.txt`、`phenotype_to_genes.txt` |
| OMIM | 疾病 | `omim/` | `mimTitles.txt`、`genemap2.txt`、`morbidmap.txt` |
| MONDO | 疾病（本体） | `mondo/` | `mondo.json`、`mondo_hierarchy_cache.json` |

## 实体类型映射

| 来源数据库 | 实体类型 | ID 格式 |
|-----------|---------|---------|
| HGNC | `gene` | `HGNC:12345` |
| OMIM | `disease` | `OMIM:123456` |
| HPO | `phenotype` | `HP:0001250` |
| ClinVar | `variant` | `ClinVarVariation:12345` |
| MONDO | `disease` | `MONDO:0007252` |
| ClinGen | （关系） | 基因-疾病有效性、剂量敏感性 |

## 下载说明

### HGNC

```bash
cd database/terminology_database/hgnc
wget https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt
```

### OMIM（需要免费 API 密钥）

```bash
cd database/terminology_database/omim
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/genemap2.txt"
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/mimTitles.txt"
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/morbidmap.txt"
```

### HPO

```bash
cd database/terminology_database/hpo
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.json
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.obo
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/genes_to_phenotype.txt
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype_to_genes.txt
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa
```

### ClinVar

```bash
cd database/terminology_database/clinvar
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
gunzip variant_summary.txt.gz
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz
```

### ClinGen

```bash
cd database/terminology_database/clingen
wget "https://search.clinicalgenome.org/kb/gene-validity/download" -O Clingen-Gene-Disease-Summary.csv
wget "https://search.clinicalgenome.org/kb/gene-dosage/download" -O Clingen-Dosage-Sensitivity.csv
```

### MONDO

```bash
cd database/terminology_database/mondo
wget https://github.com/monarch-initiative/mondo/releases/download/v2026-06-02/mondo.json
```

## 预处理

### ClinVar Core TSV 提取

完整 `variant_summary.txt`（~3.7 GB）通过提取关键字段并过滤零星审查精简为 `variant_summary.core.tsv`（~700 MB）：

```python
from pathlib import Path
from src.core.standardize_entities_and_align_knowledge.importers import build_clinvar_core_tsv

build_clinvar_core_tsv(
    source_path=Path("database/terminology_database/clinvar/variant_summary.txt"),
    target_path=Path("database/terminology_database/clinvar/variant_summary.core.tsv"),
)
```

### MONDO 层次缓存

`mondo_hierarchy_cache.json` 从 `mondo.json` 派生，用于快速疾病祖先匹配。包含 `label_to_id`（疾病名到 MONDO ID）和 `id_to_parents`（MONDO ID 到父 MONDO ID，传递闭包）。

### dbSNP SQLite 转换

原始 dbSNP VCF 转换为 `dbsnp_b157.sqlite`，用于高效的 rsID 查询。

## 导入 PostgreSQL

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua

# 导入所有来源
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

## 数据更新

1. 重新下载源文件
2. 重新运行预处理（ClinVar core TSV、MONDO 层次缓存）
3. 使用新 `--version` 标签导入：
   ```bash
   uv run python scripts/data/import/import_terminology.py \
     --terminology-root database/terminology_database \
     --version 2026.06 \
     --generate-embeddings
   ```
4. 验证日志中的导入计数
