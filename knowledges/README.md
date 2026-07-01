# Knowledges

> ACMG 变异解读的领域知识参考文档。作为系统 LLM 证据提取和分类管线的权威上下文。

## 概述

本目录包含生物医学领域知识文档，涵盖 ACMG/AMP 变异解读指南、ClinGen SVI 功能证据评估标准、基因-疾病有效性审查 SOP，以及结构化证据字段目录。这些文档作为 LLM 管线的 prompt/上下文资源加载，不是运行时依赖。

## 内容

| 文件 | 大小 | 来源 | 描述 |
|------|------|------|------|
| `acmg-2015.md` | 125 KB | Richards et al., *Genetics in Medicine* (2015) | ACMG/AMP 2015 序列变异解读指南 |
| `acmg-2019.md` | 67 KB | Brnich et al., *Human Mutation* (2019) | ClinGen SVI PS3/BS3 功能证据评估标准 |
| `acmg-2021-2026-outline.md` | 17 KB | 多来源 | ACMG 指南 2021-2026 发展概述（中文） |
| `gdv-12.md` | 166 KB | ClinGen (2020) | Gene-Disease Validity Curation Process SOP v12 |
| `evidence-field-catalog.json` | ~69 KB | ACMG 2015 + ClinGen SVI 2019 + GDV SOP v12 | 结构化证据字段目录：11 个类别（A-K）166 个字段 |
| `evidence-field-catalog.md` | ~36 KB | 同 JSON | 人类可读渲染：按类别表格、ACMG 28 码覆盖矩阵、提取分组 |

## 用途

这些文档被后端作为领域知识用于：

- **证据提取** — LLM prompt 引用 ACMG 标准分类证据强度（PS1、PM1、BA1 等）
- **基因-疾病有效性评估** — GDV SOP 指导自动化审查评分
- **变异分类** — 2015 指南的结构化规则将提取的证据映射到分类层级
- **证据字段目录** — `evidence-field-catalog.json` 提供 166 个证据字段（A-K）的机器可读目录，用于提取管线（A-J 活跃组）、基准指标和 GDV 审查（K 外部组）
