# ACMG 多语种案例分析：审稿口径

**Status:** reference

**Created:** 2026-08-18

**范围：** 把 2026-08-17 的来源覆盖、16 篇原文判定、ClinVar 对照和候选台账收成一份审稿人可以对着仓库复核的版本。授码规则可执行，数字可复跑，反例留在正文里。

**可执行协议：** `benchmark/experiments/acmg_multilingual/direct_inference.py` + `direct_inference_cases.json`。CLI：`check-direct-inference`。2026-08-18 对本仓库 `reviewed/` 核验 **14/14** 条 on-disk 事件（哈希 + 引文 + 引擎输出与冻结期望一致）。

**2026-08-19：** 字段出处和等位基因注册见 [字段桥](2026-08-19-acmg-multilingual-field-bridge.md)。`c.194delC` 的规范 id 改为 `unmatched_c.194delC`，与 ClinVar `c.195del` / `VCV001076185` 只算相邻，不算同一 SPDI。

---

## 1. 主张什么，不主张什么

### 1.1 现在可以写进回复审稿人的句子

原生非英语全文能恢复英文摘要或英文图注里写不全的 **目标变异—受累先证者—父母目标位点阴性** 事实链。在固定的 4 篇中文全文+作者英文摘要层上，英文摘要恢复 6 条 PM6-eligible 观察，中文全文恢复 11 条，增量 **+5**，来自 **2/4** 个来源。去掉病例系列 `rett_007` 之后，增量掉到 **+1**。

这些事实足够确定时，**抽取模型不打码**。冻结的 MECP2/Rett 规则机可以根据字段授予 `PM6` / `PVS1` / `PP4` / `PM1`，再按 Rett VCEP 组合规则给出 Pathogenic / LP / 证据不足。截短变异 + 父母双阴 + RTT 诊断，组合是 `PVS1+PM6+PP4`，分类为 Pathogenic。

相对 ClinVar，真正站得住的“多出来的结构化致病推理”只有两处：`c.913insT`（当前查不到精确 VCV）和 `c.194delC`（库里只有一条近邻记录，疾病还不是 Rett）。这两条的英文摘要已经能评到 Pathogenic。相对英文可见层，多出准则的是 6 条事件：`rett_007` 病例 1–4、`rett_011`（只 +PM6，分类仍不足）、`rett_004`。热点截短在 ClinVar 里本来就是 Pathogenic。交叉（英文层缺码且 ClinVar 也没有、全文还是 Pathogenic）目前是 0，见 [Stage 0c](2026-08-20-multilingual-evidence-item-increment.md)。

### 1.2 现在不能写的句子

- 正式盲法 ACMG/AMP 代码已经不是 0。Stage-1 四臂还没跑完，`assigned_acmg_codes` 在产品抽取里仍然为空。
- 多语种提取让 ClinVar 里的热点等位基因“多了一个 Pathogenic 标签”。没有。
- 论文自报 `PS2+PM2+PP3` 可以继承。`rett_011` 是反例：无亲子鉴定，错义又不在 VCEP 的 MBD/TRD 里，规则机只给 `PM6+PP4`，分类是证据不足。相对英文摘要，中文仍多授一条 `PM6`；分类没翻，分类证据加了。
- 父母阴性就是 PS2。全部 14 条合格事件都没有亲子关系确认，规则机拒绝 PS2。
- `c.1126C>T (p.P376S)` 支持致病。ClinVar 专家组聚合为 Benign。规则机先拦分类，再谈代码。
- 检索召回等于读懂全文。DOI 检索层和原文阅读层分开计。

---

## 2. 两套单位，审稿人用哪套都能对上

来源簇和事件必须同时报。只报事件会把一篇病例系列吹成四篇独立文献；只报来源簇会把 `rett_007` 里四条不同变异的事实链压成一个数字。

