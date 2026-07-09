# Lib 共享库

> 跨功能模块共享的基础设施：API 客户端、类型、hooks、常量和工具

## 概述

`lib/` 包含与业务逻辑无关的共享基础设施，供所有功能模块使用。包括 Axios API 客户端、标准化错误处理、国际化系统、共享类型定义、通用 hooks 和格式化工具。

## 文件结构

```
lib/
├── api/
│   ├── client.ts             # Axios 实例（baseURL、API Key、响应缓存、错误拦截器）
│   ├── responseCache.ts      # Axios adapter 级 GET 响应缓存（内存 + localStorage）
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
- **响应缓存**: 通过 `createResponseCacheAdapter(axios.getAdapter(...))` 包装默认网络 adapter
- **错误拦截**: 自动将 AxiosError 标准化为 `ApiError`

#### `responseCache.ts`

`createResponseCacheAdapter(networkAdapter, options): AxiosAdapter` 为共享 API 客户端提供响应缓存层：

```typescript
export function createResponseCacheAdapter(
  networkAdapter: AxiosAdapter,
  options: ApiResponseCacheOptions = {},
): AxiosAdapter
```

数据流：

```text
React Query memory cache
  -> apiClient Axios adapter
    -> browser localStorage response cache
    -> in-memory response cache
    -> backend /api/v1
```

缓存策略：

- 只缓存成功的 `GET` / `HEAD` JSON 或 text 响应。
- 默认 TTL 为 5 分钟，最多保留 80 条，每条最大 512 KiB。
- 缓存 key 由 HTTP method、baseURL、URL 和稳定序列化后的 query params 组成。
- `PATCH` / `POST` / `DELETE` 等写操作成功后清空内存和 `localStorage` 响应缓存。
- `pipeline`、`chat`、`delta-audit` 和 `annotations` 路径默认跳过缓存，避免轮询状态、聊天流和审阅记录读到旧数据。
- 请求头包含 `Cache-Control: no-store` 时跳过缓存。

三级缓存含义：

| 层级 | 实现 | 生命周期 | 作用 |
|------|------|----------|------|
| 浏览器本地 | `localStorage` | 页面刷新后保留，受 TTL 限制 | 复用后端已返回的稳定响应 |
| 前端运行时 | React Query + adapter 内存 Map | 当前页面会话 | 避免同页面重复解析和重复请求 |
| 后端 | 后端 Redis / PostgreSQL 等缓存 | 服务端配置决定 | 当前端缓存 miss 时继续复用服务端缓存 |

测试：

```bash
cd frontend
bunx vitest run tests/api/responseCache.test.tsx
```

覆盖内容包括浏览器本地命中、TTL 过期刷新、写操作失效，以及实时路径绕过缓存。

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
