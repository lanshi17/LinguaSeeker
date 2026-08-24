# ACMG 多语种四臂实验设计

**Status:** in-progress
**Created:** 2026-08-15
**Scope:** 回答"多语种文献是否提升 ACMG/AMP 代码恢复"的代码级研究设计。将审计提出的四臂方案冻结为可执行 spec，并把可立即量化的"来源覆盖层"作为 Stage 0 落地。

---

## 1. 问题与根因

现有 30 条 ClinVar-fused 消融（EN-only vs Dual-track）得到 EN=Dual=3.57 字段，不是"多语种无增益"的阴性结果，而是**结构性空比较**：

- 运行器始终提交英文 `source.md`，`source_zh.md` 是英文的 LLM 回译（非原生中文），translated track 原样复制英文文本（`skip_translate`），30/30 双轨输入 SHA-256 相同。
- 终点是 `field_id` 集合差，不是 `目标变异×代码家族×合格事件`，且 `assigned_acmg_codes` 是字段目录的静态复制，不是代码裁决。
- 因此 "ZH-only +22.8%" 只能描述同一英文文本两轨抽取的抖动，不能归因给多语种。

理论主张的效应是**信息恢复**：原生非英语全文携带英文 pivot 缺失的、可支撑 ACMG 准则复核的来源事实。要让它"更明显"，必须把比较对象换成真·原生非英语全文、把终点换成代码级事件。

---

## 2. 分层：先覆盖、后代码

| 层 | 问题 | 单位 | 门禁 | 状态 |
|---|---|---|---|---|
| **Stage 0 来源覆盖层** | 原生全文是否比同文英文摘要多恢复 PM6-eligible 来源事实？ | 来源 × 可见性 | 仅原文哈希校验 | **已落地** |
| **Stage 0c 目录字段** | 同一 PDF 原生正文是否比英文摘要/英文图注多出 catalog `field_id`？ | 来源簇 × `field_id` | 原文哈希 + 逐行引文 | **6 篇已审原文已冻结（zh+ko）；机制层，不是终点** |
| **Stage 0c 分类证据** | 原生全文是否比英文可见层多授 Stage-0 准则（PM6/PVS1/PP4/PM1）？ | 等位基因 × 授予准则差 | 英文层遮罩 + 同一规则机 | **14 条 on-disk：6 条多出准则（去 rett_007 仍 2）；分类翻转是子集；both-hero 0** |
| **Stage 0b 检索可达层** | 英文检索配置能否触达携带合格事件的来源？ | 目标变异 × 代码家族 × arm | 英文侧金标裁决 | **协议与评分已落地；已测出 provider 覆盖缺口（§7）** |
| **Stage 1 代码级四臂** | 加入原生非英语来源并以原生/译文/双轨阅读，是否恢复更多正式 ACMG 代码？ | 目标变异 × 代码家族 × 合格事件 | 译文审校 + 独立盲法裁决 | 设计已冻结，执行受阻 |

Stage 0 是 Stage 1 的必要前提：只有当原生全文确实携带英文 pivot 缺失的事实时，四臂中 `native-only`/`dual-track` 才可能超过 `translation-only`。Stage 0 已测得的增量（+5，见 §6）就是理论的真实形状。

---

## 3. 四臂定义（Stage 1）

在同一预先冻结的全语种语料集（英文论文 + 原生非英语论文，按目标变异配对）上：

| Arm | 语料 | 阅读方式 | 测量的作用 |
|---|---|---|---|
| `en_source` | 仅英文论文 | 英文原文 | 英文基线 |
| `all_source_translation_only` | 全语种 | 全部统一读英文译文 | 加来源（在译文条件下的覆盖效应） |
| `all_source_native_only` | 全语种 | 英文读原文，非英语读原生全文 | 原生语言轨道增量 |
| `all_source_dual_track` | 全语种 | 原生语言 + 英文译文双轨 | 双轨融合增量 |

对比定义（差值为代码级事件恢复量）：

