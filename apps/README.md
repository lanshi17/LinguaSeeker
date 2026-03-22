# ACMG-PS3 智能评级系统 - 应用层

本目录包含 ACMG-PS3 智能评级系统的所有应用程序代码，采用多应用架构设计。

## 目录结构

```
apps/
├── backend/          # 后端服务 (FastAPI + LangGraph Agent)
├── frontend/         # 前端 Web 应用 (React + TypeScript)
└── README.md         # 本文件
```

## 各应用说明

### 1. backend/ - 后端服务

**技术栈**:
- FastAPI (Web 框架)
- LangGraph (Agent 编排)
- DeepSeek-V3.2 + Claude 3.5 (双 LLM 协作)
- Celery (异步任务)
- PostgreSQL + Neo4j + Qdrant + Redis + MinIO (数据存储)

**主要功能**:
- PDF 文档上传和解析
- 多语种文献获取 (PubMed/Firecrawl)
- 实体抽取和证据验证
- ACMG-PS3 证据标准智能评级
- 知识图谱构建和查询
- 流式任务状态推送

**快速开始**:
```bash
cd apps/backend
uv sync
uv run python main.py
```

**详细文档**: [backend/README.md](backend/README.md)

### 2. frontend/ - 前端 Web 应用

**技术栈**:
- React 19 + TypeScript
- Ant Design 6 (UI 组件库)
- React Router DOM (路由)
- Zustand (状态管理)
- D3.js (数据可视化)
- Vite (构建工具)

**主要功能**:
- PDF 文档上传界面
- 任务状态实时监控
- 证据检索和可视化
- 基因关联分析展示
- 共现矩阵和证据链展示
- 分析结果下载

**快速开始**:
```bash
cd apps/frontend
npm install
npm run dev
```

**详细文档**: [frontend/README.md](frontend/README.md)

## 应用间通信

### API 接口

前端通过 HTTP API 与后端通信：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/pdf/upload` | POST | PDF 上传 |
| `/api/pdf/check_hash` | GET | PDF 哈希检查 |
| `/api/tasks` | POST | 创建任务 |
| `/api/stream/{task_id}` | GET | 流式任务状态 |
| `/api/evidence/search` | POST | 证据检索 |
| `/api/graph/nl-query` | POST | 图谱自然语言查询 |

### 数据流

```
用户操作 (Frontend)
  → HTTP API (Backend API Layer)
    → Controller (Presentation Layer)
      → Service (Application Layer)
        → Agent Workflow (Domain Layer)
          → Infrastructure (Database/Storage)
```

## 开发工作流

### 1. 本地开发环境

推荐使用 Docker Compose 启动所有依赖服务：

```bash
# 从项目根目录
docker-compose up -d
```

### 2. 前后端联调

1. 启动后端服务 (端口 8000)
2. 启动前端开发服务器 (端口 5173)
3. 前端通过 Vite 代理访问后端 API

### 3. 环境变量配置

**后端** (`apps/backend/.env`):
```env
# 数据库
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
NEO4J_URI=bolt://localhost:7687
QDRANT_HOST=localhost
REDIS_HOST=localhost
MINIO_ENDPOINT=localhost:9000

# LLM API
DEEPSEEK_API_KEY=sk-xxx
CLAUDE_API_KEY=sk-ant-xxx
```

**前端** (`apps/frontend/.env.local`):
```env
VITE_API_BASE_URL=http://localhost:8000/api
```

## 架构原则

### 1. 六边形架构 (Hexagonal Architecture)

后端采用六边形架构，核心特点：
- **领域层** (Domain): 纯业务逻辑，无技术依赖
- **应用层** (Application): 业务流程编排
- **基础设施层** (Infrastructure): 外部依赖实现
- **API 层** (API): HTTP 接口适配

### 2. 领域驱动设计 (DDD)

按子域划分代码：
- **Agent 子域**: Agent 工作流编排
- **证据子域**: 证据聚合、分类、评估
- **文献子域**: 文献获取和解析
- **图谱子域**: 知识图谱操作
- **变异子域**: 变异信息查询

### 3. Agent 协作模式

采用 LangGraph 实现多 Agent 协作：
- **获取 Agent**: 文献获取 (PubMed/Firecrawl)
- **解析 Agent**: PDF 解析和翻译
- **抽取 Agent**: 实体抽取和验证
- **推理 Agent**: 证据推理
- **仲裁 Agent**: ACMG 评级仲裁
- **交互 Agent**: 用户交互和澄清

## 测试策略

### 后端测试

```bash
cd apps/backend
uv run pytest tests/
```

测试分类：
- **单元测试**: 测试纯函数和工具类
- **集成测试**: 测试数据库和外部服务交互
- **端到端测试**: 测试完整 Agent 工作流

### 前端测试

```bash
cd apps/frontend
npm run test
```

测试分类：
- **组件测试**: 测试 React 组件渲染
- **集成测试**: 测试组件间交互
- **E2E 测试**: 测试完整用户流程

## 部署说明

### 开发环境

使用 `docker-compose.yml` 启动所有服务：
```bash
docker-compose up -d
```

### 生产环境

参考 [deploy/](../deploy/) 目录中的部署脚本和配置。

## 故障排查

### 常见问题

1. **后端启动失败**
   - 检查 `.env` 配置文件
   - 确认数据库连接正常
   - 查看 `backend.log` 日志

2. **前端无法连接后端**
   - 检查 `VITE_API_BASE_URL` 配置
   - 确认 CORS 设置正确
   - 查看浏览器控制台网络请求

3. **Agent 工作流卡住**
   - 检查 Celery Worker 是否运行
   - 查看 Redis 任务队列状态
   - 检查 LLM API 密钥有效性

## 相关文档

- [后端 README](backend/README.md)
- [前端 README](frontend/README.md)
- [部署指南](../deploy/)
- [API 文档](http://localhost:8000/docs)

---

**最后更新**: 2026-03-22
