# Qdrant RAG 集成 - 快速开始

## 功能概述

已成功集成 Qdrant 向量数据库实现 RAG（检索增强生成），在 PS3 证据提取过程中自动检索相关的 ACMG 指南和参考文档。

## 核心改动

### 1. 数据库层 (database/qdrant.py)
- ✅ 重构为 `QdrantManager` 类
- ✅ 支持单例模式，避免重复连接
- ✅ 集成集合管理、健康检查、文档导入功能
- ✅ 向后兼容原有函数接口

### 2. Agent 层 (component/agents.py)
- ✅ 添加 `search_knowledge_base` 工具用于知识检索
- ✅ 集成 RAG 到 `extract_ps3_evidence` 流程
- ✅ 自动检索相关知识文档并构建上下文
- ✅ 支持多查询检索和结果去重

### 3. Prompts 层 (component/prompts.py)
- ✅ 更新 `get_ps3_evidence_extraction_prompt` 支持知识库上下文
- ✅ 在提示词中动态注入检索到的参考文档

## 快速开始

### 步骤 1: 启动 Qdrant 服务

```bash
# 使用 Docker 启动
docker run -d -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    --name qdrant \
    qdrant/qdrant

# 验证服务
curl http://localhost:6333/health
```

### 步骤 2: 配置环境变量

在 `.env.local` 中添加/更新：

```bash
# Qdrant 配置
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=acmg_knowledge
QDRANT_API_KEY=  # 可选，本地开发可留空
QDRANT_DIMENSION=1536
QDRANT_PREFER_GRPC=false

# Embedding 配置
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-xxxxx
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

### 步骤 3: 准备知识文档

将 ACMG 指南和相关文档放入知识库目录：

```bash
# 已有文档
knowledge_docs/
└── Recommendations_for_the_use_of_functional_evidence_PS3-BS3_in_the_ACMG_variant_interpretation_guide.md

# 可以添加更多文档
# - ACMG_2015_guidelines.md
# - PS3_case_studies.md
# - Functional_assay_protocols.md
```

### 步骤 4: 初始化知识库

```bash
# 进入项目目录
cd apps/backend

# 安装依赖
pip install qdrant-client langchain-qdrant

# 运行初始化脚本
python scripts/init_knowledge_base.py

# 如需重置知识库
python scripts/init_knowledge_base.py --reset
```

预期输出：
```
============================================================
开始初始化 Qdrant 知识库
============================================================
Qdrant 服务: localhost:6333
集合名称: acmg_knowledge
✓ Qdrant 管理器创建成功
✓ Qdrant 服务连接成功
✓ 集合创建/检查成功
发现 1 个文档文件
  - Recommendations_for_the_use_of_functional_evidence_PS3-BS3...
开始导入文档到 Qdrant...
✓ 文档导入成功
✓ 集合中的向量数量: 42
============================================================
✓ 知识库初始化完成!
============================================================
```

### 步骤 5: 测试 RAG 检索

```bash
# 运行测试脚本
python scripts/test_rag_retrieval.py
```

预期输出：
```
============================================================
测试 1: 基础检索功能
============================================================
查询: What is PS3 evidence in ACMG guidelines?
✓ 检索到 3 个相关文档

--- 文档 1 ---
相似度: 0.8542
内容预览: PS3 Functional Evidence...

============================================================
测试结果汇总
============================================================
✓ PASS: 基础检索
✓ PASS: 多查询检索
✓ PASS: 集合状态
✓ PASS: 相似度阈值
============================================================
通过: 4/4
✓ 所有测试通过!
```

### 步骤 6: 运行完整流程

```python
from component.agents import process_medical_evidence

# 处理医学文档（自动使用 RAG）
result = process_medical_evidence(
    markdown_content=your_markdown,
    image_paths=your_images,
    max_iterations=2
)

print(f"证据强度: {result.final_evidence_strength}")
print(f"仲裁评分: {result.arbitration_score}/100")
print(f"状态: {result.status}")
```

## RAG 工作流程说明

```
用户文档输入
    ↓
[步骤 1-3: 翻译、描述图片、排版融合]
    ↓
[步骤 4: 证据提取 + RAG]
    ├─→ 生成检索查询
    │   - "PS3 BS3 functional evidence assessment criteria"
    │   - "ACMG variant interpretation guidelines functional assays"
    │   - "OddsPath calculation pathogenic benign variants"
    │
    ├─→ 向量检索 (Qdrant)
    │   - 查询向量化 (embedding)
    │   - 检索 Top-K 相关文档
    │   - 过滤低相似度结果
    │
    ├─→ 结果处理
    │   - 去重
    │   - 排序
    │   - 限制最多 5 个文档
    │
    └─→ 构建 LLM Prompt
        - 原文档内容
        - + 检索到的知识库上下文
        - → LLM 生成证据评估
    ↓
[步骤 5-6: 仲裁评分、反馈微调]
    ↓
最终结果输出
```

## 配置调优

### 相似度阈值调整

```python
# 在 config.py 或 .env.local 中调整
QDRANT_SCORE_THRESHOLD=0.7  # 默认 0.7，范围 [0, 1]
```

- 阈值过高（如 0.9）：检索精确但可能召回不足
- 阈值过低（如 0.5）：召回更多但可能包含不相关内容

### Top-K 调整

```python
# 在 agents.py 中调整
limit=3  # 每个查询检索 3 个文档
top_docs = unique_docs[:5]  # 最终使用 5 个文档
```

### 检索查询优化

```python
# 在 extract_ps3_evidence 函数中
search_queries = [
    "PS3 BS3 functional evidence assessment criteria",
    "ACMG variant interpretation guidelines functional assays", 
    "OddsPath calculation pathogenic benign variants",
    # 添加更多针对性查询
]
```

## 故障排除

### 问题 1: Qdrant 连接失败

```bash
# 检查服务状态
docker ps | grep qdrant

# 查看日志
docker logs qdrant

# 重启服务
docker restart qdrant
```

### 问题 2: 检索无结果

```python
# 检查集合状态
from database.qdrant import QdrantManager
manager = QdrantManager()
info = manager.get_collection_info()
print(f"向量数量: {info.vectors_count}")
```

### 问题 3: Import 错误

```bash
# 确保安装了所有依赖
pip install qdrant-client langchain-qdrant langchain-openai
```

## 下一步优化建议

1. **多语言支持**: 添加中英文混合检索
2. **缓存机制**: 使用 Redis 缓存检索结果
3. **重排序**: 使用 cross-encoder 重排序提高精度
4. **动态查询**: 根据文档内容动态生成检索查询
5. **混合检索**: 结合向量检索和关键词检索

## 参考文档

- [RAG 使用指南](docs/RAG_USAGE.md) - 详细使用文档
- [Qdrant 文档](https://qdrant.tech/documentation/)
- [LangChain RAG](https://python.langchain.com/docs/use_cases/question_answering/)

## 联系支持

如有问题或建议，请联系开发团队。
