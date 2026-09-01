# Archived: ACMG 多语种案例分析方法快照

**Status:** superseded historical reference

**Created:** 2026-08-31

**Archived:** 2026-09-01

> **NOT FOR SUBMISSION OR CLINICAL USE.** This retained methodology snapshot
> contains the withdrawn Stage-0 rule-engine, event-level increment, and
> classification narrative. Its local source and field notes may be useful for
> engineering archaeology, but it is superseded by the source-family
> source-visibility/provenance scope in `docs/gim/manuscript/latex/main.tex`.
> It must not be cited as a language-effect, extraction-performance, or
> clinical-validation result.

**Scope:** 把分散在 5 份案例分析文档中的执行思路收拢为一份内部方法学参考，回答两个核心问题：**变异是怎么选的**、**证据是怎么提取的**。全文以 MECP2/Rett 案例为载体描述方法本身；文中出现的具体数字（14 条 PM6-eligible、21/32 加码等）都是对应文档冻结日的历史快照，当前分母与结果以各台账为准（见 §11）。本文是方法描述，不是研究结果报告，更不是临床变异解读。

---

## 1. 定位：这套思路解决什么问题

非英语文献里藏着英文摘要写不全的家系事实（父母目标位点阴性、逐例 HGVS、诊断细节），但直接读原文产生两个风险：论文自报代码被无条件继承、同一变异跨来源被重复计数。案例分析思路就是一套**分层闸门**，让"原文事实"可以被机器稳定恢复、可审计复核，同时把"授码决定"从 LLM 手里拿走：

- **抽取模型不打码**——LLM 只负责从原文恢复字段事实；
- **授码只走确定性规则机**——只认字段布尔值，不认 `PS2+PM2+PP3` 字符串；
- **候选不等于正式**——所有代码候选都带着缺失前提进入专家审阅队列。

### 六层流水线

```mermaid
flowchart LR
    S[来源层<br/>冻结语料+哈希+可见性分层] --> V[变异层<br/>事件门槛+入选排除+去重]
    V --> E[证据层<br/>行锚引文+目录字段]
    E --> N[归一层<br/>规范等位基因注册]
    N --> R[授码层<br/>确定性规则机]
    R --> L[台账层<br/>候选/正式分层+增量终点]
```

LLM 只出现在证据层（字段抽取）；归一、授码、组合、拦截全部确定性执行。

---

## 2. 来源层：语料怎么冻结和分层

**输入不是"论文 PDF"，而是可哈希的原文文本。** 每个来源家族以 `reviewed/<case_id>/source.md` 落盘，记录 SHA-256；16 来源历史快照做原文级分析时逐篇核验哈希（16/16）。Stage 0c 扩展账本对 18 篇来源的 211/211 条引文跨度做了完整性核验（source-hash、行锚、引文、语言、可见性区段）。

**来源入选没有语言偏好，但有结构边界：**

- 综述无具体病例 → 不可裁决（如日文教育综述 `rett_055`）；
- 目标基因不符 → 排除（日文 2 篇 FOXG1/CDKL5 研究，MECP2 非目标）；
- 队列无具名先证者/无父母数据 → 不按具名 PM6 授予，只冻代表等位基因（韩文 34 例队列、日文 142 例队列）；
- 无法获得可哈希原文 → 不入仓（德文付费墙来源）。

**可见性三层是整个增量论证的坐标系**（Stage 0c §3）：

| 层 | 含义 |
|---|---|
| `english_abstract` | 作者自己写的英文摘要 |
| `english_visible` | 来源中实际存在的英文标题/摘要/关键词/图表面图注 |
| `native_fulltext` | 原生语言全文 |

任何"多语种增量"的句子都必须指明相对哪一层。语言构成是语料事实（16 快照为 zh 8 / ja 3 / ko 2 / ru 3），不是事后挑选。

---

## 3. 变异层：变异是怎么选的

### 3.1 事件门槛（唯一的入选标准）

以 Richards 2015 的新发标准为锚，一个**事件**要成为 PM6-eligible 观察，必须同时满足：

1. 同一篇文章给出**目标基因的目标变异**（MECP2 点变异）；
2. 有**受累先证者/病例**；
3. **双亲均接受检测**且**目标位点均阴性**。

三条齐备 → 记一条 PM6-eligible 事件；缺任何一条 → 该病例记 0 条，但其它可恢复的代码候选（如 PVS1 的无义/移码事实）仍然记录。

### 3.2 结构性排除项

| 情形 | 处理 | 案例 |
|---|---|---|
| 母系遗传（非 de novo） | PM6/PS2 均不适用，保留为**反例标签** | `rett_081` c.509C>T 来自母亲 |
| CNV / 大片段缺失 | 走剂量分支，不进点变异引擎 | `rett_007` 病例 5 Xq28 0.299 Mb 重复 |
| 仅"父母健康"病史、无基因检测 | 双亲未测 → 0 条 | `rett_069`/`070`/`071` |
| OCR 质量差且关键句缺失 | 按可复核引文记，缺失即 0 | `rett_079` |

