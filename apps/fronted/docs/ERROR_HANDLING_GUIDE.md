# 前端错误处理优化指南

## 更新内容

### 1. 错误处理服务 (`src/services/errorHandler.ts`)

新增功能：
- **错误分类**：区分 400（验证错误）、500（服务器错误）、网络错误
- **文件验证**：上传前验证 PDF 格式和大小（最大 50MB）
- **友好提示**：将技术错误转换为用户可理解的提示

### 2. 上传区域错误提示

- 实时显示文件验证错误
- 区分警告（黄色）和错误（红色）
- 可关闭的错误提示框

### 3. 后端状态指示器 (`src/components/BackendStatus/`)

功能：
- 显示 API、数据库、延迟状态
- 自动每 30 秒检查一次
- 三种状态：正常（绿色）、降级（黄色）、错误（红色）

## 使用说明

### 浏览器控制台命令

```javascript
// 运行健康检查
healthCheck.runHealthCheck()

// 快速检查
healthCheck.quickHealthCheck()

// 诊断 PDF 上传
healthCheck.diagnosePDFUpload()
```

### 错误类型说明

| 错误类型 | 状态码 | 用户提示 | 可重试 |
|---------|--------|---------|--------|
| 验证错误 | 400/422 | 文件格式或参数不正确 | ✅ 是 |
| 服务器错误 | 500/502/503 | 后端技术故障 | ✅ 是 |
| 网络错误 | - | 无法连接后端 | ✅ 是 |
| 端点不存在 | 404 | API 未实现 | ❌ 否 |

## 文件变更

1. `src/services/errorHandler.ts` - 新增错误处理服务
2. `src/pages/HomePage/HomePage.tsx` - 集成错误处理
3. `src/pages/HomePage/HomePage.css` - 错误提示样式
4. `src/components/BackendStatus/` - 后端状态指示器
5. `src/utils/healthCheck.ts` - 健康检查工具

## 后续建议

后端修复后，前端无需修改即可正常工作。
