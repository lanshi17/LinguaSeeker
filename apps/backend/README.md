---

# ACMG-PS3 智能评级系统 - 后端服务 v3.0

基于 GraphRAG 与 LangGraph 的变异致病性智能分类系统（六边形架构：API / Application / Domain / Infrastructure）。

## 🎯 技术栈

| 组件 | 技术选型 |
|:-----|:---------|
| **后端框架** | **FastAPI** |
| **Agent 框架** | **LangGraph** |
| **LLM 架构** | **8 个专用 Agent + 主力/仲裁双 LLM** |
| **主力 LLM** | **DeepSeek-V3/V3.2** (可选) |
| **仲裁 LLM** | **Claude 3.5 Sonnet/Opus** (可选) |
| **Agent 模型** | **Qwen 系列** (qwen3.5-flash/plus/max, qwen-mt, qwen-vl) |
| **PDF 解析** | **MinerU** |
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
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 🔄 LLM 架构与 Agent 配置

### 8 个专用 LLM Agent 架构 (v3.0+)

本系统采用**8 个专用 LLM Agent**架构，每个 Agent 独立配置，结合主力/仲裁双 LLM 的协作能力：

#### 8 个 Agent 配置与职责

| # | Agent | 职责 | 默认模型 | 配置项 |
|---|-------|------|----------|--------|
| 1 | **retrieval** (文献获取) | PubMed/Firecrawl 文献检索 | qwen3.5-flash | `RETRIEVAL_API_KEY`, `RETRIEVAL_BASE_URL`, `RETRIEVAL_MODEL` |
| 2 | **parsing** (文档解析) | PDF 解析与结构提取 | qwen3.5-flash | `PARSING_API_KEY`, `PARSING_BASE_URL`, `PARSING_MODEL` |
| 3 | **mt** (多语种翻译) | 多语种文档翻译 | qwen-mt-flash | `MT_API_KEY`, `MT_BASE_URL`, `MT_MODEL` |
| 4 | **format** (多功能排版) | 文档排版与格式化 | qwen3.5-flash | `FORMAT_API_KEY`, `FORMAT_BASE_URL`, `FORMAT_MODEL` |
| 5 | **vlm** (图片提取) | 图片内容理解与描述 | qwen3-vl-flash | `VLM_API_KEY`, `VLM_BASE_URL`, `VLM_MODEL`, `VLM_ENABLE` |
| 6 | **evidence** (证据提取) | 证据记录抽取与验证 | qwen3.5-plus | `EVIDENCE_API_KEY`, `EVIDENCE_BASE_URL`, `EVIDENCE_MODEL` |
| 7 | **classification** (ACMG 分类) | 证据初步分类 | qwen3.5-plus | `CLASSIFICATION_API_KEY`, `CLASSIFICATION_BASE_URL`, `CLASSIFICATION_MODEL` |
| 8 | **arbitration** (专家裁决) | ACMG 最终评级仲裁 | qwen3-max | `ARBITRATION_API_KEY`, `ARBITRATION_BASE_URL`, `ARBITRATION_MODEL` |

#### 主力/仲裁双 LLM 配置

除了 8 个专用 Agent 外，系统还支持配置主力和仲裁 LLM 用于特定场景：

| 角色 | 默认提供商 | 默认模型 | 配置项 | 用途 |
|------|-----------|----------|--------|------|
| **主力 LLM** | DeepSeek | deepseek-chat | `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` | 通用任务、快速响应 |
| **仲裁 LLM** | Claude | claude-3-5-sonnet | `CLAUDE_API_KEY`, `ANTHROPIC_BASE_URL`, `CLAUDE_MODEL` | 复杂推理、最终决策 |

#### 其他 LLM 相关配置

| 组件 | 配置项 | 默认值 |
|------|--------|--------|
| **Embedding** | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | qwen / text-embedding-v4 |
| **Rerank** | `RERANK_MODEL` | qwen3-rerank |
| **OCR** | `OCR_PROVIDER`, `OCR_MODEL` | qwen / qwen-vl-ocr-latest |
| **MinerU** | `MINERU_API_URL`, `MINERU_API_TOKEN` | MinerU API |

**关键特性**：
- ✅ 8 个 Agent 独立配置，灵活切换模型提供商
- ✅ 支持 Qwen 系列模型（flash/plus/max/mt/vl）
- ✅ 主力/仲裁双 LLM 用于特定场景增强
- ✅ 完整的异步 API 支持
- ✅ 统一的 Anthropic 兼容消息格式

