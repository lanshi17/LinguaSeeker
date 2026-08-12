# Lingua Seeker GIM 论文大纲

> **暂定标题:** Marginal Contribution of Cross-Lingual Evidence Extraction to ACMG/AMP Variant Classification: An Ablation Study of a Multi-Agent Literature Curation System
> **目标期刊:** Genetics in Medicine (GIM), Original Research Article
> **完整稿:** 见 `draft.md`（本文件为结构速览，随稿同步）

---

## Abstract (~250 words)

- 问题：ACMG/AMP 分类依赖人工文献证据搜集，非英语文献系统性缺失
- 方案：Lingua Seeker 四阶段多智能体流水线 + 受控 ablation（30 条 ClinGen/ClinVar 条目 × EN-only vs Dual-track）
- 结果：中文轨贡献 3.62 条/篇独有证据（+22.8% over EN 均值 15.9）；86.2% 条目受益；金标字段匹配 3.57→3.57 不变（p = 1.0）；10% 条目挽救字段
- 结论：跨语言处理对多数变异提供互补证据、偶尔挽救失败提取，且不降低平均金标表现

## 1. Introduction

1. ACMG/AMP 证据框架依赖文献；人工搜集成本高、以英文为主
2. 现有工具（Mastermind、ClinVar Miner、LitVar）仅搜英文库、无全文语义级证据提取
3. LLM 多智能体可自动化，但"原文+译文双轨 vs 纯英文"的边际价值未被量化
4. 贡献：(1) 系统；(2) ablation 方法论（证据条目层 vs 字段匹配层）；(3) 定量证据

## 2. Materials and Methods

- 2.1 系统架构（四阶段流水线，**F5 架构图**）
- 2.2 跨语言双轨证据提取（语言检测 → 翻译流水线 → 双轨提取 → 合并）
- 2.3 金标数据集（ClinGen + ClinVar 融合 75 条目，取 30 条；8 字段）
- 2.4 Ablation 设计（EN-only vs Dual-track，其余参数一致）
- 2.5 评估指标（EN-track items / ZH-only items / combined unique fields / field match）
- 2.6（现稿 2.7）统计分析（Wilcoxon / McNemar / Wilson & t CI, `gim_statistics.py`）
- 2.8 LLM 配置（通用/推理/多模态三角色独立路由）

## 3. Results

- 3.1 证据条目层：ZH-only 增益 +3.62（+22.8%, p = 5.9e-6）—— **F1, F3**
- 3.2 字段层：23 实例 / 14 类型 / 13 条目，B/C 类为主 —— **F2, F4**
- 3.3 金标字段匹配：均值不变（p = 1.0），3 挽救 / 2 丢失 / 1 互换 —— **Table 1**
- 3.4 汇总表（含最终输出条目 109.9 vs 99.7, p = 0.27）

## 4. Discussion

1. 主要发现：互补证据 + 偶尔挽救，金标口径下无平均退化
2. 为什么字段级落后于条目级：金标英文中心、匹配集语言不变字段为主
3. 挽救失败提取（fused_024 GP1BA 0→1）
4. 合并伪影（最终输出条目数下降趋势, n.s.）
5. 公平性：中文文献为主的变异会被英文中心流程低估
6. 局限：英文语料+机翻、8 字段子集、无分类终点、单模型族、样本量小
7. 结论

## References

- Richards et al. 2015, Genet Med 17(5):405-424, 10.1038/gim.2015.30
- Chunn et al. 2020 (Mastermind), Front Genet 11:577152, 10.3389/fgene.2020.577152
- Henrie et al. 2018 (ClinVar Miner), Hum Mutat 39(8):1051-1060, 10.1002/humu.23555
- Allot et al. 2018 (LitVar), NAR 46(W1):W530-W536, 10.1093/nar/gky355
- Rehm et al. 2015 (ClinGen), NEJM 372(23):2235-2242, 10.1056/NEJMsr1406261
- Landrum et al. 2014 (ClinVar), NAR 42(D1):D980-D985, 10.1093/nar/gkt1113
- 全部 6 条 DOI 已于 2026-08-12 经 Crossref 核验

## Figures 清单（`docs/nar-web-server/figures/`）

| 编号 | 文件 | 内容 |
|------|------|------|
| F1 | F1_paired_evidence_comparison.png | 逐条目 EN 条目数 vs 合并唯一字段数；ZH-only 增益 +22.8% |
| F2 | F2_field_level_zh_benefit_heatmap.png | 仅中文轨检出的字段热图（13/29 条目） |
| F3 | F3_evidence_gain_distribution.png | 逐条目 ZH-only 增益分布（25/29 > 0） |
| F4 | F4_evidence_by_category.png | 分 ACMG 类别 EN vs 中文轨证据条目数 |
| F5 | F5_architecture.png | 四阶段架构 + ablation 设计插框 |

## 待办

- [ ] 作者列表、基金声明
- [ ] （可选）分类级终点（最终 ACMG 类别），视审稿意见
