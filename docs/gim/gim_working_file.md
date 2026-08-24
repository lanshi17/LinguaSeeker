# GIM 投稿准备

> 从 NAR Web Server 转向 Genetics in Medicine (GIM)
> 核心论题：跨语言证据提取对 ACMG 变异分类的边际贡献

**创建日期:** 2026-08-09
**最后更新:** 2026-08-20

---

## 投稿目标

| 项目 | 说明 |
|------|------|
| 期刊 | Genetics in Medicine (GIM) |
| 类型 | Original Research Article |
| 核心数据 | 多语种 vs 纯英文对证据提取/变异评级的影响 |
| 实验规模 | 30 条 × 2 模式 (EN-only + Dual-track) |

---

## 核心实验: Ablation Study

**实验设计:** 同一批条目分别跑 EN-only 和 Dual-track (EN+ZH)，比较差异

**核心问题:**
1. 多语种处理比纯英文多提取多少证据？
2. 哪些字段的证据覆盖因中文文献而改善？
3. 额外证据是否改变 ACMG/AMP 分类判定？

**指标:**
- 证据增益: dual_track_count - en_only_count
- 字段改善: EN 漏检但 Dual 检出的字段
- 分类影响: 额外证据是否改变 BS/BS2/BS3 等判定

**预计时间:** 60 runs × ~7min/run ≈ 7 小时

---

## 论文结构 (GIM 向)

### 1. Introduction
- ACMG/AMP 变异分类的证据依赖
- 文献证据的语言偏倚（英文为主）
- 跨语言证据提取的潜在价值
- 本文贡献: 多智能体系统量化多语种对分类的影响

### 2. Methods
- 系统架构 (Multi-Agent, 4 阶段流水线)
- 跨语言双轨证据提取
- Gold standard 构建 (ClinGen+ClinVar fused-75)
- Ablation 实验设计

### 3. Results
- **Table 1**: EN-only vs Dual-track 证据提取对比
- **Figure 1**: 系统架构图
- **Figure 2**: 字段级改善热图
- **Figure 3**: Case study - 多语种证据改变分类的实例
- **Supplementary**: 完整 ablation 数据

### 4. Discussion
- 多语种证据的临床价值
- 对非英文人群变异分类的公平性影响
- 局限性与未来方向

---

## 关键 Figure

| # | 内容 | 类型 |
|---|------|------|
| F1 | 系统架构图 | 流程图 |
| F2 | Ablation 结果: EN-only vs Dual 证据量对比 | 柱状图/配对图 |
| F3 | 字段级改善热图 | 热图 |
| F4 | Case study: 多语种证据改变分类 | 截图/表格 |

---

## 与 NAR 版本的区别

| 维度 | NAR Web Server | GIM |
|------|----------------|-----|
| 重点 | 系统描述 + benchmark | 临床价值 + ablation |
| 核心数据 | 3-layer P/R/F1 | EN vs Dual 边际贡献 |
| Figure | 架构图 + UI + benchmark | 架构图 + ablation + case |
| 读者 | 生信/计算生物学 | 临床遗传学 |

---

## 进度

- [x] Fused-75 数据集构建
- [x] 中文翻译完成 (75/75)
- [x] Ablation runner 实现
- [x] 后端迁移 (source_language column)
- [x] Smoke test 通过
- [x] Ablation 实验运行 (30 × 2 = 60 runs, 30/30 valid)
- [x] 结果分析与可视化 (F1–F4 生成, 2026-08-12)
- [x] GIM 论文撰写 (draft.md 完整版, 2026-08-12)

---

## 最终结果 (2026-08-12)

报告文件: `benchmark/data/reports/nar_ablation/`

### 字段级金标匹配 (ablation_report.json, 30/30 valid)

| 指标 | EN-only | Dual-track |
|------|---------|------------|
| 平均匹配字段 (of 8) | 3.57 | 3.57 |
| 字段改善条目 | — | 3/30 (10%) |
| 字段丢失条目 | — | 2/30 |

