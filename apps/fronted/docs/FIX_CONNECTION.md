# 🔧 连接问题修复指南

## 问题症状

- 前端请求仍然发到 5173 端口
- POST /api/v1/pdf/upload → 500 错误
- 后端健康检查 404

## 根本原因

**Vite 代理配置需要重启前端服务才能生效**

配置已更新，但前端服务需要重启才能加载新配置。

## 修复步骤（按顺序执行）

### 步骤 1: 停止前端服务

在运行前端服务的终端中按：
```bash
Ctrl + C
```

### 步骤 2: 清除缓存

```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-fronted/apps/fronted

# 清除 Vite 缓存
rm -rf node_modules/.vite

# 可选：重新安装依赖
rm -rf node_modules package-lock.json
npm install
```

### 步骤 3: 重启前端服务

```bash
npm run dev
```

### 步骤 4: 强制刷新浏览器

1. 打开浏览器访问 http://localhost:5173
2. 按 **Ctrl + Shift + R** (Windows/Linux) 或 **Cmd + Shift + R** (Mac)
3. 打开开发者工具 (F12) → Network 标签
4. 勾选 "Disable cache"

### 步骤 5: 验证修复

在浏览器控制台运行：
```javascript
networkTest.fullNetworkDiagnostic()
```

应该看到代理请求成功转发到后端。

## 验证代理是否生效

### 方法 1: 查看控制台日志

重启后，前端控制台应该显示：
```
【代理请求】 POST /api/v1/pdf/upload
【代理响应】 200 /api/v1/pdf/upload
```

如果没有看到这些日志，说明代理未生效。

### 方法 2: 检查 Network 面板

1. 打开开发者工具 → Network 标签
2. 执行一次 PDF 上传
3. 查看请求详情：
   - **Request URL**: 应该是 `/api/v1/pdf/upload`（不是完整 URL）
   - **Remote Address**: 应该显示 `localhost:5173`
   - 但在 Response Headers 中应该有代理转发的痕迹

### 方法 3: 直接测试

在浏览器控制台：
```javascript
// 通过代理访问
fetch('/api/v1/health').then(r => console.log('代理:', r.status))

// 直接访问后端
fetch('http://localhost:8000/').then(r => console.log('直接:', r.status))
```

如果代理工作正常，两者都应该成功（或返回相同的错误）。

## 常见问题

### Q: 重启后仍然 500 错误

**A**: 后端服务没有运行或配置错误。

检查后端：
```bash
curl http://localhost:8000/
```

如果返回 404，说明后端没有正确配置根路由。

### Q: 代理日志没有出现

**A**: Vite 代理配置未加载。

检查 `vite.config.ts` 是否存在且格式正确：
```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### Q: CORS 错误

**A**: 确保使用相对路径 `/api/v1/xxx`，不是完整 URL。

检查 `src/services/api.ts`：
```typescript
const API_BASE_URL = '/api/v1'  // 应该是相对路径
```

## 紧急修复脚本

如果以上方法都无效，运行以下脚本：

```bash
#!/bin/bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-fronted/apps/fronted

echo "🧹 清理缓存..."
rm -rf node_modules/.vite
rm -rf dist

echo "🔄 重启前端服务..."
npm run dev
```

保存为 `restart.sh` 并执行：
```bash
chmod +x restart.sh
./restart.sh
```

## 检查清单

- [ ] 后端服务已启动在 8000 端口
- [ ] 前端服务已重启
- [ ] 浏览器已强制刷新
- [ ] 浏览器缓存已禁用
- [ ] 控制台显示代理日志
- [ ] 网络请求 URL 是相对路径

## 联系支持

如果仍有问题，请提供：
1. 前端控制台完整输出
2. Network 标签的请求截图
3. `vite.config.ts` 内容
4. 后端服务状态
