# Evidence DB 变异数据库功能

> 以变异为中心的证据浏览，支持双语文献对比和质量评估

## 概述

Evidence DB 模块将扁平的证据搜索结果聚合为变异维度的索引视图，提供两级浏览体验：L1 变异索引（按基因/变异/疾病聚合）和 L2 变异详情（含文献列表和双语证据视图）。支持致病性排序、审阅进度追踪和客户端筛选分页。

## 文件结构

```
evidence-db/
├── index.ts                          # 模块导出
├── evidence-db.css                   # 样式
├── components/
│   ├── VariantIndexView.tsx          # L1: 变异索引表格
│   ├── VariantDetailView.tsx         # L2: 变异详情视图
│   ├── VariantIndexSkeleton.tsx      # 索引骨架屏
│   ├── VariantDetailSkeleton.tsx     # 详情骨架屏
│   ├── BilingualEvidenceView.tsx     # 双语证据对比视图
│   ├── BilingualEvidenceSkeleton.tsx # 双语视图骨架屏
│   ├── BilingualSidebar.tsx          # 双语视图侧边栏
│   ├── SidebarControls.tsx           # 侧边栏控制面板
│   ├── LiteratureHeader.tsx          # 文献头部信息
│   ├── DocumentReader.tsx            # 文档阅读器
│   ├── StructuredBlockRenderer.tsx   # 结构化内容块渲染
│   ├── HighlightedText.tsx           # 高亮文本组件
│   └── bevStyles.ts                  # 双语视图样式常量
├── hooks/
│   ├── useVariantIndex.ts           # 变异索引数据 hook（客户端聚合）
│   ├── useVariantDetail.ts          # 变异详情数据 hook
│   └── useEvidenceDbViewPrefs.ts    # 视图偏好持久化 hook
├── services/
│   └── variantDb.ts                 # API 服务层（复用 evidence-search）
├── types/
│   └── variantDb.ts                 # 变异相关类型定义
├── utils/
│   ├── variantAggregation.ts        # 证据 → 变异聚合算法
│   ├── fieldModel.ts                # 字段质量模型（审阅进度、覆盖率）
│   ├── pathogenicity.ts             # 致病性分类与排序
│   ├── variantDetailHelpers.ts      # 详情页数据构建
│   ├── fieldLabels.ts               # 字段标签映射
│   └── scrollSync.ts               # 双语面板同步滚动
└── README.md
```

## 关键组件

### `VariantIndexView`

L1 变异索引页面。展示所有变异的聚合列表，支持：
- 搜索/筛选（基因、变异、疾病）
- 致病性排序
- 审阅进度徽章
- 分页浏览

### `VariantDetailView`

L2 变异详情页面。展示单个变异的所有证据：
- 文献列表（按来源文档分组）
- 双语证据对比（原文/翻译）
- 字段覆盖率和质量指标

### `BilingualEvidenceView`

双语文档对比视图，支持：
- 原文/翻译并排显示
- 证据高亮（按类别着色）
- 同步滚动
- 文本标注（annotations）

## Hooks

### `useVariantIndex()`

变异索引数据管理。

- 拉取全量证据（page_size=1000），客户端聚合为变异维度
- 支持搜索、筛选、排序、分页
- **返回**: `{ entries, total, filters, updateFilter, setPage, clearFilters }`

### `useVariantDetail(variantSlug, seededEntry?)`

变异详情数据管理。

- 解析 variantSlug 获取证据行
- 并行查询所有关联的证据组详情
- 构建文献引用列表和质量摘要
- **返回**: `{ detail, isLoading, refetch }`

### `useEvidenceDbViewPrefs()`

视图偏好持久化（localStorage），控制显示/隐藏列（更新时间、分类、审阅进度）。

## 核心工具

### `aggregateVariants`

将扁平的 `EvidenceSearchResult[]` 按 `gene:variant:disease` 复合键聚合为 `VariantIndexEntry[]`。计算证据组数、文献数、平均置信度、分类分布和审阅进度。

### `classifyLevel` / `severityRank`

致病性分类映射：`pathogenic` > `likely_pathogenic` > `uncertain` > `likely_benign` > `benign`。提供颜色和标签。

### `computeVariantQuality` / `computeLiteratureQuality`

质量评估：审阅进度（已审/待审比例）、字段覆盖率、冲突计数、全文/翻译可用性。

### `scrollSync`

双语面板同步滚动：使用滚动比例（0–1）而非绝对像素，通过 guard ref 防止反馈循环。
