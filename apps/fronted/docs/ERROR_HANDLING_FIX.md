# 前端修复总结：任务状态无限加载与通信错误

## 已完成的修复

### ✅ 1. 排查并隔离浏览器扩展干扰

**问题**: 错误 `A listener indicated an asynchronous response... but the message channel closed` 由浏览器扩展（React DevTools, Redux DevTools, LastPass, AdBlock 等）引起。

**解决方案**:
- 创建了全局错误处理器 `src/utils/errorHandler.ts`
- 在 `main.tsx` 中初始化，过滤以下错误模式：
  - `The message port closed before`
  - `message channel closed`
  - `Extension context invalidated`
  - `installHook.js`
  - `Unchecked runtime.lastError`
- 开发模式下将过滤的错误显示为警告，生产环境完全静默

**验证方法**: 在无痕模式/隐身模式下打开 http://localhost:5173，若状态正常加载则确认为扩展冲突。

---

### ✅ 2. 增强 fetchTaskStatus 的异常处理与超时机制

**文件**: `src/services/api.ts`

**改进内容**:

1. **通用 API 请求添加超时控制**:
   ```typescript
   const apiRequest = async <T>(
     endpoint: string,
     options: RequestInit = {},
     timeoutMs: number = 10000  // 默认 10 秒超时
   ): Promise<T>
   ```
   - 使用 `AbortController` 实现请求取消
   - 超时后自动中断请求并抛出友好错误

2. **getTaskStatus 专门优化**:
   ```typescript
   export const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse | { status: 'error'; message: string; task_id: string }>
   ```
   - 8 秒超时（更短的超时时间）
   - 错误时返回降级状态而非抛出异常
   - 返回格式: `{ status: 'error', message: '...', task_id: '...' }`
   - 区分超时错误和网络错误

3. **错误分类处理**:
   - 超时错误: "获取状态超时，请重试"
   - 网络错误: "无法获取状态，请检查网络或禁用扩展后重试"
   - 扩展干扰: 控制台警告但不阻断 UI

---

### ✅ 3. 优化前端状态加载 UI 逻辑

**文件**: `src/pages/HomePage.tsx` - RecentTasks 组件

**改进内容**:

1. **增强错误状态**:
   - 添加 `error` 状态存储错误信息
   - 添加 `retryCount` 实现自动重试机制（失败后自动重试 1 次）
   - 添加扩展干扰提示: "提示: 如果问题持续，请尝试在无痕模式下打开或禁用浏览器扩展"

2. **数据转换**:
   - API 返回 `TaskListItem[]` 转换为 `TaskSummary[]`
   - 处理可能的空值（document_id, created_at 等）

3. **错误状态 UI**:
   - 红色背景卡片显示错误
   - 错误图标 (AlertCircle)
   - 详细错误提示
   - 重试按钮 (RefreshCw)

4. **样式增强**:
   - 添加 `.recent-tasks.error` 样式
   - 添加 `.error-hint` 小字提示样式
   - 添加 `.retry-btn` 重试按钮样式

---

### ✅ 4. 检查 Vite 代理配置

**文件**: `vite.config.ts`

**当前配置**:
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      secure: false,
      ws: true,
    }
  }
}
```

**状态**: 配置正确，已指向后端 FastAPI 服务 (http://localhost:8000)

---

### ✅ 5. 清理控制台噪声

**实现**: 全局错误处理器 `src/utils/errorHandler.ts`

**功能**:
- 重写 `console.error` 和 `console.warn`
- 过滤扩展导致的特定错误模式
- 捕获 `window.onerror` 和 `window.onunhandledrejection`
- 阻止过滤的错误传播到控制台

---

## 使用建议

### 开发环境
1. **推荐**: 在无痕模式/隐身模式下开发，避免扩展干扰
2. **或者**: 禁用非必要的浏览器扩展（如广告拦截、密码管理器）
3. **查看**: 若控制台仍有扩展错误，确认是否为功能性问题

### 生产环境
- 全局错误处理器会自动静默扩展干扰错误
- 用户会看到友好的错误提示而非白屏
- 提供重试机制允许用户手动恢复

### 调试提示
若遇到加载问题：
1. 检查网络面板确认 API 请求状态
2. 查看控制台是否有被过滤的错误（开发模式下显示为 `[Filtered Extension Error]`）
3. 尝试点击"重试"按钮
4. 在无痕模式下验证是否为扩展冲突

---

## 文件变更列表

1. `src/services/api.ts` - 添加超时控制和错误降级
2. `src/utils/errorHandler.ts` - 新增全局错误处理器
3. `src/main.tsx` - 初始化全局错误处理
4. `src/pages/HomePage.tsx` - 增强错误状态和重试机制
5. `src/assets/css/home-immersive.css` - 添加错误状态样式

---

## 重启命令

```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-fronted/apps/fronted
npm run dev
```