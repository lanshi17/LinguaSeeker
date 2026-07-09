# UI 组件

> 跨功能模块共享的通用 UI 原子组件

## 概述

提供与业务逻辑无关的基础 UI 组件，供各功能模块复用。所有组件使用 CSS 变量实现主题适配，支持亮/暗模式。

## 文件结构

```
ui/
├── Badge.tsx             # 状态标签（基于 Ant Design Tag）
├── ErrorBoundary.tsx     # React 错误边界
├── LanguageSwitcher.tsx  # 语言切换按钮（中/英）
├── LivePulse.tsx         # 实时脉冲指示器（动画圆点）
├── MetricTile.tsx        # 指标卡片（标签 + 数值 + 单位）
├── PageTransition.tsx    # 页面切换动画（AnimatedOutlet）
├── Skeleton.tsx          # 骨架屏加载占位
├── Spinner.tsx           # 旋转加载指示器
├── ThemeToggle.tsx       # 主题切换按钮（亮/暗）
├── UserGuide.tsx         # 新手引导（Ant Design Tour）
└── README.md
```

## 关键组件

### `ErrorBoundary`

React 错误边界，捕获子组件渲染错误。

- **Props**: `children`, `fallback?: ReactNode`, `onError?: (error, info) => void`
- **功能**: 显示错误信息 + "Try again" 按钮重置状态

### `MetricTile`

紧凑的指标展示卡片，用于流水线阶段详情等场景。

- **Props**: `label`, `value`, `unit?`, `tone?` (default/primary/success/warning/error), `icon?`
- **样式**: 等宽数字字体、大写标签

### `LivePulse`

带脉冲动画的圆点指示器，表示进行中状态。

- **Props**: `tone?` (primary/success/warning/error/neutral), `label?`
- **实现**: CSS `ping` 动画 + `role="status"` 无障碍标记

### `UserGuide`

基于 Ant Design `Tour` 的新手引导组件。

- **Props**: `open: boolean`, `onClose: () => void`
- **功能**: Cookie 持久化引导状态（1年有效期），6步引导流程
- **状态工具**: `userGuideState.ts` 导出 `hasSeenGuide()` / `resetGuide()`

### `ThemeToggle`

亮/暗模式切换按钮。

- **实现**: 读取/写入 `appStore.mode`，带 350ms 过渡动画

### `LanguageSwitcher`

中英文切换按钮，显示 "EN"/"中" 标签。

- **实现**: 读取/写入 `appStore.locale`

### `Skeleton`

骨架屏加载占位符。

- **Props**: `variant?` (text/line/circle/block/pill), `width?`, `height?`
- **样式**: `skeleton-shimmer` CSS 动画

### `Spinner`

SVG 旋转加载指示器。

- **Props**: `size?` (sm: 16px / md: 24px / lg: 40px)

### `Badge`

状态标签，基于 Ant Design `Tag`。

- **Props**: `variant?` (default/success/warning/error/info)
- **样式**: 圆角药丸形状

### `AnimatedOutlet`

页面切换动画包装器，使用路由 `pathname` 作为 key 触发重新挂载。
