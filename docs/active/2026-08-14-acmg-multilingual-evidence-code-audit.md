# ACMG 多语种证据代码案例审计

**Status:** reference

**Created:** 2026-08-14

**Scope:** 对当前 GIM ClinVar-fused 消融的语言输入、证据字段和 ACMG 代码解释进行方法学审计；不是临床变异解读或最终分类。

## 结论

现有 30 条 ClinVar-fused 消融不能支持“多语种文献使 ACMG 证据代码提升更明显”的结论。它比较的不是英文原始文献与中文（或其他非英语）原始文献：运行器提交的始终是英文 `source.md`，英文输入随后被翻译模块原样复制到 translated track。因而报告中的 `ZH-only` 字段仅能表示同一英文文本在两次轨道抽取中的差异，不能表示中文证据、原生非英语文献覆盖，或已裁决的 ACMG 代码增益。

在完成一套以原生非英语全文、逐条来源跨度和人工 ACMG 裁决为基础的配对研究前，不应在论文、图表或结论中使用现有 `+22.8%`、`25/29`、`13/29` 等数字来主张多语种 ACMG 代码提升。下文的固定中文双语摘要层确实显示原生全文可多恢复 PM6-eligible 的**来源事实**，但它不能改变这一结论。

## 审计范围与可复核事实

| 审计问题 | 结果 | 证据位置 |
|---|---|---|
| 消融是否提交 `source_zh.md`？ | 否。`evaluate_one()` 只读 `<entry>/source.md`，并将该 Markdown 作为预解析文本提交。 | `benchmark/core/pipeline_client.py:386-394, 470-494` |
| 数据集的 `source_zh.md` 是什么？ | 由英文源文献经 LLM 生成的译文，不是原生中文论文。 | `benchmark/datasets/clinvar_fused/README.md:83-87`；`translate_to_multilingual.py:158-212` |
| 英文输入在翻译模块中如何处理？ | `skip_translate` 将 `formatted_original` 和 `translated_english` 都设为同一段文本，并标记 `source_language="en"`。 | `backend/src/core/cross_lingual_translation/api.py:82-98` |
| 30 个 dual run 的实际输入是否一致？ | 是。2026-08-14 逐一读取 `dual_track_metrics.json` 中 30 个 run 的 Phase 2 工件：30/30 存在、30/30 original/translated 的 `metadata.source_language` 均为 `en`、30/30 `formatted_text` 的 SHA-256 相同。 | 运行报告：`docs/gim/supplementary/reports/dual_track_metrics.json`；本机工件根：`/data/yangzs/Projects/01_ACMG_Lingua/data/pipeline/<run_id>/phase_2/*/{original,translated}.json` |
| `ZH-only` 的计数单位是否可审计？ | 当前 runner 的设计是 `field_id` 集合差，而非目标变异 × ACMG 代码 × 合格证据事件；但冻结报告的个别计数与对应 run 的字段集合不相符，不能把其 item 数直接视为该集合差。 | runner：`benchmark/datasets/clinvar_fused/run_multilingual_ablation.py:57-99`；报告：`docs/gim/supplementary/reports/multilingual_contribution_report.json` |

因此，这份报告中所谓的 “ZH” 是历史轨道名称，而不是本次运行的实际文献语言。它至多可作为同一英文文本的双轨抽取冗余或不稳定性的线索。

## 为什么字段标签不是 ACMG 代码裁决

`assigned_acmg_codes` 不能作为“某代码已经满足”或“某变异分类已提升”的终点。

- 合约将其定义为抽取实例的运行时评估，而不是正式分类：`backend/src/core/evidence_extraction/contracts.py:201-224`。
- 当前 broad extraction 和 target-span recovery 又会直接把字段目录的 `spec.acmg_codes` 复制给 found item：`primary_broad_extraction.py:216-231`、`target_span_recovery.py:165-190`。
- catalog prompt 明确要求“Do not score or classify ACMG/GDV evidence”：`backend/src/core/evidence_extraction/prompts/catalog.py:81-91`。

换言之，字段与代码的映射可以帮助召回候选事实，却没有执行代码特异的前提核验、证据强度判定、冲突处理、同一家庭/队列去重或最终组合规则。无论值来自 LLM 运行时判断还是静态字段映射，都不能替代 ACMG/AMP 裁决。

## 案例：`fused_014`（DCLRE1C c.241C>T, p.Arg81Ter）

