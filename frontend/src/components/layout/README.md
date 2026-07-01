# Layout 组件

> 应用整体布局框架，包含侧边栏导航、页面头部和响应式布局

## 概述

提供 Lingua Seeker 的应用外壳布局。`DashboardLayout` 是顶层布局组件，包含桌面端/移动端侧边栏、顶部工具栏和内容区域。支持响应式断点（768px）自动切换桌面/移动端布局，以及打印模式下的样式覆盖。

## 文件结构

```
layout/
├── DashboardLayout.tsx   # 主布局组件（侧边栏 + 内容区 + 工具栏）
├── Sidebar.tsx           # 侧边栏导航（品牌、菜单、设置）
├── PageHeader.tsx         # 页面标题栏（标题 + 描述 + 操作按钮）
├── layout.css            # 布局样式（响应式断点、打印覆盖）
└── README.md
```

## 关键组件

### `DashboardLayout`

应用主布局，使用 Ant Design `Layout` 组件。

- **Props**: 无（通过 `<Outlet>` 渲染子路由）
- **功能**:
  - 桌面端固定侧边栏（可折叠）
  - 移动端抽屉式侧边栏（覆盖层）
  - 顶部工具栏：折叠按钮、语言切换、主题切换
  - 首次访问自动弹出用户引导（`UserGuide`）
  - 使用 `AnimatedOutlet` 实现页面切换动画
- **状态**: 读取 `appStore` 的 `sidebarCollapsed` 状态

### `Sidebar`

侧边栏导航组件。

- **Props**:
  - `mobile?: boolean` — 是否渲染为移动端覆盖层
  - `onNavigate?: () => void` — 导航回调（用于关闭移动端菜单）
  - `onGuideOpen?: () => void` — 打开用户引导的回调
- **导航项**: Chat、Tasks（流水线）、Evidence DB、Audit
- **功能**: 品牌 Logo（暗模式自动反转）、当前路由高亮、折叠/展开、帮助按钮
- **路径**: `/chat`、`/pipeline`、`/evidence-db`、`/audit`

### `PageHeader`

通用页面标题栏。

- **Props**:
  - `title: string` — 页面标题
  - `description?: ReactNode` — 副标题/描述
  - `actions?: ReactNode` — 右侧操作按钮
  - `className?: string`

## 样式

`layout.css` 定义了：
- 响应式断点：768px 以下隐藏桌面侧边栏，显示移动端按钮
- 打印模式：隐藏导航 chrome，重置布局容器为自然文档流
