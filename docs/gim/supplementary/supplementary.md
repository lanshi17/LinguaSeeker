# Supplementary Materials

> GIM Submission 补充材料
> 数据来源: `benchmark/data/reports/nar_ablation/` (2026-08-12)

---

## Supplementary Table S1: Ablation Study — Per-Entry Field Match (EN-only vs Dual-track)

30 条 ClinGen/ClinVar 融合条目，8 字段金标匹配数对比。数据来源: `ablation_report.json`。

| Entry | Gene | EN matched | Dual matched | Δ | Field changes (EN→Dual) |
|-------|------|-----------|--------------|---|--------------------------|
| fused_000 | CFTR | 4 | 4 | 0 | — |
| fused_001 | ABCA4 | 6 | 6 | 0 | — |
| fused_002 | ACADVL | 5 | 5 | 0 | — |
| fused_003 | ACTA1 | 5 | 5 | 0 | — |
| fused_004 | ACTA1 | 6 | 6 | 0 | — |
| fused_005 | ADA | 3 | 4 | +1 | +variant_type (missense) |
| fused_006 | APC | 5 | 5 | 0 | — |
| fused_007 | ATM | 1 | 1 | 0 | — |
| fused_016 | DNM2 | 5 | 5 | 0 | +moi_reported, −gene_disease_rel |
| fused_022 | GJB2 | 4 | 3 | −1 | −disease_diagnosis |
| fused_024 | GP1BA | 0 | 1 | +1 | +gene_symbol (GP1BA) |
| fused_028 | HBB | 4 | 3 | −1 | −variant_hgvs_c |
| … (其余 18 条) | — | = | = | 0 | — |

**汇总:** 均值 3.57/8 (两种模式相同); 3/30 条目获得 ≥1 字段 (fused_005, fused_016, fused_024); 2/30 丢失 1 字段 (fused_022, fused_028); 26/30 持平。

## Supplementary Table S2: Field-Level Multilingual Benefit (ZH-only Fields)

中文轨独有证据的字段分布。数据来源: `multilingual_contribution_report.json` (29 valid entries)。

| Field ID | 字段 | ZH-only 条目数 |
|----------|------|---------------|
| B.clinical_phenotypes | 临床表型 | 3 |
| F.assay_type | 检测类型 | 3 |
| J.clinvar_assertion | ClinVar 判定 | 2 |
| B.hpo_terms | HPO 术语 | 2 |
| B.age_of_onset | 发病年龄 | 2 |
| B.disease_diagnosis | 疾病诊断 | 2 |
| C.de_novo_status | 新生变异状态 | 2 |
| B.mode_of_inheritance_reported | 遗传方式 | 1 |
| C.inheritance_source | 遗传来源 | 1 |
| H.contradiction_type | 矛盾类型 | 1 |
| B.case_count | 病例数 | 1 |
| A.variant_consequence_class | 变异后果类型 | 1 |
| A.functional_domain_or_hotspot | 功能域/热点 | 1 |
| B.sex | 性别 | 1 |

合计 23 个 ZH-only 字段实例, 分布于 13/29 条目 (44.8%)。

## Supplementary Note S1: Literature Provider Coverage

15+ 数据源详细列表及覆盖范围。

| Provider | 语言/地区 | API 类型 | 覆盖文献数 | 备注 |
|----------|---------|---------|-----------|------|
| Crossref | International | REST | - | DOI 元数据 |
| PubMed | English | E-utilities | - | 生物医学核心 |
| OpenAlex | International | REST | - | 开放学术 |
| EuropePMC | European | REST | - | 全文开放获取 |
| PMC | English | REST | - | 全文生物医学 |
| DOAJ | International | REST | - | 开放获取期刊 |
| J-STAGE | Japanese | REST | - | 日本科学技术 |
| Unpaywall | International | REST | - | 开放获取解析 |
| CyberLeninka | Russian | Scrape | - | 俄罗斯学术 |
| Hans Publishers | Chinese | Scrape | - | 汉斯出版社 |
| PubScholar | Chinese | Scrape | - | 公共学术 |
| KoreaScience | Korean | Scrape | - | 韩国科学 |
| ChinaXiv | Chinese | Scrape | - | 中国预印本 |
| Redalyc | Spanish/Portuguese | Scrape | - | 拉美期刊 |
| arXiv/bioRxiv | English | REST | - | 预印本 |

---

## Supplementary Note S2: ACMG Evidence Field Catalog

系统支持的 ACMG 证据字段目录。

| 证据代码 | 字段名 | 描述 | 数据类型 |
|---------|--------|------|---------|
| A.gene_symbol | Gene Symbol | 基因符号 | text |
| A.variant_hgvs_c | Variant HGVS (c.) | cDNA 层变异命名 | text |
| A.variant_hgvs_p | Variant HGVS (p.) | 蛋白层变异命名 | text |
| A.variant_type | Variant Type | 变异类型 | enum |
| B.disease_diagnosis | Disease Diagnosis | 疾病诊断 | text |
| A.gene_disease_relationship | Gene-Disease Relationship | 基因-疾病关系 | enum |
| B.mode_of_inheritance_reported | Mode of Inheritance | 遗传方式 | enum |
| J.expert_panel_assertion | Expert Panel Assertion | 专家小组判定 | enum |
| J.clinvar_assertion | ClinVar Assertion | ClinVar 临床意义 | enum |
| ... | ... | ... | ... |

---

## Supplementary Note S3: Translation Quality Validation

多阶段翻译质量校验机制。

1. **Terminology Preservation:** 医学术语词典约束翻译
2. **Structure Alignment:** 段落/表格结构保持
3. **Draft Translation:** 初译
4. **Review & Refine:** 审校 LLM 校正
5. **Quality Score:** 翻译质量评分（BLEU / 实体保留率 / 术语一致性）

---

## Supplementary Note S4: System Performance Metrics

| 指标 | 数值 | 说明 |
|------|------|------|
| End-to-end latency (per doc) | TBD | 从输入到证据输出 |
| Phase 1 latency | TBD | 文献获取+解析 |
| Phase 2 latency | TBD | 翻译+证据提取 |
| Phase 3 latency | TBD | 实体标准化 |
| Concurrent documents | TBD | 并行处理能力 |
| Document parse success rate | TBD | 成功解析率 |
| Source coverage (avg) | TBD | 平均命中的数据源数 |

---

## Supplementary Note S5: Comparison with Existing Tools

| Feature | Lingua Seeker | Mastermind | LitVar | ClinVar Miner |
|---------|--------------|------------|--------|---------------|
| 文献语言 | 多语言 (7+) | 英文 | 英文 | 英文 |
| 检索方式 | 语义+关键词 | 关键词 | 关键词 | 数据库查询 |
| 全文解析 | 是 (MinerU) | 否 | 否 | 否 |
| 证据提取 | LLM 结构化 | 人工标注 | 关键词匹配 | 无 |
| 实体标准化 | 是 (HGNC/OMIM/HPO/ClinVar) | 部分 | 部分 | 是 |
| ACMG 字段 | 是 | 否 | 否 | 否 |
| 专家审查 | 是 (Delta audit) | 是 | 否 | 否 |
| 开源 | 是 | 否 | 否 | 否 |
| Web server | 是 | 是 | 是 | 是 |
