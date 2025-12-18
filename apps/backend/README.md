# ACMG-PS3 智能评级系统 - 后端服务 v2.0

基于 GraphRAG 与 LangGraph 的变异致病性智能分类系统（四层架构：Controller / Service / Domain / Repository）。

## 🎯 技术栈

| 组件 | 技术选型 |
|:-----|:---------|
| **后端框架** | **FastAPI** |
| **Agent框架** | **LangGraph** |
| **主力LLM** | **DeepSeek-V3.2** |
| **仲裁LLM** | **Claude 3.5 Sonnet/Opus**|
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

### LLM 双模式架构 (v2.1.0+)

本系统采用**双LLM协作**架构，结合不同模型的优势：

- **主力模型 - DeepSeek-V3.2** (Anthropic兼容格式)
  - 快速响应，成本经济
  - 用于：实体提取、证据初步验证、Cypher查询生成
  - API格式：Anthropic标准消息格式
  
- **仲裁模型 - Claude 3.5 Sonnet/Opus** (Anthropic原生格式)
  - 复杂推理能力强
  - 用于：最终ACMG评级决策、证据冲突仲裁、高风险判断
  - API格式：Anthropic原生消息格式

**关键特性**：
- ✅ 统一Anthropic消息格式
- ✅ 双LLM共识机制（一致采纳，不一致仲裁）
- ✅ 灵活配置（支持单独或组合使用）
- ✅ 完整的异步API支持

**使用示例**：
```python
from src.service.llm_service import LLMService, LLMProvider

# 配置双LLM (统一Anthropic格式)
config = {
    "deepseek_api_key": "sk-xxx",    # DeepSeek (Anthropic兼容)
    "claude_api_key": "sk-ant-xxx"   # Claude (Anthropic原生)
}
service = LLMService(llm_config=config)

# 快速任务用DeepSeek
entities = await service.extract_entities(text, ["Gene", "Variant"])

# 关键决策用Claude
rating = await service.generate_final_rating(evidence, gene, variant)
```

详细文档：[src/service/LLM_SERVICE_GUIDE.md](src/service/LLM_SERVICE_GUIDE.md)

### 解析模式

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
    - DeepSeek (Anthropic兼容): 主力模型，用于快速任务
    - Claude (Anthropic原生): 仲裁模型，用于关键决策
    - 双LLM协作与共识机制
    - 统一Anthropic消息格式

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

- **LLM服务指南**: [src/service/LLM_SERVICE_GUIDE.md](src/service/LLM_SERVICE_GUIDE.md) - 详细的LLM使用文档
- **LLM更新总结**: [LLM_SERVICE_UPDATE_SUMMARY.md](LLM_SERVICE_UPDATE_SUMMARY.md) - v2.1.0更新说明
- **部署指南**: [DEPLOYMENT.md](DEPLOYMENT.md) - 生产环境部署文档
- **API 文档**: http://localhost:8000/docs - 交互式API文档
- **Qdrant 文档**: https://qdrant.tech/documentation/ - 向量数据库文档
- **Anthropic API**: https://docs.anthropic.com/ - Claude API官方文档
- **DeepSeek API**: https://platform.deepseek.com/docs - DeepSeek API文档

## 🔧 配置

所有配置通过环境变量管理，详见 `.env.example`

### LLM API密钥配置

系统需要配置双LLM的API密钥：

```bash
# 1. 复制配置模板
cp .env.example .env

# 2. 编辑配置文件，添加API密钥
vim .env
```

必需的配置项：

```env
# DeepSeek (主力LLM - Anthropic兼容格式)
DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"
DEEPSEEK_BASE_URL="https://api.deepseek.com"

# Claude (仲裁LLM - Anthropic原生格式)
CLAUDE_API_KEY="sk-ant-xxxxxxxxxxxxxxxx"
CLAUDE_MODEL="claude-3-5-sonnet-20241022"
```

**获取API密钥**：
- DeepSeek: https://platform.deepseek.com/
- Claude: https://console.anthropic.com/

**可选配置**：
- 如果只使用DeepSeek，可以不配置Claude密钥
- 如果只使用Claude，可以不配置DeepSeek密钥
- 推荐配置双LLM以获得最佳性能

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

## 📝 更新日志

### v2.1.0 (2024-12-18)
**LLM服务重大升级 - 自定义Anthropic格式支持**

✨ 新特性：
- ✅ 采用Anthropic Python SDK统一格式
- ✅ 统一Anthropic消息格式（兼容DeepSeek和Claude）
- ✅ 完整的DeepSeek (Anthropic兼容) + Claude (Anthropic原生) 双LLM架构
- ✅ 双LLM共识机制实现
- ✅ 专用方法封装（实体提取、证据验证、最终评级等）
- ✅ 完善的异步API支持和错误处理

🔧 技术改进：
- 使用`anthropic.AsyncAnthropic`统一客户端
- 统一Anthropic消息格式（DeepSeek和Claude）
- System消息独立处理符合Anthropic规范
- 消息序列验证和自动修正
- 详细的API调用日志

📚 文档更新：
- 新增 [LLM_SERVICE_GUIDE.md](src/service/LLM_SERVICE_GUIDE.md) - 完整使用指南
- 新增 [LLM_SERVICE_UPDATE_SUMMARY.md](LLM_SERVICE_UPDATE_SUMMARY.md) - 更新总结
- 新增 [llm_service_example.py](src/service/llm_service_example.py) - 代码示例
- 更新 `.env.example` - LLM配置说明

📦 依赖更新：
- `anthropic>=0.39.0` - 统一使用Anthropic SDK
- `requests>=2.32.5` - HTTP客户端

🔗 相关链接：
- [详细更新文档](LLM_SERVICE_UPDATE_SUMMARY.md)
- [使用指南](src/service/LLM_SERVICE_GUIDE.md)

### v2.0.0
初始版本，基于GraphRAG和LangGraph的ACMG-PS3智能评级系统
