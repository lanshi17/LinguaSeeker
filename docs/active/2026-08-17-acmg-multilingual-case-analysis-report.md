# ACMG 多语种案例分析报告：4 篇中文全文案例集

**Status:** reference

**Created:** 2026-08-17

**Scope:** 汇总固定层 4 篇中文全文案例的 PM6-eligible 来源观察恢复分析，是四臂实验 Stage-0 来源覆盖层的案例级交付物；不是临床变异解读，不授予正式 ACMG 代码或最终分类。

---

## 1. 背景与测量口径

### 1.1 研究问题

多语种文献是否提升 ACMG/AMP 代码恢复？理论效应是**信息恢复**：原生非英语全文携带英文 pivot 缺失的、可支撑 ACMG 准则复核的来源事实。现有 30 条 ClinVar-fused 消融是结构性空比较（运行器始终提交英文 `source.md`，translated track 原样复制英文文本），不能回答该问题。本报告是替代设计的 Stage-0 证据层：先验证"原生全文是否比同文英文摘要多恢复 PM6-eligible 来源事实"，再做代码级四臂。

### 1.2 固定层定义

主正文为中文、且同一 PDF 含作者英文摘要的全部去重全文：`rett_006`、`rett_007`、`rett_011`、`rett_084`。该层在审计时固定（`benchmark/experiments/acmg_multilingual/source_coverage_facts.json`，绑定语料 revision `5b1f7673e7f4ea7922f3ad7efb79f25fdbfedab7`），测量同一来源"英文摘要可见内容"与"中文全文可见内容"的 PM6-eligible 观察恢复。同名别名（`rett_082/083/087`）与内容重复（`rett_035=rett_036`）已从分母剔除。

### 1.3 事件门槛

一条 PM6-eligible 来源事件的最小门槛：同一篇文章给出**目标 MECP2 变异、受累先证者/病例、双亲均接受检测且目标位点阴性**。Richards 2015 指南下，缺少生物学父母/亲子关系确认时，这至多是 assumed-de-novo 的 **PM6-eligible 观察**，不是 PS2，也不是已完成全部临床裁决的正式代码。

### 1.4 冻结与验证

正向事实逐条哈希绑定：每篇 `source.md` 的 SHA-256 + 每条观察的逐行引文跨度，由只读验证器 `coverage.py` 逐字核验。"摘要无该事实"的 0 计数属临床审读结论，记录在事实表说明中，不作哈希级验证。本报告所有数字以冻结事实表为准。

---

## 2. 案例明细

### 2.1 `rett_006` — 赵培伟 等. Rett综合征的临床特点及MECP2基因突变分析. 中国当代儿科杂志 2014;16(4):393-396（负对照）

- **DOI:** `10.7499/j.issn.1008-8830.2014.04.017`；SHA-256 `a1f17f1e…9a33`
- **变异（5 例）：** `c.913insT`、`c.316C>T`、`c.502C>T`、`c.808C>T`、`c.1126C>T`
- **英文摘要恢复：5**（`source.md:21` 列 5 个变异并称 "No mutations were detected in their parents"）
- **中文全文恢复：5**（`:41` 所有患儿父母均未检测到突变）
- **增量：0**

审读要点：英文摘要已含全部关键事实，中文正文仅重复同一信息，无覆盖增量。

### 2.2 `rett_007` — 刘等. RTT样表型5例患儿的临床特点及基因变异分析. 中国优生与遗传杂志 2023（正对照）

- **DOI:** `10.13404/j.cnki.cjbhh.2023.04.008`；SHA-256 `1b5ba8f2…a94d`
- **变异（4 例）：** `c.509C>T`、`c.538C>T`、`c.842delG`、`c.844delC`
- **英文摘要恢复：0**（`source.md:21` 仅称 4 例诊断 RTT 并对患儿及父母做遗传分析；未列目标变异、无逐例父母阴性）
- **中文全文恢复：4**（`:51` 患儿父母均未检测到突变；`:55` 四例变异表）
- **增量：+4**

