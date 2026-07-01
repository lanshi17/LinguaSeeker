# Lingua Seeker Frontend

> 基于 React + TypeScript 的医学遗传学文献自动化平台前端

## 概述

Lingua Seeker 前端是一个单页应用（SPA），用于驱动 ACMG/ClinGen 证据提取、文献管理和审阅工作流。采用 Vite 构建，支持子路径挂载（如 `/linguaseeker`），通过反向代理与后端 API 通信。

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript 5 |
| 构建 | Vite 6 |
| UI 库 | Ant Design 6 + `@ant-design/x` (聊天组件) |
| 状态管理 | Zustand 4 |
| 数据获取 | React Query (TanStack Query 5) + Axios |
| 路由 | React Router 7 |
| 图标 | Lucide React |
| Markdown | react-markdown + remark-gfm + remark-math + rehype-katex |
| 测试 | Vitest + Testing Library + jsdom |
| 包管理 | Bun |

## 项目结构

```
src/
├── App.tsx                 # 路由定义（懒加载所有页面）
├── main.tsx                # 应用入口，挂载 Provider 层
├── providers.tsx           # QueryProvider + ThemeProvider
├── theme.ts                # Ant Design 主题配置（亮/暗模式）
├── globals.css             # 全局样式、CSS 变量、动画
├── components/
│   ├── layout/             # 布局组件（DashboardLayout、Sidebar）
│   └── ui/                 # 通用 UI 组件（ErrorBoundary、Spinner 等）
├── features/
│   ├── audit/              # 审阅审计功能
│   ├── chat/               # AI 对话功能
│   ├── evidence-db/        # 变异数据库浏览
│   ├── evidence-search/    # 证据搜索与双语对比
│   └── pipeline/           # 处理流水线管理
├── lib/
│   ├── api/                # Axios 客户端 + 错误处理
│   ├── constants/          # 证据字段目录、状态映射
│   ├── hooks/              # 共享 hooks（分页、计时）
│   ├── i18n/               # 国际化（中/英双语）
│   ├── types/              # 共享类型定义
│   └── utils/              # 格式化工具
├── stores/
│   └── appStore.ts         # 全局应用状态（侧边栏、主题、语言）
└── pages/                  # 路由页面组件
```

## 路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/chat` | ChatPage | 独立对话 |
| `/chat/:sessionId` | ChatSessionPage | 特定会话 |
| `/evidence` | EvidencePage | 证据搜索 |
| `/evidence/detail` | EvidenceDetailPage | 证据详情 |
| `/evidence-db` | EvidenceDbPage | 变异数据库索引 |
| `/evidence-db/:variantSlug` | EvidenceDbPage | 特定变异详情 |
| `/pipeline` | PipelinePage | 流水线管理 |
| `/pipeline/:runId` | PipelineRunPage | 运行详情 |
| `/audit` | AuditPage | 审阅审计 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | API 基础 URL | `${BASE_URL}api/v1` |
| `VITE_API_KEY` | API 密钥（`X-API-Key` 头） | — |
| `VITE_API_TIMEOUT` | 请求超时（ms） | `30000` |
| `VITE_BASE_PATH` | SPA 挂载路径 | `/` |
| `VITE_APP_VERSION` | 应用版本号 | `package.json` version |

## 开发命令

```bash
bun dev          # 启动开发服务器（端口 3000）
bun build        # TypeScript 检查 + 生产构建
bun test         # 运行 Vitest 测试
bun lint         # ESLint 检查
bun type-check   # TypeScript 类型检查
```

## 设计主题

- **主色**: Teal (#0891B2)
- **成功色**: Green (#22C55E)
- **字体**: Figtree / Noto Sans（正文）、JetBrains Mono（代码）
- **圆角**: 8px
- 支持亮/暗模式切换，通过 CSS 变量和 Ant Design ConfigProvider 实现