**配置示例**：
```python
from src.config import Settings

settings = Settings()

# 8 个 Agent 配置
retrieval_config = {
    "api_key": settings.retrieval_api_key,
    "base_url": settings.retrieval_base_url,
    "model": settings.retrieval_model,  # qwen3.5-flash
}

parsing_config = {
    "api_key": settings.parsing_api_key,
    "base_url": settings.parsing_base_url,
    "model": settings.parsing_model,  # qwen3.5-flash
}

mt_config = {
    "api_key": settings.mt_api_key,
    "base_url": settings.mt_base_url,
    "model": settings.mt_model,  # qwen-mt-flash (翻译专用)
}

# ... 其他 Agent 配置

# 主力/仲裁 LLM 配置（可选）
deepseek_config = {
    "api_key": settings.deepseek_api_key,
    "base_url": settings.deepseek_base_url,
    "model": settings.deepseek_model,
}

claude_config = {
    "api_key": settings.claude_api_key,
    "base_url": settings.anthropic_base_url,
    "model": settings.claude_model,
}
```

**环境变量配置**：
```bash
# 8 个 Agent 配置
RETRIEVAL_API_KEY="sk-xxx"
RETRIEVAL_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
RETRIEVAL_MODEL="qwen3.5-flash"

PARSING_API_KEY="sk-xxx"
PARSING_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
PARSING_MODEL="qwen3.5-flash"

MT_API_KEY="sk-xxx"
MT_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
MT_MODEL="qwen-mt-flash"

FORMAT_API_KEY="sk-xxx"
FORMAT_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
FORMAT_MODEL="qwen3.5-flash"

VLM_API_KEY="sk-xxx"
VLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
VLM_MODEL="qwen3-vl-flash"
VLM_ENABLE=false

EVIDENCE_API_KEY="sk-xxx"
EVIDENCE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
EVIDENCE_MODEL="qwen3.5-plus"

CLASSIFICATION_API_KEY="sk-xxx"
CLASSIFICATION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
CLASSIFICATION_MODEL="qwen3.5-plus"

ARBITRATION_API_KEY="sk-xxx"
ARBITRATION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
ARBITRATION_MODEL="qwen3-max"

# 主力/仲裁 LLM 配置（可选）
DEEPSEEK_API_KEY="sk-xxx"
DEEPSEEK_BASE_URL="https://api.deepseek.com"
DEEPSEEK_MODEL="deepseek-chat"

CLAUDE_API_KEY="sk-ant-xxx"
ANTHROPIC_BASE_URL="https://api.anthropic.com"
CLAUDE_MODEL="claude-3-5-sonnet-20241022"

# Embedding 配置
EMBEDDING_PROVIDER="qwen"
EMBEDDING_API_KEY="sk-xxx"
EMBEDDING_MODEL="text-embedding-v4"

# Rerank 配置
RERANK_MODEL="qwen3-rerank"
RERANK_API_KEY="sk-xxx"

# OCR 配置
OCR_PROVIDER="qwen"
OCR_API_KEY="sk-xxx"
OCR_MODEL="qwen-vl-ocr-latest"

# MinerU 配置
MINERU_API_URL="https://mineru.net/api/v4/extract/task"
MINERU_API_TOKEN="xxx"
```

详细文档：[src/config.py](src/config.py)

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
    ├── api/                # API 层 - HTTP 路由和依赖注入
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
    │   │   ├── llm_service.py          # LLM 服务
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
    │   ├── agent/          # Agent 领域逻辑
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
    │   ├── mineru/         # MinerU 领域
    │   │   ├── component.py
    │   │   └── constants.py
    │   └── impl/           # 领域实现（应移至 Infrastructure）
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
    │   ├── minio.py        # MinIO 客户端
    │   ├── neo4j.py        # Neo4j 客户端
    │   ├── postgres.py     # PostgreSQL 客户端
    │   ├── qdrant.py       # Qdrant 客户端
    │   ├── redis.py        # Redis 客户端
    │   └── models.py       # 数据库模型
    │
    ├── agents/             # Agent 编排层 - LangGraph 工作流
    │   ├── parsing/        # 解析 Agent
    │   │   ├── node.py
    │   │   ├── mineru_tool.py
    │   │   └── translation_tool.py
    │   ├── extraction/     # 抽取 Agent
    │   │   ├── node.py
    │   │   ├── extraction_tool.py
    │   │   └── validator_tool.py
    │   ├── reasoning/      # 推理 Agent
    │   │   └── node.py
    │   ├── arbitration/    # 仲裁 Agent
    │   │   ├── node.py
    │   │   ├── ps3_bs3_evaluator.py
    │   │   └── rule_checker.py
    │   ├── acquisition/    # 文献获取 Agent
    │   │   ├── node.py
    │   │   ├── pubmed_tool.py
    │   │   └── firecrawl_tool.py
    │   ├── interaction/    # 交互 Agent
    │   │   ├── node.py
    │   │   └── prompts.py
    │   └── supervisor.py   # Agent 监督器
    │
    ├── tools/              # 工具层 - 外部服务封装（与 Infrastructure 有重叠）
    │   ├── db/             # 数据库工具
    │   │   ├── neo4j_tool.py
    │   │   ├── postgres_tool.py
    │   │   └── qdrant_tool.py
    │   ├── external/       # 外部 API 工具
    │   │   ├── clinvar_tool.py
    │   │   └── translation_api.py
    │   └── file/           # 文件处理工具
    │       ├── minio_tool.py
    │       └── pdf_parser.py
    │
    ├── knowledge/          # 知识层 - 领域知识
    │   ├── prompts/        # Prompt 模板
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
    ├── config.py           # 配置（与 configs/重复，建议删除）
    ├── health.py           # 健康检查
    └── celery_app.py       # Celery 应用