审读要点：全文给出亲子 WES、父母均未检出及病例-变异对应表，是本文集最大增量来源。**4 条记录来自同一病例系列，是 1 个独立来源/家系簇，不能当作 4 个独立文献复现。**

### 2.3 `rett_011` — 钟少君 等. MECP2基因变异所致Rett综合征1例临床及遗传学分析. 中国医药导报 2024（正对照）

- **DOI:** `10.20047/j.issn1673-7210.2024.05.45`；SHA-256 `9cfcd607…2dfa`
- **变异：** `c.710C>G (p.Pro237Arg)`（先证者新发错义）
- **英文摘要恢复：0**（`source.md:21` 仅称 "new heterozygous mutation"，未声明双亲均检测且目标位点阴性）
- **中文全文恢复：1**（`:41` 父母未携带该变异位点、变异为新生变异）
- **增量：+1**

审读要点：全文给出先证者/双亲 WES、Sanger 确认、de novo 状态与目标位点父母阴性，构成一条完整的 PM6-eligible 事件链。

### 2.4 `rett_084` — 葛骏文 等. Report of a boy with Rett syndrome caused by a novel MECP2 mutation and literature review. 上海交通大学医学院附属儿童医院 2018（负对照）

- **DOI:** `10.3969/j.issn.1000-3606.2018.11.005`；SHA-256 `b642c536…4786`
- **变异：** `c.194delC (p.S65X)`
- **英文摘要恢复：1**（`source.md:13` 给出变异及 "not found in his parents"）
- **中文全文恢复：1**（`:23` 患儿父母在该位点均无异常）
- **增量：0**

审读要点：英文摘要已含关键事实，中文全文补充取样与 WES+Sanger 细节但无覆盖增量。`c.194delC (p.S65X)` 是强 PVS1 候选事实，但不由本文自动定码。

---

## 3. 汇总结果

| 去重来源 | 英文摘要 | 中文全文 | 增量 | 关键可复核跨度 |
|---|---:|---:|---:|---|
| `rett_006` 赵等 2014 | 5 | 5 | 0 | 摘要 `:21`；全文 `:41` |
| `rett_007` 刘等 2023 | 0 | 4 | +4 | 全文 `:51, :55`（4 变异表） |
| `rett_011` 钟等 2024 | 0 | 1 | +1 | 全文 `:41` |
| `rett_084` 葛等 2018 | 1 | 1 | 0 | 摘要 `:13`；全文 `:23` |
| **合计（事件记录）** | **6** | **11** | **+5** | — |

- **+5 来源观察**，其中 **2/4 来源有增量**（`rett_007`、`rett_011`）。
- 增量分布不均衡：**4/5 来自同一病例系列 `rett_007`**，`rett_011` 贡献 1。
- 11 条均为 PM6-eligible 观察（缺亲子关系确认），**无一条**可仅凭本文确定为正式 PS2 或最终代码。

---

## 4. 边界与限制

1. **不是"ACMG 代码提高 83.3%"**：英文摘要与全文信息量不同、样本仅限中文且很小、无配对随机化，不做显著性检验。
2. **事件记录 ≠ 独立样本**：4 条新增来自同一病例系列，不能按 4 个独立文献复现计数。
3. **PM6-eligible ≠ PS2/正式代码**：11 条全部缺少生物学父母/亲子关系确认；不得因论文自报 de novo/PS2 而继承该结论。
4. **增量不能归因于"非英语本身"**：反例 — 韩文 `rett_066` 的 Fig. 1 图注已含 `c.455C>G; P152R` 仅见于患者（非韩文正文新增）；西班牙文 `rett_035/036` 称 `c.806del` de novo 但未给父母目标基因型，不能列为 PM6/PS2；英文全文 `rett_009` 也报告 `c.538C>T (p.Arg180Ter)` 父母野生型 + Sanger segregation，同为 PM6-eligible 观察。
5. **同变异独立英语文献 ≠ 同病例配对**：如 `c.317G>A (p.Arg106Gln)` 的英语研究（Zhang 等 2019）是不同先证者、嵌合状态与表型，不能转换为病例级 EN→多语种配对增益。
6. **无任一案例可确定性完成最终 ACMG 代码裁决**：PVS1/PS3 等依赖转录本、机制、assay 等文章外事实；本层未发现可直接满足 PM3（AR + P/LP 反式伙伴）、PP1/BS4、PS3/BS3 或 PS4 的事件。