- `2 − 1`：新增非英语来源在英文译文条件下的**覆盖效应**（与检索器"发现"效应分离）。
- `4 − 2`：原生语言轨道的增量（`native_only` 相对 `translation_only`）。
- `4 − 3`：译文轨道的增量。
- `4 − 1`：总多语种效应。

固定项：模型、提示词、字段目录、检索预算、目标变异、来源锚定门槛。检索阶段的合格来源召回率单独报告。

**已冻结语料清单（2026-08-15）**：`stage1_corpus_manifest.json` 冻结 48 个去重来源家族（按内容 SHA-256 去重，5 组同文别名 `rett_004/080`、`rett_006/082`、`rett_007/083`、`rett_011/087`、`rett_035/036`）。语言构成：英文 32、中文 8、日文 3、俄文 3、韩文 2。机械提取 6 个跨语种配对锚（同一 `c.` 变异同时见于英文与非英语来源）：`c.808C>T`、`c.502C>T`、`c.316C>T`、`c.1126C>T`、`c.538C>T`、`c.455C>G`（en+ko）。目标变异的选择与每个家族的 `index_assertion` 仍需临床审校后方可作为 Stage 1 分母。

---

## 4. 终点与分母

### 4.1 主终点

每个 `目标变异 × 代码家族` 是否恢复到一条金标支持、目标锚定、来源可回溯、规则完整、经人工裁决的**合格事件**。

主终点代码家族：`PS2_PM6`、`PM3`、`PP1_BS4`、`PS3_BS3`、`PS4`。`PVS1`/`PS1`/`PM1`/`PM5`/`PM2`/`BA1`/`BS1`/`PP3`/`BP4`/`PP4` 依赖转录本、机制、群体库、预测器或表型特异等文章外事实，不作为"仅凭文章可定"的主终点；`PVS1` 可作为分母中的 **code_candidate** 辅轨，不得与正式主终点混计。

`source_eligibility` 与正式 `outcome` 分开：父母阴性但缺亲子关系确认只能计为 PM6-eligible 来源事实，不得自动计为 PS2 或正式代码。

### 4.2 分母与去重

- 主单位：`目标变异 × 疾病断言 × ACMG 准则家族 × 独立来源/家系簇`。
- 每个 `source_family_id` 只贡献一个预先选择的 `index_assertion`；重复 PDF、文章别名、同一病例系列不得扩充分母。
- 每条 `SourceSpan` 标明冻结输入工件（`original`/`translated`）；`language` 只描述引文语言，不能替代工件归属。

### 4.3 跨病种增量分母（已冻结）

范围已放宽为「仓库已有、能体现 ACMG 增量的文献均可考虑」。冻结文件：`benchmark/experiments/acmg_multilingual/increment_denominator.json`。

| 轨道 | 叙事 | 槽位数（约） |
|---|---|---:|
| `multilingual_pm6_pvs1` | Rett 等非英全文恢复 PM6-eligible / PVS1 候选 | 见 JSON |
| `english_pm3_ready` | 英文 `fused_014` DCLRE1C compound het（PM3-ready） | 3（含 IL2RG 反例） |
| `parkinson_latent_pp1_ps3_ps4` | Parkinson 工作簿待导出晋升 | 3（latent） |

校验：`check-increment-denominator` 对 on_disk 槽位做 SHA-256 + 引文核查；正式代码计数仍为 0。

## 5. 统计口径

- 配对设计：同一目标变异/来源簇跨 arm 比较。
- 二分类终点（事件恢复 yes/no）：McNemar 精确检验；按代码家族分别做 + 多重比较校正。
- 聚类到去重来源/家系簇，不能把同一病例系列的多个变异当独立样本。
- 报告：配对代码召回率、净合格代码绝对增益、新增代码精确率、来源可追溯率。

---

## 6. Stage 0 来源覆盖层（已落地）

### 6.1 固定层

主正文为中文、且同一 PDF 含作者英文摘要的全部去重全文：`rett_006`、`rett_007`、`rett_011`、`rett_084`。测量同一来源"英文摘要可见内容"与"中文全文可见内容"的 PM6-eligible 观察恢复。

### 6.2 结果（人工临床审校，冻结为内容寻址事实表）

