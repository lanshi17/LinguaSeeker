# Frontend Tests 前端测试

> 基于 Vitest + Testing Library 的组件和工具函数测试

## 概述

使用 Vitest 作为测试运行器，配合 jsdom 环境和 React Testing Library 进行组件测试。测试覆盖各功能模块的组件渲染、hooks 行为和工具函数逻辑。

## 文件结构

```
tests/
├── setup.ts                              # 全局测试设置（jsdom polyfill）
├── audit/
│   ├── EvidenceReviewDrawer.test.tsx      # 证据审阅抽屉测试
│   ├── reviewPatch.test.tsx               # 审阅补丁构建测试
│   └── useAuditEvents.test.tsx            # 审阅事件 hook 测试
├── evidence-db/
│   ├── ActiveEvidenceCard.test.tsx        # 活跃证据卡片测试
│   ├── fieldLabels.test.tsx               # 字段标签测试
│   ├── fieldModel.test.tsx                # 字段质量模型测试
│   ├── LiteratureHeader.test.tsx          # 文献头部测试
│   ├── useEvidenceDbViewPrefs.test.tsx    # 视图偏好 hook 测试
│   └── variantAggregation.test.tsx        # 变异聚合算法测试
├── evidence-search/
│   ├── BilingualComparison.test.tsx       # 双语对比测试
│   ├── evidenceDocument.test.tsx          # 证据文档构建测试
│   ├── EvidenceHighlightText.test.tsx     # 证据高亮文本测试
│   ├── literatureRows.test.ts             # 文献行聚合测试
│   └── useEvidenceSearch.test.tsx         # 搜索 hook 测试
├── layout/
│   └── Sidebar.test.tsx                   # 侧边栏测试
├── features/
│   └── chat/                              # 对话功能测试
├── config/
│   └── layeredConfig.test.ts              # 分层配置测试
└── README.md
```

## 测试配置

### Vitest 配置 (`vitest.config.ts`)

- **环境**: jsdom
- **测试文件**: `tests/**/*.test.tsx`
- **设置文件**: `tests/setup.ts`
- **路径别名**: `@/` → `src/`
- **插件**: `@vitejs/plugin-react`

### 全局设置 (`setup.ts`)

提供 jsdom 缺失的浏览器 API polyfill：
- `window.matchMedia` — `appStore.ts` 在导入时调用，jsdom 未实现

## 运行测试

```bash
bun test              # 运行所有测试
bun test:node         # 使用 Node.js 原生测试运行器（编译后）
```

## 测试覆盖

| 模块 | 测试内容 |
|------|----------|
| audit | 审阅抽屉渲染、补丁构建逻辑、事件 hook |
| evidence-db | 字段标签、质量模型、变异聚合、视图偏好 |
| evidence-search | 双语对比、文档构建、高亮文本、文献行、搜索 hook |
| layout | 侧边栏渲染 |
| config | 分层配置逻辑 |

## 编写规范

- 测试文件与源文件同名，后缀 `.test.tsx` / `.test.ts`
- 使用 `@testing-library/react` 的 `render` + `screen` 进行组件测试
- 使用 `vi.fn()` / `vi.mock()` 进行 mock
- 测试行为而非实现细节
