# ACMG-Lingua 部署配置

本目录包含 ACMG-Lingua 多语种文献证据提取平台的部署配置和运维脚本。

## 目录结构

```
deploy/
├── dev_start.sh          # 本地开发环境启动脚本
├── .work_logs.sh         # 工作日志脚本
├── docker/               # Docker 配置文件
└── README.md             # 本文件
```

## 快速开始

### 本地开发环境

使用 `dev_start.sh` 脚本快速启动开发环境：

```bash
# 赋予执行权限
chmod +x dev_start.sh

# 启动开发环境
./dev_start.sh
```

脚本会自动：
1. 检查系统依赖 (Docker, Docker Compose, uv, Node.js)
2. 检查项目目录结构
3. 检查端口占用情况 (8000, 5173)
4. 启动后端服务 (FastAPI + Celery, 端口 8000)
5. 启动前端服务 (Vite, 端口 5173)
6. 显示访问地址和调试信息

### 使用 Docker Compose

从项目根目录启动所有服务：

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止所有服务
docker-compose down
```

## 服务说明

### 后端服务 (FastAPI)

**端口**: 8000
**健康检查**: http://localhost:8000/health
**API 文档**: http://localhost:8000/docs

**环境变量**:
```env
# 数据库配置
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=admin
POSTGRES_PASSWORD=password
POSTGRES_DB=acmg_ps3

NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

QDRANT_HOST=qdrant
QDRANT_PORT=6333

REDIS_HOST=redis
REDIS_PORT=6379

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# 8 个专用 Agent 配置
# 1. 文献获取 Agent (retrieval)
RETRIEVAL_API_KEY=sk-xxx
RETRIEVAL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RETRIEVAL_MODEL=qwen3.5-flash

# 2. 文档解析 Agent (parsing)
PARSING_API_KEY=sk-xxx
PARSING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
PARSING_MODEL=qwen3.5-flash

# 3. 多语种翻译 Agent (mt)
MT_API_KEY=sk-xxx
MT_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MT_MODEL=qwen-mt-flash

# 4. 多功能排版 Agent (format)
FORMAT_API_KEY=sk-xxx
FORMAT_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
FORMAT_MODEL=qwen3.5-flash

# 5. 图片提取 Agent (vlm)
VLM_API_KEY=sk-xxx
VLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VLM_MODEL=qwen3-vl-flash
VLM_ENABLE=false

# 6. 证据提取 Agent (evidence)
EVIDENCE_API_KEY=sk-xxx
EVIDENCE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EVIDENCE_MODEL=qwen3.5-plus

# 7. ACMG 分类 Agent (classification)
CLASSIFICATION_API_KEY=sk-xxx
CLASSIFICATION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
CLASSIFICATION_MODEL=qwen3.5-plus

# 8. 专家裁决 Agent (arbitration)
ARBITRATION_API_KEY=sk-xxx
ARBITRATION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ARBITRATION_MODEL=qwen3-max

# Embedding 配置
EMBEDDING_PROVIDER=qwen  # qwen | nomic | openai
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-v4

# Rerank 配置
RERANK_MODEL=qwen3-rerank
RERANK_API_KEY=sk-xxx

# OCR 配置
OCR_PROVIDER=qwen
OCR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OCR_API_KEY=sk-xxx
OCR_MODEL=qwen-vl-ocr-latest

# MinerU 配置
MINERU_API_URL=https://mineru.net/api/v4/extract/task
MINERU_API_TOKEN=xxx

# 主力 LLM 配置（可选，用于通用任务）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 仲裁 LLM 配置（可选，用于复杂推理）
CLAUDE_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=https://api.anthropic.com
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

### 前端服务 (React + Vite)

**端口**: 5173
**代理配置**: 通过 Vite 代理访问后端 API

**环境变量**:
```env
VITE_API_BASE_URL=http://localhost:8000/api
```

### 数据库服务

#### PostgreSQL
- **端口**: 5432
- **数据卷**: postgres_data
- **初始化脚本**: ./init-scripts/

#### Neo4j
- **端口**: 7687 (Bolt), 7474 (Browser)
- **数据卷**: neo4j_data

#### Qdrant
- **端口**: 6333 (API), 6334 (Dashboard)
- **数据卷**: qdrant_data

#### Redis
- **端口**: 6379
- **数据卷**: redis_data

#### MinIO
- **端口**: 9000 (API), 9001 (Console)
- **数据卷**: minio_data
- **Console**: http://localhost:9001

## 部署模式

### 开发模式

特点：
- 代码热重载
- 详细日志输出
- 调试模式启用
- 使用本地数据库