**文献：** *Targeted Next-Generation Sequencing in the Molecular Diagnosis of Severe Combined Immunodeficiency*（PMID 41011036；PMCID PMC12471661）。目标变异为 `NM_001033855.3(DCLRE1C):c.241C>T (p.Arg81Ter)`，ClinVar Variation ID 4665，AR DCLRE1C-SCID 背景见 `benchmark/data/ground_truth/clinvar_fused/fused_014/expected.json:5-27`。

| 候选代码/事实 | 本文可直接支持的内容 | 本审计结论 |
|---|---|---|
| PVS1 候选 | P2 的目标变异被描述为 nonsense，并可能产生截短蛋白或经 NMD 而无蛋白。 | 可记录为 LoF 候选事实；PVS1 的最终适用和强度还需基因-疾病 LoF 机制、转录本/NMD 位置及疾病特异规格，不能由该段文字自动判定。 |
| PM3-ready 相位事件 | P2 母源为 exon 1–3 大缺失，父源为 `c.241C>T`；文章明确为 compound heterozygous。 | 这是可审计的 trans/双等位事件。正式 PM3 仍须核验另一等位基因的 P/LP 状态、适用的 AR 规则和强度；本案例不把它计为仅凭当前文章即可锁定的 PM3。 |
| PS3 候选 | 文中仅二次转述既往研究显示 Artemis activity 显著降低，并引用文献 27。 | 不授予 PS3。当前文章没有可供规则判定的变异特异 assay、对照、统计和验证信息；应读取原始功能研究后再裁决。 |
| PS2/PM6 排除 | 文中的 de novo 描述属于 P3 的 `IL2RG c.437T>C (p.Leu146Pro)`，不是 P2 的 DCLRE1C 目标变异。 | 不得把它迁移为 DCLRE1C 的 de novo 证据。 |

原文可复核跨度位于 `source.md:106`（PVS1/功能二次转述）、`:108`（父母来源与 compound heterozygous）、`:117`（另一患者 IL2RG 的 de novo）和 `:132`（病例汇总）。

这也是当前报告最清楚的反例。冻结报告将 `fused_014` 记为 EN 17、ZH 18、合并 23、所谓 ZH-only 7，并列出唯一的 `ZH-only field_id` 为 `F.assay_type`。但对应 run 的原始工件中，found item 数确为 17 和 18，按字段去重却是 original 16、translated 17、并集 17，translated-only 也只有 `F.assay_type`。因此 `23` 和 `7` 的 item 口径不能由当前报告或 runner 复建，必须在重新生成可追溯报告前停用。

不受该计数冲突影响的是该字段的定性审阅：translated track 的 `F.assay_type` 值为 `Artemis protein activity`，标有 `PS3`/`BS3`，但 `evidence_source_language` 是 `en`，且来源正是上述二次转述。它是同一英文文本的候选字段，不是中文带来的 PS3/BS3，更不是可直接采纳的代码。

## 固定中文双语摘要层：可复核的来源覆盖分析

为避免从少数亮点病例外推，本审计在父项目 Rett 语料中固定了一个可完整枚举的层：**主正文为中文、且作者在同一 PDF 中提供英文摘要的所有去重全文**。该层是在本次审计时固定、而非历史预注册；它测量同一来源的“英文摘要可见内容”与“中文全文可见内容”，不是英语全文论文与非英语全文论文的随机配对，也不是模型性能实验。

原始下载目录有 92 份 PDF；标注集有 53 条 `rett_*` 记录，但去重后为 49 个唯一 PDF、48 个唯一 `source.md`。精确 PDF 重复为 `rett_004=rett_080`、`rett_006=rett_082`、`rett_007=rett_083`、`rett_011=rett_087`，另有 `rett_035` 与 `rett_036` 的 Markdown 完全相同。该固定层排除这些别名后包含 `rett_006`、`rett_007`、`rett_011`、`rett_084` 四篇；`rett_004`、`rett_079`、`rett_081`、`rett_085` 仅有英文题名/关键词或无作者英文摘要，故不混入分母。

一个来源事件的最小门槛为：同一篇文章给出**目标 MECP2 变异、受累先证者/病例、双亲均接受检测且目标位点阴性**。Richards 等 2015 指南下，缺少生物学父母/亲子关系确认时，这至多是 assumed-de-novo 的 **PM6-eligible 观察**，不是 PS2，也不是已经完成全部临床裁决的正式代码。

