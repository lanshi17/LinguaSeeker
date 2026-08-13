# Figure Specifications (GIM)

> 论文插图规格说明。与实际生成的图文件一致（`docs/nar-web-server/figures/`）。
> 生成脚本：`benchmark/analysis/generate_gim_figures.py`（F1–F4）、`benchmark/analysis/generate_gim_architecture.py`（F5）。
> 数据源：`benchmark/data/reports/nar_ablation/multilingual_contribution_report.json` 等。

---

## Figure 1: F1_paired_evidence_comparison.png — 配对证据量对比

**用途:** 逐条目展示英文轨 vs 合并多语输出的证据量差异

**内容:**
- X 轴: 30 个条目 (fused_000–fused_029)
- 蓝色柱: English-only 轨道的 found 条目数（item count）
- 绿色柱: 合并去重后的唯一字段数（field count，单位与蓝柱不同，图例已注明）
- 红色连线/标注: 有 ZH-only 贡献的条目 (+N)

**注意:** 单位差异（item vs field）已在图例与稿件 §2.5/§3.1 中说明；核心增益数字为 ZH-only 条目 +22.8%。

---

## Figure 2: F2_field_level_zh_benefit_heatmap.png — 中文轨独有字段热图

**用途:** 展示哪些字段的证据仅由中文轨检出

**内容:**
- 行: 条目，列: 字段类型
- ✓: 该条目在该字段上有仅中文轨检出的证据
- 13/29 条目有至少一个 ZH-only 字段

---

## Figure 3: F3_evidence_gain_distribution.png — 增益分布

**用途:** ZH-only 条目增益的分布

**内容:**
- X 轴: ZH-only 增益（items/entry）
- 25/29 条目增益 > 0；增益按构造非负（度量定义为"仅中文轨检出的条目数"）

---

## Figure 4: F4_evidence_by_category.png — 分类别证据量

**用途:** 按 ACMG 类别（A–J）对比英文轨 vs 中文轨检出的证据条目数

**内容:**
- 分组柱状图：每类别两柱（English track / Chinese track）
- 中文轨在类别 B（疾病/表型）、A（变异）贡献最明显

---

## Figure 5: F5_architecture.png — 系统架构 + Ablation 设计

**用途:** 展示四阶段流水线及受控 ablation 设计（Methods §2.1 引用）

**内容:**
- 上排: Phase 1 文献获取与数字化 → Phase 2 跨语言双轨提取 → Phase 3 实体标准化 → Phase 4 专家审查
- 下排插框: Mode A (EN-only, 3.57/8 字段) vs Mode B (Dual-track, 3.57/8 字段 + ZH-only +22.8%)，含输出指标列表

**风格:** matplotlib 方块图，白底，与 F1–F4 同色系（蓝/橙/绿/红）
**尺寸:** 11.5 × 5.2 in @ 300 dpi

---

## 生成方式

```bash
cd <repo-root>
./backend/.venv/bin/python benchmark/analysis/generate_gim_figures.py   # F1–F4
./backend/.venv/bin/python benchmark/analysis/generate_gim_architecture.py  # F5
```
