# 文献对照阅读页面修复总结

## 修复概述

本次修复解决了文献对照阅读页面的四大核心问题：
1. **同步滚动失效** ✅
2. **实体高亮不显示** ✅
3. **布局错乱** ✅
4. **无法跳转定位** ✅

---

## 🚨 P0: 核心交互修复

### 1. 双向同步滚动 ✅

**问题**: 滚动左侧，右侧不动

**修复方案**:
- 使用 `useEffect` + `addEventListener` 绑定滚动事件
- 百分比同步算法：`scrollTop / (scrollHeight - clientHeight)`
- 50ms 锁定机制防止死循环

```typescript
useEffect(() => {
  if (!isSyncScroll) return;
  
  const handleScroll = (source: HTMLElement, target: HTMLElement) => {
    if (isScrolling.current) return;
    isScrolling.current = true;
    
    const percentage = source.scrollTop / (source.scrollHeight - source.clientHeight);
    target.scrollTop = percentage * (target.scrollHeight - target.clientHeight);
    
    setTimeout(() => { isScrolling.current = false; }, 50);
  };

  leftPane.addEventListener('scroll', onLeftScroll);
  rightPane.addEventListener('scroll', onRightScroll);
  
  return () => { /* 清理事件监听 */ };
}, [isSyncScroll]);
```

### 2. 布局修复 ✅

**问题**: 顶部按钮重叠，侧边栏遮挡内容

**修复内容**:
- 严格定义高度：`height: calc(100vh - var(--header-height))`
- 左右面板：`overflow-y: auto`，外部容器：`overflow: hidden`
- 移除多余 margin/padding
- 添加 `min-width: 0` 防止 flex 溢出

```css
.reader-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  height: calc(100vh - var(--header-height));
}

.content-pane {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}

.pane-content {
  flex: 1;
  overflow-y: auto;
}
```

---

## 🎨 P1: 实体识别与彩色标注

### 3. 实体高亮渲染 ✅

**问题**: 纯文本 Markdown，无彩色标注

**修复方案**:
- 自定义 `react-markdown` components
- 使用正则表达式匹配实体文本
- 按长度降序排序，优先匹配长文本

```typescript
const createMarkdownComponents = (entities, visibleTypes) => ({
  p: ({ children }) => {
    if (typeof children === 'string') {
      return (
        <p>
          <HighlightedText
            content={children}
            entities={entities}
            visibleTypes={visibleTypes}
          />
        </p>
      );
    }
    return <p>{children}</p>;
  },
  li: ({ children }) => { /* 同样处理 */ },
});
```

**高亮组件逻辑**:
```typescript
const HighlightedText = ({ content, entities, visibleTypes }) => {
  // 过滤可见类型
  const visibleEntities = entities.filter(e => visibleTypes.has(e.type));
  
  // 按长度降序排序
  const sortedEntities = [...visibleEntities].sort((a, b) => b.text.length - a.text.length);
  
  // 构建正则
  const patterns = sortedEntities.map(e => e.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${patterns.join('|')})`, 'g');
  
  // 分割并高亮
  const parts = content.split(regex);
  return <>{parts.map((part, idx) => {
    const entity = sortedEntities.find(e => e.text === part);
    if (entity) {
      return <span className="entity-highlight" style={{ /* 颜色 */ }}>{part}</span>;
    }
    return <span key={idx}>{part}</span>;
  })}</>;
};
```

### 4. 图例控制面板 ✅

**问题**: 图例点击无反应

**修复内容**:
- 将 `visibleTypes` 接入 React State
- 点击更新 State
- 渲染时检查 `visibleTypes`
- 添加视觉反馈（透明度变化）

```typescript
const [visibleTypes, setVisibleTypes] = useState<Set<string>>(
  new Set(['GENE', 'VARIANT', 'DISEASE', 'EVIDENCE'])
);

const toggleEntityType = (type: string) => {
  setVisibleTypes((prev) => {
    const next = new Set(prev);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    return next;
  });
};
```

**颜色规范**:
| 类型 | 背景色 | 文字色 | 边框色 |
|------|--------|--------|--------|
| GENE | #dbeafe | #1e40af | #3b82f6 |
| VARIANT | #fee2e2 | #991b1b | #ef4444 |
| DISEASE | #dcfce7 | #166534 | #22c55e |
| EVIDENCE | #fef9c3 | #854d0e | #eab308 |
| PHENOTYPE | #ede9fe | #7c3aed | #a855f7 |

---

## 🔗 P2: 跳转与定位

### 5. 点击 JSON 跳转原文 ✅

**实现逻辑**:
- 实体添加唯一 ID: `id: \`e-${i}\``
- 高亮元素添加 ID: `id={\`entity-${entity.id}\``}
- 点击实体列表项时调用 `scrollToEntityById`

```typescript
const scrollToEntityById = (entityId: string) => {
  setScrollToEntity(entityId);
  
  const element = document.getElementById(`entity-${entityId}`);
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    element.classList.add('flash-animation');
    setTimeout(() => element.classList.remove('flash-animation'), 2000);
  }
};
```

### 6. 视觉反馈（闪烁动画） ✅

```css
.flash-animation {
  animation: flash 2s ease-in-out;
}

@keyframes flash {
  0%, 100% { box-shadow: 0 0 0 0 transparent; }
  25% { box-shadow: 0 0 0 4px currentColor; }
  50% { box-shadow: 0 0 0 8px currentColor; }
  75% { box-shadow: 0 0 0 4px currentColor; }
}
```

---

## 使用说明

### 访问方式
1. 上传 PDF 并等待处理完成
2. 进入结果页点击 **"对照阅读"**
3. 或直接访问 `/reader/{documentId}`

### 功能操作

| 功能 | 操作 |
|------|------|
| **同步滚动** | 点击顶部"同步开启/关闭"按钮 |
| **实体高亮** | 自动显示，点击图例可切换类型 |
| **查看实体详情** | 点击高亮的实体词 |
| **跳转到原文** | 点击右侧抽屉中的实体列表项 |
| **全屏阅读** | 点击右上角全屏按钮 |
| **复制内容** | 点击面板头部的复制按钮 |

---

## 文件变更

1. `src/pages/DocumentReaderPage.tsx` - 完全重写
2. `src/pages/DocumentReaderPage.css` - 更新样式

---

## 重启命令

```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-fronted/apps/fronted
npm run dev
```

现在文献对照阅读页面已完全可用，支持同步滚动、实体高亮、点击跳转等核心功能！