| 去重来源 | 英文摘要 | 中文全文 | 增量 |
|---|---:|---:|---:|
| `rett_006` 赵等 2014 | 5 | 5 | 0 |
| `rett_007` 刘等 2023 | 0 | 4 | +4 |
| `rett_011` 钟等 2024 | 0 | 1 | +1 |
| `rett_084` 葛等 2018 | 1 | 1 | 0 |
| **合计** | **6** | **11** | **+5** |

约束（写入叙事，不得越界）：

- 2/4 来源有增量；4/5 来自同一病例系列 `rett_007`，不能当 4 个独立文献复现。
- 11 条都缺亲子关系确认，是 PM6-eligible 观察，不是正式 PS2/代码。
- 这是来源覆盖增益，不是"ACMG 代码提高 83.3%"，不做显著性检验。

### 6.3 落地方式

冻结事实表 `benchmark/experiments/acmg_multilingual/source_coverage_facts.json`（绑定语料 revision + 每篇 `source.md` 的 SHA-256 + 每条正向观察的逐行引文跨度），配合只读验证器 `coverage.py`：逐篇校验原文哈希、逐条确认引文逐字存在于对应行，输出内容寻址收据。正向事实可机器复核；"摘要无该事实"的 0 计数属临床审读结论，记录在表内说明，不作哈希级验证。

运行（语料为仓库外符号链接，需本地 `<annotation-root>`）：

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli verify-coverage \
  --facts ../benchmark/experiments/acmg_multilingual/source_coverage_facts.json \
  --source-root <annotation-root> \
  --report <coverage-verification-report.json>
```

### 6.4 Stage 0c 分类证据（字段是机制）

目录 `field_id` 回答「英文层少字段」；终点是英文可见层与全文在**同一规则机**上授予的准则差。分类翻转（Pathogenic / LP）是更强子集。`rett_011` 只 +PM6、分类仍不足，也计入增量。协议见 `docs/active/2026-08-20-multilingual-evidence-item-increment.md`。

字段层（6 篇 zh+ko）：4/6 相对英文摘要有 `field_id` 增量；去掉 `rett_007` 仍有 3 篇。韩文 `rett_066` 计入英文 Fig. 1 后字段仍 +2，但准则差为 0。准则层（14 条 on-disk）：6/14 多出准则，去掉 `rett_007` 仍 2（`011`、`004`），5 个等位基因。日/德/俄未进本表。

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-allele-class-increment

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-evidence-item-coverage \
  --facts ../benchmark/experiments/acmg_multilingual/evidence_item_coverage_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```

---

## 7. 检索层共同主终点（Stage 0b）

### 7.1 为什么需要单独一层

Stage 0 与 Stage 1 读的都是人工已经收集好的 `source.md`，因此它们无法回答"纯英文管线本来能不能**找到**这些来源"。四臂中 `2−1` 若不把检索效应单独剥离，就会把"发现来源"与"读懂来源"混为一谈。

### 7.2 终点定义

单位与 Stage 1 一致：`目标变异 × 代码家族`。对每个目标，判定某 arm 是否检索到**至少一条携带合格事件的来源**：

| Arm | 查询 | provider 计划 |
|---|---|---|
| `english_only` | 冻结英文查询 | `build_provider_plan(language="en")` |
| `multilingual` | 冻结英文查询 + 冻结原生语言查询 | 英文计划 ∪ 各原生语言计划 |

- `multilingual` 强制为 `english_only` 的**严格超集**（契约校验），使召回单调，差值可解释。
- 命中判定只用**精确标识符相等**：规范化 DOI，或 PMID。两者都需要，因为中文期刊的 PubMed esummary 记录常有 PMID 而无 DOI（`rett_006` 即如此）。标题只记录供人工审阅，不得据此声称命中。
- 查询字符串**预注册冻结**在台账内，不在运行时调用译文模型，probe 因此可重放。
- 每个 arm 发送的是**按统一规则生成的查询梯度**，不是单条查询：由 `(gene, variant HGVS, disease)` 生成召回型与具体型各一条，每种语言同规则。必须如此，因为 PubMed 对所有检索词做 AND，单条过度具化的查询会返回 0 条，测到的是"这条查询是否恰好匹配"而不是可达性（见 §7.9）。English 梯度对两臂完全相同，`multilingual` 仍为严格超集；**禁止**按金标记录标题手工调参，否则等于把答案泄漏进多语种臂。
- 报告 target 级召回、事件级召回，以及配对不一致计数（即 McNemar 的 b/c）；推断仍留给分析层，与 `CodeRecoveryReport` 一致。

