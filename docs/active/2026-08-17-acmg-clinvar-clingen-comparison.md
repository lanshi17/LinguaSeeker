# MECP2 原文变异与 ClinVar/ClinGen 当前证据对比

**Status:** reference

**Created:** 2026-08-17

**查询日期：** 2026-08-17

**范围：** 对本项目 16 个非英语来源中出现的 15 个去重 MECP2 变异进行原文证据与当前 ClinVar/ClinGen 记录对比。ClinVar 数据通过 NCBI E-utilities/ClinVar Variation 页面查询；转录本等价关系用 Ensembl Variant Recoder 复核。ClinGen 的 CAID 是等位基因注册标识，不等同于 ClinGen 专家组临床裁决。

> **2026-08-19 更正：** `c.194delC`（`rett_084`）与 ClinVar `VCV001076185`（`c.195del`/`c.231del`，SPDI `NC_000023.11:154032388:T:`）只是相邻 1 bp，不是同一 SPDI，也不是 LOVD `c.194C>G p.S65X`。规范 id 改为 `unmatched_c.194delC`。映射计数不因这条回退：仍是 13/15 可映射、12 个 VCV；未精确匹配的仍是 `c.913insT` 与 `c.1217_1445del`，外加这条“近邻薄记录”。口径见 [2026-08-19 字段桥](2026-08-19-acmg-multilingual-field-bridge.md)。

> **2026-08-18 更正：** `c.844delC` 已映射到 `VCV000143702`（`NM_001110792.2:c.844del p.Arg282fs`，Pathogenic，9 SCV）。2026-08-17 的“未安全找到精确 VCV”是裸搜 `c.844delC` 的检索串伪影，且易与无义突变 `c.844C>T`（`VCV000011815`）混淆。更正后可安全映射 **13/15** 个去重变异、**12** 个不同 VCV；仍未精确匹配的是 `c.913insT` 和 `c.1217_1445del`。SCV/RCV 总数随该条增加（+9 SCV、+6 RCV），不得把 17 日的 307/77 继续写成当前快照。完整授码口径见 [2026-08-18 审稿口径案例分析](2026-08-18-acmg-multilingual-case-analysis-reviewer.md)。

> **2026-08-17 核心结果（历史快照，已被上一则更正）：** 本地原文共有 **19 条来源级病例/观察记录**，其中 **14 条 PM6-eligible**。当时查询可安全映射到 **12/15** 个去重变异、**11** 个不同 ClinVar VCV，累计 **307** 条 SCV、**77** 条 RCV。12 个可映射变异中，ClinVar 汇总为 **9** 个 Pathogenic、**2** 个 Pathogenic/Likely pathogenic、**1** 个 Benign（专家组）。当时未能精确匹配的 3 个变异是 `c.913insT`、`c.844delC` 和 `c.1217_1445del`。

---

## 1. 计数口径

### 1.1 原文侧

- **来源级观察记录：** 同一变异在不同文章、不同病例或同一病例系列中的每个独立病例观察单独计数。
- **PM6-eligible：** 同一原文同时给出目标变异、受累病例、父母目标位点阴性；没有亲子关系确认时不升级为 PS2。
- 同一变异跨来源不合并为一个病例；同一病例系列的多个变异不当作独立文献复现。

### 1.2 ClinVar/ClinGen 侧

- **VCV：** ClinVar variant-level record；不同转录本可能被聚合到同一个 VCV/等位基因记录。
- **SCV：** ClinVar submitted record。它是提交记录数，不是独立实验数，也不等于独立研究数。
- **RCV：** ClinVar variant-condition record。同一等位基因可关联多个疾病或表型，因此不能直接当作独立证据样本数。
- **ClinVar classification：** 数据库聚合分类，不是本项目的 ACMG 正式裁决；尤其不能把 ClinVar 的 Pathogenic 标签直接拆成 PS2/PVS1/PM2 等代码。
- **ClinGen CAID：** 规范等位基因标识。CAID 存在说明等位基因已被注册/关联，不说明已有专家组定级。

---

## 2. 总体对比