| 口径 | 分母 | 数字 | 敏感度 |
|---|---|---|---|
| Stage-0 来源簇（同文英文摘要 vs 中文全文） | 4 篇：`rett_006/007/011/084` | 摘要 6 vs 全文 11，**+5**；2/4 来源有增量；**4/5 来自 `rett_007` 同一系列** | 去掉 `rett_007` 后 **+1** |
| 16 篇非英语来源的 PM6-eligible 事件 | zh 8 / ja 3 / ko 2 / ru 3 | **14** 条合格，**0** 条正式代码 | 13/14 来自中文；韩文 1 条（`rett_066`）；日文、俄文 0 条 PM6 |
| 规则机 Pathogenic 事件 | 冻结表 18 条事件 | **8** 条 Pathogenic | 折叠到 **6** 个规范等位基因；其中 2 个是 ClinVar 缺口或薄记录 |
| 规则机双语增量 | 按来源簇计，不按事件相加 | **+5**；无 `rett_007` 时 **+1** | 与 Stage-0 覆盖层同一数字，由 `summarize_direct_inference()` 复现 |

`rett_007` 英文摘要只写“5 例 RTT 样表型、4 例诊断 RTT、1 例 MDS、对患儿及父母做了遗传分析”。逐例变异和父母阴性在中文结果和表 1。所以 +4 是真的，也是集群，不能拆成四篇论文。

16 篇里日文 2 篇是 FOXG1/CDKL5 研究，MECP2 不是目标；俄文队列多数未测双亲。语言构成偏中文是语料事实，不是把日文俄文藏起来。PM6=0 也不等于正文没有目录字段或分类证据；英文层缺的准则见 [Stage 0c](2026-08-20-multilingual-evidence-item-increment.md)。

---

## 3. 等位基因必须先归一，否则 ClinVar 会被加两次

MECP2 有两条常用转录本。`NM_004992.3`（e2，Rett VCEP 主转录本）比 `NM_001110792.2`（e1，当前 MANE Select）在 N 端少 12 个氨基酸、编码区少 36 bp。`rett_007` 表 1 还把两套编号写在同一张表里：病例 1 的 `c.509C>T p.Thr170Met` 是 e2 热点写法，病例 2–4 的 `c.538C>T p.Arg180Ter`、`c.842delG`、`c.844delC` 与 e1/MANE Select 一致。

| 论文写法 | VCEP / e2 | 规范等位基因 | ClinVar（查询日） | 备注 |
|---|---|---|---|---|
| `c.502C>T p.R168X` | `c.502C>T p.Arg168Ter` | `VCV000011828` | Pathogenic | 与下一行同一基因组等位基因 |
| `c.538C>T p.Arg180Ter` | `c.502C>T p.Arg168Ter` | `VCV000011828` | 同上 | 不得把 54 条 SCV 加两遍 |
| `c.808C>T p.R270X` | `c.808C>T p.Arg270Ter` | `VCV000011815` | Pathogenic | e1 写作 `c.844C>T p.Arg282Ter` |
| `c.844delC p.Arg282GlufsTer19` | `c.808del p.Arg270fs` | **`VCV000143702`** | Pathogenic，9 SCV（2026-08-18） | **帧移**。2026-08-17 写成“未映射”是检索串伪影 |
| `c.844C>T p.Arg282Ter` | `c.808C>T p.Arg270Ter` | `VCV000011815` | Pathogenic | **无义**。与上一行不是同一变异 |
| `c.842delG p.Gly281fs` | `c.806del p.Gly269fs` | `VCV000095202` | Pathogenic，专家组 | 与 `c.844delC` 相邻 2 bp，仍是另一条等位基因 |
| `c.913insT p.K305fs` | `c.913_914insT` | 无精确 VCV | 未匹配 | 附近 K305fs 别名会误中大片段缺失 `c.950_1208del` |
| `c.194delC p.S65X` | 早期移码，位置 65 | **`unmatched_c.194delC`** | 无精确 VCV | 相邻于 `VCV001076185`（`c.195del`/`c.231del`，SPDI `154032388:T:`，新生儿脑病）。Sanger 少一个 C，不是 LOVD 的 `c.194C>G p.S65X` |
| `c.1126C>T p.P376S` | `c.1126C>T p.Pro376Ser` | `VCV000095184` | **Benign，专家组** | e1 显示 `c.1162C>T p.Pro388Ser` |
| `c.710C>G p.Pro237Arg` | `c.674C>G p.Pro225Arg` | `VCV000143653` | Pathogenic | 残基 225/237 不在 MBD 90–162 或 TRD 302–306 |

