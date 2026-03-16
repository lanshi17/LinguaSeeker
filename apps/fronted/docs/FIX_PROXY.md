# Vite 代理配置修复

## 问题

- 前端检测到后端服务未运行
- API 代理路径返回 404
- PDF 上传返回 400 错误

## 修复内容

### 1. 增强 Vite 代理日志

**文件**: `vite.config.ts`

添加了详细的代理日志：
- 代理请求日志
- 代理响应日志  
- 代理错误日志

### 2. 新增代理诊断组件

**文件**: 
- `src/components/ProxyDiagnostic/ProxyDiagnostic.tsx`
- `src/components/ProxyDiagnostic/ProxyDiagnostic.css`
- `src/utils/proxyTest.ts`

功能：
- 自动测试直接访问后端
- 自动测试代理访问
- 显示详细的 HTTP 状态码
- 提供修复建议

### 3. 控制台诊断命令

在浏览器控制台可以运行：
```javascript
// 运行完整的代理测试
proxyTest.runProxyTest()

// 快速检查
proxyTest.quickProxyCheck()
```

## 使用步骤

### 步骤 1: 重启前端服务（必须）

```bash
# 停止当前服务
Ctrl + C

# 清除缓存
rm -rf node_modules/.vite

# 重启服务
npm run dev
```

### 步骤 2: 强制刷新浏览器

- 按 `Ctrl + Shift + R` (Windows/Linux)
- 或 `Cmd + Shift + R` (Mac)

### 步骤 3: 查看诊断结果

1. 打开 http://localhost:5173
2. 查看页面上的 **"代理连接诊断"** 组件
3. 检查所有测试项目是否通过

## 测试结果解读

### 情况 1: 直接访问后端 ❌
```
❌ 直接访问后端 (/) 
错误: 连接失败
```
**解决**: 后端服务未启动
```bash
cd /path/to/backend
uvicorn main:app --reload --port 8000
```

### 情况 2: 直接访问后端 ✅，代理访问 ❌
```
✅ 直接访问后端 (/) (200)
❌ 代理访问 (/api/)
错误: 连接失败
```
**解决**: 代理配置未生效，需要重启前端服务
```bash
# 停止前端服务
Ctrl + C

# 清除缓存并重启
rm -rf node_modules/.vite
npm run dev
```

### 情况 3: 所有测试通过 ✅
```
✅ 直接访问后端 (/) (200)
✅ 代理访问 (/api/) (200/404)
✅ 代理访问 API (/api/v1) (200/404)
✅ PDF 上传端点 (200/405)
```
**说明**: 代理工作正常！404/405 表示连接成功，只是端点不存在。

## 验证后端 API

确保后端有以下端点：
- `POST /api/v1/pdf/upload` - FormData 上传
- `POST /api/v1/pdf/fetch-by-pmid` - PMID 获取
- `GET  /api/v1/tasks/{task_id}` - 任务状态

如果后端缺少这些端点，需要实现对应的处理函数。

## 文件变更

1. `vite.config.ts` - 添加代理日志
2. `src/utils/proxyTest.ts` - 新增诊断工具
3. `src/components/ProxyDiagnostic/` - 新增诊断组件
4. `src/pages/HomePage/HomePage.tsx` - 集成诊断组件
5. `src/main.tsx` - 导入诊断工具

## 快速诊断

访问 http://localhost:5173 后：

1. 查看页面上的 **代理连接诊断** 面板
2. 如果显示 ❌，按照建议操作
3. 点击 **重新测试** 按钮验证修复

在浏览器控制台也可以运行：
```javascript
proxyTest.runProxyTest()
```