| 指标 | 本地原文分析 | ClinVar/ClinGen 当前查询 | 解释 |
|---|---:|---:|---|
| 去重变异数 | **15** | — | 以本项目原文 HGVS/蛋白后果去重 |
| 来源级病例/观察记录 | **19** | — | 文章、病例或家系级记录 |
| PM6-eligible 记录 | **14** | — | 其中 0 条自动升级 PS2 |
| 可安全映射到 ClinVar 的去重变异 | — | **13/15**（2026-08-18；17 日快照为 12/15） | 仍有 2 个需结构/转录本进一步核验 |
| 不同 ClinVar VCV | — | **12**（2026-08-18；17 日快照为 11） | c.502 与 c.538 共用 VCV11828；`c.844delC` 为独立的 VCV143702 |
| ClinVar SCV 提交 | — | **316**（2026-08-18；17 日 11 个 VCV 为 307） | 12 个不同 VCV 的去重总和 |
| ClinVar RCV 记录 | — | **83**（2026-08-18；17 日 11 个 VCV 为 77） | 12 个不同 VCV 的去重总和 |
| ClinGen CAID | — | **12/12 可映射变异** | CAID 为等位基因标识，不是专家裁决 |
| ClinVar Pathogenic | — | **10/13**（2026-08-18；17 日为 9/12） | 聚合分类 |
| ClinVar Pathogenic/Likely pathogenic | — | **2/13** | 聚合分类 |
| ClinVar Benign | — | **1/13** | `c.1126C>T (p.Pro376Ser)` 的转录本等价记录；专家组 |
| 本项目正式 ACMG 代码 | **0** | 不适用 | 本项目仍需独立盲法 ACMG/AMP 审阅 |

**不能直接做的比较：** `19 条原文观察` 与 `316 条 SCV` 不是同一统计单位。前者是病例/文章事实，后者是数据库提交记录；316 不能写成 316 个独立实验或 316 条独立 ACMG 证据。

---

## 3. 逐变异对比表

