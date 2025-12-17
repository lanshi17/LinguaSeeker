# ACMG-PS3 智能评级系统 - 后端服务 v2.0

基于 GraphRAG 与 LangGraph 的变异致病性智能分类系统（四层架构：Controller / Service / Domain / Repository）。

## 🎯 技术栈

| 组件 | 技术选型 |
|:-----|:---------|
| **后端框架** | **FastAPI** |
| **Agent框架** | **LangGraph** |
| **主力LLM** | **DeepSeek-V3.2** |
| **仲裁LLM** | **Claude Opus 4.5** |
| **PDF解析** | **MinerU** |
| **图数据库** | **Neo4j** |
| **向量数据库** | **Qdrant（默认）** |
| **关系型数据库** | **PostgreSQL** |
| **对象存储** | **MinIO** |

## 🚀 快速开始

### 1. 安装依赖
```bash
# 复制环境变量配置
cp .env.example .env

# 编辑配置文件
vim .env

# 安装依赖
pip install -e .

# 检查配置
python check_config.py
```

### 2. 启动服务
```bash
# 方式1: 使用启动脚本
chmod +x start.sh
./start.sh

# 方式2: 直接运行
python main.py
```

### 3. 访问服务
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 🔄 LLM 与解析模式

- **LLM模式**：支持 OpenAI 兼容 API（前期）与本地部署（后期），采用主力模型（DeepSeek）+ 仲裁模型（Claude）协作。
- **解析模式**：MinerU（Magic-PDF）支持 API 调用（前期）与本地部署（后期）。

## 📁 项目结构

本项目采用**四层架构设计**：

```
backend/
├── main.py                 # 应用入口
├── pyproject.toml         # 项目配置和依赖
└── src/
    ├── controller/        # Controller/Web层 - 接收HTTP请求
    │   ├── task_controller.py
    │   ├── document_controller.py
    │   ├── variant_controller.py
    │   ├── report_controller.py
    │   └── graph_controller.py
    │
    ├── service/          # Service层 - 业务逻辑和应用服务
    │   ├── parser_service.py              # P1.0 智能解析
    │   ├── graph_builder_service.py       # P2.0 图谱构建
    │   ├── reasoning_service.py           # P3.0 循环推理
    │   ├── task_orchestration_service.py  # 任务编排
    │   └── llm_service.py                 # LLM调用封装
    │
    ├── domain/           # Domain/Entity层 - 领域模型和核心业务逻辑
    │   ├── entities/                      # 实体
    │   │   ├── task.py                    # 任务实体
    │   │   ├── report.py                  # 报告实体
    │   │   ├── graph_entities.py          # 图数据库实体
    │   │   └── vector_entity.py           # 向量实体
    │   └── value_objects/                 # 值对象
    │       └── rating.py                  # 评级结果值对象
    │
    ├── repository/       # Repository/Dao层 - 数据持久化
    │   ├── postgresql_repository.py       # PostgreSQL仓储
    │   ├── neo4j_repository.py            # Neo4j图数据库仓储
    │   ├── qdrant_repository.py           # Qdrant向量数据库仓储（默认）
    │   └── milvus_repository.py           # Milvus向量数据库仓储（可选）
    │
    ├── config/           # 配置管理
    │   ├── app_config.py                 # 应用配置
    │   └── database_config.py            # 数据库配置
    │
    └── utils/            # 工具类
        ├── logger.py                     # 日志工具
        ├── exceptions.py                 # 异常定义
        ├── validators.py                 # 数据验证
        ├── text_processor.py             # 文本处理
        └── container.py                  # 依赖注入容器
```

## 架构说明

### 1. Controller/Web层
- 职责：接收HTTP请求，参数验证，调用Service层，返回响应
- 文件：
  - `task_controller.py`: 任务管理API
  - `document_controller.py`: 文档上传和解析API
  - `variant_controller.py`: 变异查询和评级API
  - `report_controller.py`: 报告查询和导出API
  - `graph_controller.py`: 知识图谱查询API

