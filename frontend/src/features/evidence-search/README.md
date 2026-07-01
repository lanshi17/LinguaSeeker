# Evidence Search 证据搜索功能

> 多维度证据搜索、双语对比查看和证据修正审阅

## 概述

Evidence Search 模块提供 ACMG/ClinGen 证据的全文搜索、结构化展示和审阅修正功能。支持按基因、变异、疾病、PMID/DOI 多维筛选，提供双语对比视图（原文/翻译）、证据高亮、文献概览、导出报告和文档标注。

## 文件结构

```
evidence-search/
├── index.ts                              # 模块导出
├── evidence-search.css                   # 样式
├── components/
│   ├── EvidenceSearchView.tsx            # 搜索页面主视图
│   ├── EvidenceSearchForm.tsx            # 搜索表单
│   ├── EvidenceResultsTable.tsx          # 搜索结果表格
│   ├── EvidenceHighlightText.tsx         # 证据高亮文本
│   ├── EvidenceDetailView.tsx            # 证据详情视图
│   ├── BilingualComparison.tsx           # 双语对比视图
│   ├── BilingualCompareView.tsx          # 双语对比完整视图
│   ├── LiteratureOverview.tsx            # 文献概览面板
│   ├── MarkdownDocumentViewer.tsx        # Markdown 文档查看器
│   ├── EvidenceAuditHistory.tsx          # 证据审阅历史
│   ├── EvidenceCorrectionForm.tsx        # 证据修正表单
│   ├── ExportReportDrawer.tsx            # 报告导出抽屉
│   ├── FieldReviewPopover.tsx            # 字段审阅弹窗
│   ├── evidenceTableColumns.tsx          # 表格列定义
│   ├── annotationLayer.tsx               # 文本标注层
│   └── annotationPopover.tsx             # 标注弹窗
├── hooks/
│   ├── useEvidenceSearch.ts             # 搜索 hook（分页、筛选）
│   └── useEvidenceGroupDetail.ts        # 证据组详情 hook
├── services/
│   ├── evidenceSearch.ts                # 搜索 + 详情 API
│   ├── evidenceCorrection.ts            # 证据修正 + 审阅事件 API
│   └── annotations.ts                   # 文档标注 CRUD API
├── types/
│   ├── evidenceSearch.ts                # 搜索/结果/详情类型
│   └── annotations.ts                   # 标注类型定义
├── utils/
│   ├── evidenceDocument.ts              # 证据文档构建 + 高亮映射
│   ├── literatureRows.ts                # 文献行聚合
│   ├── evidenceReport.ts                # 报告导出逻辑
│   ├── categoryStyles.ts                # 分类样式映射
│   └── evidenceDocument.ts              # 证据文档构建（含多语言别名匹配）
└── README.md
```

## 关键组件

### `EvidenceSearchView`

搜索页面主视图，组合搜索表单和结果表格。

### `EvidenceSearchForm`

搜索表单，支持基因、变异、疾病、PMID、DOI 多维筛选。

### `EvidenceResultsTable`

搜索结果分页表格，展示证据摘要信息。

### `BilingualComparison` / `BilingualCompareView`

双语证据对比视图，支持原文/翻译并排显示、证据高亮和同步滚动。

### `LiteratureOverview`

文献概览面板，展示按来源文档分组的证据摘要。

### `ExportReportDrawer`

报告导出抽屉，支持生成结构化报告。

### `EvidenceCorrectionForm`

证据修正表单，支持编辑字段值、选择审阅状态（批准/修正/拒绝）并提交变更原因。

### `annotationLayer` / `FieldReviewPopover`

文档文本标注功能，支持在原文/翻译段落上创建、编辑、删除高亮标注。

## Hooks

### `useEvidenceSearch()`

搜索数据管理 hook。

- 维护筛选状态（基因、变异、疾病、PMID、DOI、分页）
- 使用 `keepPreviousData` 避免翻页闪烁
- **返回**: `{ results, total, page, pageSize, filters, updateFilter, applyFilters, clearFilters, setPage }`

### `useEvidenceGroupDetail(groupId?, sourceDocumentId?)`

证据组详情查询 hook。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/evidence/search` | 搜索证据 |
| GET | `/evidence/groups/detail` | 证据组详情 |
| PATCH | `/evidence/{id}` | 修正证据 |
| GET | `/delta-audit/` | 审阅事件列表 |
| GET | `/documents/{id}/annotations` | 列出标注 |
| POST | `/documents/{id}/annotations` | 创建标注 |
| PATCH | `/documents/{id}/annotations/{id}` | 更新标注 |
| DELETE | `/documents/{id}/annotations/{id}` | 删除标注 |

## 核心工具

### `buildEvidenceDocument`

将证据组详情构建为可渲染的文档结构，支持：
- 原文/翻译双轨道
- 按类别（A–J）着色高亮
- 多语言别名匹配（支持非英文源文本中的证据值定位）
- HGVS 表示法的灵活空格匹配

### `buildLiteratureRows`

将搜索结果按来源文档聚合为文献行，计算基因、变异、疾病、分类列表和审阅状态。

### `ANNOTATION_COLORS`

标注颜色调色板：琥珀、蓝、绿、粉、紫、橙（6色）。