### 7.3 硬门禁：英文侧金标必须先裁决

`retrieval_targets.json` 当前 `english_source_adjudication = "pending"`，`score_retrieval_reachability()` 会**拒绝计分**。原因是：如果只把中文来源列为合格来源，`english_only` 臂在构造上必然为 0，配对比较会凭空偏向多语种。必须先逐目标裁决"哪些英文来源也携带合格事件"（如 `c.538C>T` 的英文 `rett_009` 已报告父母野生型），才能计分。

另有 3 个合格来源（`rett_004`、`rett_066`、`rett_085`）的 DOI 未记录在冻结事实表中，已列入 `pending_doi_source_family_ids`，不得静默缩小分母。当前分母为 4 个有 DOI 的来源、11 个 PS2_PM6 目标、11 条合格事件。

### 7.4 首次 probe 结果：这是 provider 覆盖缺口，不是英文/多语种差异

2026-08-18 对 `c.710C>G`（`rett_011`）做了单目标 live probe，并对 4 个有 DOI 的中文来源做了 DOI 级覆盖核查：

| 检查 | 结果 |
|---|---|
| `english_only` 主题检索（12 provider，10 候选） | 未命中金标 DOI |
| `multilingual` 主题检索（英文 + 中文查询，20 候选） | 同样未命中金标 DOI |
| Crossref DOI 直查 4 个中文 DOI | 0/4 解析成功 |
| OpenAlex DOI 直查 | 1/4（仅 `rett_084`） |
| EuropePMC DOI 直查 `rett_084` | success 但 0 条目 |
| 对照：Crossref 直查 `10.1038/gim.2015.30` | 成功，1 条目 |

对照组证明 DOI 直查链路本身可用，因此上述失败是**真实的收录缺口**：这些中文期刊（知网/万方系）不在 Crossref/OpenAlex/EuropePMC 的收录范围内。

**首轮结论：** 首轮两个 arm 都是 0，因此当时只能支持"英文中心管线触达不到这些来源"。为定位是查询问题还是收录问题，随后做了注册与索引溯源（§7.5）。

### 7.5 注册与索引溯源：四篇来源分成三类，不是同一个问题

用 Handle System（`doi.org/api/handles`，免密钥）逐个查证：**4/4 DOI 全部有效（`responseCode=1`）**，因此零命中不是 DOI 录错。解析目标地址直接暴露了注册机构：

| 来源 | DOI 解析目标 | 注册机构 | 聚合库收录 | 可达路径 |
|---|---|---|---|---|
| `rett_006` | `cjcp.org` | 期刊自建 | Crossref/OpenAlex 无；**PubMed 有（PMID 24750837）** | **需 `db=pubmed` provider** |
| `rett_007` | `chndoi.org` | **中文 DOI（ISTIC）** | 全无 | 真实收录缺口 |
| `rett_011` | `chndoi.org` | **中文 DOI（ISTIC）** | 全无 | 真实收录缺口 |
| `rett_084` | `doi.med.wanfangdata.com.cn` | 万方 | **OpenAlex + Semantic Scholar 有** | 已有 provider，需可命中的查询 |
| 对照 `10.1038/gim.2015.30` | Elsevier | Crossref | 有 | — |

关键洞察：`rett_007`/`rett_011` 用的是**中文 DOI 注册体系**（chndoi.org，非 Crossref RA），所以 Crossref API 永远查不到它们——这正是本项目正向来源（+5 增量）所在的两篇。

