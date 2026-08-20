# ACMG 多语种案例分析：分类证据增量（Stage 0c）

**Status:** in-progress
**Created:** 2026-08-20
**Scope:** 终点是某个规范等位基因上、相对同 PDF 英文可见层**多出来的 Stage-0 ACMG 准则证据**（冻结规则机授予的 `PM6` / `PVS1` / `PP4` / `PM1`）。组合分类翻转（Pathogenic / LP）是更强子集，不是入门门槛。目录 `field_id` 个数只说明英文层少字段。产品路径不写 `assigned_acmg_codes`；正式盲法 Stage-1 代码仍为 0。

---

## 1. 终点：分类证据，不是字段并集，也不要求改分类

审稿人要看的是：**这篇非英语文献有没有给某个位点补上 ACMG 分类所需要的准则证据。** 典型形态是英文可见层评不到 `PM6`，中文/韩文正文写出双亲未携带，规则机因此多授一条 Moderate。分类可以仍停在证据不足；那也是增量。

更强、但仍属子集的句子是：多出来的证据把组合分类推到 Pathogenic / LP。再叠一层 ClinVar/ClinGen 无精确 VCV，就是「英文层没有、库里也没有」的交叉格。交叉目前是 0，不能拿来当主结论。

可执行对照：`check-allele-class-increment`。对 14 条 on-disk 事件用英文可见层事实跑一遍规则机，再用全文事实跑一遍；主差值是 `native granted_codes − english granted_codes`。

---

## 2. 已审 14 条：多出来的准则（2026-08-20）

CLI 复现：`added codes 6/14`（去掉 `rett_007` 仍 2 条、5 个等位基因）；其中 4 条事件、3 个等位基因顺带翻到 Pathogenic。ClinVar 缺口 Pathogenic 仍是 2，但那两条英文摘要已经授了同一套码。both-hero（多出准则 **且** 全文 Pathogenic **且** 库缺口）= 0。

| | ClinVar 已有精确/别名 VCV | ClinVar 缺口（无 VCV 或仅相邻） |
|---|---|---|
| **英文可见层已授同一套准则** | 热点（R106W、R270X、R168X-in-006、P152R 等） | **`c.913insT`、`c.194delC`** — 相对数据库的 Pathogenic，不是相对英文层 |
| **英文层缺码，全文补上** | **6 条事件 / 5 个等位基因**：`rett_007` 病例 1–4、`rett_011` P237R（**只 +PM6，分类仍不足**）、`rett_004` R168X | **空（both-hero = 0）** |

`rett_011` 是口径样板：英文摘要已有诊断（PP4），中文补父母未携带 → 多一条 `PM6`。错义不在 MBD/TRD，组合仍是证据不足。字段多了、分类没翻，但分类**证据**多了。

`rett_007` 病例 1（T170M）同样只到证据不足，但英文摘要没写 HGVS，全文补上 `PM6+PP4`。三条截短和 `rett_004` 才把分类推到 Pathogenic；这些等位基因 ClinVar 里已有。

韩文 `rett_066` 的英文 Fig. 1 已经写出 `c.455C>G` 且 only in the patient。全文多出的 missense/MBD 字样不增准则。

ClinVar 缺口两条的英文摘要已经写了等位基因和父母阴性，规则机在英文层就是 `PVS1+PM6+PP4`。多语种贡献是「中文期刊病例 vs 库」，不是「同页中英对照」。

---

## 3. 字段层仍要保留（机制，不是终点）

同一 PDF 仍切三层：`english_abstract` / `english_visible`（含英文图注）/ `native_fulltext`。规则机在英文层能否评分，取决于该层有没有 `A.variant_hgvs_c`；有 HGVS 之后，变异类型和 VCEP 残基跟位点走，不跟语言走。父母检测和诊断按英文层是否出现对应字段来遮罩。

6 篇字段表见同目录事实文件。4/6 来源相对英文摘要有 `field_id` 增量；去掉 `rett_007` 仍有 3 篇。那只说明「英文层少字段」。`rett_011` 的字段增量对应 +PM6；`rett_066` 的字段增量不对应任何新准则。

---

## 4. 日文、德文、俄文：按「英文层缺的准则」收

要增加分类证据，新来源尽量同时满足：

1. 目标 **MECP2** 点变异（本规则机只授 PM6/PVS1/PP4/PM1；FOXG1/CDKL5 另表）。
2. 英文摘要/英文图注 **缺** 父母阴性、HGVS 或诊断中至少一项，使全文能多授码。双亲检测是补 `PM6` 的常见路径；截短且英文没写 HGVS 时，全文也可以先补 `PVS1`/`PP4`。
3. 有可哈希的 `reviewed/<id>/source.md`。

「全文 Pathogenic 且 ClinVar 无精确 VCV」仍然值得找，用来填交叉格，但不是入门门槛。相邻 1 bp 只标 `coordinate_near`，不算填上 both-hero。

现有语料对这条猎场不友好：日文 2/3 不是 MECP2 病例；俄文有变异但常未测双亲（`rett_070` 大片段还被引擎排除）；没有德文。查询已在 `WEB_SEARCH_QUERIES`。未许可前不下载 PDF。

俄文 `approved/` 仍可按字段冻 HGVS。没有父母就补不上 `PM6`，但只要英文层缺 HGVS/诊断，截短仍可能多出 `PVS1`/`PP4`，那也算分类证据，不能事先当成 0。

---

## 5. 运行

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-allele-class-increment

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-evidence-item-coverage \
  --facts ../benchmark/experiments/acmg_multilingual/evidence_item_coverage_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```

---

## 6. 声明边界

可以写：已审 14 条里，相对英文可见层多出准则的有 6 条事件、5 个等位基因；去掉 `rett_007` 仍有 2 条（`rett_011` +PM6，`rett_004` +PM6/PVS1/PP4）。其中 4 条事件顺带翻到 Pathogenic，这些等位基因 ClinVar 已有。ClinVar 缺口 Pathogenic 有 2 个位点，英文摘要已能评到同一套码。交叉是 0。

不能写：已经补上一个「英文没有、ClinVar 也没有」的位点分类；正式盲法 ACMG 代码不是 0；多语种给热点等位基因多贴了 ClinVar Pathogenic 标签；`rett_011` 因为分类没翻就不算增量。

---

## 关联工件

| 工件 | 位置 |
|---|---|
| 分类证据对照 | `benchmark/experiments/acmg_multilingual/allele_class_increment.py` |
| 字段增量事实表 | `benchmark/experiments/acmg_multilingual/evidence_item_coverage_facts.json` |
| 规则机与 ClinVar 匹配 | `direct_inference_cases.json` / `canonical_alleles.json` |
| ClinVar 对照 | `docs/active/2026-08-17-acmg-clinvar-clingen-comparison.md` |
| 四臂设计 | `docs/active/2026-08-15-acmg-multilingual-four-arm-design.md` |