PVS1 切点按 e2 蛋白 **p.E472**：映射后的终止/移码起点 ≤ 472 给 Very Strong，之后降为 Moderate。PM1 只给错义落在 MBD **90–162** 或 TRD **302–306**。`p.Thr170Met` 紧贴 MBD 外侧，本协议不给 PM1。

---

## 4. 直接授码：字段门禁，不是模型“更敢打码”

流水线已经把 `assigned_acmg_codes` 留空，并禁止把作者自报代码抄进去。本协议补的是抽取之后的确定性层：

1. 抽取：变异类型、父母基因型、亲子鉴定状态、表型诊断、相位。
2. 规则机：只认字段，不认 `PS2+PM2+PP3` 字符串。
3. 组合器：Rett VCEP / Richards 2015 致病与 LP 组合。
4. 冲突器：专家组 Benign、母系遗传、CNV/未映射区间直接拦截。

LLM 不出现在 2–4 步。

| 代码 | 必须为真的字段 | 冻结外部规则 | 本协议强度 |
|---|---|---|---|
| PM6 | 点变异 + 受累先证者 + 双亲均检测 + 目标位点均阴性 + 亲子未确认 + 遗传方式不是母系/父系 | 无。事实在文章里 | Moderate。单篇观察不升 Strong |
| PVS1 | 无义或移码，且能落到 e2 蛋白位置 | MECP2 LoF 是致病机制；位置 ≤ p.E472 | Very Strong；E472 之后为 `PVS1_Moderate` |
| PP4 | 诊断为 RTT，或至少是与 MECP2 相符的神经发育表型 | VCEP 不要求再填一张详细表型清单 | Supporting |
| PM1 | 错义，残基在 MBD 90–162 或 TRD 302–306 | 冻结结构域表 | Moderate |
| PM2_Supporting | 本协议不从论文旧频率注释授予 | 需要冻结日期的 gnomAD | 可自动化，但不是多语种抽取增量 |
| PS2 | 本协议在 `parentage_confirmed=false` 时拒绝 | 亲子鉴定 | 不授予 |

组合里必须先判致病再判 LP。**1 Very Strong + 1 Moderate 只到 LP**；再加上 1 条 Supporting 才到 Pathogenic。所以截短 + 父母双阴如果没有 RTT/相符 NDD，规则机停在 LP。`rett_079` 的 Q208X 有 PVS1+PP4、没有父母数据，停在证据不足。

错义没有 PVS1。`PM1+PM6+PP4` 是 2 Moderate + 1 Supporting，LP 需要 2 Moderate + 2 Supporting。`R106W`、`P152R`、`D156E` 都停在证据不足。本协议故意不把论文里的旧 gnomAD 注释补成第二条 Supporting。

大片段缺失和重复不走点变异引擎。`rett_007` 病例 5 是 Xq28 0.299 Mb 重复、诊断 MDS：同一句“患儿父母均未检测到突变”盖住了 1–5 例，规则机仍然把它排除，不计入 Pathogenic。

---

## 5. 英雄案例（原文跨度可核）

### 5.1 `rett_007`：+4 来自一篇病例系列

刘文晶等，中国优生与遗传杂志，DOI `10.13404/j.cnki.cjbhh.2023.04.008`。SHA-256 `1b5ba8f2…c94d`。

英文摘要（`:21`）没有逐例核苷酸改变，也没有“父母该位点阴性”。中文 `:45` 是先证者及父母的 WES+CNV；`:51` 写“患儿父母均未检测到突变”；`:55` 表 1 列出 `c.509C>T`、`c.538C>T`、`c.842delG`、`c.844delC`；`:167` 病例 1–4 诊断经典型 RTT，病例 5 诊断 MDS。

