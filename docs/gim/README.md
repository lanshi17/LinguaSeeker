# NAR Web Server Issue 投稿工作区

**目标期刊:** Nucleic Acids Research - Web Server Issue
**投稿分支:** `feature/nar-web-server-submission`
**工作树:** `/data/yangzs/Projects/01_ACMG_Lingua-nar-web-server`
**创建日期:** 2026-08-09

---

## 文件结构

```text
docs/nar-web-server/
├── README.md              # 本文件 - 投稿工作区索引
├── manuscript/            # 论文正文
│   ├── outline.md         # 论文大纲（结构 + 各节要点）
│   └── draft.md           # 论文草稿（完整正文）
├── figures/               # 论文插图
│   ├── figure_specs.md    # 各 Figure 的规格说明 + 绘制指令
│   └── (PNG/SVG files)    # 实际图片文件
├── supplementary/         # 补充材料
│   └── supplementary.md   # 补充表格、方法细节、案例展示
├── benchmark/             # Benchmark 数据与脚本
│   └── benchmark_plan.md  # 评估方案、数据集说明、指标定义
└── assets/                # 投稿相关素材
    └── (cover letter 等)
```

## 投稿要求摘要

- **论文类型:** Web Server Issue article（非 standard research paper）
- **篇幅:** 正文 ~4-6 页（NAR Web Server 格式）
- **必要条件:** Web server 必须免费公开可用
- **结构:** Abstract → Introduction → Materials and Methods → Web Server Usage → Results → Discussion
- **图表:** 通常 3-5 个 Figure
- **补充材料:** 可附 Supplementary Data

## 关键时间节点

| 节点 | 目标日期 | 状态 |
|------|---------|------|
| 论文大纲完成 | TBD | pending |
| Benchmark 方案定稿 | TBD | pending |
| 论文初稿完成 | TBD | pending |
| Figures 制作完成 | TBD | pending |
| 内部审阅完成 | TBD | pending |
| 投稿 | TBD | pending |

## 投稿检查清单

- [ ] Web server 公开可访问（免费、无需注册即可体验核心功能）
- [ ] 论文正文（按 NAR Web Server 格式）
- [ ] 3-5 个 Figure（系统架构图、流程图、截图、benchmark 结果）
- [ ] 补充材料
- [ ] Cover letter
- [ ] 作者列表与贡献声明
- [ ] 数据/代码可用性声明（GitHub + DOI）
- [ ] Benchmark 数据（至少 30 篇文献，覆盖中英文）

## 命名与提交规范

- 论文使用英文撰写
- 图表分辨率 ≥ 300 dpi
- 引用格式: NAR 要求的 Vancouver 风格
- 代码仓库: 提交时打 release tag 并获取 Zenodo DOI
