# 前端问题修复总结

## 修复内容概览

本次修复解决了以下五个核心问题：

1. ✅ CORS跨域问题 - 配置代理服务器
2. ✅ PDF上传422错误 - 文件验证增强
3. ✅ API端点404错误 - 路由配置确认
4. ✅ 错误处理机制 - 友好提示UI
5. ✅ 前端渲染逻辑 - 防止重复请求

---

## 1. CORS跨域问题修复

### 问题
前端 (http://localhost:5173) 无法直接访问后端 (http://localhost:8000)，导致跨域错误。

### 解决方案

#### Vite代理配置 (已存在，进行了增强)
```typescript
// vite.config.ts
server: {
  port: 5173,
  host: true,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      secure: false,
      ws: true,
      configure: (proxy, _options) => {
        proxy.on('error', (err, req, res) => {
          console.log('【代理错误】', err.message);
          // 返回友好的JSON错误
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            error: 'Proxy Error',
            message: err.message,
            hint: 'Backend may not be running on http://localhost:8000'
          }));
        });
      },
    },
  },
}
```

#### 新增API配置中心
```typescript
// src/services/apiConfig.ts
export const API_CONFIG = {
  BASE_URL: '/api/v1',
  TIMEOUT: 30000,
  RETRY: { MAX_ATTEMPTS: 3, DELAY: 1000 },
};

export const CORS_CONFIG = {
  DEV_ORIGINS: ['http://localhost:5173', 'http://127.0.0.1:5173'],
  METHODS: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
  CREDENTIALS: true,
};
```

### 后端配置建议
后端需要添加CORS中间件：
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 2. PDF上传422错误修复

### 问题
上传文件时返回422验证错误，可能是由于：
- 文件类型验证失败
- 文件名包含特殊字符
- 文件内容不符合预期

### 解决方案

#### 增强的文件验证
```typescript
// src/services/errorHandler.ts
export interface FileValidationResult {
  valid: boolean;
  error?: string;
  code?: string;
  details?: {
    fileName: string;
    fileSize: number;
    fileType: string;
    sizeInMB: string;
  };
}

export function validatePDFFile(file: File): FileValidationResult {
  // 1. 检查文件是否存在
  // 2. 检查文件是否为空
  // 3. 检查文件大小（50MB限制）
  // 4. 检查文件扩展名
  // 5. 检查文件名长度
  // 6. 检查文件名中的特殊字符
}

// 新增PDF文件头验证
export async function validatePDFFileHeader(file: File): Promise<FileValidationResult> {
  // 读取文件前8个字节，验证 %PDF- 魔数
}
```

#### 使用示例
```typescript
const validation = validatePDFFile(file);
if (!validation.valid) {
  setUploadError({
    title: '文件验证失败',
    message: validation.error,
    type: 'warning',
  });
  return;
}

// 额外的PDF文件头验证
const headerValidation = await validatePDFFileHeader(file);
if (!headerValidation.valid) {
  // 处理无效PDF
}
```

---

## 3. API端点404错误修复

### 问题
任务状态查询接口返回404，可能是路由配置错误。

### 解决方案

#### 标准化API端点配置
```typescript
// src/services/apiConfig.ts
export const API_ENDPOINTS = {
  PDF: {
    UPLOAD: '/pdf/upload',
    CHECK_HASH: '/pdf/check_hash',
    FETCH_BY_PMID: '/pdf/fetch-by-pmid',
    FETCH_BY_DOI: '/pdf/fetch-by-doi',
  },
  TASKS: {
    STATUS: (taskId: string) => `/tasks/${encodeURIComponent(taskId)}`,
    PROGRESS: (taskId: string) => `/tasks/${encodeURIComponent(taskId)}/progress`,
    CANCEL: (taskId: string) => `/tasks/${encodeURIComponent(taskId)}`,
    RETRY: (taskId: string) => `/tasks/${encodeURIComponent(taskId)}/retry`,
  },
};
```

#### 增强的API错误处理
```typescript
// src/services/apiClient.ts
async function handleErrorResponse(response: Response, endpoint: string): Promise<never> {
  switch (response.status) {
    case 404:
      throw new APIError(
        `API端点不存在: ${endpoint}`,
        response.status,
        undefined,
        'server'
      );
    case 422:
      throw new APIError(
        `数据验证失败: ${details}`,
        response.status,
        errorData.detail,
        'validation'
      );
    // ... 其他状态码
  }
}
```

### 后端路由确认
请确保后端有以下路由：
```python
# FastAPI示例
@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    ...

@app.get("/api/v1/tasks/{task_id}/progress")
async def get_task_progress(task_id: str):
    ...

@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    ...
```

---

## 4. 错误处理机制优化

### 问题
API错误显示不友好，用户无法理解具体原因。

### 解决方案

#### 新建错误显示组件
```typescript
// src/components/ui/ErrorDisplay/ErrorDisplay.tsx
export interface ErrorDisplayProps {
  title?: string;
  message: string;
  severity?: 'error' | 'warning' | 'info';
  details?: string;
  action?: string;
  retryable?: boolean;
  onRetry?: () => void;
  onClose?: () => void;
}

// 专门的API错误组件
export const ApiErrorDisplay: React.FC<ApiErrorDisplayProps> = ({
  error,
  onRetry,
  onClose,
}) => {
  // 自动解析错误类型，显示友好提示
};
```

#### 使用示例
```tsx
{apiError && (
  <ApiErrorDisplay
    error={apiError}
    onRetry={() => {
      setApiError(null);
      handleRetry();
    }}
    onClose={() => setApiError(null)}
  />
)}
```

#### 错误分类
- **network**: 网络连接失败 → "请确保后端服务已启动"
- **validation**: 400/422错误 → "请检查输入数据格式"
- **duplicate**: 409错误 → "文件已存在，请勿重复上传"
- **server**: 500错误 → "服务器内部错误，请稍后重试"
- **not_found**: 404错误 → "API端点不存在"

---

## 5. 前端渲染逻辑优化

### 问题
- 重复请求导致服务器压力
- 组件卸载后仍有未完成请求
- 资源加载失败导致UI异常

### 解决方案

#### 请求管理Hook
```typescript
// src/hooks/useRequestManager.ts
export function useRequestManager() {
  // 请求去重
  const executeRequest = useCallback(<T>(
    url: string,
    options: RequestInit & ExtendedRequestOptions = {}
  ): Promise<T> => {
    // 1. 检查缓存
    // 2. 检查是否有相同请求正在进行
    // 3. 创建新的请求
    // 4. 存储请求状态
  }, []);
  
  // 请求取消
  const cancelRequest = useCallback((url: string, method?: string) => {...}, []);
  const cancelAllRequests = useCallback(() => {...}, []);
  
  // 缓存管理
  const clearCache = useCallback((pattern?: RegExp) => {...}, []);
  
  return { executeRequest, cancelRequest, cancelAllRequests, clearCache };
}
```

#### 使用示例
```typescript
const requestManager = useRequestManager();

// 执行请求（自动去重）
const response = await requestManager.executeRequest<UploadSuccessResponse>(
  `${API_BASE_URL}/pdf/upload`,
  {
    method: 'POST',
    body: formData,
    deduplicate: true, // 启用请求去重
    timeout: 60000,    // 60秒超时
  }
);
```

#### 组件卸载时自动清理
```typescript
useEffect(() => {
  return () => {
    // 组件卸载时取消所有进行中的请求
    cancelAllRequests();
  };
}, []);
```

---

## 文件变更清单

### 新增文件
1. `src/services/apiConfig.ts` - API配置中心
2. `src/services/apiClient.ts` - 增强版API客户端
3. `src/hooks/useRequestManager.ts` - 请求管理Hook
4. `src/components/ui/ErrorDisplay/ErrorDisplay.tsx` - 错误显示组件
5. `src/components/ui/ErrorDisplay/ErrorDisplay.css` - 错误显示样式

### 修改文件
1. `src/services/api.ts` - 集成新的API客户端
2. `src/services/errorHandler.ts` - 增强文件验证
3. `src/pages/HomePage/HomePage.tsx` - 集成错误显示和请求管理
4. `src/pages/HomePage/HomePage.css` - 添加错误横幅样式
5. `src/pages/TaskStatusPage/TaskStatusPage.tsx` - 使用新的错误组件
6. `src/pages/TaskStatusPage/TaskStatusPage.css` - 更新错误容器样式

---

## 使用指南

### 开发环境启动
```bash
# 1. 启动后端 (端口8000)
cd backend
uvicorn main:app --reload --port 8000

# 2. 启动前端 (端口5173)
cd frontend
npm run dev
```

### 测试文件上传
1. 选择有效的PDF文件（< 50MB）
2. 观察文件验证结果
3. 查看控制台日志中的hash计算
4. 上传成功后自动跳转到分析页面

### 调试模式
在开发环境下，可以开启强制上传绕过重复检测：
- 在首页勾选 "⚠️ 强制上传（绕过重复检测）"
- 这会在请求URL中添加 `?force=true` 参数

---

## 后续优化建议

1. **文件分片上传**：对于大文件，实现分片上传和断点续传
2. **WebSocket进度**：使用WebSocket替代轮询获取实时进度
3. **请求缓存持久化**：将缓存数据持久化到 localStorage
4. **离线支持**：添加 Service Worker 支持离线访问
5. **错误上报**：集成 Sentry 等错误监控服务
