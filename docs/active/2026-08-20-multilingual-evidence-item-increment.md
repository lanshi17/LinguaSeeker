# ACMG 多语种案例分析：分类证据增量（Stage 0c）

**Status:** in-progress
**Created:** 2026-08-20
**Updated:** 2026-08-21
**Scope:** 终点是某个规范等位基因上、相对同 PDF 英文可见层**多出来的 Stage-0 ACMG 准则证据**（冻结规则机授予的 `PM6` / `PVS1` / `PP4` / `PM1`）。组合分类翻转（Pathogenic / LP）是更强子集，不是入门门槛。目录 `field_id` 个数只说明英文层少字段。产品路径不写 `assigned_acmg_codes`；正式盲法 Stage-1 代码仍为 0。

---

## 1. 终点：分类证据，不是字段并集，也不要求改分类

审稿人要看的是：**这篇非英语文献有没有给某个位点补上 ACMG 分类所需要的准则证据。** 典型形态是英文可见层评不到 `PM6`，中文/韩文正文写出双亲未携带，规则机因此多授一条 Moderate。分类可以仍停在证据不足；那也是增量。

更强、但仍属子集的句子是：多出来的证据把组合分类推到 Pathogenic / LP。再叠一层 ClinVar/ClinGen 无精确 VCV，就是「英文层没有、库里也没有」的交叉格。交叉目前是 0，不能拿来当主结论。

可执行对照：`check-allele-class-increment`。对 on-disk 事件用英文可见层事实跑一遍规则机，再用全文事实跑一遍；主差值是 `native granted_codes − english granted_codes`。

---

## 2. 已审 31 条：多出来的准则（2026-08-21）

CLI 复现：`added codes 20/31`（去掉 `rett_007` 仍 16 条、11 个等位基因）；其中 4 条事件顺带翻到 Pathogenic。ClinVar 缺口 Pathogenic 仍是 2，但那两条英文摘要已经授了同一套码。both-hero（多出准则 **且** 全文 Pathogenic **且** 库缺口）= 0。

语种：中文、韩文、俄文、土耳其文、西班牙文、葡萄牙文、法文、日文。字段覆盖 17 篇来源、200/200 条引文哈希核验通过。

| | ClinVar 已有精确/别名 VCV | ClinVar 缺口（无 VCV 或仅相邻） |
|---|---|---|
| **英文可见层已授同一套准则** | 热点（R106W-in-006、R270X、R168X-in-006、P152R、俄文 `rett_071` D156E、西班牙 `c.806del`、葡萄牙 R255X） | **`c.913insT`、`c.194delC`** — 相对数据库的 Pathogenic，不是相对英文层 |
| **英文层缺码，全文补上** | **20 条事件 / 11 个等位基因**：`rett_007` 病例 1–4、`rett_011` P237R（**只 +PM6，分类仍不足**）、`rett_004` R168X、俄文 `rett_069` D156E（**+PP4+PM1**）、中文 `rett_085` D156E（**+PM6+PP4+PM1**，同位点补父母）、`rett_079` Q208X（**+PVS1+PP4**）、`rett_081` 母源 T170M（**+PP4，拒绝 PM6**）、土耳其 `rett_078` P302L（**+PP4+PM1**）、法文海报 `rett_041` 三条热点、韩文队列 `rett_067` 三条、日文队列 `rett_088` 三条（D156E / R168X / T158M，蛋白符号，无 c. HGVS） | **空（both-hero = 0）** |

`rett_011` 仍是口径样板：英文摘要已有诊断（PP4），中文补父母未携带 → 多一条 `PM6`。错义不在 MBD/TRD，组合仍是证据不足。

D156E 现在是跨语种锚：俄文 `rett_069`（摘要无 HGVS）、俄文 `rett_071`（摘要已有 HGVS，负对照）、中文 `rett_085`（补父母，PM6）、韩文 `rett_067` Table 2（摘要只给计数）、日文 `rett_088` Table 2（英文摘要未点名 D156E）。

