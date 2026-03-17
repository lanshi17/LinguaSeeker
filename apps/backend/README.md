# ACMG-PS3 智能评级系统 - 后端服务 v2.1

基于 GraphRAG 与 LangGraph 的变异致病性智能分类系统（六边形架构：API / Application / Domain / Infrastructure）。

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
| **缓存** | **Redis** |
| **异步任务** | **Celery** |
| **架构模式** | **六边形架构（Hexagonal Architecture）** |
| **领域驱动设计** | **DDD（Domain-Driven Design）** |
| **依赖管理** | **uv** |
| **语言检测** | **lingua-language-detector** |

## 🚀 快速开始

### 1. 安装依赖（使用 uv）
```bash
# 复制环境变量配置
cp .env.example .env

# 编辑配置文件
vim .env

# 安装依赖
uv sync

# 检查配置
uv run python check_config.py
```

### 2. 启动服务（使用 uv）
```bash
# 推荐方式：使用主入口
uv run python main.py

# 注意：app.py 是旧版入口，已废弃
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
from src.application.services.llm_service import LLMService

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

详细文档：[src/application/services/llm_service.py](src/application/services/llm_service.py)

### 解析模式

- **MinerU（Magic-PDF）**：支持 API 调用（前期）与本地部署（后期）
- **适配器模式**：通过 `src/infrastructure/adapters/mineru/` 实现解耦

## 📁 项目结构

本项目采用**六边形架构（Hexagonal Architecture）**，遵循 DDD（领域驱动设计）原则：

```
backend/
├── main.py                 # 应用入口（FastAPI）- 推荐使用
├── app.py                  # 旧版入口（已废弃，建议删除）
├── pyproject.toml          # 项目配置和依赖
└── src/
    ├── api/                # API层 - HTTP路由和依赖注入
    │   ├── routes/         # 路由定义
    │   │   ├── core.py     # 核心路由
    │   │   ├── task.py     # 任务路由
    │   │   ├── evidence.py # 证据路由
    │   │   └── stream.py   # 流式路由
    │   └── dependencies.py # 依赖注入和错误处理
    │
    ├── presentation/       # 表现层 - 控制器
    │   ├── upload_controller.py
    │   ├── task_controller.py
    │   └── base_controller.py
    │
    ├── application/        # 应用层 - 业务流程编排
    │   ├── services/       # 应用服务
    │   │   ├── document_service.py     # 文档处理服务
    │   │   ├── embedding_service.py    # 向量化服务
    │   │   ├── llm_service.py          # LLM服务
    │   │   ├── rerank_service.py       # 重排序服务
    │   │   └── base_service.py         # 服务基类
    │   ├── processors/     # 处理器
    │   │   └── async_document_processor.py
    │   └── dtos/           # 数据传输对象
    │       └── document_dto.py
    │
    ├── domain/             # 领域层 - 核心业务逻辑
    │   ├── models.py       # 领域模型
    │   ├── enums.py        # 枚举定义
    │   ├── abc/            # 抽象接口
    │   │   └── document_parser.py
    │   ├── agent/          # Agent领域逻辑
    │   │   ├── workflow.py
    │   │   ├── rag.py
    │   │   ├── interaction.py
    │   │   └── prompts.py
    │   ├── evidence/       # 证据领域
    │   │   ├── aggregator.py
    │   │   ├── classifier.py
    │   │   ├── evaluation_framework.py
    │   │   └── tools.py
    │   ├── graph/          # 图谱领域
    │   │   ├── search.py
    │   │   ├── sync.py
    │   │   └── association_service.py
    │   ├── literature/     # 文献领域
    │   │   ├── pubmed_service.py
    │   │   ├── firecrawl_service.py
    │   │   └── acquisition_agent.py
    │   ├── variant/        # 变异领域
    │   │   ├── service.py
    │   │   ├── clinvar_client.py
    │   │   └── clingen_client.py
    │   ├── mineru/         # MinerU领域
    │   │   ├── component.py
    │   │   └── constants.py
    │   └── impl/           # 领域实现（应移至Infrastructure）
    │       ├── document_storage.py
    │       └── pdf_parser.py
    │
    ├── infrastructure/     # 基础设施层 - 外部依赖实现
    │   ├── adapters/       # 适配器
    │   │   └── mineru/
    │   │       ├── mineru_adapter_interface.py
    │   │       ├── mineru_adapter_impl.py
    │   │       └── mineru_mapping.py
    │   ├── store/          # 存储适配器
    │   │   ├── base_store.py
    │   │   └── minio_store.py
    │   ├── minio.py        # MinIO客户端
    │   ├── neo4j.py        # Neo4j客户端
    │   ├── postgres.py     # PostgreSQL客户端
    │   ├── qdrant.py       # Qdrant客户端
    │   ├── redis.py        # Redis客户端
    │   └── models.py       # 数据库模型
    │
    ├── agents/             # Agent编排层 - LangGraph工作流
    │   ├── parsing/        # 解析Agent
    │   │   ├── node.py
    │   │   ├── mineru_tool.py
    │   │   └── translation_tool.py
    │   ├── extraction/     # 抽取Agent
    │   │   ├── node.py
    │   │   ├── extraction_tool.py
    │   │   └── validator_tool.py
    │   ├── reasoning/      # 推理Agent
    │   │   └── node.py
    │   ├── arbitration/    # 仲裁Agent
    │   │   ├── node.py
    │   │   ├── ps3_bs3_evaluator.py
    │   │   └── rule_checker.py
    │   ├── acquisition/    # 文献获取Agent
    │   │   ├── node.py
    │   │   ├── pubmed_tool.py
    │   │   └── firecrawl_tool.py
    │   ├── interaction/    # 交互Agent
    │   │   ├── node.py
    │   │   └── prompts.py
    │   └── supervisor.py   # Agent监督器
    │
    ├── tools/              # 工具层 - 外部服务封装（与Infrastructure有重叠）
    │   ├── db/             # 数据库工具
    │   │   ├── neo4j_tool.py
    │   │   ├── postgres_tool.py
    │   │   └── qdrant_tool.py
    │   ├── external/       # 外部API工具
    │   │   ├── clinvar_tool.py
    │   │   └── translation_api.py
    │   └── file/           # 文件处理工具
    │       ├── minio_tool.py
    │       └── pdf_parser.py
    │
    ├── knowledge/          # 知识层 - 领域知识
    │   ├── prompts/        # Prompt模板
    │   │   ├── loader.py
    │   │   ├── system.yaml
    │   │   ├── extraction.yaml
    │   │   ├── arbitration.yaml
    │   │   └── acmg_rules.yaml
    │   └── ontologies/     # 本体定义
    │
    ├── state/              # 状态管理
    │   ├── schemas.py      # 状态模式
    │   └── global_state.py # 全局状态
    │
    ├── configs/            # 配置管理
    │   ├── app_config.py
    │   └── database_config.py
    │
    ├── utils/              # 工具类
    │   ├── exceptions.py
    │   ├── logger.py
    │   ├── file_utils.py
    │   ├── evidence_annotation.py
    │   ├── pipeline_utils.py
    │   ├── sanitizers.py
    │   ├── timer.py
    │   ├── celery_config.py
    │   └── celery_tasks.py
    │
    ├── config.py           # 配置（与configs/重复，建议删除）
    ├── health.py           # 健康检查
    └── celery_app.py       # Celery应用
