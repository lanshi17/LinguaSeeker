# GIM 投稿工作区

**目标期刊:** Genetics in Medicine (GIM), Original Research Article
**投稿分支:** `feature/gim-submission`
**工作树:** `/data/yangzs/Projects/01_ACMG_Lingua-gim`
**创建日期:** 2026-08-09（原 NAR Web Server 工作区，2026-08-13 更名为 GIM）

---

## 文件结构

```text
docs/gim/
├── README.md              # 本文件 - 投稿工作区索引
├── gim_working_file.md    # GIM 投稿工作文件（实验设计、结果口径、进度）
├── manuscript/            # 论文正文
│   ├── outline.md         # 论文大纲（结构速览，随稿同步）
│   ├── draft.md           # Markdown 内容与数据参考稿
│   └── latex/             # LaTeX 投稿版（elsarticle，正文单一真相源）
│       ├── main.tex       # 英文主稿（去 AI 化终稿；main.pdf，19 页）
│       ├── main_zh_translation.md  # 英文主稿的中文直译
│       ├── supplementary.tex  # 补充材料（supplementary.pdf，10 页）
│       └── elsarticle.cls # Elsevier 文档类（vendored）
├── figures/               # 论文插图 Figure 1–4 + Suppl. Fig. S1
│   ├── figure_specs.md    # 各 Figure 规格说明 + 生成脚本对应关系
│   └── (PNG files)
├── supplementary/         # 补充材料（英文；Fig S1、Table S1–S3、Note S1–S6）
│   ├── supplementary.md
│   └── reports/           # 统计报告 committed copy（复现数据源）
├── benchmark/             # Benchmark 方案文档
│   ├── benchmark_plan.md  # 原 NAR 版三层 P/R/F1 评估方案（暂缓）
│   └── preparation_status.md
└── assets/                # 投稿素材
    └── cover_letter.md    # Cover letter 草稿
```

## 当前状态（2026-08-20）

- `manuscript/latex/main.tex` 为 submission-ready 英文终稿，GIM 格式合规：
  - 摘要 ≤200 词；正文低于 4,000 词
  - Display items 5 个（Figure 1–4 + Table 1，≤5）；分类别图移入 Supplementary Figure S1；原文案例分析表为 Supplementary Table S3
  - 图按正文首次引用顺序编号（架构图 = Figure 1）
  - 参考文献 29 条（案例分析含中/韩/俄/土/西/葡/法原文；法文为 2018 会议海报）
  - End matter 按 GIM 要求排序：Data Availability → Acknowledgments → Funding → Author Contributions → Ethics Declaration → COI → AI 写作声明
  - 正文已移除机械化列表、加粗段首标签、模板化贡献/局限性结构和非必要破折号；中文直译见 `main_zh_translation.md`
  - 2026-08-21：原文 Rett/MECP2 案例分析 CLI `added codes 20/31`（11 等位基因，8 语种含日文队列）。终点是相对英文可见层多出的 Stage-0 准则，不要求分类翻转，产品不写 ACMG 码，both-hero = 0
- 统计数字 2026-08-13 经 `benchmark/analysis/gim_statistics.py` 复现，与正文一致
- 报告 JSON 已复制入仓库（`supplementary/reports/`），分析脚本支持回退读取，Data Availability 声明可成立
- 详细进度、结果口径与统计数字见 `gim_working_file.md`

## 投稿检查清单

- [x] 论文正文（结构化摘要 Purpose/Methods/Results/Conclusion，≤200 词）
- [x] Figures 1–4 + Suppl. Fig. S1（生成脚本：`benchmark/analysis/generate_gim_figures.py`、`generate_gim_architecture.py`）
- [x] 补充材料（英文：Fig S1 + Table S1/S2/S3 + Note S1–S6）
- [x] 统计分析可复现（`benchmark/analysis/gim_statistics.py`，报告 committed copy 在 `supplementary/reports/`）
- [x] Data and Code Availability 核对（GitHub `lanshi17/LinguaSeeker` + 分支 `feature/gim-submission` + 报告文件已入库）
- [x] Cover letter 草稿（`assets/cover_letter.md`，占位符待填）
- [x] Ethics Declaration / Author Contributions (CRediT) / Funding 章节框架
- [x] LaTeX 版（elsarticle）：`manuscript/latex/main.tex` + `supplementary.tex`，编译通过、无 overfull
- [ ] 作者列表、单位、通讯方式、CRediT 贡献、基金声明（在 `main.tex` 填写）
- [ ] AI 写作声明工具名确认（或删除该节）
- [ ] 投稿系统上传（Editorial Manager: PDF 上传、图表单独上传、页码）

## 说明

- 原 NAR Web Server Issue 投稿计划暂缓：其三层 P/R/F1 全量评估（fused-75）未执行，方案保留在 `benchmark/benchmark_plan.md` 备后续启用。