### 3.3 去重单位：来源家族 × 病例

**同一个变异在多篇来源出现，不是独立复现，而是"跨语种锚"。** 计数单位永远是 `来源家族 × 病例`，不跨来源合并：

- `c.468C>G (D156E)` 出现在 zh `rett_085` + ru `rett_069`/`071` 三篇 → 三条独立事件（仅中文篇有父母数据）；
- `c.509C>T (T170M)` 在 `rett_007`（父母阴性，入 PM6）与 `rett_081`（母系遗传，拒 PM6）结局相反 → 证明同变异不可合并；
- `c.538C>T` 与英文来源 `rett_009` 同变异但先证者不同 → 不能互为独立复现，也不能给 PS1/PM5。

### 3.4 两套单位必须同时报告

只报事件会把一篇病例系列吹成多篇独立文献；只报来源簇会把系列内多条变异压扁。`rett_007` 的 +4 全部来自同一系列，报告时必须并列给出"去掉该簇后 +1"的敏感度。

---

## 4. 证据层：提取哪些证据

### 4.1 证据的最小单元：行锚引文

每条事实必须绑定 `source.md` 的行号 + 原文引文 + 语言（`DirectInferenceSpan`：`line`/`quote`/`language`）。例如 `rett_007` 的父母阴性链由三处行锚共同支撑：`:45`（方法段 WES+CNV）、`:51`（"患儿父母均未检测到突变"）、`:55`（表 1 逐例变异）。**没有引文跨度的事实不进入台账。**

### 4.2 目录字段门禁（授码规则机实际读取的字段）

抽取出的是 166 个目录字段（A–K 十类，ACMG/ClinGen GDV 证据模型）中的一个子集。规则机授码只依赖以下门禁字段：

| 类 | 字段 | 内容 | 支撑哪条授码 |
|---|---|---|---|
| A | `A.variant_hgvs_c` | 编码区 HGVS（行锚或表格单元格） | 先认出变异 |
| A | `A.variant_type` | missense / nonsense / frameshift / cnv | PVS1 路由 |
| A | `A.variant_hgvs_p` | 蛋白后果 + 位置 | PVS1 截断位置 |
| A | `A.functional_domain_or_hotspot` | MBD/TRD 结构域命中 | PM1 |
| B | `B.disease_diagnosis` | 经典型/先天型 RTT、MDS 等 | PP4、排除分支 |
| C | `C.de_novo_status` | de_novo / inherited / unknown | PM6 |
| C | `C.maternal_genotype` / `C.paternal_genotype` | 父/母目标位点基因型 | PM6 |
| C | `C.parentage_confirmed` | 亲子关系确认状态 | PS2 拒绝依据 |

### 4.3 抽取后的确定性修复（`TargetSpanFieldRecovery`）

原文语言形态经常绕过逐字匹配，恢复层按规则修复而非重问模型：

- **联合父母阴性句拆分**："患儿父母均未检测到突变" 同时写入 `C.maternal_genotype` 与 `C.paternal_genotype` = `target_absent`，并假定 `C.de_novo_status=de_novo`；允许父母与"该位点"之间最多隔 12 个字的语序变化；
- **亲子鉴定缺席检查**：扫描词表（`亲子鉴定`、`亲权鉴定`、`STR分型`、`paternity test`、`parentage confirmation` 等）在全文无命中 → 补 `C.parentage_confirmed=not_confirmed`；
- **遗传句压制 de novo**：写了"遗传自母/父"的句子不授 de novo（`rett_081` 母系反例由此保住）；
- **变异类型归一化**：论文把 `c.194delC` 写成"无义突变（p.S65X）"时，编码区 indel 证据把类型改正为 frameshift；
- **HTML 实体与 markdown 转义解包**：`c.538C&gt;T` → `c.538C>T`；诊断 grounding 对 `1\~4` vs `1~4` 的假失配需先解转义。

---

## 5. 归一层：等位基因先注册，再谈映射

**MECP2 有两条常用转录本**（VCEP 主转录本 `NM_004992.3` 少 36 bp 编码区；MANE Select `NM_001110792.2`），同一基因组等位基因在论文里有多种写法。归一层用**闭集注册表**（`canonical_alleles.json`）解决三件事：