规则机：错义 T170M → `PM6+PP4`，证据不足（170 不在 PM1 域）。三条截短 → 各 `PVS1+PM6+PP4`，Pathogenic。这三条在 ClinVar 已是 Pathogenic（含 2026-08-18 补上的 `c.844delC` = `VCV000143702`）。多语种贡献是可引用的父母阴性观察，不是新的库分类。

### 5.2 `rett_011`：作者自报代码过强

钟少君等，中国医药导报，DOI `10.20047/j.issn1673-7210.2024.05.45`。转录本写明 `NM_001110792.2`。

英文摘要（`:21`）有 `c.710C＞G`，没有父母阴性。中文 `:41`：“变异为新生变异，父母未携带该变异位点……判读为 PS2+PM2+PP3”。图 2 图注（`:98`）父亲母亲均为野生型。

规则机拒绝 PS2，拒绝把 PM2/PP3 从字符串拷进来。P237R 映射到 e2 p.Pro225Arg，不在 MBD/TRD。输出 `PM6+PP4`，证据不足。ClinVar 这条已经是 Pathogenic（13 SCV），那是库里别的证据，不是这篇中文能单独凑齐的组合。

对审稿人来说，这个例子证明系统会压低作者自报，而不是放大它。

### 5.3 同一核苷酸，相反遗传：`rett_007` 病例 1 vs `rett_081`

两条都是 `c.509C>T p.Thr170Met`。`rett_007` 病例 1 父母阴性，进入 PM6。`rett_081` 为母系传递，规则机不给 PM6，分类直接 `blocked_conflict`。ClinVar 上 T170M 已经是 P/LP，消除不了这篇中文里的来源冲突。任何“凡是中文全文出现的 T170M 都是新发”的句子，这一对就能拆掉。

`rett_081` 的 `source.md` 还在外部语料，冻结表标了 `needs_external_corpus`。主张母系反例时，以 2026-08-17 原文分析为准，不假装本实验树里已有哈希。

### 5.4 `rett_006` B：P376S 必须拦住

赵培伟等，中国当代儿科杂志 2014，DOI `10.7499/j.issn.1008-8830.2014.04.017`。英文摘要（`:21`）已经列出 5 个变异和 “No mutations were detected in their parents”，双语增量 0。

患儿 B：`c.1126C>T p.P376S`，CTS 区，不在 PM1。ClinVar `VCV000095184` 专家组 Benign（gnomAD 频率约 0.001）。规则机仍能看见原文 PM6 事实，分类是 `blocked_conflict`。这是能力，不是尴尬：系统能同时恢复家系事实和挡住把良性位点写成致病。

### 5.5 相对 ClinVar 真正多出来的两条

**`c.913insT`（`rett_006` G）。** 摘要和正文都写了插入、K305 起改变、330 提前终止、父母未检出。规则机 `PVS1+PM6+PP4` → Pathogenic。2026-08-18 对 `c.913_914insT` 仍无精确 VCV；不能把邻近大缺失当作本插入。双语增量是 0（摘要已经写全），增量发生在对 ClinVar 的结构化授码，不是中英对照。

**`c.194delC`（`rett_084`）。** 男童半合子。英文摘要（`:13`）已有变异和 “not found in his parents”。正文（`:23`）把缺失写成“无义突变（p.S65X）”，并写父母该位点无异常。Sanger（`:31`）是 `AGACAT-AGAAGG` 对父母 `AGACATCAGAAGG`。规则机按移码、位置 65 授 PVS1。ClinVar `VCV001076185` 是相邻的 `c.195del`/`c.231del`（E66fs），1 条 SCV，疾病是新生儿脑病。规范 id 是 `unmatched_c.194delC`，匹配级别仍是 `coordinate_near`，不是同一 SPDI，也不是 LOVD 的 `c.194C>G p.S65X`。

---

## 6. 可见性分层：增量相对谁

