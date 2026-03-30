# ACMG-Lingua 多语种文献证据提取平台

## 项目简介

ACMG-Lingua 是一个基于 **GraphRAG** 与 **LangGraph** 的多语种文献证据智能提取平台，采用 **六边形架构（Hexagonal Architecture）** 和 **领域驱动设计（DDD）**，旨在帮助研究人员从不同语言的学术文献中自动提取和整理 ACMG-PS3 证据标准的变异致病性证据。

## 核心特性

- 🌍 **多语种支持**: 支持中文、英文等多语种文献的自动翻译和证据提取
- 🤖 **8 个专用 LLM Agent**: 每个 Agent 独立配置，针对特定任务优化
- 📊 **GraphRAG 增强**: 基于知识图谱的检索增强生成，提升证据质量
- 🔄 **实时流式推送**: 基于 Celery + Redis 的异步任务处理和状态推送
- 📈 **可视化分析**: 基因关联、共现矩阵、证据链等可视化展示
- 🔍 **智能检索**: 支持自然语言查询的知识图谱检索

## 技术架构

### 架构模式

- **六边形架构（Hexagonal Architecture）**: 端口 - 适配器模式，业务逻辑与技术实现解耦
- **领域驱动设计（DDD）**: 按子域划分代码，限界上下文管理复杂业务
- **多 Agent 协作**: 基于 LangGraph 的多 Agent 工作流编排

### 技术栈

| 层次 | 技术选型 |
|------|---------|
| **前端** | React 19 + TypeScript + Ant Design 6 + D3.js + Vite |
| **后端框架** | FastAPI + Celery + Redis |
| **Agent 编排** | LangGraph |
| **LLM 架构** | 8 个专用 Agent (Qwen 系列) + 主力/仲裁双 LLM (可选) |
| **PDF 解析** | MinerU (API/Local) |
| **向量嵌入** | Qwen/Nomic/OpenAI Embedding |
| **重排序** | Qwen3-rerank |
| **图数据库** | Neo4j |
| **向量数据库** | Qdrant |
| **关系数据库** | PostgreSQL |
| **缓存** | Redis |
| **对象存储** | MinIO |
| **依赖管理** | uv (Python), npm (Node.js) |

## 目录结构

```
01_ACMG_Lingua/
├── README.md                     # 本文件 - 项目入口说明书
├── docker-compose.yml            # 本地开发环境编排
├── LICENSE                       # 开源许可证
├── acmg_lingua_c4_model.puml    # C4 架构模型图
│
├── apps/                         # 应用程序代码
│   ├── README.md                 # 应用层说明
│   ├── backend/                  # 后端服务 (FastAPI + LangGraph)
│   │   ├── README.md             # 后端详细文档
│   │   ├── main.py               # 应用入口
│   │   ├── pyproject.toml        # 依赖配置
│   │   └── src/
│   │       ├── api/              # API 层 - HTTP 路由
│   │       ├── application/      # 应用层 - 业务编排
│   │       ├── domain/           # 领域层 - 核心业务逻辑
│   │       ├── infrastructure/   # 基础设施层 - 外部依赖
│   │       ├── agents/           # Agent 编排层 - LangGraph 工作流
│   │       ├── tools/            # 工具层 - 外部服务封装
│   │       ├── knowledge/        # 知识层 - Prompt 和本体
│   │       ├── state/            # 状态管理
│   │       ├── utils/            # 工具类
│   │       └── config.py         # 配置管理
│   └── frontend/                 # 前端 Web 应用 (React + TypeScript)
│       ├── README.md             # 前端详细文档
│       ├── package.json
│       └── src/
│
├── deploy/                       # 部署配置和运维脚本
│   ├── README.md                 # 部署指南
│   ├── dev_start.sh              # 本地开发启动脚本
│   └── docker/                   # Docker 配置
│
└── docs/                         # 技术文档中心
    ├── README.md                 # 文档中心说明
    └── plans/                    # 实施计划文档
```

## 快速开始

### 环境要求

- **Python**: >= 3.12
- **Node.js**: >= 18.x
- **Docker**: >= 20.x
- **Docker Compose**: >= 2.x
- **uv**: Python 包管理工具（推荐）

