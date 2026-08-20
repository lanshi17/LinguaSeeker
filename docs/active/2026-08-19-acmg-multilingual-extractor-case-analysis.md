# ACMG 多语种案例分析：抽取字段进规则机

**Status:** reference

**Created:** 2026-08-19

**范围：** 18 日规则机吃的是人手填的布尔字段。19 日字段桥证明这些字段在 `reviewed/*/source.md` 里找得到。本层问：production `broad` 抽取器 live 吐出来的目录值，能不能撑住同一台规则机。产品路径仍然不写 `assigned_acmg_codes`。叠加授码只发生在探针收据里。

**可执行协议：** `live_extraction_probe.py` 的 `compare_live_gates_to_engine()`。CLI：`probe-extraction --all-on-disk`。收据：`logs/2026-08-19_live_extraction_probe_14_on_disk.json`（2026-08-19，qwen3.7-flash / plus，14/14 completed，50.8 分钟）。HTML 补丁后、解开 `\~` 之前的两例旧收据：`logs/2026-08-19_live_extraction_probe_after_html_patch.json`。

---

## 1. 主张什么，不主张什么

### 1.1 现在可以写的句子

14 条 on-disk 事件都 live 跑完了。产品 `assigned_acmg_codes` 14 条都是空的。阴影规则机分类与冻结表一致 **13/14**。唯一翻盘是 `rett_084`：论文把 `c.194delC` 写成无义 / `p.S65X`，抽取器照抄 `nonsense`，字段桥要的是 frameshift，PVS1 拿不到，分类从 Pathogenic 掉到证据不足。

`rett_007` 病例 1–4 的诊断门这轮都保住了。上一轮病例 2 因为 `source.md` 里的 `1\~4` 丢掉 PP4、阴影机降到 LP；探针文档先解开 markdown `\~` 之后，同一事件回到 Pathogenic。

`rett_011` 6/6 门禁。阴影机仍是 `PM6+PP4`、证据不足。这轮 notes 里只剩 PM6，没有把正文 `PS2+PM2+PP3` 写成授码。

字段桥 98 扇门里 88 扇金标匹配。11 扇亲子缺席由 recovery 补上。origin=missing 是 0。

### 1.2 现在不能写的句子

正式盲法 ACMG 代码已经不是 0。产品代码仍全空。

抽取器已经按冻结表授了 8 条 Pathogenic。阴影机只有 7 条：`rett_084` 被论文无义标签卡住。

14 条探针都是 original-track 全文，不能拿来比较「英文可见层 vs 原生正文」。相对英文层多出的准则见 [Stage 0c](2026-08-20-multilingual-evidence-item-increment.md)。

蛋白 HGVS 金标全中。7 条事件停在 `p.R180*` / `p.R168*` / `p.K305fs` 对三字母金标。`A.variant_type` 仍匹配时 PVS1 不掉。这是探针匹配器和蛋白归一化（`p.Gly281AlafsTer20` 被压成 `p.G281A`）的洞，不是 LoF 身份丢了。

---

## 2. 叠加规则

冻结事件保持等位基因位置、冲突旗标、作者自报列表不变。live 只改规则机真正读的那几扇门：

| 门禁 miss | 阴影机怎么改 |
|---|---|
| `C.maternal_genotype` 或 `C.paternal_genotype` | 父母阴性、双亲已测都改成假，PM6 拿不到 |
| `C.de_novo_status` | `inheritance=unknown`，PM6 拿不到 |
| `C.parentage_confirmed` 写成已确认 | `parentage_confirmed=true`，PM6 拿不到（本协议拒 PS2） |
| `B.disease_diagnosis` | `phenotype_class=other`，PP4 拿不到 |
| `A.variant_type`（无义/移码事件） | 改成 missense，PVS1 拿不到 |
| `A.functional_domain_or_hotspot`（错义） | 清掉蛋白位置，PM1 拿不到 |

字段桥里没有的门保持冻结值。`rett_011` 没有 `A.variant_type` 门，错义身份继续用表。`A.variant_hgvs_c` miss 记进 `degraded_field_ids`，但不改 `variant_class`：病例系列的目标变异已经由 `ExtractionTarget` 钉死。