| 原文变异 | 原文来源级观察 | PM6-eligible | 当前 ClinVar/ClinGen 对应 | ClinVar 当前聚合分类 | Review status | SCV / RCV | ClinGen CAID | 对本项目的意义 |
|---|---:|---:|---|---|---|---:|---|---|
| `c.502C>T (p.R168X)` | 2 | 2 | `VCV000011828.114`，与 c.538C>T 共用基因组等位基因记录 | Pathogenic | multiple submitters, no conflicts | 54 / 9 | `CA256092` | 原文新发事实与数据库 LoF/既往病例证据一致；数据库记录还涉及 NMD、功能和既往病例，但不能自动转成本项目正式代码 |
| `c.316C>T (p.R106W)` | 1 | 1 | `VCV000011814.96`（ClinVar 当前主表示为 `NM_001110792.2:c.352C>T p.Arg118Trp`；与源转录本等价） | Pathogenic/Likely pathogenic | multiple submitters, no conflicts | 34 / 10 | `CA256089` | 原文 MBD 定位与 ClinVar 多提交支持形成复核入口 |
| `c.1126C>T (p.P376S)` | 1 | 1 | `VCV000095184.32`（当前主表示 `c.1162C>T p.Pro388Ser`；源转录本等价） | **Benign** | **reviewed by expert panel** | 16 / 4 | `CA148292` | **关键冲突点：** 原文把它作为 RTT 患儿变异，但当前 ClinVar 专家组聚合为 Benign；必须先核对 HGVS、样本、转录本和文章病例，不能自动沿用 P/LP |
| `c.808C>T (p.R270X)` | 1 | 1 | `VCV000011815.120`（当前主表示 `c.844C>T p.Arg282Ter`；源转录本等价） | Pathogenic | multiple submitters, no conflicts | 49 / 9 | `CA172577` | 原文无义 + 当前多提交一致，PVS1/LoF 专家复核价值高 |
| `c.913insT (p.K305fs)` | 1 | 1 | **未安全找到精确 ClinVar VCV**；规范化为 `NM_004992.4:c.913_914insT` / `NC_000023.11:g.154030914_154030915insA`，直接查询未返回精确匹配 | — | — | — | — | 原文 PVS1 候选仍保留；当前应优先做结构化 indel/CNV 查询，不能把同坐标的其他替代等位基因当作本变异 |
| `c.509C>T (p.Thr170Met)` | 2 | 1 | `VCV000011811.138` | Pathogenic/Likely pathogenic | multiple submitters, no conflicts | 61 / 12 | `CA211252` | 原文同时包含 de novo 候选和母系遗传反例；ClinVar P/LP 不消除病例级遗传来源冲突 |
| `c.538C>T (p.Arg180Ter)` | 1 | 1 | `VCV000011828.114`，与 c.502C>T 为同一基因组等位基因的转录本等价表示 | Pathogenic | multiple submitters, no conflicts | 54 / 9（与 c.502 共享） | `CA256092` | 跨语言同变异不能重复累加 ClinVar 54 条提交；本地仍按病例/来源去重 |
| `c.842delG (p.Gly281AlafsTer20)` | 1 | 1 | `VCV000095202.89`（当前主表示 `NM_001110792.2:c.842del p.Gly281fs`） | Pathogenic | **reviewed by expert panel** | 37 / 11 | `CA199475` | 原文移码与 ClinGen/ClinVar 专家组记录高度一致；PVS1 仍需按当前转录本和规则单独审阅 |
| `c.844delC (p.Arg282GlufsTer19)` | 1 | 1 | **`VCV000143702.18`**（2026-08-18）：`NM_001110792.2:c.844del p.Arg282fs`；e2 等价 `NM_004992.3:c.808del p.Arg270fs`。17 日裸搜失败属检索串伪影 | Pathogenic | multiple submitters, no conflicts | 9 / 6 | 蛋白别名含 R282fs / R270fs | **帧移，不是无义 `c.844C>T`（`VCV000011815`）。** 原文 PM6 观察可引用；库分类已是 Pathogenic，不构成 ClinVar 缺口 |
| `c.710C>G (p.Pro237Arg)` | 1 | 1 | `VCV000143653.60` | Pathogenic | multiple submitters, no conflicts | 13 / 7 | `CA270500` | 原文自报 PS2+PM2+PP3；当前 ClinVar P 记录支持进入外部事实核验，但不替代亲子关系和 PM2/PP3 审阅 |
| `c.194delC (p.S65X)` | 1 | 1 | **相邻，非同一 SPDI。** `VCV001076185` 是 `c.195del`/`c.231del p.Glu66fs/Glu78fs`（查询日 2026-08-19）。规范 id `unmatched_c.194delC` | Pathogenic（近邻记录） | single submitter, criteria provided | 1 / 1 | `CA2499226478` | 原文 Sanger 少一个 C；库记录疾病为新生儿脑病。不得写成已证明同一等位基因 |
| `c.468C>G (p.Asp156Glu)` | 3 | 1 | `VCV000095196.36`，当前主表示 `c.504C>G p.Asp168Glu`；源转录本等价 | Pathogenic | multiple submitters, no conflicts | 11 / 3 | `CA202769` | 中文/俄文三来源同变异与 ClinVar P 记录形成跨语言锚；不能把 3 篇文章当作 3 个独立 ClinVar 证据集 |
| `c.455C>G (p.P152R)` | 1 | 1 | `VCV000143579.51`，当前主表示 `c.491C>G p.Pro164Arg`；源转录本等价 | Pathogenic | **reviewed by expert panel** | 25 / 8 | `CA270424` | 原文韩文 de novo + ClinVar 专家组 P；仍需分开处理本地 PS2 门禁和数据库既有结论 |
| `c.622C>T (p.Q208X)` | 1 | 0 | `VCV000143641.24`，当前主表示 `c.658C>T p.Gln220Ter`；源转录本等价 | Pathogenic | multiple submitters, no conflicts | 6 / 3 | `CA270487` | 原文父母数据缺失，但 ClinVar P 不能反向补足本地 PM6/PS2 |
| `c.1217_1445del (p.Gln406Profs*30)` | 1 | 0 | **未安全找到精确 ClinVar VCV/CAID**；基因组区间检索过宽，命中大量其他 CNV | — | — | — | — | 需按结构变异/CNV 规范重新定位，不能把附近 Xq28 CNV 记录迁移到该缺失 |

