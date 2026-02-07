# API 路由与文献解析功能实现文档

## 概述

本实现基于 OpenAPI 3.1.0 规范 (`api_docs/openapi_v1.json`)，实现了完整的路由配置与文献解析功能。

## 实现内容

### 1. API 类型定义 (`src/types/api.ts`)

根据 OpenAPI 规范定义了完整的类型系统：

#### 枚举类型
- `TaskStatusEnum`: 任务状态 (pending, processing, completed, failed, cancelled)
- `UploadSource`: 上传来源 (file, pmid, doi)

#### 请求类型
- `PDFUploadRequest`: JSON + Base64 上传请求
- `PDFUploadFormRequest`: multipart/form-data 上传请求
- `FetchByPMIDRequest`: PMID 获取请求
- `FetchByDOIRequest`: DOI 获取请求

#### 响应类型
- `TaskStatusResponse`: 任务状态响应（包含进度、证据项等）
- `EvidenceItemSummary`: 证据项摘要
- `DocumentParseResult`: 文档解析结果
- `ApiResponse`: 通用 API 响应

### 2. API 服务层 (`src/services/api.ts`)

实现了所有 OpenAPI 定义的端点：

#### PDF 解析 API
```typescript
uploadPDFForm(file: File, priority?: number, force?: boolean, clientHash?: string): Promise<UploadSuccessResponse>
uploadPDFForm(file: File, priority?: number): Promise<UploadSuccessResponse>
fetchByPMID(request: FetchByPMIDRequest): Promise<UploadSuccessResponse>
fetchByDOI(request: FetchByDOIRequest): Promise<UploadSuccessResponse>
```

#### 任务管理 API
```typescript
getTaskStatus(taskId: string): Promise<TaskStatusResponse>
cancelTask(taskId: string): Promise<ApiResponse>
getTaskProgress(taskId: string): Promise<TaskProgressResponse>
retryTask(taskId: string): Promise<ApiResponse>
```

#### 轮询工具
```typescript
pollTaskStatus(taskId, onProgress, interval, maxAttempts): Promise<TaskStatusResponse>
createTaskPoller(): { poll, abort }
```

### 3. 路由配置 (`src/router/index.tsx`)

#### 页面路由
- `/` - 首页（上传/输入）
- `/analysis/:id` - 分析页面
- `/graph` - 知识图谱页面
- `/tasks/status?taskId=xxx` - 任务状态页面
- `/documents/:documentId` - 文献查看页面

#### API 风格路由重定向
- `/api/v1/documents/:id` → `/analysis/:id`
- `/api/v1/graph` → `/graph`
- `/api/v1/tasks/:taskId/status` → `/tasks/status?taskId=:taskId`

### 4. 任务管理 Hooks (`src/hooks/useTaskPolling.ts`)

#### useTaskPolling
实时监控单个任务状态：
```typescript
const { status, isPolling, startPolling, stopPolling } = useTaskPolling(
  onProgress,
  onComplete,
  onError,
  { interval: 2000 }
);
```

#### useMultiTaskPolling
同时监控多个任务：
```typescript
const { tasks, addTask, removeTask, stopAll } = useMultiTaskPolling(
  onTaskProgress,
  onTaskComplete
);
```

#### useTaskQueue
任务队列管理：
```typescript
const { queue, addTask, updateTaskProgress, removeTask } = useTaskQueue();
```

### 5. 页面组件

#### TaskStatusPage (`src/pages/TaskStatusPage/`)
- 实时显示任务处理状态
- 进度条和当前阶段显示
- 证据项列表展示
- 任务控制（重试、取消、查看文档）
- 自动轮询更新

#### DocumentViewPage (`src/pages/DocumentViewPage/`)
- 动态加载文献结构
- 章节导航侧边栏
- 内容区块自动高亮
- 证据项汇总显示
- 元信息展示（PMID、DOI、作者等）

#### HomePage (更新)
- 集成新的 API 服务
- 任务队列显示
- 支持 PMID/DOI 获取
- 实时进度更新

## 使用方式

### 1. 上传 PDF

```typescript
import { uploadPDFForm, pollTaskStatus } from './services/api';

const handleUpload = async (file: File) => {
  const response = await uploadPDFForm(file, 0);
  
  // 开始轮询任务状态
  const status = await pollTaskStatus(
    response.task_id,
    (progress) => console.log(`Progress: ${progress.progress_percentage}%`),
    2000
  );
  
  if (status.status === 'completed') {
    navigate(`/analysis/${status.document_id}`);
  }
};
```

### 2. 通过 PMID 获取

```typescript
import { fetchByPMID, pollTaskStatus } from './services/api';

const handlePMIDSubmit = async (pmid: string) => {
  const response = await fetchByPMID({ pmid, priority: 0 });
  
  const status = await pollTaskStatus(response.task_id, onProgress);
  // 处理结果...
};
```

### 3. 使用任务轮询 Hook

```typescript
import { useTaskPolling } from './hooks/useTaskPolling';

const MyComponent = () => {
  const { status, isPolling, startPolling } = useTaskPolling(
    (progress) => console.log(progress),
    (completed) => console.log('Task completed!', completed),
    (error) => console.error(error),
    { interval: 2000 }
  );
  
  useEffect(() => {
    startPolling('task-123');
  }, []);
};
```

## 后端 API 规范

### 基础信息
- Base URL: `/api/v1`
- Content-Type: `application/json` 或 `multipart/form-data`

### 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/pdf/upload` | FormData 上传 |
| POST | `/pdf/fetch-by-pmid` | 通过 PMID 获取 |
| POST | `/pdf/fetch-by-doi` | 通过 DOI 获取 |
| GET | `/tasks/{task_id}` | 获取任务状态 |
| DELETE | `/tasks/{task_id}` | 取消任务 |
| GET | `/tasks/{task_id}/progress` | 获取实时进度 |
| POST | `/tasks/{task_id}/retry` | 重试任务 |

## 特性

### 1. 真实解析与动态加载
- 支持从后端 API 获取真实文献数据
- 动态渲染文献章节结构
- 实时显示解析进度

### 2. 任务状态管理
- 自动轮询任务状态
- 支持多个任务并行监控
- 本地持久化任务队列

### 3. 错误处理
- 统一的 API 错误类
- 验证错误详细信息
- 用户友好的错误提示

### 4. 响应式设计
- 适配不同屏幕尺寸
- 移动端友好的任务列表
- 可折叠的章节导航

## 开发说明

### 类型安全
- 所有 API 函数都有完整的 TypeScript 类型定义
- 使用接口确保前后端数据一致性
- 运行时类型检查

### 性能优化
- 防抖和节流的滚动处理
- Intersection Observer 实现懒加载
- 任务轮询自动清理

### 可访问性
- 语义化 HTML 结构
- 键盘导航支持
- 清晰的视觉反馈

## 后续扩展

1. **WebSocket 支持**: 替换轮询为实时推送
2. **离线支持**: 使用 Service Worker 缓存文档
3. **批量操作**: 支持批量上传和处理
4. **高级搜索**: 实现复杂的文献筛选功能