- 改善: fused_005 (ADA, +variant_type=missense), fused_016 (DNM2, +moi=AD), fused_024 (GP1BA, +gene_symbol, 0→1 完全失败被挽救)
- 丢失: fused_022 (GJB2, −disease_diagnosis), fused_028 (HBB, −variant_hgvs_c)
- fused_016 有 1 换 1 (−gene_disease_relationship)

### 证据条目层多语种贡献 (multilingual_contribution_report.json, 29 valid)

| 指标 | 值 |
|------|-----|
| EN track 平均条目 | 15.9 / entry |
| Combined unique 平均 (字段数) | 17.24 / entry |
| ZH-only 平均增益 | +3.62 items (+22.8% of EN 均值) |
| Wilcoxon (单侧, gain>0) | p = 5.9e-06; r = 0.49; 95% CI [2.62, 4.62] |
| 受益条目 (有 ZH-only 条目) | 25/29 (86.2%; Wilson 95% CI 69.4–94.5%) |
| 有 ZH-only 字段条目 | 13/29 (44.8%; Wilson 95% CI 28.4–62.5%) |
| ZH-only 字段类型 | 14 种, 23 实例 (top: B.clinical_phenotypes 3, F.assay_type 3, J.clinvar_assertion 2) |

### 结论 (论文口径)

多语种处理对 86% 条目提供互补证据 (+22.8%)，对 10% 条目挽救具体字段 (variant type / MOI / gene symbol)，平均金标字段匹配不变 (3.57→3.57)。金标为英文中心 (ClinGen/ClinVar)，字段级收益被稀释；证据条目级收益是更敏感的多语种贡献度量。

---

## 论文完成度更新 (2026-08-12, 二次修订)

- [x] **统计检验** — `benchmark/analysis/gim_statistics.py` (可复现):
  - ZH-only 增益: Wilcoxon 单侧 p = 5.9e-06, 秩双列 r = 0.49, 95% CI [2.62, 4.62]
  - 字段匹配: 均值差 0.000 (95% CI −0.139/+0.139), Wilcoxon p = 1.0; McNemar 精确 b=3, c=3, p = 1.0
  - 最终输出条目: 109.9 vs 99.7, 差 −10.2 (95% CI −30.6/+10.3), p = 0.27 (n.s.)
- [x] **参考文献核验** (Crossref, 2026-08-12) — 修正 3 条错误 DOI:
  - Mastermind: 10.1101/214155(错, 癌症恶病质论文) → 10.3389/fgene.2020.577152 (Chunn, Front Genet 2020;11:577152)
  - ClinVar Miner: 10.1101/194480(错, 蚂蚁算法论文) → 10.1002/humu.23555 (Henrie, Hum Mutat 2018;39(8):1051–1060)
  - LitVar: 10.1093/nar/gky310(错, MetaboAnalyst) → 10.1093/nar/gky355 (Allot, NAR 2018;46(W1):W530–W536)
  - 另修正 ClinVar 2014 标题为 "public archive of relationships among sequence variation and human phenotype"
- [x] **数字口径修正** (单位混用问题):
  - multilingual_gain = ZH-only **条目数** (3.62, +22.8% of EN 均值 15.9), 非 combined−EN (1.34)
  - combined_unique_items = 去重后 **字段数** (17.24), 与 EN 条目数不同单位, 稿件已注明
  - ZH-only 字段实例数 25 → **23** (报告 field_level_zh_benefit 合计, §3.2/Table S2/工作文件同步修正)
  - 删除 "并集按构造为超集" 的错误表述 (去重后字段并集对部分条目 < EN 条目数)
- [x] **架构图 F5** — `benchmark/analysis/generate_gim_architecture.py` → `figures/F5_architecture.png` (4 阶段流水线 + ablation 设计插框), Methods 2.1 引用
- [x] **Data and Code Availability** 段已加入 (GitHub 仓库 + 报告文件 + 复现脚本)
- [ ] 待人工: 作者列表、基金声明 (期刊联系信息)

### 稿件文件状态