| 层 | 含义 | 本批例子 |
|---|---|---|
| 作者英文摘要已有 | 中文全文不产生双语增量 | `rett_006`、`rett_084` |
| 英文图注已有 | 韩文正文的 de novo 在英文 figure legend 里已经写了 patient-only | `rett_066` `:69` |
| 只在原生正文 | 英文摘要点到遗传分析或变异，但不给父母阴性 | `rett_007` +4，`rett_011` +1 |

`rett_066` 计入 16 篇里的那条韩文 PM6-eligible，但不计入“韩文独占、英文完全看不见”的增量。ClinGen 上 P152R 已有 PM6_Very Strong（多条英文新发）。这篇韩文不能用来升级强度。

---

## 7. 审稿人可能怎么问

**“+5 是不是一篇文章刷出来的？”** 是。4/5 来自 `rett_007`。正文和 `summarize_direct_inference()` 都把去掉该簇后的 +1 放在明处。

**“热点已经是 Pathogenic，多语种还有什么用？”** 对 R168X / R270X / G281fs / R282fs，用处是可引用的父母阴性观察和本地规则机与 ClinVar 同向。位点级增量只主张 `c.913insT` 和 `c.194delC`。

**“`c.844delC` 你们 17 号还说没映射。”** 18 号用 MANE Select 字符串 `NM_001110792.2:c.844del` 查到 `VCV000143702`。17 号失败是因为裸搜 `c.844delC` 会撞到别的基因，并且容易和无义 `c.844C>T`（`VCV000011815`）搅在一起。更正写进对照文档和冻结表，分母没有偷偷缩小。

**“语料几乎全是中文。”** 16 篇非英语来源的语言构成是 zh 8 / ja 3 / ko 2 / ru 3。日文两篇不是 MECP2 目标；俄文缺双亲检测。这是 Stage-1 清单的构成，不是事后挑选阳性中文。

**“译文是模型审校的。”** `rett_007` / `rett_011` 的英文全文是 `model_reviewed`，不是人工。Stage-0 覆盖层用的是原文里的作者英文摘要，不依赖那份译文。不能把模型译文写成 human-reviewed。

**“规则机是不是绕过了盲法审阅？”** 没有。冻结表的 Pathogenic 是 Stage-0 分析输出，用来说明哪些字段组合已经足够确定。正式代码计数仍为 0，直到两名独立审阅者走完 Stage-1 包。产品抽取层继续把 `assigned_acmg_codes` 留空。

**“错义为什么不直接定 P？”** `P237R` 只有 `PM6+PP4`。`R106W` 加上 PM1 仍少一条 Supporting。本协议不从论文里的 PM2/PP3 字符串补那一条。这是有意偏保守。

---

## 8. 和既有文档的关系

| 文档 | 角色 |
|---|---|
| [2026-08-17 案例分析报告](2026-08-17-acmg-multilingual-case-analysis-report.md) | Stage-0 四篇双语摘要层，+5 的原始计数 |
| [2026-08-17 真实案例分析](2026-08-17-acmg-multilingual-real-case-analysis.md) | 16 篇原文级判定，14 条 PM6-eligible |
| [2026-08-17 候选台账](2026-08-17-acmg-evidence-code-candidate-ledger.md) | 候选 vs 正式代码分层；本文把其中可确定的子集交给规则机 |
| [2026-08-17 ClinVar 对照](2026-08-17-acmg-clinvar-clingen-comparison.md) | 外部映射；`c.844delC` 的未映射结论以本文 2026-08-18 更正为准；`c.194delC` 以 2026-08-19 相邻口径为准 |
| [2026-08-19 字段桥](2026-08-19-acmg-multilingual-field-bridge.md) | 目录字段出处、亲子鉴定缺席、等位基因注册 |
| 四臂实验设计 | Stage-1 还没跑；本文不替代盲法计分 |

复跑：

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-direct-inference \
  --cases ../benchmark/experiments/acmg_multilingual/direct_inference_cases.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```
