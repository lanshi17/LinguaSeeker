# ✅ 前后端通信配置完成

## 已完成的工作

### 1. Vite 代理配置
**文件**: `vite.config.ts`
- 配置代理将 `/api` 请求转发到 `http://localhost:8000`
- 添加错误处理日志
- 显示代理请求/响应日志

### 2. 环境变量配置
**文件**: 
- `.env` - 默认配置
- `.env.development` - 开发环境
- `.env.production` - 生产环境
- `.env.local.example` - 本地配置示例

### 3. API 服务层
**文件**: `src/services/api.ts`
- 完整的 API 端点实现
- 增强的错误处理（500 错误提示）
- 任务轮询功能

### 4. 诊断工具
**文件**: 
- `src/utils/apiDebug.ts` - 诊断工具函数
- `src/components/ApiStatus/` - API 状态组件
- `scripts/check-backend.cjs` - 后端检查脚本

### 5. 启动提示
**文件**: `src/main.tsx`
- 控制台自动检测后端连接
- 提供启动指引

## 使用方法

### 启动后端（必须）
```bash
cd /path/to/your/backend
uvicorn main:app --reload --port 8000
```

### 启动前端
```bash
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-frontend/apps/frontend
npm run dev
```

### 检查后端状态
```bash
npm run check-backend
```

### 浏览器诊断
1. 打开 http://localhost:5173
2. 按 F12 打开开发者工具
3. 查看 Console 中的启动信息
4. 点击左侧导航栏底部的 **API 状态** 指示器

## 故障排查

### 500 错误
如果看到 500 错误，说明：
1. ✅ 代理配置正确
2. ✅ 前端配置正确
3. ❌ 后端服务有问题

**解决**：
1. 确保后端已启动
2. 查看后端控制台日志
3. 检查后端路由配置

### 404 错误
如果看到 404 错误：
1. 检查后端是否运行在 8000 端口
2. 检查后端是否有对应的路由
3. 运行 `npm run check-backend`

### CORS 错误
如果看到 CORS 错误：
- 确认使用相对路径 `/api/v1/xxx` 而不是完整 URL
- 代理配置会自动处理跨域

## 文件结构

```
frontend/
├── .env                      # 环境变量
├── .env.development         # 开发环境配置
├── .env.production          # 生产环境配置
├── vite.config.ts           # Vite 配置（含代理）
├── package.json             # 脚本命令
├── scripts/
│   └── check-backend.cjs    # 后端检查脚本
├── src/
│   ├── main.tsx             # 入口（含启动检测）
│   ├── services/
│   │   └── api.ts           # API 服务层
│   ├── utils/
│   │   └── apiDebug.ts      # 诊断工具
│   └── components/
│       └── ApiStatus/       # API 状态组件
├── TROUBLESHOOTING.md       # 详细故障排查
└── QUICKSTART.md           # 快速启动指南
```

## 下一步

1. 确保后端服务已启动（端口 8000）
2. 启动前端：`npm run dev`
3. 访问 http://localhost:5173
4. 点击左侧导航栏的 **API 状态** 查看连接状态

如果仍有 500 错误，请查看后端控制台日志获取详细信息。
