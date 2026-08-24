# ACMG 多语种案例分析：字段桥与等位基因注册

**Status:** reference

**Created:** 2026-08-19

**范围：** 回答审稿人下一刀：规则机吃的是人手填的 JSON，不是抽取器吐出来的字段。本层把授码门禁映射到产品目录 `field_id`，用 `reviewed/*/source.md` 做阴影审计，并冻结等位基因别名与硬性不同一。后半把字段桥标出的洞补回 `evidence_extraction`。仍不是盲法 Stage-1。抽取器 live 见第 7 节和 [抽取字段进规则机](2026-08-19-acmg-multilingual-extractor-case-analysis.md)。

**可执行协议：** `canonical_alleles.py` + `field_bridge.py`。CLI：`check-field-bridge`。2026-08-19 对本仓库 `reviewed/` 核验 **14/14** 条 on-disk 事件（哈希 + 行锚引文 + 亲子鉴定缺席 + 等位基因绑定）。

---

## 1. 这一层补什么

18 日的规则机已经能从冻结事实授 `PM6` / `PVS1` / `PP4` / `PM1`。审稿人可以问：这些布尔字段从哪来？如果只存在于 `direct_inference_cases.json`，那只是分析员自己填的表。

本层把每条授码门禁写成目录字段：

| 授码 | 必须恢复的目录字段 | 原文怎么算过 |
|---|---|---|
| 先认出变异 | `A.variant_hgvs_c` | 行锚 HGVS 或表格单元格 |
| PM6 | `C.de_novo_status`、`C.maternal_genotype`、`C.paternal_genotype`、`C.parentage_confirmed` | 父母目标位点阴性的句子可同时填母本/父本；亲子鉴定是**缺席检查** |
| PVS1 / PVS1_Moderate | `A.variant_type`、`A.variant_hgvs_p` | 无义/移码字样，或 Sanger 缺碱基 |
| PP4 | `B.disease_diagnosis` | 经典型 RTT、先天型 RTT、Rett 증후군 |
| PM1 | `A.functional_domain_or_hotspot` | 原文写 MBD / methyl binding domain，且残基落在 VCEP 90–162 |
| 排除 | `B.disease_diagnosis` | `rett_007` 病例 5 写的是 MDS，不是点变异 RTT |

`C.parentage_confirmed` 在全部 PM6 事件上是 `absent`。扫描词是 `亲子鉴定`、`亲权鉴定`、`STR分型`、`paternity test`、`maternity test`、`parentage confirmation`、`identity testing`。14 篇 on-disk 原文都没有这些词。所以规则机继续拒 PS2。

这不是把 LLM 再跑一遍。仓库里没有这些病例的 `extraction_result.json`。本层只证明：原文里已经有抽取器按目录应当收回的句子。

---

## 2. 等位基因必须先注册

`canonical_alleles.json` 是闭集。转录本别名共用一个 `allele_id`。`not_same_as` 是硬拆，不能靠“看起来像”合并。

| 论文写法 | 规范 id | 绑定 | 不得当成 |
|---|---|---|---|
| `c.502C>T p.R168X` 与 `c.538C>T p.Arg180Ter` | `VCV000011828` | 同一 SPDI `NC_000023.11:154031325:G:A` | 两条 ClinVar 记录 |
| `c.844delC` / `c.808del` | `VCV000143702` | `NC_000023.11:154031019:GG:G` | 无义 `c.844C>T` / `VCV000011815` |
| `c.842delG` | `VCV000095202` | `NC_000023.11:154031021:CCCC:CCC` | 上一行的 2 bp 邻居 |
| `c.913insT` | `unmatched_c.913insT` | 无精确 VCV | 附近 K305fs 大缺失 `c.950_1208del` |
| `c.194delC`（`rett_084`） | **`unmatched_c.194delC`** | 无 SPDI | ClinVar `c.195del` / `VCV001076185`；LOVD `c.194C>G p.S65X` |

`coordinate_near` 不许把近邻 VCV 当作 `canonical_allele_id`。`rett_084` 的 `clinvar_vcv` 仍写 `VCV001076185`，只表示“查过这条近邻”，id 必须是 `unmatched_c.194delC`。

### `c.194delC`：相邻，不是同一条

18 日还把这篇写成“候选等价、SPDI 未钉死”。19 日把口径收死。

Sanger（`rett_084` `:31`）是真的少一个 C：患儿 `AGACAT-AGAAGG`，父母 `AGACATCAGAAGG`。蛋白写成 `p.S65X` 是历史无义标签，规则机按残基 65 的移码授 PVS1，这一点不变。

ClinVar `VCV001076185` 是 `NM_004992.4:c.195del p.Glu66fs` / `NM_001110792.2:c.231del p.Glu78fs`，SPDI `NC_000023.11:154032388:T:`，1 条 SCV，疾病是新生儿脑病。编码位差 1，蛋白起点是 E66 不是 S65。

LOVD/CCHMC 的 `c.194C>G p.S65X` 才是真的无义置换。中文这篇删的是 C，不能并进去。

所以 ClinVar 缺口仍是两条：`c.913insT` 无 VCV，`c.194delC` 只有相邻薄记录。Pathogenic 事件还是 8 条，折 6 个等位基因。数字没变，只是不再暗示“差不多就是 VCV1076185”。

---

## 3. 和 18 日规则机怎么接

