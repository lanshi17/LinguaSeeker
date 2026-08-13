# GIM 投稿准备

> 从 NAR Web Server 转向 Genetics in Medicine (GIM)
> 核心论题：跨语言证据提取对 ACMG 变异分类的边际贡献

**创建日期:** 2026-08-09
**最后更新:** 2026-08-12

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