法文 `rett_041` 是 2018 年 SFE 会议海报，没有英文摘要；对照序列不是父母基因型，不授 PM6。韩文 `rett_067` 是 34 例队列、未测双亲；只冻 3 个代表等位基因。日文 `rett_088`（近藤 2002，脑と発達）是 142 例队列、表 2 只有蛋白名；队列级亲起源分析不按具名先证者 PM6 授予。西班牙/葡萄牙是负对照：英文摘要已经写出 HGVS。

`rett_085` 已从 PDF 重新数字化（MinerU 曾抽掉数字）。`rett_070` 大片段仍排除。已有日文 `rett_055`/`062`/`063` 仍是综述或 FOXG1/CDKL5，未当作日文增量。Deutscher 2002 德文四例在 Thieme 付费墙后，studylibde OCR 不可哈希；Rostock 2022 幻灯片涂掉了变异。

---

## 3. 字段层仍要保留（机制，不是终点）

同一 PDF 仍切三层：`english_abstract` / `english_visible`（含英文图注）/ `native_fulltext`。规则机在英文层能否评分，取决于该层有没有 `A.variant_hgvs_c`；有 HGVS 之后，变异类型和 VCEP 残基跟位点走，不跟语言走。父母检测和诊断按英文层是否出现对应字段来遮罩。

17 篇字段表：12/17 相对英文摘要有 `field_id` 增量；去掉 `rett_007` 仍有 11 篇。`rett_069` / `rett_078` / `rett_067` / `rett_088` 的字段增量对应 +PP4+PM1 或 +PVS1+PP4；`rett_071` 与 `rett_066` 一样，字段或正文多字不增准则。

---

## 4. 德文仍缺可哈希病例；日文已冻队列、未授 PM6

日文 `rett_088`（近藤 2002）已入仓：英文摘要有蛋白热点名、没有 `c.` HGVS；表 2 蛋白符号 D156E/R168X/T158M。只冻三个代表等位基因。队列级「新鲜突变 / 亲起源」不按具名先证者 PM6。已有 `rett_055`/`062`/`063` 仍不作日文增量。

要再增加分类证据，尤其是德文或带父母检测的日文个案，新来源尽量同时满足：

1. 目标 **MECP2** 点变异（本规则机只授 PM6/PVS1/PP4/PM1；FOXG1/CDKL5 另表）。
2. 英文摘要/英文图注 **缺** 父母阴性、HGVS 或诊断中至少一项。
3. 有可哈希的 `reviewed/<id>/source.md`。

「全文 Pathogenic 且 ClinVar 无精确 VCV」仍然值得找，用来填交叉格，但不是入门门槛。相邻 1 bp 只标 `coordinate_near`，不算填上 both-hero。

不把作者自报 PS2/PM2/PP3 写成授予码。不把产品路径的 `assigned_acmg_codes` 写上。

---

## 5. 运行

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-allele-class-increment

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-evidence-item-coverage \
  --facts ../benchmark/experiments/acmg_multilingual/evidence_item_coverage_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```

2026-08-21 核验：`added codes 20/31 (without rett_007 16, 11 alleles); class flip 4 Pathogenic; ClinVar-gap Pathogenic 2; both-hero 0`。覆盖：`17 sources (es,fr,ja,ko,pt,ru,tr,zh); verified 200/200 spans`。

---

## 6. 声明边界

可以写：已审 31 条里，相对英文可见层多出准则的有 20 条事件、11 个等位基因；去掉 `rett_007` 仍有 16 条。其中 4 条事件顺带翻到 Pathogenic，这些等位基因 ClinVar 已有。ClinVar 缺口 Pathogenic 有 2 个位点，英文摘要已能评到同一套码。交叉是 0。俄文/韩文/日文/法文可因英文层没有 `c.` HGVS 而多出准则。`rett_081` 证明同一 T170M 可以是母源。

不能写：已经补上一个「英文没有、ClinVar 也没有」的位点分类；正式盲法 ACMG 代码不是 0；多语种给热点等位基因多贴了 ClinVar Pathogenic 标签；`rett_011` / `rett_069` 因为分类没翻就不算增量；已经有德文 MECP2 点变异增量；日文队列测了具名先证者双亲并授了 PM6；产品抽取写入了 ACMG 码；法文海报测了父母；韩文或日文队列把表中每一种变异都冻成独立论文。
