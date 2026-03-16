# 文献对照阅读与证据可视化功能

## 功能概述

实现了专业的文献对照阅读界面，支持中英双语对照、同步滚动、实体彩色标注和证据可视化。

## 访问方式

1. 上传 PDF 并等待处理完成
2. 进入结果页面 (`/results/:documentId`)
3. 点击 **"对照阅读"** 按钮进入阅读模式

或直接访问：`/reader/:documentId`

## 核心功能

### 🚀 P0: 双语对照与同步滚动

#### 1. 左右分栏布局
- **左侧**: 原文 (中文 Markdown)
- **右侧**: 译文 (English Markdown)
- **分隔线**: 可拖动调整宽度

#### 2. 同步滚动
- 基于百分比同步算法
- 节流处理 (50ms 锁定)
- 可开关控制

```typescript
const handleScroll = (source: 'left' | 'right') => {
  if (!isSyncScroll || isScrolling.current) return;
  
  isScrolling.current = true;
  const percentage = sourceRef.scrollTop / 
    (sourceRef.scrollHeight - sourceRef.clientHeight);
  targetRef.scrollTop = percentage * 
    (targetRef.scrollHeight - targetRef.clientHeight);
  
  setTimeout(() => { isScrolling.current = false; }, 50);
};
```

#### 3. Markdown 渲染
- 使用 `react-markdown` + `remark-gfm`
- 支持表格、代码块、引用等语法
- 自定义组件实现实体高亮

### 🎨 P1: 实体识别与彩色标注

#### 支持的实体类型

| 类型 | 颜色 | 图标 | 说明 |
|------|------|------|------|
| **GENE** | 蓝色 | 🧬 | 基因名称 (BRCA1, TP53) |
| **VARIANT** | 红色 | 🧪 | 变异位点 (c.5266dupC) |
| **DISEASE** | 绿色 | 🏥 | 疾病名称 (breast cancer) |
| **EVIDENCE** | 黄色 | 📊 | 证据关键词 |
| **PHENOTYPE** | 紫色 | ℹ️ | 表型描述 |

#### 交互功能
- **点击实体**: 打开详情抽屉，显示置信度和证据
- **悬停提示**: 显示实体类型和置信度
- **图例控制**: 右下角悬浮窗，可切换显示/隐藏类型

### 📊 P2: 数据可视化

#### 1. JSON 证据抽屉
点击 **"证据数据"** 按钮打开：
- **ACMG 分类**: 显示致病性评级 (Pathogenic/Likely pathogenic)
- **证据代码**: PM1, PS3, PP5 等
- **基因-变异关联**: 列表展示
- **提取实体**: 标签云形式
- **原始 JSON**: 可折叠查看

#### 2. 复制功能
- 复制文档 ID
- 复制实体名称
- 复制完整 JSON

#### 3. 全屏模式
点击全屏按钮沉浸式阅读

## 技术实现

### 依赖库
```bash
npm install react-markdown remark-gfm rehype-highlight
```

### 文件结构
```
src/pages/
├── DocumentReaderPage.tsx    # 主页面组件
├── DocumentReaderPage.css    # 样式文件
├── ResultsViewPage.tsx       # 结果页（添加入口按钮）
```

### 路由配置
```typescript
<Route path="/reader/:documentId" element={<DocumentReaderPage />} />
```

### 核心组件

1. **HighlightedText**: 文本高亮组件
   - 解析实体 offset
   - 包裹高亮 span
   - 处理重叠实体

2. **EntityLegend**: 图例悬浮窗
   - 可折叠
   - 类型筛选
   - 颜色指示

3. **EntityDrawer**: 实体详情
   - 置信度进度条
   - 证据依据
   - 类型标签

4. **EvidenceJsonDrawer**: JSON 预览
   - 树形展示
   - 分类信息
   - 原始 JSON

## 使用示例

### 实体数据结构
```json
{
  "entities": [
    {
      "text": "BRCA1",
      "type": "GENE",
      "offset_start": 102,
      "offset_end": 107,
      "confidence": 0.98
    },
    {
      "text": "c.5266dupC",
      "type": "VARIANT",
      "offset_start": 200,
      "offset_end": 210,
      "confidence": 0.95
    }
  ],
  "acmg_classification": {
    "classification": "Pathogenic",
    "evidence_codes": ["PS3", "PM1"],
    "confidence": 0.92
  }
}
```

### 颜色配置
```typescript
const ENTITY_CONFIG = {
  GENE: {
    color: '#1e40af',
    bgColor: '#dbeafe',
    borderColor: '#93c5fd',
  },
  VARIANT: {
    color: '#991b1b',
    bgColor: '#fee2e2',
    borderColor: '#fca5a5',
  },
  // ...
};
```

## 性能优化

1. **节流处理**: 滚动事件 50ms 节流
2. **锁定机制**: 防止滚动死循环
3. **懒加载**: 证据 JSON 异步加载
4. **虚拟滚动**: 长文档优化

## 响应式适配

- **桌面**: 左右分栏
- **平板**: 保持分栏，调整宽度
- **手机**: 垂直堆叠，隐藏分隔线

## 后续优化建议

1. **P3**: 添加全文搜索功能
2. **P3**: 支持导出 PDF/Word
3. **P3**: 添加标注和笔记功能
4. **P3**: 支持多文档对比

## 重启命令

```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-fronted/apps/fronted
npm run dev
```

访问：`http://localhost:5173/reader/{documentId}`