而 `rett_006` 的期刊《中国当代儿科杂志》**被 PubMed 收录**，且用普通英文主题查询 `MECP2 c.316C>T Rett syndrome parents` 就能在 PubMed 命中。它首轮落空的原因是：平台现行检索路径只有 `pmc` provider（`db=pmc`），**没有 `db=pubmed` 的 provider**；`pubmed_service.py` 早已实现 `search_candidates` 但从未被 gateway 或 workflow 调用。

### 7.6 已补 provider：PubMed（`db=pubmed`）

按上述证据补了最小改动，未引入浏览器抓取：

- `gateway.py` 新增 `_search_pubmed_via_service`，在 `call_provider` 里按 `jstage` 的先例把 `pubmed` 的 search 路由到 Python 服务（复用已存在但未接线的 `pubmed_service.py`）。
- `normalizers.py` 新增 `normalize_pubmed`，保留 PMID/PMCID/DOI 标识符（该记录常无 DOI），并在有 PMCID 时给出 PMC PDF 链接。
- `search_service.py` 把 `pubmed` 插入 `en` 与 `zh` 计划；刻意放在 `pmc` **之后**，使 `plan[0]` 不变，排序行为不受影响。
- `pubmed_service.py` 的 httpx 客户端改为使用 `get_config().network.proxy`，与 Rust provider 共用同一 egress。

**未采用的方案及原因：** 知网/万方/维普没有免密钥检索 API（需商业授权）；PubScholar 的 `/api/*` 路径全部返回 SPA HTML，无 JSON 接口，其归档适配器依赖 DuckDuckGo 抓取 + crawl4ai 浏览器自动化，正是 2026-06-16 因维护成本与稳定性被弃用的方案，不予复活。

**因此检索层的诚实定位是：** `rett_006` 类（PubMed 收录）可由英文查询触达——这会**加强**英文臂而不是多语种臂；`rett_007`/`rett_011` 类（中文 DOI 注册、无任何聚合库收录）在有商业授权的中文索引 API 之前，任何 arm 都触达不到。这两类的分野本身是可报告的结论：**证据只存在于原生全文的来源，恰好也是英文文献基础设施根本不收录的来源。** 在补齐授权 API 之前，语料仍属人工收集，不得表述为平台自动检索所得。

### 7.7 译文保真度：`native vs translation` 的去混淆

若英文全文丢掉关键事实，`native_only` 相对 `english_pivot` 的优势就是翻译损失而不是语言能力。`translation_fidelity.py` 把这一点做成确定性检查：每条关键事实给出原文逐行引文与必须存活的英文 token，验证器折叠空白后逐条比对（因此 OCR 的 `c . 7 1 0 C > G` 仍能匹配干净的 `c.710C>G`）。

对两个 ready 来源的结果：**8/8 关键事实在英文全文中全部存活**，3×2 工件哈希全部匹配，原文覆盖率 1.0。这支持一个重要判断：`rett_007`/`rett_011` 上任何 `native_only > english_pivot` 的差异**不能**归因于翻译丢事实。

同时暴露一个粒度问题：两份 `alignment.json` 都只有 **1 个整篇 chunk**，因此 chunk 级定位等价于文档级，无法定位段落级损失。设计文档此前描述的"逐段/表格对齐"尚未真正达到段落粒度。

### 7.9 零命中必须先做查询健全性检查

补上 PubMed provider 后重跑，仍然 0/11，但 PubMed 已记录 34 条带 PMID 的命中、其中没有金标 `rett_006`（PMID 24750837）。逐层排查后确认这**不是** provider 能力问题：

| 假设 | 检验 | 结果 |
|---|---|---|
| 排序截断（无 DOI 记录被 `has_doi` 打分压到尾部） | `candidate_limit` 由 10 提到 40 | 目标仍不出现，且返回集 `candidates_without_doi=0` → 该记录**从未进入候选集**，不是被截断 |
| 查询无法匹配 | 单独对 `pubmed` provider 试查询 | 预注册长查询返回 **0** 条；缩短为 `MECP2 c.316C>T Rett syndrome` 返回 2 条且**命中目标** |

根因是 PubMed 默认 AND 所有检索词，预注册查询里的 `p.R106W`、`de novo`、`not detected` 使交集为空。因此协议改为查询梯度（§7.2）。