```

## 架构说明

### 六边形架构分层

#### 1. API 层 (`src/api/`)
- **职责**：HTTP 路由定义、依赖注入、请求验证
- **文件**：
  - `routes/core.py` - 核心 API 路由
  - `routes/task.py` - 任务管理路由
  - `routes/evidence.py` - 证据查询路由
  - `routes/stream.py` - 流式响应路由
  - `dependencies.py` - 依赖注入和错误处理

#### 2. 表现层 (`src/presentation/`)
- **职责**：控制器逻辑，协调 API 层和应用层
- **文件**：
  - `upload_controller.py` - 文档上传控制器
  - `task_controller.py` - 任务控制器
  - `base_controller.py` - 基础控制器

#### 3. 应用层 (`src/application/`)
- **职责**：业务流程编排，协调领域层和基础设施层
- **服务**：
  - `document_service.py` - 文档处理（上传、解析、存储）
  - `embedding_service.py` - 文本向量化
  - `llm_service.py` - LLM 调用封装（8 个 Agent + 主力/仲裁）
  - `rerank_service.py` - 检索结果重排序

#### 4. 领域层 (`src/domain/`)
- **职责**：核心业务逻辑，与技术实现无关
- **子域**：
  - **Agent 领域** (`agent/`) - Agent 工作流定义
  - **证据领域** (`evidence/`) - 证据聚合、分类、评估
  - **图谱领域** (`graph/`) - 知识图谱搜索和同步
  - **文献领域** (`literature/`) - PubMed/Firecrawl 文献获取
  - **变异领域** (`variant/`) - ClinVar/ClinGen 变异查询
  - **MinerU 领域** (`mineru/`) - PDF 解析领域逻辑

#### 5. 基础设施层 (`src/infrastructure/`)
- **职责**：外部依赖实现（数据库、存储、第三方服务）
- **适配器**：
  - `minio.py` - MinIO 对象存储
  - `neo4j.py` - Neo4j 图数据库
  - `postgres.py` - PostgreSQL 关系数据库
  - `qdrant.py` - Qdrant 向量数据库
  - `redis.py` - Redis 缓存
  - `adapters/mineru/` - MinerU 适配器

#### 6. Agent 编排层 (`src/agents/`)
- **职责**：LangGraph 工作流节点和工具定义
- **Agent 类型**：
  - **解析 Agent** (`parsing/`) - PDF 解析和翻译
  - **抽取 Agent** (`extraction/`) - 实体抽取和验证
  - **推理 Agent** (`reasoning/`) - 证据推理
  - **仲裁 Agent** (`arbitration/`) - ACMG 评级仲裁
  - **获取 Agent** (`acquisition/`) - 文献获取（PubMed/Firecrawl）
  - **交互 Agent** (`interaction/`) - 用户交互

#### 7. 工具层 (`src/tools/`)
- **职责**：外部服务封装（与 Infrastructure 有重叠）
- **分类**：
  - `db/` - 数据库工具
  - `external/` - 外部 API 工具
  - `file/` - 文件处理工具

#### 8. 知识层 (`src/knowledge/`)
- **职责**：领域知识和 Prompt 模板
- **内容**：
  - `prompts/` - ACMG 规则、系统提示、抽取提示、仲裁提示
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
  → API 层 (路由 + 依赖注入)
    → 表现层 (控制器)
      → 应用层 (业务编排)
        → 领域层 (核心逻辑)
          → 基础设施层 (外部依赖)
            → 数据库/存储 (PostgreSQL/Neo4j/Qdrant/MinIO)
```