抽取器（将来）→ 目录字段。本层证明这些字段在原文里找得到。规则机只看字段。组合器还是 Rett VCEP。冲突器最后。LLM 不进后三步。

`rett_011` 仍是反例：正文有 `父母未携带该变异位点` 和 `判读为 PS2+PM2+PP3`，字段桥只收前者进 PM6，不收自报代码。亲子鉴定缺席，所以没有 PS2。

`rett_007` 病例 5 只收 `Xq28区域存在重复变异` 和 `诊断为 MECP2 重复综合征`。点变异引擎继续排除。

`rett_066` 的 de novo 在韩文结果里写成 `denovo`，英文图注是 `observed only in the patient`。字段桥两处都记了。这不是韩文独占增量。

---

## 4. 现在仍不能写的句子

正式盲法 ACMG 代码已经不是 0。没有。

线上抽取器已经按这 14 条吐出了同样字段。14 条 on-disk live 已跑完，见抽取器案例分析。阴影分类 13/14 与冻结表一致；`rett_084` 因论文无义标签丢掉 PVS1。产品授码仍全空。

`c.194delC` 等于 `VCV001076185`。不等于。

多语种提取给热点等位基因多贴了一个 ClinVar Pathogenic 标签。没有。

---

## 5. 复跑

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-field-bridge \
  --cases ../benchmark/experiments/acmg_multilingual/direct_inference_cases.json \
  --alleles ../benchmark/experiments/acmg_multilingual/canonical_alleles.json \
  --facts ../benchmark/experiments/acmg_multilingual/field_bridge_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```

授码层仍用 `check-direct-inference`。两层都过，才把 18 日的 Pathogenic 数字和 19 日的字段出处绑在一起。

---

## 6. 产品抽取层补了什么

字段桥标出的洞已经写进 `evidence_extraction`。

`TargetSpanFieldRecovery` 会拆联合父母阴性句。`患儿父母均未检测到突变`、`父母在该位点均无异常`、`not found in his parents` 同时写成 `C.maternal_genotype` / `C.paternal_genotype` = `target_absent`，并假定 `C.de_novo_status=de_novo`。全文没有亲子鉴定用语时补 `C.parentage_confirmed=not_confirmed`。写了遗传自母/父的句子不授 de novo。

病例系列里父母句往往离 HGVS 表很远。目标变异一旦出现在全文、且通篇没有继承用语，也会从文级联合句恢复。第一版正则要求 `父母该位点均无` 中间不能插字，漏了 `患儿父母在该位点均无异常`；现在中间最多隔 12 个字。

`A.variant_type` 看编码区 indel。论文把 `c.194delC` 写成无义 / `p.S65X` 时，恢复和归一化都改成 frameshift。

B8 和目录提示写了同一条。span recovery 之后再跑一遍值归一化，LLM 先写成 nonsense 或 `parentage_confirmed=true` 也会被改回来。

14 条 on-disk PM6 事件对着 `reviewed/*/source.md` 做确定性阴影测试，父母门禁都能收回。正式盲法代码仍是 0。

---

## 7. live 探针：recovery 补上了什么

2026-08-19 对 `rett_007_case2_R180X` 和 `rett_011_P237R` 先跑了一轮 production `broad`（收据 `logs/2026-08-19_live_extraction_probe.json`），HTML / de novo 补丁后又跑一轮（`logs/2026-08-19_live_extraction_probe_after_html_patch.json`，约 7.1 分钟）。命令把 `--report` 换成对应路径即可：

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli probe-extraction \
  --cases ../benchmark/experiments/acmg_multilingual/direct_inference_cases.json \
  --facts ../benchmark/experiments/acmg_multilingual/field_bridge_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed \
  --report ../logs/2026-08-19_live_extraction_probe_after_html_patch.json \
  --event-id rett_007_case2_R180X \
  --event-id rett_011_P237R
```

两例 `assigned_acmg_codes` 都是空的。`rett_011` 没有把 `PS2+PM2+PP3` 写成授码。

| 门禁 | rett_007 病例 2（补丁后） | rett_011（补丁后） |
|---|---|---|
| `C.maternal_genotype` / `C.paternal_genotype` | LLM `target_absent`，金标匹配 | 同上 |
| `C.parentage_confirmed` | recovery 补 `not_confirmed` | 同上 |
| `C.de_novo_status` | 归一化成 `de_novo`，金标匹配 | LLM `de_novo` |
| `A.variant_hgvs_c` | 保住 `c.538C>T`（原文 `c.538C&gt;T`） | 保住 `c.710C>G` |
| `A.variant_type` | LLM `nonsense` | 本事件字段桥没要这条 |
| `B.disease_diagnosis` | LLM 写出后被 grounding 丢掉：引文 `1~4`，原文 `1\~4` | `Rett syndrome`，匹配 |

补丁前合计 11/14 门禁金标，补丁后 12/14。阴影规则机（不写产品代码）把病例 2 从 Pathogenic 降到 LP，因为诊断门没了、PP4 没了。`rett_011` 6/6，分类仍是证据不足。

14 条 on-disk 全量 live（2026-08-19，50.8 分钟，88/98 门禁金标，阴影分类 13/14 一致）见 [抽取字段进规则机](2026-08-19-acmg-multilingual-extractor-case-analysis.md)。`rett_007` 诊断门在解开 `\~` 后保住。`rett_084` 的 live `variant_type` 停在论文无义标签上。