---

## 4. 证据数量变化

### 4.1 从病例事实看

| 层级 | 原本 | 当前扩展后 | 增量 |
|---|---:|---:|---:|
| 非英语来源 | 4 篇中文全文 | 16 篇非英语全文 | +12 篇 |
| 去重变异 | 原 4 篇涉及 11 条 PM6-eligible 观察 | 15 个去重变异 | +4 个去重变异 |
| 来源级观察记录 | 原 4 篇 11 条 PM6-eligible | 19 条来源级病例/观察记录 | +8 条记录 |
| PM6-eligible | 11 | 14 | **+3** |
| PS2 正式代码 | 0 | 0 | 0 |
| PVS1 候选事件 | 原报告未冻结为正式代码 | 10 | 新增候选台账，不是正式授码 |

“+8 条来源级观察”包含未满足 PM6 的母系遗传、父母未检测和结构变异记录；因此不能把它们全部写成 PM6 增量。真正的 PM6-eligible 增量是 **+3**。

### 4.2 从 ClinVar 数据库看

| 层级 | 当前查询结果 |
|---|---:|
| 可映射的本地去重变异 | 13/15（2026-08-18） |
| 不同 ClinVar VCV | 12 |
| SCV 提交总数（去重 VCV） | 316 |
| RCV 记录总数（去重 VCV） | 83 |
| ClinGen CAID | 随可映射变异补入；17 日 12 条 CAID 仍有效 |
| ClinVar P | 10 |
| ClinVar P/LP | 2 |
| ClinVar Benign | 1（专家组，c.1126C>T 转录本等价记录） |
| 精确匹配未完成 | 2：`c.913insT`、`c.1217_1445del` |

### 4.3 不能合并解释的两类“证据”

- **原文 14 条 PM6-eligible** 是病例级家系事实资格，不是数据库分类证据数量。
- **ClinVar 316 条 SCV** 是提交记录数量，不是 316 个独立家系，也不是 316 条可相加 ACMG 代码。

正确的优势表述是：

> 本地多语种全文新增了 3 条可复核 PM6-eligible 家系事实，并对 15 个去重变异建立了 ClinVar/ClinGen 外部证据映射；其中 13 个变异可关联到 12 个 ClinVar VCV、316 条 SCV 提交和 83 条 RCV 记录（2026-08-18）。该外部映射同时发现了 `c.1126C>T (p.Pro376Ser)` 的 ClinVar 专家组 Benign 冲突，证明本项目能够发现并阻断论文自报与数据库证据之间的潜在矛盾。`c.913insT` 仍无精确 VCV；`c.194delC` 只有相邻 1 bp 的薄记录，不是同一 SPDI。

---

## 5. 最重要的临床审阅风险

### 5.1 `c.1126C>T (p.Pro376Ser)` 的数据库冲突

本地 `rett_006` 将其作为 RTT 患儿中的 MECP2 错义变异并计入 PM6-eligible；当前 ClinVar 通过转录本等价记录 `VCV000095184.32` 聚合为 **Benign，reviewed by expert panel**。这不是可以自动解决的冲突，必须核对：

1. 原文变异 HGVS 与当前 ClinVar 等位基因是否完全相同；
2. 原文使用的转录本版本；
3. ClinVar 专家组的具体 RCV、适用疾病和证据依据；
4. `rett_006` 患儿的表型、测序质量、家系状态和样本身份；
5. 是否存在同义/错义转录本映射或历史 HGVS 错配。

在核验完成前，该变异可以保留为原文 PM6-eligible 观察，但不应写成“ClinVar 与原文共同支持致病”。

### 5.2 转录本等价不等于证据相加

以下记录使用不同转录本表示同一基因组等位基因：

