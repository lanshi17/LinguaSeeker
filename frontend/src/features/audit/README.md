# Audit 审阅审计功能

> 证据审阅事件的查询、展示和批量审阅操作

## 概述

Audit 模块提供证据审阅审计功能，包括：查看审阅事件历史、筛选特定证据/文档的审阅记录、批量审阅证据（批准/修正/拒绝）。审阅事件每 10 秒自动轮询更新。

## 文件结构

```
audit/
├── index.ts                          # 模块导出
├── components/
│   ├── AuditView.tsx                 # 审阅页面主视图
│   ├── AuditEventTable.tsx           # 审阅事件列表表格
│   ├── AuditEventDetailDrawer.tsx    # 事件详情抽屉
│   └── EvidenceReviewDrawer.tsx      # 证据审阅操作抽屉（批量审阅）
├── hooks/
│   └── useAuditEvents.ts            # 审阅事件查询 hook（10s 轮询）
├── services/
│   └── audit.ts                      # API 服务层
├── types/
│   └── audit.ts                      # 类型定义
├── utils/
│   └── reviewPatch.ts               # 审阅补丁构建工具
└── README.md
```

## 关键组件

### `AuditView`

审阅审计页面主视图，组合 `AuditEventTable` 展示审阅事件列表。

### `AuditEventTable`

审阅事件列表表格，展示事件 ID、证据 ID、审阅人、状态变更、变更原因、时间等字段。

### `AuditEventDetailDrawer`

单个审阅事件的详情抽屉，展示字段级别的变更差异（`DeltaEntry`）。

### `EvidenceReviewDrawer`

证据批量审阅操作抽屉。

- 支持三种操作：批准（approved）、修正（corrected）、拒绝（rejected）
- 可编辑证据字段值并附加变更原因
- 使用 `buildReviewPatchOperations` 构建批量补丁请求

## Hooks

### `useAuditEvents(query?)`

查询审阅事件，支持按 `canonical_evidence_id`、`source_document_id`、`reviewer_id` 筛选。

- **轮询**: 每 10 秒自动刷新
- **返回**: `{ data, isLoading, error }`

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/delta-audit/` | 查询审阅事件列表 |

## 类型

- `AuditEventQuery` — 查询参数
- `DeltaEntry` — 字段变更差异（`{ field, old_value, new_value }`）
- `ReviewStatusValue` — 审阅状态：`provisional` / `approved` / `corrected` / `rejected`
- `ReviewAuditEventResponse` — 审阅事件响应

## 工具函数

### `buildReviewPatchOperations`

根据编辑的字段值和目标状态，构建批量审阅补丁操作列表。自动映射字段 ID 到后端字段名（如 `A.gene_symbol` → `gene`）。