启动命令：
```bash
./deploy/dev_start.sh
```

### 生产模式

特点：
- 代码优化编译
- 最小化日志输出
- 启用安全配置
- 使用远程数据库

部署步骤：
1. 配置生产环境变量
2. 构建前端应用
3. 启动后端服务 (使用 Gunicorn/Uvicorn)
4. 配置 Nginx 反向代理
5. 配置 SSL 证书

## 环境变量管理

### 环境文件

创建 `.env` 文件（基于 `.env.example`）：

```bash
# 后端
cd apps/backend
cp .env.example .env
vim .env

# 前端
cd apps/frontend
cp .env.local.example .env.local
vim .env.local
```

### 敏感信息管理

**不要**将以下信息提交到版本控制：
- API 密钥 (LLM API, 数据库密码)
- 私钥和证书
- 个人访问令牌

使用 `.gitignore` 排除敏感文件：
```
.env
.env.local
*.pem
*.key
```

## 日志管理

### 日志位置

- **后端日志**: `backend.log` (开发模式)
- **前端日志**: `frontend.log` (开发模式)
- **Docker 日志**: `docker-compose logs`

### 日志级别

```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 日志轮转

生产环境建议配置日志轮转：
```bash
# 使用 logrotate
sudo vim /etc/logrotate.d/acmg-lingua
```

## 监控和告警

### 健康检查端点

| 端点 | 说明 |
|------|------|
| `/health` | 整体健康状态 |
| `/health/db` | 数据库连接状态 |
| `/health/redis` | Redis 连接状态 |
| `/health/minio` | MinIO 连接状态 |

### 指标收集

建议集成 Prometheus + Grafana 进行监控：
- API 响应时间
- 数据库查询性能
- 任务队列长度
- LLM API 调用次数

## 备份策略

### 数据库备份

```bash
# PostgreSQL 备份
docker exec mdecp_postgres pg_dump -U admin mdecp_dev > backup.sql

# PostgreSQL 恢复
docker exec -i mdecp_postgres psql -U admin mdecp_dev < backup.sql
```

### 对象存储备份

定期备份 MinIO 数据卷：
```bash
# 备份 MinIO 数据
tar -czf minio-backup-$(date +%Y%m%d).tar.gz /var/lib/docker/volumes/minio_data
```

## 故障排查

### 常见问题

1. **服务无法启动**
   ```bash
   # 检查端口占用
   lsof -i :8000
   lsof -i :5173
   
   # 查看 Docker 日志
   docker-compose logs backend
   docker-compose logs frontend
   ```

2. **数据库连接失败**
   ```bash
   # 检查数据库容器状态
   docker-compose ps
   
   # 测试数据库连接
   docker exec mdecp_postgres psql -U admin -c "SELECT 1"
   ```

3. **LLM API 调用失败**
   - 检查 API 密钥配置
   - 检查网络连接
   - 查看 API 限额状态

### 调试技巧

1. **启用调试模式**
   ```env
   DEBUG=true
   LOG_LEVEL=DEBUG
   ```

2. **查看实时日志**
   ```bash
   tail -f backend.log frontend.log
   ```

3. **使用 curl 测试 API**
   ```bash
   curl http://localhost:8000/health
   curl -X POST http://localhost:8000/api/pdf/upload -F "file=@test.pdf"
   ```

## 安全建议

### 生产环境配置

1. **使用强密码**
   - 数据库密码至少 16 位
   - 定期更换 API 密钥

2. **启用 HTTPS**
   - 配置 SSL 证书
   - 强制 HTTPS 重定向

3. **限制访问**
   - 配置防火墙规则
   - 使用 VPC 隔离数据库

4. **最小权限原则**
   - 数据库账号限制最小权限
   - 分离读写账号

## 性能优化

### 数据库优化

1. **PostgreSQL**
   - 配置连接池
   - 创建必要索引
   - 定期 VACUUM

2. **Qdrant**
   - 配置合适的向量维度
   - 使用 HNSW 索引
   - 定期优化集合

### 缓存策略

1. **Redis 缓存**
   - PDF 哈希缓存
   - 任务状态缓存
   - LLM 响应缓存

2. **前端缓存**
   - 静态资源 CDN
   - API 响应缓存
   - 组件级缓存

## 相关文档

- [项目根目录 README](../README.md)
- [后端 README](../apps/backend/README.md)
- [前端 README](../apps/frontend/README.md)
- [数据库统一管理](../apps/backend/database/README.md)
- [数据库 compose 配置](../apps/backend/database/podman-compose.yml)

---

**最后更新**: 2026-03-22 (v3.0)
