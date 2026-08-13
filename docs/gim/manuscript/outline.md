# Lingua Seeker GIM 论文大纲

> **暂定标题:** Marginal Contribution of Cross-Lingual Evidence Extraction to ACMG/AMP Variant Classification: An Ablation Study of a Multi-Agent Literature Curation System
> **目标期刊:** Genetics in Medicine (GIM), Original Research Article
> **完整稿:** 见 `draft.md`（本文件为结构速览，随稿同步）
> **格式合规:** 摘要 188 词（≤200）；正文 ~2,240 词（≤4,000）；display items 5 个（Figure 1–4 + Table 1，≤5）；参考文献 12 条（≤40，编号制）

---

## Abstract (188 words, 结构化)

- Purpose：ACMG/AMP 分类依赖人工文献证据搜集，非英语文献系统性缺失；量化跨语言提取的边际贡献
- Methods：Lingua Seeker 四阶段多智能体流水线 + 受控 ablation（30 条 ClinGen/ClinVar 条目 × EN-only vs Dual-track）
- Results：中文轨贡献 3.62 条/篇独有证据（+22.8% over EN 均值 15.9, p = 5.9e-6）；86.2% 条目受益；金标字段匹配 3.57→3.57 不变（p = 1.0）；3 条目获得字段/2 净丢失/1 互换
- Conclusion：跨语言处理提供互补证据且不降低平均精度；证据条目层比英文中心金标字段匹配更敏感

## 1. Introduction

1. ACMG/AMP 证据框架依赖文献（refs 1–3: Richards/Tavtigian/Harrison）；人工搜集成本高、以英文为主（ref 4: Amano 语言壁垒）
2. 现有工具（Mastermind、ClinVar Miner、LitVar, refs 5–7）仅搜英文库、无全文语义级证据提取
3. LLM 多智能体可自动化（ref 8: Singhal），但"原文+译文双轨 vs 纯英文"的边际价值未被量化
4. 贡献：(1) 系统；(2) ablation 方法论（证据条目层 vs 字段匹配层）；(3) 定量证据

## 2. Materials and Methods

- 2.1 系统架构（四阶段流水线，**Figure 1 架构图**；MinerU ref 9、bge-m3 ref 10）
- 2.2 跨语言双轨证据提取（语言检测 → 翻译流水线 → 双轨提取 → 合并）
- 2.3 金标数据集（ClinGen ref 11 + ClinVar ref 12 融合 75 条目，取 30 条 fused_000–029；8 字段）
- 2.4 Ablation 设计（EN-only vs Dual-track，其余参数一致；耗时见 Supplementary Note S4）
- 2.5 评估指标（EN-track items / ZH-only items / combined unique fields / field match）
- 2.6 统计分析（Wilcoxon / McNemar / Wilson & t CI, `gim_statistics.py`）
- 2.7 LLM 配置（通用/推理/多模态三角色独立路由）

## 3. Results

- 3.1 证据条目层：ZH-only 增益 +3.62（+22.8%, p = 5.9e-6）—— **Figure 2, Figure 3**
- 3.2 字段层：23 实例 / 14 类型 / 13 条目，B/C 类为主 —— **Figure 4**；分类别总量 → Supplementary Figure S1
- 3.3 金标字段匹配：均值不变（p = 1.0），3 获得 / 3 丢失（含 1 互换 fused_016），净 +2/−2 —— **Table 1**
- 3.4 汇总表（含最终输出条目 109.9 vs 99.7, p = 0.27）

## 4. Discussion

1. 主要发现：互补证据 + 偶尔挽救，金标口径下无平均退化
2. 为什么字段级落后于条目级：金标英文中心、匹配集语言不变字段为主
3. 挽救失败提取（fused_024 GP1BA 0→1）
4. 合并伪影（最终输出条目数下降趋势, n.s.）
5. 公平性：中文文献为主的变异会被英文中心流程低估
6. 局限：英文语料+机翻、8 字段子集、无分类终点、单模型族、样本量小
7. 结论

## End matter（GIM 要求顺序）

Data Availability → Acknowledgments → Funding Statement① → Author Contributions①(CRediT) → Ethics Declaration（纯公开数据，无需 IRB）→ Conflict of Interest → AI 写作声明① → References → Figure Legends

① 待人工填写/确认

## References（12 条，全部核验 2026-08-13）

1. Richards 2015, Genet Med, 10.1038/gim.2015.30
2. Tavtigian 2018, Genet Med, 10.1038/gim.2017.210
3. Harrison 2019, Curr Protoc Hum Genet, 10.1002/cphg.93
4. Amano 2016, PLoS Biol, 10.1371/journal.pbio.2000933
5. Chunn 2020 (Mastermind), Front Genet, 10.3389/fgene.2020.577152
6. Henrie 2018 (ClinVar Miner), Hum Mutat, 10.1002/humu.23555
7. Allot 2018 (LitVar), NAR, 10.1093/nar/gky355
8. Singhal 2023, Nature, 10.1038/s41586-023-06291-2
9. Wang 2024 (MinerU), arXiv:2409.18839
10. Chen 2024 (M3-Embedding), arXiv:2402.03216
11. Rehm 2015 (ClinGen), NEJM, 10.1056/NEJMsr1406261
12. Landrum 2014 (ClinVar), NAR, 10.1093/nar/gkt1113

## Figures 清单（`docs/gim/figures/`，按引用顺序编号）

| 编号 | 文件 | 内容 |
|------|------|------|
| Figure 1 | F1_architecture.png | 四阶段架构 + ablation 设计插框 |
| Figure 2 | F2_paired_evidence_comparison.png | 逐条目 EN 条目数 vs 合并唯一字段数；ZH-only 增益 +22.8% |
| Figure 3 | F3_evidence_gain_distribution.png | 逐条目 ZH-only 增益分布（25/29 > 0） |
| Figure 4 | F4_field_level_zh_benefit_heatmap.png | 仅中文轨检出的字段热图（13/29 条目） |
| Suppl. Fig. S1 | S1_evidence_by_category.png | 分 ACMG 类别 EN vs 中文轨证据条目数 |

## 待办

- [ ] 作者列表、单位、通讯方式、CRediT 贡献、基金声明（人工）
- [ ] AI 写作声明中工具名确认（或删除该节）
- [ ] （可选）分类级终点（最终 ACMG 类别），视审稿意见