**方法论要求：** 任何检索召回实验在解读零命中前，必须先确认预注册查询本身能返回已知应命中的样本，否则无法区分三种完全不同的原因——**provider 不收录 / 查询无法匹配 / 排序截断丢弃**。首轮把第二类误读成第一类，差点得出错误的"覆盖缺口"结论。

随后又发现第四种污染：**egress 故障**。查询梯度重跑时本机 `network.proxy`（`127.0.0.1:7890`）不可达，22 个 probe 中 19 个空结果，PubMed 日志为 `All connection attempts failed`。该轮 **不得**当作科学结果。同时暴露一处实现缺口：新接线的 `pubmed_service` 最初未走 `get_config().network.proxy`，与 Rust provider 的 egress 不一致；已改为共用同一代理。

第三种零命中（排序截断）是真实的产品行为：`search_parallel` 把 13 个 provider 的结果合并后截到 `candidate_limit`（默认 10），并按 `has_doi` 加分。中文期刊的 PubMed 记录常无 DOI，会被 Crossref 淹没。检索层 probe 因此改为**保留每个 provider 的全部候选、不截断并集**——可达性问的是"计划里有没有返回金标标识符"，不是"能否排进 top-10"。top-k 精度是另一项指标，不得与召回混报。

### 7.10 运行

live probe 是独立显式命令（会发起外部检索），计分与保真度验证均为离线只读：

```bash
cd backend

# 显式 live probe（外部检索；写出可重放的 probe 台账）
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.retrieval_reachability \
  --targets ../benchmark/experiments/acmg_multilingual/retrieval_targets.json \
  --probed-on <YYYY-MM-DD> --candidate-limit 10 --report <probe-ledger.json>

# 离线计分（英文侧金标裁决完成前会被门禁拒绝）
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli score-retrieval \
  --targets ../benchmark/experiments/acmg_multilingual/retrieval_targets.json \
  --probes <probe-ledger.json> --report <retrieval-recall-report.json>

# 译文保真度（只读，无模型调用）
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli verify-translation-fidelity \
  --facts ../benchmark/experiments/acmg_multilingual/translation_fidelity_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed \
  --report <fidelity-report.json>
```

---

## 8. 与现有三臂基础设施的关系

现有 `benchmark/experiments/acmg_multilingual/` 是**同一来源内**的三臂实验（`english_pivot`/`native_only`/`dual_track`），已实现并测试，被"人工审校英文全文译本"门禁（ready=0）阻塞。

四臂是**语料级**的超集，需要先冻结全语种语料清单（英文论文 + 按目标变异配对的非英语论文），再复用三臂的物化/审阅/评分契约。两者不冲突：三臂回答"同一来源不同阅读方式"，四臂回答"加入非英语来源是否提升代码恢复"。四臂落地前，三臂基础设施保持不动。

---

## 9. 声明边界（诚实口径）

- 当前数据能支持的最强结论有三句，不要合成一句：（1）原生非英语全文比同文英文摘要多恢复 PM6-eligible 来源事实（+5，Stage 0；无 `rett_007` 时 +1）；（2）相对英文可见层，14 条 on-disk 里有 6 条多出 Stage-0 准则（去 `rett_007` 仍 2，含 `rett_011` 只 +PM6）；其中 4 条顺带翻到 Pathogenic，这些等位基因 ClinVar 已有；（3）ClinVar 缺口 Pathogenic 2 个位点（`c.913insT`、`c.194delC`），英文摘要已授同一套码。**「英文层缺码且 ClinVar 也没有、全文还是 Pathogenic」的交叉目前是 0。**
- 不能支持：多语种使正式 ACMG 代码或最终分类"提升更明显"。后者需 Stage 1 四臂 + 完整组合规则 + 两名独立盲法 ACMG/AMP 裁决 + 第三审裁决分歧。分类没翻不等于没有分类证据增量。
- 不能支持：日文、德文、俄文已经有与中文同规模的准则增量。清单里没有德文；日文 2/3 不是 MECP2 病例；俄文有变异字段但常未测双亲，补不上 `PM6`，截短仍可能多出 `PVS1`/`PP4`。
- 稿件叙事（`docs/gim/`）在提交前须按此边界复核：不得把 translated track 称作 "Chinese evidence"、把字段增益解释为多语种增益、把字段映射解释为代码改善。
- **译文审校已按用户指令以模型替代人工**：`rett_007`/`rett_011` 的英文全文为模型翻译 + 模型审校（新增 `model_reviewed` 状态，非 `human_reviewed`）。任何下游声明必须写明"模型审校（非人工）"，不得表述为"人工审校/人类复核"；正式 ACMG 代码裁决与最终分类仍未经人类确认。

