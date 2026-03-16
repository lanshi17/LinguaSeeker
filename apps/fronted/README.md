# ACMG-PS3 Intelligence System Frontend

这是一个用于ACMG-PS3证据标准智能系统的前端应用，提供PDF上传、证据检索、分析和可视化等功能。

## 功能特性

- **PDF上传与处理**：支持PDF文档上传并进行自动化处理
- **证据检索**：基于基因符号、变异等条件检索科学证据
- **证据分析**：包括基因关联分析、共现矩阵、证据链检测等
- **质量监控**：实时监控证据质量和完整性
- **可视化展示**：以图表形式展示证据关系和统计数据
- **结果下载**：支持分析结果的下载和导出

## 技术栈

- React 19.x
- TypeScript
- React Router DOM
- D3.js
- Lucide React Icons

## 环境要求

- Node.js >= 18.0.0
- npm 或 yarn

## 安装与运行

### 1. 克隆项目

```bash
git clone <repository-url>
cd apps/fronted
```

### 2. 安装依赖

```bash
npm install
```

### 3. 配置环境变量

复制示例环境文件：

```bash
cp .env.local.example .env.local
```

编辑 `.env.local` 文件，配置后端API地址：

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### 4. 启动开发服务器

```bash
npm run dev
```

应用将在 `http://localhost:5173` 上运行。

### 5. 构建生产版本

```bash
npm run build
```

## 主要页面

- `/` - 首页
- `/pdf/upload` - PDF上传页面
- `/tasks/status` - 任务状态页面
- `/evidence/search` - 证据检索页面
- `/evidence/aggregate` - 证据聚合页面
- `/evidence/association` - 基因关联分析页面
- `/evidence/co-occurrence` - 共现矩阵页面
- `/evidence/chains` - 证据链检测页面
- `/evidence/quality` - 证据质量监控页面
- `/evidence/graph-stats` - 图数据库统计页面
- `/results/:documentId` - 结果查看页面

## API 集成

前端通过 `src/services/apiService.ts` 与后端API通信，支持以下主要功能：

- 健康检查
- PDF上传和哈希检查
- 任务管理和状态查询
- 证据检索和聚合
- 基因/变异关联分析
- 共现分析和证据链检测
- 质量评估和图统计

## 目录结构

```
src/
├── components/     # 可复用UI组件
├── pages/         # 页面组件
├── services/      # API服务
├── types/         # TypeScript类型定义
├── hooks/         # 自定义React Hooks
├── utils/         # 工具函数
├── router/        # 路由配置
└── assets/        # 静态资源
```

## 开发指南

### 前端开发宪法原则

为确保代码质量和一致性，所有前端开发必须遵循[前端开发宪法原则](FRONTEND_CONSTITUTION.md)。在开始开发前，请务必仔细阅读并理解这些原则。

参阅[开发指南](DEVELOPMENT_GUIDELINES.md)了解快速入门要点和代码审查清单。

### 添加新页面

1. 在 `src/pages/` 目录下创建新页面组件
2. 在 `src/router/index.tsx` 中添加路由配置
3. 如需要，更新类型定义

### API 调用

所有API调用都通过 `src/services/apiService.ts` 进行：

```typescript
import { healthCheck, searchEvidence } from '../services/apiService';

// 示例：健康检查
const health = await healthCheck();

// 示例：证据检索
const results = await searchEvidence({
  gene_symbol: 'BRCA1',
  min_confidence: 90
});
```

## 故障排除

### 常见问题

1. **API连接失败**：检查后端服务是否运行，以及 `VITE_API_BASE_URL` 配置是否正确
2. **跨域错误**：确保后端API设置了正确的CORS头部
3. **构建错误**：运行 `npm run lint` 检查代码质量问题
4. **类型错误**：运行 `npx tsc --noEmit` 检查TypeScript类型错误

### 调试

- 使用浏览器开发者工具查看网络请求
- 检查控制台是否有错误信息
- 运行 `npm run diagnose` 进行基本诊断
- 运行 `npx tsc --noEmit` 检查TypeScript类型问题

## 贡献

欢迎提交Issue和Pull Request来改进此项目。

## 许可证

[在此处添加许可证信息]