```

## 架构说明

### 六边形架构分层

#### 1. API层 (`src/api/`)
- **职责**：HTTP路由定义、依赖注入、请求验证
- **文件**：
  - `routes/core.py` - 核心API路由
  - `routes/task.py` - 任务管理路由
  - `routes/evidence.py` - 证据查询路由
  - `routes/stream.py` - 流式响应路由
  - `dependencies.py` - 依赖注入和错误处理

#### 2. 表现层 (`src/presentation/`)
- **职责**：控制器逻辑，协调API层和应用层
- **文件**：
  - `upload_controller.py` - 文档上传控制器
  - `task_controller.py` - 任务控制器
  - `base_controller.py` - 基础控制器

#### 3. 应用层 (`src/application/`)
- **职责**：业务流程编排，协调领域层和基础设施层
- **服务**：
  - `document_service.py` - 文档处理（上传、解析、存储）
  - `embedding_service.py` - 文本向量化
  - `llm_service.py` - LLM调用封装（DeepSeek + Claude）
  - `rerank_service.py` - 检索结果重排序

#### 4. 领域层 (`src/domain/`)
- **职责**：核心业务逻辑，与技术实现无关
- **子域**：
  - **Agent领域** (`agent/`) - Agent工作流定义
  - **证据领域** (`evidence/`) - 证据聚合、分类、评估
  - **图谱领域** (`graph/`) - 知识图谱搜索和同步
  - **文献领域** (`literature/`) - PubMed/Firecrawl文献获取
  - **变异领域** (`variant/`) - ClinVar/ClinGen变异查询
  - **MinerU领域** (`mineru/`) - PDF解析领域逻辑

#### 5. 基础设施层 (`src/infrastructure/`)
- **职责**：外部依赖实现（数据库、存储、第三方服务）
- **适配器**：
  - `minio.py` - MinIO对象存储
  - `neo4j.py` - Neo4j图数据库
  - `postgres.py` - PostgreSQL关系数据库
  - `qdrant.py` - Qdrant向量数据库
  - `redis.py` - Redis缓存
  - `adapters/mineru/` - MinerU适配器

#### 6. Agent编排层 (`src/agents/`)
- **职责**：LangGraph工作流节点和工具定义
- **Agent类型**：
  - **解析Agent** (`parsing/`) - PDF解析和翻译
  - **抽取Agent** (`extraction/`) - 实体抽取和验证
  - **推理Agent** (`reasoning/`) - 证据推理
  - **仲裁Agent** (`arbitration/`) - ACMG评级仲裁
  - **获取Agent** (`acquisition/`) - 文献获取（PubMed/Firecrawl）
  - **交互Agent** (`interaction/`) - 用户交互

#### 7. 工具层 (`src/tools/`)
- **职责**：外部服务封装（与Infrastructure有重叠）
- **分类**：
  - `db/` - 数据库工具
  - `external/` - 外部API工具
  - `file/` - 文件处理工具

#### 8. 知识层 (`src/knowledge/`)
- **职责**：领域知识和Prompt模板
- **内容**：
  - `prompts/` - ACMG规则、系统提示、抽取提示、仲裁提示
  - `ontologies/` - 本体定义

### 架构问题说明

⚠️ **当前架构存在以下问题**：

1. **双入口文件**：
   - `main.py` - 主入口（推荐使用）
   - `app.py` - 旧版入口（已废弃，建议删除）

2. **重复目录**：
   - `src/config.py` 与 `src/configs/` - 配置重复（建议删除 `src/config.py`）
   - `src/domain/impl/` - 领域实现应移至 `infrastructure/`
   - `src/tools/` 与 `src/infrastructure/` - 职责重叠（建议合并）

3. **分层边界模糊**：
   - `tools/` 层与 `infrastructure/` 层功能重复
   - `domain/impl/` 违反领域层纯度原则（包含技术实现细节）

### 数据流转

```
用户请求
  → API层 (路由 + 依赖注入)
    → 表现层 (控制器)
      → 应用层 (业务编排)
        → 领域层 (核心逻辑)
          → 基础设施层 (外部依赖)
            → 数据库/存储 (PostgreSQL/Neo4j/Qdrant/MinIO)
