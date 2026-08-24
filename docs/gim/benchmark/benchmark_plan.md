# Benchmark Evaluation Plan

**关联文档:** [ClinGen + ClinVar Fused Benchmark Dataset Plan](../../active/2026-06-15-clingen-clinvar-fused-benchmark-dataset-plan.md)

---

## 1. 评估目标

为 NAR Web Server 投稿提供定量性能数据，证明 Lingua Seeker 在以下方面的有效性：

1. **证据提取准确性**（Precision / Recall / F1）
2. **跨语言一致性**（中文 vs 英文文献提取对比）
3. **双轨融合增益**（双轨 vs 单轨提取的改进）
4. **实体标准化准确率**
5. **系统性能**（端到端处理时间、检索覆盖度）

---

## 2. 数据集

### 2.1 Dataset 1: ClinGen-30（冒烟测试）

- **来源:** ClinGen Gene-Disease Validity Curation
- **规模:** 30 篇文献
- **金标字段:** gene_symbol, disease_label, gene_disease_relationship
- **用途:** 快速回归验证，不用于论文正文

### 2.2 Dataset 2: ClinGen + ClinVar Fused（主评估数据集）

- **来源:** ClinGen GDI + ClinVar 融合
- **规模:** 50-100 篇文献（目标）
- **金标字段:** ~10 个（gene, disease, variant_hgvs_c, variant_hgvs_p, variant_type, inheritance, clinical_significance, classification, gcep, review_status）
- **语言分布:** ~60% 英文 + ~30% 中文 + ~10% 其他语言
- **用途:** 论文正文主结果

### 2.3 Dataset 3: Cross-Lingual Case Set（案例展示）

- **规模:** 5-10 篇纯中文文献（英文文献库中未收录的）
- **用途:** 展示跨语言能力，证明非英语文献的增量价值
- **评估方式:** 人工确认提取的证据是否正确

---

## 3. 评估指标

### 3.1 证据提取层（gene-disease 层）

| 指标 | 计算方式 | 适用层 |
|------|---------|--------|
| Precision (P) | TP / (TP + FP) | gene-disease |
| Recall (R) | TP / (TP + FN) | gene-disease |
| F1 | 2 * P * R / (P + R) | gene-disease |

- **匹配规则:** 提取值与金标值在标准化后精确匹配（gene -> HGNC symbol, disease -> MONDO/OMIM ID）

### 3.2 变异提取层

| 指标 | 计算方式 | 说明 |
|------|---------|------|
| Precision | 正确提取的变异 / 系统提取的总变异 | Recall 不可测（文中变异集合不完整） |

- **匹配规则:** HGVS 表达式归一化后匹配

### 3.3 实体标准化准确率

| 指标 | 计算方式 |
|------|---------|
| Standardization Accuracy | 正确标准化的实体 / 总提取实体 |
| Match Rate | 成功匹配到标准数据库的实体 / 总提取实体 |

### 3.4 跨语言对比

| 对比项 | 说明 |
|--------|------|
| EN-only P/F1 | 仅英文文献的 P/F1 |
| ZH-only P/F1 | 仅中文文献的 P/F1 |
| Dual-track gain | 双轨融合 vs 仅原文提取的 F1 差值 |
| Unique evidence from ZH | 仅从中文文献中发现的、英文库未覆盖的证据数 |

### 3.5 系统性能

| 指标 | 说明 |
|------|------|
| End-to-end latency | 单篇文献从输入到证据输出的时间 |
| Source coverage | 检索命中的数据源数 / 总数据源数 |
| Document parse success rate | 成功解析的文档 / 总文档数 |

---

## 4. 评估流程

```
1. 准备金标数据集 (Dataset 2)
   -> 验证: 金标字段完整，语言分布合理

2. 批量运行 Lingua Seeker 处理金标文献
   -> 验证: 所有文献成功处理，无 pipeline 失败

3. 提取系统输出，与金标逐字段比对
   -> 验证: 比对脚本正确，边界 case 处理明确

4. 计算各层指标
   -> 验证: 指标计算与公式一致

5. 人工审核争议 case（2 名标注者，Cohen's κ）
   -> 验证: κ ≥ 0.70

6. 生成结果图表
   -> 验证: 图表清晰可读，数据与表格一致
```

---

## 5. 结果展示方案

### Figure 4: Benchmark Results

- **左图:** 分字段 P/R/F1 分组柱状图（gene, disease, variant, inheritance, classification）
- **右图:** 跨语言对比（EN-only vs ZH-only vs Dual-track F1）
- **附表:** 完整数值表 + 置信区间

### Supplementary Table S1

- 每篇文献的详细提取结果 vs 金标对照

### Supplementary Table S2

- 实体标准化详细结果（原始值 -> 标准值 -> 匹配状态 -> 数据源）

---

## 6. 对照组（可选）

如果审稿人要求与现有工具对比：

| 工具 | 对比维度 | 可行性 |
|------|---------|--------|
| Mastermind (Genomenon) | 文献检索覆盖率 | 可行（手动查询对比） |
| LitVar | 变异-文献关联 | 可行（API 对比） |
| GPT-4 直接提取 | 证据提取质量 | 可行（提供原文让 GPT-4 直接提取，对比系统输出） |

---

## 7. 时间规划

| 步骤 | 预计工时 | 依赖 |
|------|---------|------|
| Dataset 2 金标准备 | 3-5 天 | ClinGen/ClinVar 数据下载 + 人工筛选 |
| 批量运行 | 1 天 | 系统 deploy 到稳定环境 |
| 结果比对与计算 | 2 天 | 比对脚本开发 |
| 人工审核 | 2-3 天 | 2 名标注者 |
| 图表制作 | 1 天 | - |
| **总计** | **9-12 天** | |