### 2. Service层
- 职责：实现业务逻辑，协调多个领域服务和数据访问
- 对应DFD的三个主要流程：
  - **P1.0 智能解析** (`parser_service.py`)
    - 接收上传（PDF/PMID）
    - MinerU解析（PDF → Markdown）
    - 数据分块与向量化
  
  - **P2.0 图谱构建** (`graph_builder_service.py`)
    - 实体抽取（Gene, Variant, Method, Evidence）
    - 关系构建（创建Neo4j节点和边）
  
  - **P3.0 循环推理** (`reasoning_service.py`)
    - 查询生成/规划
    - 混合检索（Graph + Vector）
    - 证据验证与评分
    - 评级决策

  - **任务编排** (`task_orchestration_service.py`)
    - 协调上述三个流程的完整工作流

  - **LLM服务** (`llm_service.py`)
    - 支持 OpenAI 兼容 API（前期）与本地部署（后期），DeepSeek/Claude 协作调用

### 3. Domain/Entity层
- 职责：定义核心业务模型和数据结构
- 实体：
  - `Task`: 任务实体（PostgreSQL）
  - `Report`: 报告实体（PostgreSQL）
  - `Paper/Gene/Variant/Evidence`: 图数据库节点（Neo4j）
  - `VectorDocument`: 向量文档（Qdrant/Milvus）
- 值对象：
  - `RatingResult`: 评级结果
  - `EvidenceLevel`: 证据等级枚举

### 4. Repository/Dao层
- 职责：数据持久化操作，封装数据库访问
- 三个数据源：
  - **PostgreSQL** (`postgresql_repository.py`)
    - 存储任务状态和报告
  - **Neo4j** (`neo4j_repository.py`)
    - 存储知识图谱（Paper-Gene-Variant-Evidence关系）
  - **Qdrant** (`qdrant_repository.py`)
    - 默认向量库，存储文本向量，支持语义检索
  - **Milvus** (`milvus_repository.py`)
    - 备用向量库，可按需切换

## 数据流转

```
用户请求 
  → Controller (参数验证)
    → Service (业务逻辑)
      → Repository (数据访问)
        → 数据库 (PostgreSQL / Neo4j / Qdrant/Milvus)
```

## 技术栈

## 📚 文档与参考

- 部署指南: 见 [DEPLOYMENT.md](DEPLOYMENT.md)
- API 文档: http://localhost:8000/docs
- Qdrant 文档: https://qdrant.tech/documentation/

## 🔧 配置

所有配置通过环境变量管理，详见 `.env.example`

## 🧭 服务-数据分离（重点）

生产环境中，建议将服务与数据严格分离：
- 数据库（PostgreSQL/Neo4j/Qdrant/Milvus/MinIO）部署在云或独立主机，不与应用服务同机。
- 应用仅通过内网或安全公网连接远程数据库，避免 `localhost` 生产使用。
- 在 `.env` 中使用远程主机名或地址，例如：

```env
# PostgreSQL（示例）
POSTGRES_HOST="db.postgres.example.com"
POSTGRES_PORT="5432"

# Neo4j（示例）
NEO4J_URI="bolt://neo4j.example.com:7687"

# Qdrant（示例）
QDRANT_HOST="qdrant.example.com"
QDRANT_PORT="6333"

# MinIO（示例）
MINIO_ENDPOINT="minio.example.com:9000"
```

安全建议：
- 使用强密码与专用数据库账号，限制最小权限。
- 通过 VPC/私有网络或 VPN 访问数据库。
- 为 MinIO/对象存储启用 TLS（`MINIO_SECURE=true`）。
- 不在生产环境中启用 `DEBUG`，并限制开放端口。

## 📊 主要API端点

- `POST /api/tasks` - 创建任务
- `POST /api/documents/upload` - 上传PDF
- `POST /api/variants/query` - 查询变异评级
- `POST /api/graph/nl-query` - 自然语言查询图谱

完整文档: http://localhost:8000/docs
