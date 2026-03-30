# 空指针异常修复总结

## 问题
```
TypeError: Cannot read properties of undefined (reading 'borderColor')
```

发生在 `DocumentReaderPage.tsx` 第 639 行，根本原因是实体类型在配置对象中找不到对应定义。

## 修复内容

### 1. 防御性编程 - 所有访问 ENTITY_CONFIG 的地方添加默认值

#### 修复 1: HighlightedText 组件 (第 155 行)
```typescript
// 防御性编程：确保类型配置存在
const typeKey = entity.type?.toUpperCase() || 'UNKNOWN';
const config = ENTITY_CONFIG[typeKey] || {
  label: typeKey,
  color: '#6b7280',
  bgColor: '#f3f4f6',
  borderColor: '#9ca3af',
  icon: <Info size={14} />,
};
```

#### 修复 2: 实体详情弹窗 (第 563 行)
```typescript
const typeKey = selectedEntity.type?.toUpperCase() || 'UNKNOWN';
const config = ENTITY_CONFIG[typeKey] || {
  label: typeKey,
  color: '#6b7280',
  bgColor: '#f3f4f6',
  borderColor: '#9ca3af',
  icon: <Info size={14} />,
};
```

#### 修复 3: 实体列表抽屉 (第 639 行)
```typescript
const typeKey = entity.type?.toUpperCase() || 'UNKNOWN';
const config = ENTITY_CONFIG[typeKey] || {
  label: typeKey,
  color: '#6b7280',
  bgColor: '#f3f4f6',
  borderColor: '#9ca3af',
  icon: <Info size={14} />,
};

// 调试：如果类型未配置，打印警告
if (!ENTITY_CONFIG[typeKey]) {
  console.warn(`⚠️ 未找到实体类型的颜色配置: "${entity.type}" (标准化后: "${typeKey}")`, entity);
}
```

### 2. 数据标准化 - 加载时统一转大写

```typescript
// 为实体添加 ID 并标准化类型（转大写）
if (data.evidence_annotations) {
  data.evidence_annotations = data.evidence_annotations.map((e: Entity, i: number) => ({
    ...e,
    id: `e-${i}`,
    type: e.type?.toUpperCase() || 'UNKNOWN', // 标准化类型为大写
  }));
}
```

### 3. 默认值配置

| 属性 | 值 | 说明 |
|------|-----|------|
| label | 原始类型值 | 显示原始类型名 |
| color | #6b7280 | 灰色文字 |
| bgColor | #f3f4f6 | 浅灰背景 |
| borderColor | #9ca3af | 灰色边框 |
| icon | Info 图标 | 信息图标 |

## 预防措施

1. **大小写标准化**: 所有实体类型统一转大写处理
2. **默认值兜底**: 任何访问配置对象的地方都提供默认值
3. **调试日志**: 未配置的类型会打印警告，便于发现新问题
4. **类型检查**: 使用可选链 `?.` 防止访问 undefined 属性

## 未知类型处理流程

```
后端返回类型 → 转大写 → 查找配置
                              ↓
                    找到 ←→ 未找到
                     ↓         ↓
                   使用配置   使用默认值
                            + 打印警告
```

## 重启命令

```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-frontend/apps/frontend
npm run dev
```

现在页面不会再因为未知实体类型而崩溃，而是使用灰色默认样式显示，并在控制台打印警告便于调试。