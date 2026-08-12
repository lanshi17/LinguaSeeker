# Figure Specifications

> 论文插图规格说明。每张图包含：用途、内容描述、绘制工具、尺寸/分辨率要求。

---

## Figure 1: System Architecture

**用途:** 展示 Lingua Seeker 的四阶段流水线与技术栈分层架构

**内容:**
- 上层：用户交互层（Web UI: Chat / Evidence Workbench / Knowledge Base）
- 中层：四阶段流水线（Phase 1-4），每阶段标注核心功能
  - Phase 1: Literature Acquisition (15+ sources, Rust I/O, MinerU parsing)
  - Phase 2: Cross-Lingual Dual-Track Extraction (Translation + Native + Translated extraction)
  - Phase 3: Entity Standardization (HGNC, OMIM, HPO, ClinVar + vector similarity)
  - Phase 4: Expert Review (Evidence cards, Delta audit, Export)
- 下层：基础设施层（PostgreSQL, Redis, LLM Services, Rust Extensions）
- 箭头：数据流向（文献输入 -> 结构化证据 -> 标准化 -> ACMG 报告）

**风格:** 简洁矢量图，NAR 风格（白底，蓝色系主色调，灰线分隔）
**工具:** draw.io / BioRender / Figma
**尺寸:** 双栏宽度 (~180mm)，高度 ~120mm
**分辨率:** 300 dpi（矢量优先）

---

## Figure 2: Cross-Lingual Dual-Track Extraction

**用途:** 详细展示双轨证据提取机制，这是论文核心创新点

**内容:**
```
Input Document (非英文)
    │
    ├─→ Language Detection
    │       │
    │       ▼
    │   Multi-Stage Translation
    │   (Terminology → Structure → Draft → Review)
    │       │
    │       ▼
    │   Translated Document (English)
    │
    ├──────────────────────────┐
    │                          │
    ▼                          ▼
Native Track              Translated Track
(原文证据提取)             (译文证据提取)
    │                          │
    ▼                          ▼
Native Evidence           Translated Evidence
    │                          │
    └─────────┬────────────────┘
              ▼
    Evidence Grouping + Source Grounding
    (每条证据回溯到原文位置)
              │
              ▼
    Quality Review + Evidence Chain
              │
              ▼
    Bilingual Evidence Output
```

- 右侧标注每步使用的 LLM 角色（Fast LLM / Reasoning LLM）
- 底部标注溯源机制：每条证据 -> 原文 page + span + translated span

**风格:** 流程图，配色与 Figure 1 一致
**工具:** draw.io / Mermaid 导出
**尺寸:** 双栏宽度，高度 ~100mm
**分辨率:** 300 dpi

---

## Figure 3: Web Server Interface

**用途:** 展示实际 web server 的使用界面

**内容（3-panel 截图）:**
- **Panel A:** Chat 入口 - 用户输入 PMID/DOI，SSE 实时进度反馈
- **Panel B:** Evidence Workbench - 左侧原文 Markdown + 右侧证据卡片，高亮溯源
- **Panel C:** Evidence Database - 证据检索结果，按 ACMG 证据维度分组

**风格:** 浏览器截图，裁剪掉地址栏，加 Panel 标注 (A/B/C)
**工具:** 浏览器截图 + 图像编辑器加标注
**尺寸:** 双栏宽度，高度 ~150mm
**分辨率:** 300 dpi
**注意:** 隐藏敏感数据（患者信息等），使用示例数据

---

## Figure 4: Benchmark Results

**用途:** 定量展示系统性能

**内容（2-panel）:**
- **Panel A:** 分字段 P/R/F1 分组柱状图
  - X 轴: 字段 (Gene, Disease, Variant, Inheritance, Classification)
  - Y 轴: Score (0-1)
  - 每字段 3 根柱子: Precision (蓝), Recall (橙), F1 (绿)
  - 数值标注在柱顶
- **Panel B:** 跨语言对比
  - X 轴: 字段或总体
  - Y 轴: F1 Score
  - 3 组: English-only, Chinese-only, Dual-track
  - 星号标注显著性 (* p<0.05, ** p<0.01)

**风格:** matplotlib / seaborn，白底，error bar
**工具:** Python matplotlib
**尺寸:** 双栏宽度，高度 ~100mm
**分辨率:** 300 dpi

---

## Figure 5 (optional): Case Study

**用途:** 用一个完整案例展示端到端流程

**内容:**
- 选取一篇中文遗传学文献
- 展示：文献输入 -> 翻译结果 -> 提取的证据卡片 -> 标准化结果 -> ACMG 证据矩阵
- 4-panel 布局，每 panel 一个阶段

**风格:** 截图 + 标注
**工具:** 截图 + 图像编辑器
**尺寸:** 单栏宽度 (~85mm) x 4 panel，或双栏宽度 2x2 布局
**分辨率:** 300 dpi