### 1. 克隆项目

```bash
git clone <repository-url>
cd 01_ACMG_Lingua
```

### 2. 配置环境变量

```bash
# 后端配置
cd apps/backend
cp .env.example .env
vim .env  # 编辑 API 密钥和数据库配置
```

**必需的配置**（8 个 Agent）：
```env
# Qwen Agent 配置
RETRIEVAL_API_KEY="sk-xxx"
PARSING_API_KEY="sk-xxx"
MT_API_KEY="sk-xxx"
FORMAT_API_KEY="sk-xxx"
VLM_API_KEY="sk-xxx"
EVIDENCE_API_KEY="sk-xxx"
CLASSIFICATION_API_KEY="sk-xxx"
ARBITRATION_API_KEY="sk-xxx"

# 数据库配置
POSTGRES_HOST=localhost
NEO4J_URI=bolt://localhost:7687
QDRANT_HOST=localhost
REDIS_HOST=localhost
MINIO_ENDPOINT=localhost:9000
```

### 3. 安装依赖

```bash
# 后端（使用 uv）
cd apps/backend
uv sync

# 前端
cd apps/frontend
npm install
```

### 4. 启动服务

```bash
# 方式 1: 使用 Docker Compose（推荐）
# 从项目根目录
docker-compose up -d

# 方式 2: 本地开发启动
# 从项目根目录
./deploy/dev_start.sh

# 方式 3: 手动启动
# 后端
cd apps/backend
uv run python main.py

# 前端
cd apps/frontend
npm run dev
```

### 5. 访问应用

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端** | http://localhost:5173 | React Web 应用 |
| **后端 API** | http://localhost:8000 | FastAPI RESTful API |
| **API 文档** | http://localhost:8000/docs | Swagger/OpenAPI |
| **健康检查** | http://localhost:8000/health | 健康状态检查 |
| **MinIO Console** | http://localhost:9001 | 对象存储管理 |

## LLM 架构

### 8 个专用 Agent

系统采用 **8 个专用 LLM Agent** 架构，每个 Agent 独立配置，针对特定任务优化：

| # | Agent | 职责 | 默认模型 | 配置项 |
|---|-------|------|----------|--------|
| 1 | **retrieval** | 文献获取 (PubMed/Firecrawl) | qwen3.5-flash | `RETRIEVAL_*` |
| 2 | **parsing** | PDF 解析与结构提取 | qwen3.5-flash | `PARSING_*` |
| 3 | **mt** | 多语种文档翻译 | qwen-mt-flash | `MT_*` |
| 4 | **format** | 文档排版与格式化 | qwen3.5-flash | `FORMAT_*` |
| 5 | **vlm** | 图片内容理解 | qwen3-vl-flash | `VLM_*` (可选) |
| 6 | **evidence** | 证据记录抽取 | qwen3.5-plus | `EVIDENCE_*` |
| 7 | **classification** | ACMG 证据分类 | qwen3.5-plus | `CLASSIFICATION_*` |
| 8 | **arbitration** | ACMG 最终评级仲裁 | qwen3-max | `ARBITRATION_*` |

### 主力/仲裁 LLM（可选）

除了 8 个专用 Agent，系统还支持配置主力和仲裁 LLM 用于特定场景：

| 角色 | 默认提供商 | 默认模型 | 配置项 |
|------|-----------|----------|--------|
| **主力 LLM** | DeepSeek | deepseek-chat | `DEEPSEEK_*` |
| **仲裁 LLM** | Claude | claude-3-5-sonnet | `CLAUDE_*` |

### 其他 LLM 配置

| 组件 | 配置项 | 默认值 |
|------|--------|--------|
| **Embedding** | `EMBEDDING_*` | qwen / text-embedding-v4 |
| **Rerank** | `RERANK_*` | qwen3-rerank |
| **OCR** | `OCR_*` | qwen / qwen-vl-ocr-latest |
| **MinerU** | `MINERU_*` | MinerU API |

