# API 连接故障排查指南

## 快速诊断

### 1. 自动检查（推荐）

运行后端检查脚本：
```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-frontend/apps/frontend
npm run check-backend
```

或者在浏览器中：
1. 打开前端页面
2. 点击左侧导航栏底部的 **API 状态指示器**
3. 查看详细诊断信息

### 2. 浏览器控制台检查

打开浏览器开发者工具 (F12) → Console：
```javascript
// 运行完整诊断
import("./src/utils/apiDebug.ts").then(m => m.printDiagnostics())

// 快速检查连接
import("./src/utils/apiDebug.ts").then(m => m.quickCheck().then(console.log))
```

---

## 常见问题及解决方案

### ❌ 问题 1: 后端服务未启动（500 错误）

**症状**：
- POST /api/v1/pdf/upload → 500
- POST /api/v1/pdf/fetch-by-pmid → 500
- GET /api → 404

**原因**：后端服务没有运行在 8000 端口

**解决方案**：
```bash
# 1. 启动后端服务（在 backend 目录中）
cd /path/to/your/backend
uvicorn main:app --reload --port 8000

# 或使用你的后端启动命令
python -m uvicorn app:app --reload --port 8000
```

**验证**：
```bash
# 检查后端是否运行
curl http://localhost:8000/
# 应该返回 {"message": "Welcome to API"} 或类似内容

curl http://localhost:8000/api/v1
# 应该返回 API 信息
```

---

### ❌ 问题 2: 代理配置错误

**症状**：
- 浏览器网络请求显示 404
- 请求 URL 是 `http://localhost:5173/api/xxx`

**检查**：

1. 确认 `vite.config.ts` 配置正确：
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

2. 重启前端服务：
```bash
npm run dev
```

---

### ❌ 问题 3: 后端返回 500 内部服务器错误

**症状**：
- 代理配置正确
- 后端已启动
- 但 API 返回 500 错误

**排查步骤**：

1. **查看后端日志**
   后端控制台会显示详细的错误堆栈

2. **检查后端路由配置**
   确认后端有定义这些路由：
   ```python
   # FastAPI 示例
   @app.post("/api/v1/pdf/upload")
   async def upload_pdf(...)
   
   @app.post("/api/v1/pdf/fetch-by-pmid")
   async def fetch_by_pmid(...)
   ```

3. **测试后端直接访问**
   ```bash
   curl -X POST http://localhost:8000/api/v1/pdf/upload \
     -H "Content-Type: multipart/form-data" \
     -F "file=@test.pdf"
   ```

---

### ❌ 问题 4: CORS 跨域错误

**症状**：
```
Access to fetch at 'http://localhost:8000/api/v1/...' 
from origin 'http://localhost:5173' has been blocked by CORS policy
```

**解决方案**：

使用代理（推荐）→ 请求 URL 应该是相对路径 `/api/v1/xxx`，不是完整 URL

或配置后端 CORS：
```python
# FastAPI 示例
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

## 完整启动流程

### 步骤 1: 启动后端
```bash
# 在 backend 目录中
cd /path/to/backend

# 激活虚拟环境（如果使用）
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 启动服务
uvicorn main:app --reload --port 8000 --host 0.0.0.0

# 你应该看到类似输出：
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete.
```

### 步骤 2: 验证后端
打开新终端：
```bash
curl http://localhost:8000/
curl http://localhost:8000/docs  # API 文档
```

### 步骤 3: 启动前端
```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-frontend/apps/frontend
npm run dev

# 你应该看到：
# VITE v7.x.x  ready in xxx ms
# ➜  Local:   http://localhost:5173/
```

### 步骤 4: 验证连接
1. 打开浏览器访问 http://localhost:5173
2. 打开开发者工具 (F12)
3. 查看 Console 中的连接状态
4. 点击左侧导航栏的 API 状态指示器

---

## 环境变量配置

### 开发环境
`.env.development`:
```
VITE_API_BASE_URL=/api/v1
```

使用相对路径，通过 Vite 代理转发到 8000 端口。

### 生产环境
`.env.production`:
```
VITE_API_BASE_URL=https://your-api-domain.com/api/v1
```

使用完整 URL，需要配置 Nginx 反向代理。

---

## 调试技巧

### 1. 查看代理日志
前端启动后，控制台会显示：
```
【代理请求】 POST /api/v1/pdf/upload
【代理响应】 200 /api/v1/pdf/upload
```

### 2. 网络面板检查
浏览器开发者工具 → Network：
- 检查请求 URL：应为 `/api/v1/xxx`（不是完整 URL）
- 检查状态码
- 查看 Response 内容

### 3. 后端日志
后端控制台会显示：
- 接收到的请求
- 错误堆栈
- 处理时间

---

## 紧急修复

如果所有方法都无效，尝试：

```bash
# 1. 清理并重新安装依赖
rm -rf node_modules package-lock.json
npm install

# 2. 重启后端服务
# 在 backend 目录
pkill -f uvicorn  # 停止现有服务
uvicorn main:app --reload --port 8000

# 3. 重启前端
npm run dev

# 4. 强制刷新浏览器
Ctrl + Shift + R  # 或 Cmd + Shift + R
```

---

## 联系支持

如果问题仍然存在，请提供：
1. `npm run check-backend` 的输出
2. 浏览器 Console 的完整日志
3. Network 标签中的请求/响应详情
4. 后端控制台错误日志
5. `vite.config.ts` 的内容
