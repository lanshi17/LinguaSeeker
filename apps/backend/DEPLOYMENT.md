# 🚀 快速部署指南

## 📋 前置要求

### 1. 系统要求
- Python >= 3.12
- 8GB+ RAM
- 20GB+ 磁盘空间

### 2. 外部服务
```bash
# PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -p 5432:5432 \
  postgres:16

# Neo4j
docker run -d --name neo4j \
  -e NEO4J_AUTH=neo4j/yourpassword \
  -p 7474:7474 -p 7687:7687 \
  neo4j:5.15

# Milvus
docker run -d --name milvus \
  -p 19530:19530 \
  milvusdb/milvus:latest

# MinIO (可选)
docker run -d --name minio \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=password \
  -p 9000:9000 -p 9001:9001 \
  minio/minio server /data --console-address ":9001"
```

## ⚡ 快速启动

### 方式1: 使用启动脚本
```bash
# 1. 配置环境变量
cp .env.example .env
vim .env  # 填入API密钥

# 2. 运行检查
python check_config.py

# 3. 启动服务
chmod +x start.sh
./start.sh
```

### 方式2: 手动启动
```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -e .

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 4. 启动服务
python main.py
```

## 🔧 环境变量配置

### 必需配置
```bash
# LLM API密钥
DEEPSEEK_API_KEY="sk-xxx"
CLAUDE_API_KEY="sk-ant-xxx"

# 数据库密码
POSTGRES_PASSWORD="yourpassword"
NEO4J_PASSWORD="yourpassword"
```

### 可选配置
```bash
# 调整服务端口
API_PORT="8000"

# 日志级别
DEBUG="true"

# MinerU服务地址
MINERU_API_URL="http://localhost:8080"
```

## 📊 验证部署

### 1. 健康检查
```bash
curl http://localhost:8000/health
```

预期响应:
```json
{
  "status": "healthy",
  "service": "ACMG-PS3 Intelligence System",
  "version": "2.0.0"
}
```

### 2. API文档
访问: http://localhost:8000/docs

### 3. 测试端点
```bash
# 创建测试任务
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "input_type": "Search_Query",
    "input_data": {}
  }'
```

## 🐳 Docker部署 (推荐)

### 1. 构建镜像
```bash
docker build -t acmg-ps3-backend .
```

### 2. 运行容器
```bash
docker run -d \
  --name acmg-backend \
  -p 8000:8000 \
  --env-file .env \
  acmg-ps3-backend
```

### 3. Docker Compose (完整栈)
```bash
docker-compose up -d
```

## 🔍 故障排查

### 问题1: 端口被占用
```bash
# 更改端口
export API_PORT=8001
python main.py
```

### 问题2: 数据库连接失败
```bash
# 检查数据库是否运行
docker ps | grep postgres
docker ps | grep neo4j
docker ps | grep milvus

# 查看日志
docker logs postgres
docker logs neo4j
docker logs milvus
```

### 问题3: LLM API调用失败
```bash
# 验证API密钥
echo $DEEPSEEK_API_KEY
echo $CLAUDE_API_KEY

# 测试连接
curl https://api.deepseek.com \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY"
```

### 问题4: 依赖安装失败
```bash
# 升级pip
pip install --upgrade pip

# 清理缓存重装
pip cache purge
pip install -e . --no-cache-dir
```

## 📈 生产环境部署

### 1. 使用Gunicorn + Uvicorn Workers
```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### 2. Nginx反向代理
```nginx
server {
    listen 80;
    server_name api.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. systemd服务
创建 `/etc/systemd/system/acmg-backend.service`:
```ini
[Unit]
Description=ACMG-PS3 Backend Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/acmg-backend
Environment="PATH=/opt/acmg-backend/venv/bin"
ExecStart=/opt/acmg-backend/venv/bin/python main.py

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl enable acmg-backend
sudo systemctl start acmg-backend
sudo systemctl status acmg-backend
```

## 📊 监控和日志

### 查看日志
```bash
# 实时日志
tail -f logs/app.log

# Docker日志
docker logs -f acmg-backend
```

### 性能监控
```bash
# CPU和内存使用
htop

# 请求统计
curl http://localhost:8000/api/stats
```

## 🔒 安全建议

1. **不要在.env中使用默认密码**
2. **生产环境启用HTTPS**
3. **配置CORS白名单**
4. **定期更新依赖**: `pip install --upgrade -r requirements.txt`
5. **启用API速率限制**
6. **使用环境变量管理敏感信息**

## 📞 获取帮助

- 查看日志: `docker logs acmg-backend`
- 运行检查: `python check_config.py`
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