### Agent 工作流

```
文献获取 (acquisition)
  → PDF 解析 (parsing)
    → 实体抽取 (extraction)
      → 证据推理 (reasoning)
        → ACMG 仲裁 (arbitration)
          → 生成报告
```

## 📚 文档与参考

- **部署指南**: [DEPLOYMENT.md](DEPLOYMENT.md) - 生产环境部署文档
- **API 文档**: http://localhost:8000/docs - 交互式 API 文档
- **Qdrant 文档**: https://qdrant.tech/documentation/ - 向量数据库文档
- **Anthropic API**: https://docs.anthropic.com/ - Claude API 官方文档
- **DeepSeek API**: https://platform.deepseek.com/docs - DeepSeek API 文档
- **Qwen API**: https://help.aliyun.com/zh/dashscope/ - Qwen API 文档
- **LangGraph**: https://langchain-ai.github.io/langgraph/ - Agent 工作流框架
- **六边形架构**: 本项目采用六边形架构（端口 - 适配器模式），实现业务逻辑与技术实现的解耦
- **DDD**: 领域驱动设计，通过子域划分和限界上下文管理复杂业务逻辑

## 🔧 配置

所有配置通过环境变量管理，详见 `.env.example`

### LLM API 密钥配置

系统需要配置 8 个 Agent 的 API 密钥，以及可选的主力/仲裁 LLM：

```bash
# 1. 复制配置模板
cp .env.example .env

# 2. 编辑配置文件，添加 API 密钥
vim .env
```

**必需的配置项（8 个 Agent）**：

```env
# 1. 文献获取 Agent
RETRIEVAL_API_KEY="sk-xxxxxxxxxxxxxxxx"
RETRIEVAL_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
RETRIEVAL_MODEL="qwen3.5-flash"

# 2. 文档解析 Agent
PARSING_API_KEY="sk-xxxxxxxxxxxxxxxx"
PARSING_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
PARSING_MODEL="qwen3.5-flash"

# 3. 多语种翻译 Agent
MT_API_KEY="sk-xxxxxxxxxxxxxxxx"
MT_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
MT_MODEL="qwen-mt-flash"

# 4. 多功能排版 Agent
FORMAT_API_KEY="sk-xxxxxxxxxxxxxxxx"
FORMAT_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
FORMAT_MODEL="qwen3.5-flash"

# 5. 图片提取 Agent (VLM)
VLM_API_KEY="sk-xxxxxxxxxxxxxxxx"
VLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
VLM_MODEL="qwen3-vl-flash"
VLM_ENABLE=false

# 6. 证据提取 Agent
EVIDENCE_API_KEY="sk-xxxxxxxxxxxxxxxx"
EVIDENCE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
EVIDENCE_MODEL="qwen3.5-plus"

# 7. ACMG 分类 Agent
CLASSIFICATION_API_KEY="sk-xxxxxxxxxxxxxxxx"
CLASSIFICATION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
CLASSIFICATION_MODEL="qwen3.5-plus"

# 8. 专家裁决 Agent
ARBITRATION_API_KEY="sk-xxxxxxxxxxxxxxxx"
ARBITRATION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
ARBITRATION_MODEL="qwen3-max"
```

**可选配置（主力/仲裁 LLM）**：

```env
# DeepSeek (主力 LLM)
DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"
DEEPSEEK_BASE_URL="https://api.deepseek.com"
DEEPSEEK_MODEL="deepseek-chat"

# Claude (仲裁 LLM)
CLAUDE_API_KEY="sk-ant-xxxxxxxxxxxxxxxx"
ANTHROPIC_BASE_URL="https://api.anthropic.com"
CLAUDE_MODEL="claude-3-5-sonnet-20241022"
```

**其他配置**：

```env
# Embedding
EMBEDDING_PROVIDER="qwen"
EMBEDDING_API_KEY="sk-xxxxxxxxxxxxxxxx"
EMBEDDING_MODEL="text-embedding-v4"

# Rerank
RERANK_MODEL="qwen3-rerank"
RERANK_API_KEY="sk-xxxxxxxxxxxxxxxx"

# OCR
OCR_PROVIDER="qwen"
OCR_API_KEY="sk-xxxxxxxxxxxxxxxx"
OCR_MODEL="qwen-vl-ocr-latest"

# MinerU
MINERU_API_URL="https://mineru.net/api/v4/extract/task"
MINERU_API_TOKEN="xxxxxxxxxxxxxxxx"
```

**获取 API 密钥**：
- Qwen (阿里云百炼): https://help.aliyun.com/zh/dashscope/
- DeepSeek: https://platform.deepseek.com/
- Claude: https://console.anthropic.com/