| 去重来源 | 英文摘要直接恢复的 PM6-eligible 观察 | 中文全文直接恢复的 PM6-eligible 观察 | 全文新增 | 可复核跨度 |
|---|---:|---:|---:|---|
| `rett_006`，赵等，2014，DOI `10.7499/j.issn.1008-8830.2014.04.017` | 5 | 5 | 0 | 英文摘要已经列 5 个变异并称父母未检出（`source.md:21`）；中文结果重复同一事实（`:41`）。 |
| `rett_007`，刘等，2023，DOI `10.13404/j.cnki.cjbhh.2023.04.008` | 0 | 4 | +4 | 英文摘要只说对患儿及父母做遗传分析、4 例诊断为 RTT（`:21`）；中文正文给出亲子 WES、父母均未检出（`:45, 51`）及 `c.509C>T`、`c.538C>T`、`c.842delG`、`c.844delC` 的病例对应表（`:53-55`）。原始 PDF 印刷页 784-785 已复核英文摘要和中文结果。 |
| `rett_011`，钟等，2024，DOI `10.20047/j.issn1673-7210.2024.05.45` | 0 | 1 | +1 | 英文摘要只称 `c.710C>G` 为 “new heterozygous mutation”（`:21`）；中文正文给出先证者/双亲 WES、Sanger 和父母阴性（`:41`）。 |
| `rett_084`，葛等，2018，DOI `10.3969/j.issn.1000-3606.2018.11.005` | 1 | 1 | 0 | 英文摘要已给出 `c.194delC (p.S65X)` 及 “not found in his parents”（`:13`）；中文正文补充取样和 WES + Sanger（`:23`）。 |
| **合计（事件记录，不是独立样本数）** | **6** | **11** | **+5** | **2/4 个来源有新增；其中 4 条来自同一个病例系列 `rett_007`。** |

这 4 个来源的原生全文将可追溯的 PM6-eligible 观察从 6 条增至 11 条。它是明确的**来源事实覆盖增量**，但不能写成 “ACMG 代码提高 83.3%” 或进行显著性检验：英文摘要与全文的信息量不同；样本仅限中文且很小；4 条新增记录来自同一病例系列，不能当作 4 个独立文献复现；所有 11 条都还缺少亲子关系确认和独立临床审阅。

作为跨语言稳健性对照，韩文 `rett_066` 的英文 Fig. 1 图注已写明 `c.455C>G; P152R` 仅见于患者（`source.md:69`），故不得计为韩文正文新增；西班牙文 `rett_035/036` 虽称 `c.806del` de novo（`:105`），但未给出父母目标基因型，不能列为 PM6/PS2。英文全文 `rett_009` 也报告 `c.538C>T (p.Arg180Ter)`、父母野生型和 Sanger segregation（`source.md:15, 39`），同样只是 PM6-eligible 观察。这些反例说明增量不能归因于“非英语本身”。

同变异的独立英语文献也不能替代同一病例的比较。例如，`c.317G>A (p.Arg106Gln)` 的英语研究（Zhang 等，*Genet Med.* 2019；PMCID `PMC6752670`）是不同先证者、嵌合状态和表型；`c.455C>G (p.Pro152Arg)` 的英语病例/功能研究也不是 Kim 等的同一家庭；`c.194delC` 未找到合格的独立英语原始病例对照。因此，不能把“同变异曾见于英语文献”转换为一个病例级 EN→多语种配对的代码提升。

### 代码级裁决边界

这组案例没有一条能仅凭文章内容**确定性地完成**最终 ACMG 代码裁决。PM6 是唯一有直接来源事实支持的代码家族，且仍需逐例核实 HGVS、检测和样本可信度、表型与基因-疾病关系，以及家系去重。PS2 需要父系和母系生物学身份/亲子关系确认，本层均未报告；不得因论文自报 `PS2` 而继承该结论。PVS1 的早停/移码文字只能作为候选事实，须先规范化转录本并应用 MECP2 的 LoF 规则；例如 `c.194delC (p.S65X)` 是强 PVS1 候选，但不由本文自动定码。对已筛查的原生非英语来源，未发现可直接满足 PM3（AR + P/LP 反式伙伴）、PP1/BS4（可计的共分离/反分离）、PS3/BS3（变异特异且经验证的功能 assay）或 PS4（可比病例-对照统计）的事件。

因此，这个固定层支持的最强表述是：**原生非英语全文可以比同文英文摘要多恢复 ACMG 复核所需的 PM6-eligible 来源事实。**它不支持“多语种使正式 ACMG 代码或最终分类提升更明显”；当前 GIM 双轨结果又是同一英文输入的复制，完全不能用来补足这一缺口。

## 建议的代码级研究终点

