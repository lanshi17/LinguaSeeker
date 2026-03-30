# 快速启动指南

## 环境要求

- Node.js 18+
- Python 3.8+ (后端)
- 后端服务代码

## 1. 启动后端服务

```bash
# 进入后端目录
cd /path/to/your/backend

# 启动服务（确保在 8000 端口）
uvicorn main:app --reload --port 8000

# 或使用你的启动命令
python -m uvicorn app:app --reload --port 8000
```

验证后端运行：
```bash
curl http://localhost:8000/
```

## 2. 启动前端服务

```bash
# 进入前端目录
cd /mnt/data/Documents/Graduate/02_Research/03_Multi-ACMG-frontend/apps/frontend

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev
```

## 3. 访问应用

打开浏览器访问：http://localhost:5173

## 4. 验证连接

1. 打开浏览器开发者工具 (F12)
2. 查看 Console 中的蓝色启动信息
3. 检查是否有后端连接提示
4. 点击左侧导航栏底部的 **API 状态指示器** 查看详情

## 故障排查

如果遇到 500 错误：

```bash
# 运行后端检查
npm run check-backend
```

查看详细文档：[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

## 常用命令

```bash
# 检查后端状态
npm run check-backend

# 构建生产版本
npm run build

# 代码检查
npm run lint
```