## 主要 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/documents/upload` | POST | PDF 文档上传 |
| `/api/tasks` | POST | 创建任务 |
| `/api/stream/{task_id}` | GET | 流式任务状态 |
| `/api/evidence/search` | POST | 证据检索 |
| `/api/graph/nl-query` | POST | 图谱自然语言查询 |
| `/api/variants/query` | POST | 变异评级查询 |

完整 API 文档：http://localhost:8000/docs

## Agent 工作流

```
用户请求
  ↓
interaction (交互 Agent) - 分析需求，提取基因/变异
  ↓
acquisition (获取 Agent) - PubMed/Firecrawl 文献检索
  ↓
parsing (解析 Agent) - PDF 解析 + translation (翻译)
  ↓
extraction (抽取 Agent) - 实体抽取和证据验证
  ↓
reasoning (推理 Agent) - 证据推理分析
  ↓
arbitration (仲裁 Agent) - ACMG 评级仲裁
  ↓
finalize - 生成报告
  ↓
END
```

## 开发工作流

### 前后端联调

1. 启动后端服务（端口 8000）
2. 启动前端开发服务器（端口 5173）
3. 前端通过 Vite 代理访问后端 API

### 环境变量配置

**后端** (`apps/backend/.env`):
```env
# 数据库
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
NEO4J_URI=bolt://localhost:7687
QDRANT_HOST=localhost
REDIS_HOST=localhost
MINIO_ENDPOINT=localhost:9000

# 8 个 Agent API 密钥
RETRIEVAL_API_KEY=sk-xxx
PARSING_API_KEY=sk-xxx
# ... 其他 Agent
```

**前端** (`apps/frontend/.env.local`):
```env
VITE_API_BASE_URL=http://localhost:8000/api
```

### 测试

```bash
# 后端测试
cd apps/backend
uv run pytest tests/

# 前端测试
cd apps/frontend
npm run test
```

## 部署

### 开发环境

使用 Docker Compose 启动所有服务：
```bash
docker-compose up -d
```

### 生产环境

参考 [deploy/README.md](deploy/README.md) 获取完整部署指南。

**关键配置**：
- 使用远程数据库（非 localhost）
- 启用 HTTPS/TLS
- 配置强密码和最小权限
- 启用日志和监控
- 配置备份策略

## 文档

| 文档 | 位置 |
|------|------|
| **后端文档** | [apps/backend/README.md](apps/backend/README.md) |
| **前端文档** | [apps/frontend/README.md](apps/frontend/README.md) |
| **部署指南** | [deploy/README.md](deploy/README.md) |
| **文档中心** | [docs/README.md](docs/README.md) |
| **C4 模型** | [acmg_lingua_c4_model.puml](acmg_lingua_c4_model.puml) |

## 架构演进

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **v3.0** | 2026-03-22 | 8 个专用 Agent 架构，Qwen 系列模型 |
| **v2.1** | 2024-12-18 | 双 LLM 共识机制，Anthropic 格式统一 |
| **v2.0** | 2024-12-01 | 初始版本，GraphRAG + LangGraph |

## 故障排查

### 常见问题

1. **后端启动失败**
   - 检查 `.env` 配置文件
   - 确认数据库连接正常
   - 查看日志 `docker-compose logs backend`

2. **前端无法连接后端**
   - 检查 `VITE_API_BASE_URL` 配置
   - 确认 CORS 设置正确
   - 检查浏览器控制台网络请求

3. **Agent 工作流卡住**
   - 检查 Celery Worker 状态
   - 查看 Redis 任务队列
   - 验证 LLM API 密钥有效性

### 调试技巧

```bash
# 启用调试模式
DEBUG=true
LOG_LEVEL=DEBUG

# 查看实时日志
docker-compose logs -f

# 测试 API
curl http://localhost:8000/health
```

## 贡献指南

1. Fork 项目
2. 创建功能分支：`git checkout -b feature/xxx`
3. 提交变更：`git commit -m 'feat: add xxx'`
4. 推送分支：`git push origin feature/xxx`
5. 创建 Pull Request

## 许可证

本项目采用 [MIT](LICENSE) 许可证。

## 团队成员

如有问题，请联系团队成员或提交 Issue。

---

**最后更新**: 2026-03-22 (v3.0)