将“字段是否出现”与“代码是否合格”分开。后续研究的首要终点应为每个 `目标变异 × 代码家族` 是否恢复到一条金标支持、目标锚定、来源可回溯、规则完整且经人工裁决的合格事件。

| 代码家族 | 文献必须直接给出的最小事实 | 计数注意事项 |
|---|---|---|
| PS2 / PM6 | 目标变异、先证者、父母基因型，以及亲子关系确认状态。 | 每个事件只能在 PS2 或 PM6 中择一；与其他变异或患者的 de novo 不可迁移。 |
| PP1 / BS4 | 目标锚定的家系基因型/表型观察，足以计算共分离或不共分离。 | 每个家系只计一次；保留 LOD、携带者和表型缺失信息。 |
| PS3 / BS3 | 目标变异特异的功能结果、assay、系统、阳/阴性对照、验证和统计。 | 每个变异–assay 数据集只计一次；矛盾结果进入人工复核。 |
| PS4 | 病例与对照中的目标变异计数、可比的纳入定义和效应统计。 | 单纯病例数不是 PS4；不能与同一批受试者的家系事件重复计数。 |
| PM3（次级） | trans 相位和另一等位基因的明确身份。 | 可先计为“PM3-ready phasing event”；正式代码还需独立的伙伴变异 P/LP 前提。 |

PVS1、PS1、PM1/PM5、PM2/BA1/BS1、PP3/BP4 和 PP4 不宜作为本研究的“仅由文章直接决定”的主要终点，因为它们还依赖基因机制、转录本、群体数据库、预测器或表型特异性等外部事实。

## 能真正回答多语种问题的设计

采用四臂、同一目标变异配对的设计，而非目前的两轨字段并集：

1. **EN-source**：仅英语原始论文，以英语抽取。
2. **All-source / translation-only**：英语加原生非英语论文，全部统一读英语译文。
3. **All-source / native-only**：同一全语言语料，英语读原文、非英语读原生全文。
4. **All-source / dual-track**：同一全语言语料，原生语言与英语译文双轨抽取。

在预先冻结的全语种语料集内，2−1 衡量新增非英语来源在英语译文条件下的覆盖效应（不是检索器本身的“发现”效应）；4−2 衡量原生语言轨道的增量；4−3 衡量译文轨道的增量；4−1 是总多语种效应。四臂必须固定模型、提示词、字段目录、检索预算、目标变异和来源锚定门槛，并单独报告检索阶段的合格来源召回率。

每条记录至少保存：

```text
(target variant, disease, code, event type, family/cohort/assay ID,
 participant set, native publication language, source article ID,
 exact source span, prerequisite facts, rule outcome, review status)
```

建议两名具备 ACMG/AMP 解读资质的审阅者独立、盲法裁决，分歧交由第三位审阅者解决。主要报告配对代码召回率、净合格代码绝对增益、新增代码精确率和来源可追溯率；按代码家族使用配对检验并进行多重比较校正。只有完成完整组合规则的独立裁决后，才讨论最终变异分类是否变化。

## 对当前投稿材料的影响

本审计不修改现有未提交的 `docs/gim/` 稿件和图表，以免覆盖并行编辑。但在提交前，所有把 translated track 称作“Chinese evidence”、把字段增益解释为多语种文献增益、或把字段映射解释为 ACMG 代码改善的叙述都需要由稿件负责人据此复核和改写。

## 参考方法学

- Richards S, et al. Standards and guidelines for the interpretation and reporting of sequence variants. *Genet Med.* 2015. DOI: `10.1038/gim.2015.30`.
- Abou Tayoun AN, et al. Recommendations for interpreting the loss of function PVS1 ACMG/AMP variant criterion. *Hum Mutat.* 2018. DOI: `10.1002/humu.23626`.
- Brnich SE, et al. Recommendations for application of the functional evidence PS3/BS3 criterion. *Genome Med.* 2019. DOI: `10.1186/s13073-019-0690-2`.
- Biesecker LG, et al. ClinGen guidance for PP1/BS4 segregation evidence. *Am J Hum Genet.* 2023. DOI: `10.1016/j.ajhg.2023.11.009`.
- ClinGen Rett/Angelman-like VCEP, Sequence Variant Interpretation CSpec GN036 v6.0: <https://cspec.genome.network/cspec/SequenceVariantInterpretation/id/643243106>. 该记录目前标为 pilot/revision，本文只将其用作 MECP2 转录本和规则核验线索，不作为已定稿的临床裁决权威。
