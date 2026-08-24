# Figure Specifications (GIM)

> 论文插图规格说明。与实际生成的图文件一致（`docs/gim/figures/`）。
> 编号按正文首次引用顺序（GIM 要求）；display items 共 5 个（Figure 1–4 + Table 1），类别图移入补充材料 S1。
> Figure 1 最终投稿图为人工审定的扁平矢量风格重设计稿；`benchmark/analysis/generate_gim_architecture.py` 保留生成旧版回退图。F2–F4、S1 由 `benchmark/analysis/generate_gim_figures.py` 生成。
> 数据源：`docs/gim/supplementary/reports/multilingual_contribution_report.json` 等（committed copy；脚本优先读 `benchmark/data/reports/nar_ablation/`，不存在时回退到 committed copy）。

---

## Figure 1: F1_architecture_redesign.png — 系统架构 + Ablation 设计

**用途:** 展示四阶段流水线及受控 ablation 设计（Methods §2.1 引用，正文首个引用的图）

**内容:**
- 上排: Literature Intake → Dual-Track Extraction（English / Chinese 分流、LLM Extraction、Merge + Provenance）→ Entity Alignment → Expert Review
- 下排: 30 条配对条目的受控消融，Mode A (EN-only) vs Mode B (EN + ZH)，并展示相同模型/提示词/字段约束
- 结果面板: ZH-only gain +3.62/entry (+22.8%)、Evidence gain 25/29、Field match 3.57/8 vs 3.57/8

**风格:** 纯白背景、扁平矢量线稿、淡蓝/杏色/薄荷绿/淡紫色模块；无阴影、渐变、纹理或 3D 效果。视觉哲学见 `F1_architecture_design_philosophy.md`。
**尺寸:** 1536 × 1024 px（3:2 横向；优先保证正文宽度下的标签可读性）@ 300 dpi
**回退图:** `F1_architecture.png`（matplotlib 脚本生成，不用于当前 LaTeX 主稿）

---

## Figure 2: F2_paired_evidence_comparison.png — 配对证据量对比

**用途:** 逐条目展示英文轨 vs 合并多语输出的证据量差异（Results §3.1）

**内容:**
- X 轴: 30 个条目 (fused_000–fused_029)
- 蓝色柱: English-only 轨道的 found 条目数（item count）
- 绿色柱: 合并去重后的唯一字段数（field count，单位与蓝柱不同，图例已注明）
- 红色连线/标注: 有 ZH-only 贡献的条目 (+N)

**注意:** 单位差异（item vs field）已在图例与稿件 §2.5/§3.1 中说明；核心增益数字为 ZH-only 条目 +22.8%。

---

## Figure 3: F3_evidence_gain_distribution.png — 增益分布

**用途:** ZH-only 条目增益的分布（Results §3.1）

**内容:**
- X 轴: ZH-only 增益（items/entry）
- 25/29 条目增益 > 0；增益按构造非负（度量定义为"仅中文轨检出的条目数"）

---

## Figure 4: F4_field_level_zh_benefit_heatmap.png — 中文轨独有字段热图

**用途:** 展示哪些字段的证据仅由中文轨检出（Results §3.2）

**内容:**
- 行: 条目，列: 字段类型
- ✓: 该条目在该字段上有仅中文轨检出的证据
- 13/29 条目有至少一个 ZH-only 字段

---

## Supplementary Figure S1: S1_evidence_by_category.png — 分类别证据量

**用途:** 按 ACMG 类别（A–J）对比英文轨 vs 中文轨检出的证据条目数（Results §3.2 引用，补充材料）

**内容:**
- 分组柱状图：每类别两柱（English track / Chinese track）
- 中文轨在类别 B（疾病/表型）、A（变异）贡献最明显

**注意:** 生成需要 per-run pipeline 输出（`PIPELINE_DATA_DIR`，默认指向外部数据项目），不在仓库内。

---

## 生成方式

```bash
cd <repo-root>
./backend/.venv/bin/python benchmark/analysis/generate_gim_architecture.py  # F1
./backend/.venv/bin/python benchmark/analysis/generate_gim_figures.py       # F2-F4, S1
```
