# 任务状态页面修复总结

## 问题根源
前端代码逻辑与后端返回的数据结构不匹配，导致页面一直显示"加载中"。

## 后端实际返回结构
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "...",
    "status": "SUCCESS",  // ✅ 在根层级，不是 response.status
    "document_id": "...", // ✅ 在根层级，不是 data.result.document_id
    "file_size_bytes": 304613,
    "processing_duration_seconds": 245.13,
    "created_at": "2026-02-26T06:50:10.608487+00:00",
    "updated_at": "2026-02-26T06:54:15.738487+00:00",
    "error": null
  }
}
```

## 🚨 P0: 核心逻辑修复 (已完成)

### 1. 修正状态字段读取路径 ✅
```typescript
// ❌ 错误写法
if (response.status === 'SUCCESS') { ... }

// ✅ 正确写法 (status 在 data 根层级)
const { status, document_id, error } = response.data;
if (status === 'SUCCESS') { ... }
```

### 2. 更新成功态的数据映射 ✅
```typescript
// ❌ 错误写法 (访问不存在的 result)
const docId = data.result.document_id;

// ✅ 正确写法 (直接从根层级提取)
const docId = data.document_id;
const fileSize = data.file_size_bytes;
const duration = data.processing_duration_seconds;
```

### 3. 修复轮询终止条件 ✅
```typescript
// ❌ 错误写法 (可能等待不存在的字段)
if (data.result) { stopPolling(); }

// ✅ 正确写法 (根据 status 判断)
const isTerminalStatus = ['SUCCESS', 'FAILURE', 'REVOKED'].includes(status);
if (isTerminalStatus) {
  stopPolling();
  setLoading(false);
}
```

## 🎨 P1: 结果页 UI 渲染 (已完成)

### 4. 渲染文档基本信息卡片 ✅
- 文档 ID: 支持点击复制
- 文件大小: 格式化显示 (304613 → "297.47 KB")
- 处理耗时: 格式化显示 (245.13 → "4分5秒")
- 时间戳: 格式化为本地时间

### 5. 添加"查看分析报告"入口 ✅
- 醒目的主按钮 "查看完整评级报告"
- 自动跳转到 `/results/{document_id}`

### 6. 错误状态处理 ✅
- status === 'FAILURE' 时显示红色警告框
- 展示用户友好的错误提示
- 提供"重试"和"重新上传"按钮

## ⚡ P2: 性能与体验优化 (已完成)

### 7. 移除冗余的 Loading 状态 ✅
- 接收到 SUCCESS/FAILURE 立即清除 loading
- 成功时延迟 1.5 秒后自动跳转

### 8. 增加空值防御 ✅
```typescript
// 使用可选链和默认值
formatFileSize(task.file_size_bytes) // 内部处理 undefined
formatDuration(task.processing_duration_seconds ?? 0)
```

## 📁 新增/修改文件

1. `src/pages/TaskStatusPage.tsx` - 完全重写，修复所有逻辑问题
2. `src/pages/TaskStatusPage.css` - 新建样式文件

## 🛠️ 新增工具函数

```typescript
// 格式化文件大小
formatFileSize(304613) // → "297.47 KB"

// 格式化时长
formatDuration(245.13) // → "4分5秒"

// 格式化时间
formatTime("2026-02-26T06:50:10...") // → "2026/02/26 14:50:10"
```

## 🚀 使用说明

访问任务状态页面：
```
http://localhost:5173/tasks/status?taskId=your-task-id
```

页面现在会：
1. ✅ 正确读取后端返回的状态
2. ✅ 在 SUCCESS 时自动跳转到结果页
3. ✅ 展示格式化的文件大小、处理时长等信息
4. ✅ 提供清晰的错误提示和重试机制

## 重启命令
```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-frontend/apps/frontend
npm run dev
```