1. **转录本别名合并**：`c.502C>T p.R168X` 与 `c.538C>T p.Arg180Ter` 绑定同一个 SPDI（`NC_000023.11:154031325:G:A`）→ 同一 `allele_id`，ClinVar 54 条 SCV 只算一次；
2. **硬性不同一**（`not_same_as`）：`c.844delC`（帧移，`VCV000143702`）与 `c.844C>T`（无义，`VCV000011815`）差一个碱基替换 vs 缺失，禁止合并；`c.842delG` 与 `c.844delC` 相邻 2 bp 仍是两条等位基因；
3. **近邻降级**：编码位差 1 只标 `coordinate_near`，不算同一（`rett_084` 的 `c.194delC` 规范 id 是 `unmatched_c.194delC`，ClinVar `VCV001076185` 是 `c.195del` 且疾病为新生儿脑病——"查过这条近邻"与"是这条"必须分开记录）。

匹配级别枚举：`exact` / `transcript_alias` / `coordinate_near` / `unmatched` / `not_applicable`。

---

## 6. 授码层：确定性规则机

### 6.1 冻结的 VCEP 切片

规则机的坐标是冻结常量（`Mecp2VcepSlice`），不做实时 VCEP 拉取：PVS1 有效截断 ≤ **p.E472**（e2 蛋白）；PM1 只给错义落在 **MBD 90–162** 或 **TRD 302–306**。

### 6.2 授码门禁（`infer_event`，逐条对应字段）

| 代码 | 字段条件（全部为真） | 强度 |
|---|---|---|
| PM6 | 点变异 + 受累先证者 + 双亲均测 + 目标位点均阴 + 亲子**未**确认 + `de_novo_unconfirmed` | Moderate（单篇观察不升 Strong） |
| PVS1 | nonsense/frameshift 且蛋白位置 ≤ 472 | Very Strong |
| PVS1_Moderate | 同上但位置 > 472（NMD 逃逸区，降级） | Moderate |
| PP4 | 诊断为 RTT 或相符的 MECP2 神经发育表型 | Supporting |
| PM1 | missense 且位置在 MBD/TRD 区间 | Moderate |

**无条件拒绝**：PS2（全部事件；亲子鉴定缺席是硬前提）；`author_self_code`（论文自报代码永不继承）；论文自报 PM2/PP3 时连这两个码的候选资格都单独标注为"来自论文注释"，需独立核验后才可进入审阅。

**分流与拦截**：

- CNV 重复或未映射区间 → `excluded`（点变异引擎外）；
- 冲突旗标命中（`clinvar_benign_expert_panel`、`maternal_inheritance`）→ `blocked_conflict`：字段事实可以照常授码，但分类被拦下。`rett_006` B 的 P376S（ClinVar 专家组 Benign）和 `rett_081`（母系 T170M）都是这样处理的——**系统能同时恢复家系事实并挡住错误方向**。

### 6.3 组合规则（`_combine_rett_vcep`，Richards 2015）

先判 Pathogenic 再判 LP；`1 VS + 1 Moderate` 只到 **LP**，再加 1 条 Supporting 才到 Pathogenic。因此截短 + 父母双阴（PVS1+PM6）没有 PP4 时停在 LP；错义 `PM1+PM6+PP4`（2 Moderate + 1 Supporting）停在证据不足。这是有意偏保守：不从论文旧 gnomAD 注释补第二条 Supporting。

---

## 7. 台账层：候选、升级队列与正式代码严格分层

| 层级 | 含义 |
|---|---|
| 原文事实 | 行锚引文支撑的变异/病例/家系/预测事实 |
| 候选代码 | 事实与某代码方向一致，但缺至少一个代码前提 |
| 升级队列 | 补齐指定外部事实后可重新进入正式审阅（如 PS2 ← 亲子确认） |
| 正式代码 | 两名独立 ACMG/AMP 审阅者完成规则、强度、冲突和去重裁决 |

每条候选事件生成结构化审阅包：`source_family_id / case_id / variant_hgvs / transcript / variant_type / participant_set / parentage_status / native_language / source_span / candidate_codes / required_external_checks / conflicting_or_exclusion_facts / deduplication_group` + 双审与终审字段。

**每个代码家族都有明确的"不能顺手增加"清单**（完整表见候选台账 §5），核心几条：

- 同变异跨来源重复 ≠ PS1/PM5（PS1 要求同一氨基酸由**不同**核苷酸改变造成）；
- X 连锁家系事实不能迁移为 PM3（AR trans）；
- 病例数 ≠ PS4（无可比对照与效应统计）；
- 二次功能引用 ≠ PS3/BS3；
- RTT 表型保留为 PP4 候选，但特异性和排除标准待 VCEP 规格核验。

---

## 8. 增量层：Stage 0c 的终点定义