## 🧭 服务 - 数据分离（重点）

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

## 📊 主要 API 端点

- `POST /api/tasks` - 创建任务
- `POST /api/documents/upload` - 上传 PDF
- `POST /api/variants/query` - 查询变异评级
- `POST /api/graph/nl-query` - 自然语言查询图谱
- `POST /api/evidence/search` - 证据检索
- `GET /api/stream/{task_id}` - 流式任务状态
- `GET /` - 健康检查

完整文档：http://localhost:8000/docs

## 📝 更新日志

### v3.0.0 (2026-03-22)
**LLM 架构重大更新 - 8 个专用 Agent**

✨ 新特性：
- ✅ 8 个专用 LLM Agent 架构（retrieval/parsing/mt/format/vlm/evidence/classification/arbitration）
- ✅ 每个 Agent 独立配置（API 密钥、Base URL、模型）
- ✅ Qwen 系列模型支持（qwen3.5-flash/plus/max, qwen-mt, qwen-vl）
- ✅ 主力/仲裁双 LLM 作为可选增强
- ✅ Embedding/Rerank/OCR 独立配置

🔧 配置变更：
- 新增 8 组 Agent 配置环境变量
- 保留 DeepSeek/Claude 配置作为可选
- 统一使用 Anthropic 兼容消息格式

📚 文档更新：
- 更新技术栈说明
- 更新 LLM 架构描述
- 更新配置示例

### v2.1.1 (2026-03-17)
**架构文档更新**

✨ 更新内容：
- ✅ 更新项目结构为六边形架构（Hexagonal Architecture）
- ✅ 详细说明各层职责和文件组织
- ✅ 标注当前架构存在的问题（双入口、重复目录、边界模糊）
- ✅ 更新数据流转和 Agent 工作流说明
- ✅ 补充 API 端点文档
- ✅ 更新技术栈（Redis、Celery、DDD、uv、语言检测）

### v2.1.0 (2024-12-18)
**LLM 服务重大升级 - 自定义 Anthropic 格式支持**

✨ 新特性：
- ✅ 采用 Anthropic Python SDK 统一格式
- ✅ 统一 Anthropic 消息格式（兼容 DeepSeek 和 Claude）
- ✅ 完整的 DeepSeek (Anthropic 兼容) + Claude (Anthropic 原生) 双 LLM 架构
- ✅ 双 LLM 共识机制实现
- ✅ 专用方法封装（实体提取、证据验证、最终评级等）
- ✅ 完善的异步 API 支持和错误处理

🔧 技术改进：
- 使用 `anthropic.AsyncAnthropic` 统一客户端
- 统一 Anthropic 消息格式（DeepSeek 和 Claude）
- System 消息独立处理符合 Anthropic 规范
- 消息序列验证和自动修正
- 详细的 API 调用日志

📚 文档更新：
- 新增 [LLM_SERVICE_GUIDE.md](src/service/LLM_SERVICE_GUIDE.md) - 完整使用指南
- 新增 [LLM_SERVICE_UPDATE_SUMMARY.md](LLM_SERVICE_UPDATE_SUMMARY.md) - 更新总结
- 新增 [llm_service_example.py](src/service/llm_service_example.py) - 代码示例
- 更新 `.env.example` - LLM 配置说明

📦 依赖更新：
- `anthropic>=0.39.0` - 统一使用 Anthropic SDK
- `requests>=2.32.5` - HTTP 客户端

🔗 相关链接：
- [详细更新文档](LLM_SERVICE_UPDATE_SUMMARY.md)
- [使用指南](src/service/LLM_SERVICE_GUIDE.md)

### v2.0.0
初始版本，基于 GraphRAG 和 LangGraph 的 ACMG-PS3 智能评级系统

## 🎓 架构演进路线

本项目经历了从**四层架构**到**六边形架构**的演进：

1. **v2.0.0** - 初期采用传统的 Controller/Service/Domain/Repository 四层架构
2. **v2.1.0** - 引入 LangGraph Agent 编排，开始向六边形架构过渡
3. **v2.1.1** - 正式采用六边形架构，明确各层职责
4. **v3.0.0** - 升级为 8 个专用 Agent 架构，支持 Qwen 系列模型

**未来优化方向**：
- ✅ 清理重复代码（`app.py`、`src/config.py`、`src/domain/impl/`）
- ✅ 合并 `tools/` 和 `infrastructure/` 层
- ✅ 完善领域模型和仓储接口
- ✅ 统一配置管理（使用 `src/configs/`）

---

**最后更新**: 2026-03-22