---

## 5. 与三臂/四臂实验的关系

- **Stage-0（本报告）**：来源覆盖层已冻结并验证，支持的最强表述为"原生中文全文比同文英文摘要多恢复 PM6-eligible 来源事实（+5，2/4 来源）"。
- **三臂（同一来源内）**：`english_pivot` / `native_only` / `dual_track` 基础设施已就绪；正向来源 `rett_007`、`rett_011` 的英文全文为**模型翻译 + 模型审校**（`model_reviewed`，非人工；2/6 ready），其余 4 篇仍 `needs_translation_review`。正式模型运行与盲法裁决待人工确认。
- **Stage-1 四臂（语料级）**：48 去重来源家族清单已冻结（en 32 / zh 8 / ja 3 / ru 3 / ko 2；6 跨语种配对锚）。已为两篇正向来源预选 index assertion：`rett_007 → c.509C>T`、`rett_011 → c.710C>G`（模型提议，待临床确认），计划代码家族均为 `PS2_PM6`。

---

## 6. 结论

**支持：** 原生非英语全文可以比同文英文摘要多恢复 ACMG 复核所需的 PM6-eligible 来源事实（6 → 11，+5；2/4 来源有增量）。

**不支持：** 多语种使正式 ACMG 代码或最终分类"提升更明显"。来源覆盖增益须先通过译文审校门禁、代码级四臂与两名独立盲法 ACMG/AMP 裁决（分歧由第三审解决），方可报告正式代码恢复量。任何下游声明必须写明 `model_reviewed` 状态，不得表述为人工审校。

---

## 关联工件

| 工件 | 位置 |
|---|---|
| 冻结事实表（本报告数据源） | `benchmark/experiments/acmg_multilingual/source_coverage_facts.json` |
| 只读覆盖验证器 | `benchmark/experiments/acmg_multilingual/coverage.py` |
| 试点审校清单（2/6 ready） | `benchmark/experiments/acmg_multilingual/pilot_model_reviewed.json` |
| 正向子集清单 | `benchmark/experiments/acmg_multilingual/pilot_positive_ready.json` |
| 候选清单（6 去重来源） | `benchmark/experiments/acmg_multilingual/pilot_candidates.json` |
| Stage-1 语料清单（48 家族） | `benchmark/experiments/acmg_multilingual/stage1_corpus_manifest.json` |
| 方法学审计 | `docs/active/2026-08-14-acmg-multilingual-evidence-code-audit.md` |
| 三臂实验设计 | `docs/active/2026-08-14-acmg-multilingual-code-experiment.md` |
| 四臂实验设计 | `docs/active/2026-08-15-acmg-multilingual-four-arm-design.md` |

## 参考方法学

- Richards S, et al. Standards and guidelines for the interpretation and reporting of sequence variants. *Genet Med.* 2015. DOI: `10.1038/gim.2015.30`.
- Abou Tayoun AN, et al. Recommendations for interpreting the loss of function PVS1 ACMG/AMP variant criterion. *Hum Mutat.* 2018. DOI: `10.1002/humu.23626`.
- Biesecker LG, et al. ClinGen guidance for PP1/BS4 segregation evidence. *Am J Hum Genet.* 2023. DOI: `10.1016/j.ajhg.2023.11.009`.