探针文档会先解开 HTML 实体和 markdown `\~`。`_normalize_variant_type` 本应在 `c.…del/ins` 证据里把论文无义改成 frameshift；`rett_084` 这条 live 上没改成，`final_value` 仍是 `nonsense`。归一化看的是该 item 自己的 `target_variant` 和引文，模型如果只在类型字段写了“无义”、没有把 `c.194delC` 带进同一条 item，就不会触发。

---

## 3. 冻结 14 条：人手字段进规则机

数字与 18 日审稿口径同一台引擎。`check-direct-inference` 对 `reviewed/` 仍是 14/14。

| 事件 | 论文 HGVS | 类 | 冻结授码 | 分类 |
|---|---|---|---|---|
| `rett_007_case1_T170M` | `c.509C>T` | missense | PM6+PP4 | insufficient |
| `rett_007_case2_R180X` | `c.538C>T` | nonsense | PM6+PVS1+PP4 | pathogenic |
| `rett_007_case3_G281fs` | `c.842delG` | frameshift | PM6+PVS1+PP4 | pathogenic |
| `rett_007_case4_R282fs` | `c.844delC` | frameshift | PM6+PVS1+PP4 | pathogenic |
| `rett_007_case5_Xq28dup` | Xq28 0.299 Mb dup | CNV | 无 | excluded |
| `rett_011_P237R` | `c.710C>G` | missense | PM6+PP4 | insufficient |
| `rett_006_A_R106W` | `c.316C>T` | missense | PM6+PP4+PM1 | insufficient |
| `rett_006_B_P376S` | `c.1126C>T` | missense | PM6+PP4 | blocked_conflict |
| `rett_006_D_R270X` | `c.808C>T` | nonsense | PM6+PVS1+PP4 | pathogenic |
| `rett_006_F_R168X` | `c.502C>T` | nonsense | PM6+PVS1+PP4 | pathogenic |
| `rett_006_G_913insT` | `c.913insT` | frameshift | PM6+PVS1+PP4 | pathogenic |
| `rett_084_194delC` | `c.194delC` | frameshift | PM6+PVS1+PP4 | pathogenic |
| `rett_004_R168X` | `c.502C>T` | nonsense | PM6+PVS1+PP4 | pathogenic |
| `rett_066_P152R` | `c.455C>G` | missense | PM6+PP4+PM1 | insufficient |

8 条 Pathogenic，折 6 个规范等位基因。错义没有一条走到 LP：`PM1+PM6+PP4` 缺第二条 Supporting。`P376S` 先拦住。病例 5 的 MDS 重复继续排除。

外部语料 4 条（`rett_081/079/085/070`）本层不跑 live。

---

## 4. 对照：解开 `\~` 之前的两例

HTML 补丁后、探针还不解 markdown 时，病例 2 诊断被 grounding 丢掉，阴影机 Pathogenic → LP。同一模型、同一事件，14 条这轮诊断门匹配，分类回到 Pathogenic。蛋白门仍是 `p.R180*` 对 `p.Arg180Ter`。

| 收据 | 病例 2 诊断 | 病例 2 阴影分类 | rett_011 门禁 |
|---|---|---|---|
| `…_after_html_patch.json` | SOURCE_INVALID（`1~4` vs `1\~4`） | likely_pathogenic | 6/6 |
| `…_14_on_disk.json` | Rett syndrome，匹配 | pathogenic | 6/6 |

---

## 5. 14 条 on-disk live

模型：qwen3.7-flash / plus。原轨 `broad`。合计 3047 秒。origin：llm 80，recovered 11，normalized 7，missing 0。门禁金标 **88/98**。产品代码全部 `[]`。阴影分类翻盘 **1/14**。

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli probe-extraction \
  --cases ../benchmark/experiments/acmg_multilingual/direct_inference_cases.json \
  --facts ../benchmark/experiments/acmg_multilingual/field_bridge_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed \
  --report ../logs/2026-08-19_live_extraction_probe_14_on_disk.json \
  --all-on-disk