- `manuscript/draft.md` — 188 行完整稿, 统计/引用/图表全部就绪
- `supplementary/supplementary.md` — Table S1/S2 数据已修正 (23 实例)
- `figures/` — F1–F5 (F1 图注已修正单位标注, 2026-08-12 重新生成)

---

## GIM 格式合规修订 (2026-08-13, submission-ready)

对照 GIM Guide for Authors (Elsevier) 完成整改:

- [x] **摘要 297 → 188 词** (GIM 上限 200, 结构化 Purpose/Methods/Results/Conclusion)
- [x] **Display items 6 → 5** (上限 5): 分类别柱状图移入 Supplementary Figure S1, 保留 Figure 1–4 + Table 1
- [x] **图按引用顺序重编号** (GIM 要求编号=首次引用顺序): 架构图 F5→Figure 1, 配对图 F1→Figure 2, 分布图 F3 不变, 热图 F2→Figure 4, 类别图 F4→S1; 生成脚本同步改名并重新生成, 旧 PNG 已删除
- [x] **Methods 编号修正**: 2.5→2.6(统计)→2.7(LLM 配置), 原稿缺 2.6
- [x] **End matter 按 GIM 顺序**: Data Availability → Acknowledgments → Funding Statement → Author Contributions (CRediT 模板) → Ethics Declaration (纯公开数据无需 IRB) → COI → AI 写作声明 → References → Figure Legends
- [x] **Table 1 口径统一**: gained/lost 均按 "≥1 字段" 计 (3/3, fused_016 互换计入两侧), 新增净值行 (+2/−2/1 swap); §3.3 文字同步; 补充材料 S1 汇总同步
- [x] **参考文献 6 → 12 条**: 新增 Tavtigian 2018 / Harrison 2019 / Amano 2016 / Singhal 2023 / MinerU arXiv / M3-Embedding arXiv, 全部经 Crossref / arXiv API 核验 (2026-08-13); 按首次引用顺序重排; Rehm/Landrum 原先未被正文引用, 现在 §2.3 引用
- [x] **Data Availability 修复**: `benchmark/data` 为仓库外符号链接且被 .gitignore 忽略, 报告文件原本未入库 → 5 个报告文件复制到 `docs/gim/supplementary/reports/` (committed copy), `gim_statistics.py` / `generate_gim_figures.py` 增加回退读取路径, 声明文字改指向 committed copy
- [x] **统计复现** (2026-08-13): `uv run python benchmark/analysis/gim_statistics.py` 输出与正文全部一致
- [x] **补充材料英文化**: Fig S1 图注 + Table S1/S2 + Note S1–S5; Note S3 修正为与代码一致的描述 (无 BLEU, 实际为完整性/覆盖率/语言检查); Note S4 用实测耗时替换 TBD (EN-only mean 759.6s / median 623.1s; dual mean 612.6s / median 416.5s, n=30/模式, 附 batch 时段负载注记)
- [x] **Cover letter 草稿**: `assets/cover_letter.md`
- [x] **Title page 要素**: running title, 通讯作者占位
- [x] **LaTeX 版** (2026-08-13): `manuscript/latex/` — elsarticle (preprint, 12pt, 带页码无行号); elsarticle.cls 从 CTAN 源生成并 vendored; 参考文献内嵌 thebibliography (numbers,sort&compress); 构建产物已 .gitignore
- [x] **原文案例分析写入稿** (2026-08-20): §2.8/§3.5 + Supplementary Table S3 / Note S6；终点是 native−english 授予准则，不要求 Pathogenic 翻转；产品不写 ACMG 码；both-hero = 0
- [x] **扩语种扩事件** (2026-08-21): CLI `added codes 20/31`（11 等位基因；去掉 rett_007 仍 16）；17 篇来源、8 语种（es,fr,ja,ko,pt,ru,tr,zh）；both-hero 仍为 0；日文入仓为近藤 2002 队列三个代表等位基因（无具名先证者 PM6）；德文可哈希点变异病例仍未入仓
- [ ] 待人工: 作者列表/单位/通讯/CRediT/基金 (md 与 tex 两处同步); AI 声明工具名确认; Editorial Manager 上传