```

### Agent工作流

```
文献获取 (acquisition)
  → PDF解析 (parsing)
    → 实体抽取 (extraction)
      → 证据推理 (reasoning)
        → ACMG仲裁 (arbitration)
          → 生成报告
```

## 技术栈

## 📚 文档与参考

- **部署指南**: [DEPLOYMENT.md](DEPLOYMENT.md) - 生产环境部署文档
- **API 文档**: http://localhost:8000/docs - 交互式API文档
- **Qdrant 文档**: https://qdrant.tech/documentation/ - 向量数据库文档
- **Anthropic API**: https://docs.anthropic.com/ - Claude API官方文档
- **DeepSeek API**: https://platform.deepseek.com/docs - DeepSeek API文档
- **LangGraph**: https://langchain-ai.github.io/langgraph/ - Agent工作流框架
- **六边形架构**: 本项目采用六边形架构（端口-适配器模式），实现业务逻辑与技术实现的解耦
- **DDD**: 领域驱动设计，通过子域划分和限界上下文管理复杂业务逻辑

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
- `POST /api/evidence/search` - 证据检索
- `GET /api/stream/{task_id}` - 流式任务状态
- `GET /` - 健康检查

完整文档: http://localhost:8000/docs

## 📝 更新日志

### v2.1.1 (2026-03-17)
**架构文档更新**

✨ 更新内容：
- ✅ 更新项目结构为六边形架构（Hexagonal Architecture）
- ✅ 详细说明各层职责和文件组织
- ✅ 标注当前架构存在的问题（双入口、重复目录、边界模糊）
- ✅ 更新数据流转和Agent工作流说明
- ✅ 补充API端点文档
- ✅ 更新技术栈（Redis、Celery、DDD、uv、语言检测）

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

## 🎓 架构演进路线

本项目经历了从**四层架构**到**六边形架构**的演进：

1. **v2.0.0** - 初期采用传统的 Controller/Service/Domain/Repository 四层架构
2. **v2.1.0** - 引入 LangGraph Agent 编排，开始向六边形架构过渡
3. **v2.1.1** - 正式采用六边形架构，明确各层职责

**未来优化方向**：
- ✅ 清理重复代码（`app.py`、`src/config.py`、`src/domain/impl/`）
- ✅ 合并 `tools/` 和 `infrastructure/` 层
- ✅ 完善领域模型和仓储接口
- ✅ 统一配置管理（使用 `src/configs/`）

---

**最后更新**: 2026-03-17