- `c.502C>T (p.R168X)` ↔ `c.538C>T (p.Arg180Ter)`；
- `c.316C>T (p.R106W)` ↔ 当前 `c.352C>T (p.Arg118Trp)`；
- `c.1126C>T (p.P376S)` ↔ 当前 `c.1162C>T (p.Pro388Ser)`；
- `c.808C>T (p.R270X)` ↔ 当前 `c.844C>T (p.Arg282Ter)`；
- `c.844delC (p.Arg282fs)` ↔ `NM_004992.3:c.808del p.Arg270fs`（`VCV000143702`，与上一行无义突变不是同一等位基因）；
- `c.468C>G (p.Asp156Glu)` ↔ 当前 `c.504C>G (p.Asp168Glu)`；
- `c.455C>G (p.P152R)` ↔ 当前 `c.491C>G (p.Pro164Arg)`；
- `c.622C>T (p.Q208X)` ↔ 当前 `c.658C>T (p.Gln220Ter)`。

如果不先做基因组等位基因归一化，容易把同一 ClinVar VCV、同一 ClinGen CAID 和同一批 SCV 重复计数。

### 5.3 ClinGen 状态的正确读法

- CAID 是等位基因注册和规范化标识；
- “reviewed by expert panel”是 ClinVar 的提交/聚合审阅状态；
- ClinGen CAID 本身不代表某个 ACMG 代码已经满足；
- ClinVar Pathogenic 也不自动等于本项目可以授予 `PS2+PVS1+PM2`。

---

## 6. 建议的下一步

1. 对 13 个已映射变异保存 VCV、RCV、SCV、CAID 和查询日期。
2. 优先审阅 `c.1126C>T` 的 ClinVar 专家组 Benign 冲突。
3. 对仍未匹配的 2 个变异执行结构化 indel/CNV 专项检索：`c.913insT`、`c.1217_1445del`。`c.844delC` 已映射到 `VCV000143702`，不要再列入未匹配队列。
4. 将 ClinVar 既有证据与本地原文事件分开存储：`external_database_evidence` 不覆盖 `source_fact_evidence`。
5. 仅在完成 HGVS、亲子关系、转录本和专家审阅后，更新 `PS2/PVS1/PM2/PP3` 的正式状态。

---

## 7. 官方查询入口

- [ClinVar programmatic access](https://www.ncbi.nlm.nih.gov/clinvar/docs/programmatic_access/)
- [ClinVar review status](https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/)
- [ClinVar c.502/c.538 VCV000011828](https://www.ncbi.nlm.nih.gov/clinvar/variation/11828/)
- [ClinVar c.316 transcript-equivalent VCV000011814](https://www.ncbi.nlm.nih.gov/clinvar/variation/11814/)
- [ClinVar c.1126 transcript-equivalent VCV000095184](https://www.ncbi.nlm.nih.gov/clinvar/variation/95184/)
- [ClinVar c.808 transcript-equivalent VCV000011815](https://www.ncbi.nlm.nih.gov/clinvar/variation/11815/)
- [ClinVar c.509 VCV000011811](https://www.ncbi.nlm.nih.gov/clinvar/variation/11811/)
- [ClinVar c.842 VCV000095202](https://www.ncbi.nlm.nih.gov/clinvar/variation/95202/)
- [ClinVar c.844del frameshift VCV000143702](https://www.ncbi.nlm.nih.gov/clinvar/variation/143702/)
- [ClinVar c.710 VCV000143653](https://www.ncbi.nlm.nih.gov/clinvar/variation/143653/)
- [ClinVar c.194 coordinate-equivalent VCV001076185](https://www.ncbi.nlm.nih.gov/clinvar/variation/1076185/)
- [ClinVar c.468 transcript-equivalent VCV000095196](https://www.ncbi.nlm.nih.gov/clinvar/variation/95196/)
- [ClinVar c.455 transcript-equivalent VCV000143579](https://www.ncbi.nlm.nih.gov/clinvar/variation/143579/)
- [ClinVar c.622 transcript-equivalent VCV000143641](https://www.ncbi.nlm.nih.gov/clinvar/variation/143641/)