案例分析的最终可报告终点**不是字段并集，也不是分类翻转**，而是：**某个规范等位基因上，相对可得英文可见层多出来的冻结规则准则**（`native granted_codes − english granted_codes`）。典型形态：英文可见层评不到 PM6，原生正文写出双亲阴性 → 多授一条 Moderate。**分类停在"证据不足"也算增量**；分类翻转到 Pathogenic/LP 是更强子集；再叠加"ClinVar 无精确 VCV"是交叉格（当前为 0，不是主结论）。

比较器三分层（不构成统一的同 PDF 比较）：

| 分层 | 含义 | 快照计数（2026-08-26） |
|---|---|---|
| `same_pdf_bilingual` | 同 PDF 有英文可见层可比 | 8 来源 / 16 事件 |
| `missing_english_pivot` | 缺英文 pivot，仅可达性审计 | 5 来源 / 7 事件 |
| `none` | 无增量结果类别 | 5 来源 / 9 事件 |

---

## 9. 全流程验证钩子

方法每一层都有可执行校验，防止"分析员自己填表"：

| 层 | 校验 | 入口 |
|---|---|---|
| 变异+授码 | 冻结事件哈希 + 行锚引文 + 引擎输出与冻结期望一致 | `check-direct-inference` |
| 证据层 | 每扇门禁字段在 `reviewed/*/source.md` 里可找到（含亲子缺席扫描） | `check-field-bridge` |
| 证据层（live） | production 抽取器吐出的字段喂给同一台规则机，对照冻结分类 | `probe-extraction --all-on-disk` |
| 归一层 | 等位基因注册表绑定与 `not_same_as` 硬拆 | `canonical_alleles.py` |
| 增量层 | 英文可见层 vs 全文两次过规则机取差值 | `check-allele-class-increment` |

live 探针的历史观察值得记录为方法风险：LLM 蛋白写法常被归一化成单字母星号（`p.R180*`）导致门禁 miss（但不改分类）；论文的历史错误标签（`rett_084` "无义"）可能被抽取器照抄导致 PVS1 丢失——这正是确定性修复（§4.3）和阴影对照存在的理由。

---

## 10. 主张边界（复述纪律）

**可以写：** 原生非英语全文能恢复英文可见层写不全的"目标变异—受累先证者—父母目标位点阴性"事实链；恢复的事实经确定性规则机授码后，相对英文可见层多出冻结准则；作者自报代码被系统性压低而非放大。

**不能写：** 正式盲法 ACMG 代码不是 0（Stage-1 未完成，产品 `assigned_acmg_codes` 恒为空）；多语种提取给 ClinVar 热点"多贴了 Pathogenic 标签"；父母阴性 = PS2；候选数量 = 正式代码数；本方法验证了翻译等价性、语言效应或临床正确性。任何汇报写"恢复 14 个 PS2"均属过度表述，正确写法是"建立 14 条 PS2 升级队列"。

---

## 11. 工件与当前权威指针

| 工件 | 位置 |
|---|---|
| 冻结事件表（事实+期望输出） | `benchmark/experiments/acmg_multilingual/direct_inference_cases.json` |
| 规则机（授码/组合/拦截） | `benchmark/experiments/acmg_multilingual/direct_inference.py` |
| 等位基因注册表 | `benchmark/experiments/acmg_multilingual/canonical_alleles.py` + `canonical_alleles.json` |
| 字段出处审计 | `benchmark/experiments/acmg_multilingual/field_bridge.py` + `field_bridge_facts.json` |
| live 抽取探针 | `benchmark/experiments/acmg_multilingual/live_extraction_probe.py` |
| Stage-0c 覆盖账本 | `benchmark/experiments/acmg_multilingual/evidence_item_coverage_facts.json` |
| **当前分母权威** | `docs/active/2026-08-20-multilingual-evidence-item-increment.md`（Stage 0c，18 来源/32 事件） |

关联文档：16 来源原文级判定 `2026-08-17-acmg-multilingual-real-case-analysis.md`；候选台账 `2026-08-17-acmg-evidence-code-candidate-ledger.md`；审稿口径与等位基因注册细节 `docs/archive/plans/2026-08-18-acmg-multilingual-case-analysis-reviewer.md`、`2026-08-19-acmg-multilingual-field-bridge.md`、`2026-08-19-acmg-multilingual-extractor-case-analysis.md`；验证门禁 `2026-08-26-gim-validation-readiness.md`。

## 方法学参考

- Richards S, et al. *Genet Med.* 2015. DOI: `10.1038/gim.2015.30`（新发标准与组合规则）。
- Abou Tayoun AN, et al. *Hum Mutat.* 2018. DOI: `10.1002/humu.23626`（PVS1 规范化）。
- Biesecker LG, et al. *Am J Hum Genet.* 2023. DOI: `10.1016/j.ajhg.2023.11.009`。
- Brnich SE, et al. *Genome Med.* 2019. DOI: `10.1186/s13073-019-0690-2`（Rett VCEP 规格）。