```

| 事件 | 门禁 | 冻结分类 | 阴影 live | 丢掉的门 |
|---|---|---|---|---|
| `rett_007_case1_T170M` | 6/6 | insufficient | insufficient | 无 |
| `rett_007_case2_R180X` | 7/8 | pathogenic | pathogenic | `A.variant_hgvs_p`（`p.R180*` vs `p.Arg180Ter`） |
| `rett_007_case3_G281fs` | 7/8 | pathogenic | pathogenic | `A.variant_hgvs_p`（`p.G281A` vs `p.Gly281fs`） |
| `rett_007_case4_R282fs` | 7/8 | pathogenic | pathogenic | `A.variant_hgvs_p`（`p.R282E` vs `p.Arg282fs`） |
| `rett_007_case5_Xq28dup` | 1/2 | excluded | excluded | `A.variant_hgvs_c`（下划线写法对不上空格金标） |
| `rett_011_P237R` | 6/6 | insufficient | insufficient | 无 |
| `rett_006_A_R106W` | 7/7 | insufficient | insufficient | 无 |
| `rett_006_B_P376S` | 6/6 | blocked_conflict | blocked_conflict | 无 |
| `rett_006_D_R270X` | 7/8 | pathogenic | pathogenic | `A.variant_hgvs_p` |
| `rett_006_F_R168X` | 7/8 | pathogenic | pathogenic | `A.variant_hgvs_p` |
| `rett_006_G_913insT` | 7/8 | pathogenic | pathogenic | `A.variant_hgvs_p`（`p.K305fs` vs `p.Lys305fs`） |
| `rett_084_194delC` | 6/8 | pathogenic | **insufficient** | `A.variant_type=nonsense`，蛋白停在 `p.S65*` |
| `rett_004_R168X` | 7/8 | pathogenic | pathogenic | `A.variant_hgvs_p` |
| `rett_066_P152R` | 7/7 | insufficient | insufficient | 无 |

PM6 链（de novo / 父母阴性 / 亲子缺席）14 条里点变异事件都过了。错义 PM1 两例（`R106W`、`P152R`）域门也过了。`P376S` 冲突拦截仍在。病例 5 继续排除。

10 扇 miss 里 7 扇是蛋白别名或归一化把 fs 吃掉；1 扇是 CNV 字符串；2 扇挤在 `rett_084`。分类只跟最后这两扇走。

### 5.1 `rett_084`：论文无义标签压过 Sanger 缺 C

葛骏文等。摘要和正文都写 `c.194delC`、父母阴性、先天型 RTT。Sanger 是 `AGACAT-AGAAGG` 对父母 `AGACATCAGAAGG`。字段桥和冻结规则机按残基 65 的移码授 PVS1。

live 抽取器写成 `A.variant_type=nonsense`，跟论文“无义突变（p.S65X）”一致。阴影机因此不授 PVS1，只剩 `PM6+PP4`，证据不足。产品代码仍空。

这不是模型发明了一种新解读，是跟着论文的历史无义标签走。确定性阴影测试对着 `source.md` 能把 del 收成 frameshift；live 这条 item 的引文里没有带上 `c.194delC`，`_normalize_variant_type` 没改值。

### 5.2 蛋白门经常 miss，但不改分类

LLM 常常先写出三字母（`p.Arg180Ter`），归一化成单字母星号（`p.R180*`）。金标还是三字母或 `p.Gly281fs`。移码有时被压成氨基酸替换：`p.Gly281AlafsTer20` → `p.G281A`。`A.variant_type` 仍是 nonsense/frameshift 时，阴影机继续授 PVS1。

### 5.3 作者自报代码

14 条 notes 里都能扫到 `PM6`（B8 提示用语）。`rett_011` 上一轮还扫到 PS2/PM2/PP3，这一轮没有。两轮 `assigned_acmg_codes` 都是空的。

---

## 6. 复跑

授码层：`check-direct-inference`。字段出处：`check-field-bridge`。抽取叠加：上面的 `probe-extraction --all-on-disk`。只重算阴影机、不调模型：

```bash
cd backend
PYTHONPATH=.. uv run --all-groups python - <<'PY'
from pathlib import Path
from benchmark.experiments.acmg_multilingual.live_extraction_probe import LiveExtractionProbeReport

report = LiveExtractionProbeReport.model_validate_json(
    Path("../logs/2026-08-19_live_extraction_probe_14_on_disk.json").read_text()
)
for item in report.events:
    engine = item.engine
    print(item.event_id, engine.live_classification, engine.classification_changed, engine.degraded_field_ids)
PY
```

应打印 14 行，只有 `rett_084_194delC` 的 `classification_changed` 为真。