---

## 10. 执行状态

- [x] Stage 0 事实表冻结 + 内容寻址验证器
- [x] Stage 0 验证收据（对本地语料 `5b1f7673e7f4ea7922f3ad7efb79f25fdbfedab7`）
- [x] Stage 0c 目录字段事实表 + 验证器（6 篇 zh+ko；`check-evidence-item-coverage`）
- [x] Stage 0c 分类证据对照（英文可见层 vs 全文授予准则差；`check-allele-class-increment`；6/14 多出准则，both-hero 0）
- [ ] 将 ja/ru `approved/` 按 `field_id` 冻进 Stage 0c（允许无父母字段；无父母仍可能多出 PVS1/PP4）
- [ ] 按「英文层缺的准则」收入德文及其它语种 **MECP2 点变异**（优先双亲阴性以补 PM6；先清单、后下载）。both-hero 仍是空格，不是入门门槛
- [x] Stage 1 全语种语料清单冻结（48 家族：en 32 / zh 8 / ja 3 / ru 3 / ko 2；6 跨语种配对锚）→ `stage1_corpus_manifest.json` + `four_arm_corpus.py` 扫描/验证器 + `freeze-corpus`/`verify-corpus` CLI
- [x] 正向来源 `rett_007`/`rett_011` 英文全文模型翻译+模型审校（`model_reviewed`，按用户指令以模型替代人工；2/6 ready，其余 4 仍 `needs_translation_review`）→ `pilot_model_reviewed.json` + `reviewed/` 工件，materialize 端到端通过
- [x] Stage 0b 检索层协议 + 评分 + live probe 运行器（`retrieval_reachability.py`、`retrieval_targets.json`、`score-retrieval` CLI；11 目标 / 11 事件，英文侧金标未裁决因此计分被门禁拦住）
- [x] 译文保真度验证器（`translation_fidelity.py`、`translation_fidelity_facts.json`、`verify-translation-fidelity` CLI；2 来源 8/8 事实存活）
- [x] **跨病种增量分母冻结**（`increment_denominator.json` + `increment_denominator.py` + `check-increment-denominator` CLI）：31 槽位 = Rett 多语 PM6/PVS1（含 `rett_007`/`011` 增量）+ 英文 `fused_014` PM3-ready + Parkinson 工作簿 latent（PP1/PS3/PS4）；24/24 on-disk 哈希与引文验证通过；正式代码仍为 0
- [ ] **补授权中文索引 API**（知网/万方/维普；`rett_007`/`rett_011` 为中文 DOI，现有聚合库永不收录）
- [ ] 英文侧合格来源逐目标裁决 + 3 个待补 DOI
- [ ] 网络恢复后，用查询梯度 + 不截断并集重跑 11 目标 live probe（上一轮被本机代理宕机污染，作废）
- [ ] 从 Parkinson 工作簿导出并晋升 3–5 个 PP1/PS3/PS4 具体 `case_id` 槽位
- [ ] 四臂运行 + 独立盲法裁决 + 计分

## 参考方法学

- Richards S, et al. *Genet Med.* 2015. DOI `10.1038/gim.2015.30`
- Abou Tayoun AN, et al. *Hum Mutat.* 2018. DOI `10.1002/humu.23626`
- Brnich SE, et al. *Genome Med.* 2019. DOI `10.1186/s13073-019-0690-2`
- Biesecker LG, et al. *Am J Hum Genet.* 2023. DOI `10.1016/j.ajhg.2023.11.009`
