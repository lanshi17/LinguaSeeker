# Lib 共享库

> 跨功能模块共享的基础设施：API 客户端、类型、hooks、常量和工具

## 概述

`lib/` 包含与业务逻辑无关的共享基础设施，供所有功能模块使用。包括 Axios API 客户端、标准化错误处理、国际化系统、共享类型定义、通用 hooks 和格式化工具。

## 文件结构

```
lib/
├── api/
│   ├── client.ts             # Axios 实例（baseURL、API Key、错误拦截器）
│   └── error.ts              # ApiError 类 + 错误标准化/提取工具
├── constants/
│   ├── evidenceFields.ts     # ACMG 证据字段目录（166 字段，10 类别 A–K）
│   └── statusVariant.ts      # 审阅状态 → Badge variant 映射
├── hooks/
│   ├── usePagination.ts      # 分页逻辑 hook（页码窗口、导航）
│   └── useElapsedSeconds.ts  # 实时计时 hook（250ms 更新）
├── i18n/
│   ├── index.ts              # useI18n hook + 翻译系统
│   └── locales/
│       ├── en.ts             # 英文翻译
│       └── zh.ts             # 中文翻译
├── types/
│   ├── common.ts             # 共享类型（ProcessingStatus、PhaseId）
│   └── evidence.ts           # 证据类型（ReviewStatusValue、DeltaEntry、ReviewAuditEventResponse）
├── utils/
│   └── format.ts             # 格式化工具（时长、相对时间、时间戳）
└── README.md
```

## 关键模块

### API 客户端 (`api/`)

#### `client.ts`

共享 Axios 实例，所有功能服务层使用。

- **Base URL**: `VITE_API_BASE_URL` 或 `${BASE_URL}api/v1`（跟随 SPA 挂载点）
- **认证**: `X-API-Key` 头（来自 `VITE_API_KEY`）
- **超时**: `VITE_API_TIMEOUT`（默认 30s）
- **错误拦截**: 自动将 AxiosError 标准化为 `ApiError`

#### `error.ts`

- `ApiError` — 标准化错误类（`status`、`backendMessage`）
- `normalizeError(error)` — AxiosError → ApiError 转换
- `extractErrorMessage(err, fallback)` — 从任意错误提取可读消息

### 国际化 (`i18n/`)

轻量级 i18n 方案，基于 Zustand `appStore.locale`。

- `useI18n()` → `{ t, locale }`
- 支持 `{param}` 插值：`t("key", { name: "value" })`
- 回退机制：当前语言缺失时回退到英文，再回退到 key 本身
- 语言检测：Cookie → 浏览器语言 → 默认英文

### 类型 (`types/`)

#### `common.ts`
- `ProcessingStatus` — 处理状态：`pending` / `running` / `completed` / `failed` / `skipped`
- `PhaseId` — 阶段标识：`phase_1` / `phase_2` / `phase_3`

#### `evidence.ts`
- `ReviewStatusValue` — 审阅状态：`provisional` / `approved` / `corrected` / `rejected`
- `DeltaEntry` — 字段变更差异
- `ReviewAuditEventResponse` — 审阅事件响应

### Hooks (`hooks/`)

#### `usePagination({ page, totalPages, onPageChange })`

分页逻辑 hook，返回页码窗口（最多 7 页 + 省略号）和导航函数。

#### `useElapsedSeconds(start)`

实时计时 hook，从 `start` ISO 时间戳开始计时，每 250ms 更新。用于流水线运行时长显示。

### 常量 (`constants/`)

#### `evidenceFields.ts`

ACMG/ClinGen 证据字段目录，166 个字段覆盖 10 个类别（A–K）：
- A: Variant Information
- B: Case/Phenotype
- C: Segregation/Family
- D: Population/Frequency
- E: Computational/Prediction
- F: Functional Evidence
- G: Case-Control
- H: Contradiction/Exclusion
- I: Gene Function/Experimental
- J: Authority/Time Validity
- K: Gene-Disease Validity

提供 `FIELD_SPEC_BY_ID` 快速查找和 `FIELD_CATEGORIES` 类别元数据。

#### `statusVariant.ts`

审阅状态到 Badge variant 的映射：provisional → default、approved → success、corrected → warning、rejected → error。

### 工具 (`utils/`)

#### `format.ts`
- `formatDuration(seconds)` — 智能时长格式化（ms/s/m/h）
- `formatRelative(iso)` — 相对时间（just now / Xs ago / Xm ago）
- `formatTimestamp(iso)` — 完整时间戳
