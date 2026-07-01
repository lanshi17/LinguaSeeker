# Stores 全局状态

> Zustand 全局应用状态管理

## 概述

使用 Zustand 管理跨功能模块的全局 UI 状态。仅包含无法归入单一功能模块的切面状态（侧边栏、主题、语言）。功能特定状态由各模块自行管理。

## 文件结构

```
stores/
├── appStore.ts    # 全局应用状态（侧边栏、主题、语言）
└── README.md
```

## Store: `useAppStore`

全局应用状态 store，使用 Zustand `devtools` 中间件。

### 状态字段

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `sidebarCollapsed` | `boolean` | 侧边栏是否折叠 | `false` |
| `locale` | `"en" \| "zh"` | 当前语言 | Cookie → 浏览器语言 → `"en"` |
| `mode` | `"light" \| "dark"` | 主题模式 | Cookie → 系统偏好 → `"light"` |

### Actions

| 方法 | 说明 |
|------|------|
| `toggleSidebar()` | 切换侧边栏折叠状态 |
| `setSidebarCollapsed(collapsed)` | 设置侧边栏折叠状态 |
| `setLocale(lang)` | 设置语言并持久化到 Cookie（1年有效期） |
| `setMode(mode)` | 设置主题并持久化到 Cookie + 更新 `data-theme` 属性 |

### 持久化

- **语言**: `ls_lang` Cookie（1年有效期）
- **主题**: `ls_theme` Cookie（1年有效期）+ `document.documentElement` 的 `data-theme` 属性
- **检测顺序**: Cookie → 浏览器/系统偏好 → 默认值
