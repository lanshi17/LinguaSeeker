# Qdrant 知识库 RAG 使用指南

## 概述

本项目集成了 Qdrant 向量数据库用于实现检索增强生成（RAG），在 PS3 证据提取过程中自动检索相关的参考文档和指南。

## 系统架构

```
知识文档 → Embedding → Qdrant 向量库
                              ↓
用户文档 → 提取证据 → 检索相关知识 → LLM + RAG → 证据评估
```

## 核心组件

### 1. QdrantManager (database/qdrant.py)

管理 Qdrant 向量数据库的所有操作：

```python
from database.qdrant import QdrantManager

# 创建管理器实例
manager = QdrantManager()

# 健康检查
if manager.ping():
    print("Qdrant 服务正常")

# 创建集合
manager.create_collection_if_not_exists()

# 导入知识文档
manager.ingest_files("./knowledge_docs")
```

### 2. RAG 检索工具 (component/agents.py)

`search_knowledge_base` 工具用于检索相关文档：

```python
@tool
def search_knowledge_base(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """从 Qdrant 知识库中检索相关文档"""
    # 1. 生成查询向量
    # 2. 检索相似文档
    # 3. 返回格式化结果
```

### 3. 证据提取流程

在 `extract_ps3_evidence` 函数中自动执行 RAG 检索：

```python
def extract_ps3_evidence(state: ProcessingState) -> ProcessingState:
    # 步骤 1: 检索知识库
    search_queries = [
        "PS3 BS3 functional evidence assessment criteria",
        "ACMG variant interpretation guidelines functional assays",
        "OddsPath calculation pathogenic benign variants",
    ]
    
    retrieved_docs = []
    for query in search_queries:
        docs = search_knowledge_base(query, top_k=3)
        retrieved_docs.extend(docs)
    
    # 步骤 2: 使用 LLM + RAG 上下文提取证据
    prompt = prompts.get_ps3_evidence_extraction_prompt(
        state['translated_md'],
        state['image_descriptions'],
        knowledge_context=knowledge_context
    )
```

## 配置要求

在 `.env.local` 中配置以下参数：

```bash
# Qdrant 配置
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=acmg_knowledge
QDRANT_API_KEY=your_api_key_here
QDRANT_DIMENSION=1536
QDRANT_PREFER_GRPC=false

# Embedding 配置
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=your_api_key_here
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

## 初始化知识库

### 1. 启动 Qdrant 服务

使用 Docker：
```bash
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage \
    qdrant/qdrant
```

### 2. 准备知识文档

将知识文档放入 `knowledge_docs/` 目录：
```
knowledge_docs/
├── Recommendations_for_the_use_of_functional_evidence_PS3-BS3_in_the_ACMG_variant_interpretation_guide.md
├── ACMG_guidelines_2015.md
└── ...
```

### 3. 导入知识库

```python
from database.qdrant import QdrantManager

manager = QdrantManager()

# 创建集合
manager.create_collection_if_not_exists()

# 导入文档
manager.ingest_files("./knowledge_docs")

print("知识库初始化完成!")
```

或使用 CLI：
```bash
python -m scripts.init_knowledge_base
```

## 使用示例

### 完整流程示例

```python
from component.agents import process_medical_evidence

# 处理医学文档（自动使用 RAG）
result = process_medical_evidence(
    markdown_content=your_markdown,
    image_paths=your_images,
    max_iterations=2
)

# 查看结果
print(f"证据强度: {result.final_evidence_strength}")
print(f"仲裁评分: {result.arbitration_score}/100")
print(f"状态: {result.status}")
```

### 直接调用检索

```python
from component.agents import search_knowledge_base

# 检索相关文档
docs = search_knowledge_base(
    "How to calculate OddsPath for PS3 evidence?",
    top_k=5
)

for i, doc in enumerate(docs):
    print(f"文档 {i+1} (相似度: {doc['score']:.3f}):")
    print(doc['content'][:200])
    print()
```

## RAG 工作流程

1. **查询生成**: 根据待评估文档内容生成多个检索查询
2. **向量检索**: 使用 embedding 模型将查询向量化，在 Qdrant 中检索相似文档
3. **去重排序**: 对检索结果去重并按相似度排序
4. **上下文构建**: 将 Top-K 文档构建为知识上下文
5. **RAG 推理**: LLM 结合知识上下文和待评估文档进行证据提取
6. **证据评估**: 按照 PS3 四步法框架进行系统化评估

## 优化建议

### 1. 检索策略优化

```python
# 动态查询生成
def generate_search_queries(document: str) -> List[str]:
    """根据文档内容动态生成检索查询"""
    # 提取关键实体和概念
    # 构建多角度查询
    pass

# 混合检索
def hybrid_search(query: str, top_k: int = 5):
    """结合向量检索和关键词检索"""
    # 向量召回
    # 关键词召回
    # 融合排序
    pass
```

### 2. 重排序

```python
from sentence_transformers import CrossEncoder

def rerank_documents(query: str, docs: List[Dict]) -> List[Dict]:
    """使用 cross-encoder 重排序"""
    reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    # 重排序逻辑
    pass
```

### 3. 缓存机制

```python
# 使用 Redis 缓存检索结果
import redis
import hashlib

def cached_search(query: str, top_k: int = 5):
    cache_key = hashlib.md5(query.encode()).hexdigest()
    # 检查缓存
    # 执行检索
    # 更新缓存
    pass
```

## 监控和调试

### 查看检索日志

```python
from loguru import logger

logger.add("logs/rag_{time}.log", rotation="500 MB")
```

### 评估检索质量

```python
def evaluate_retrieval(query: str, relevant_doc_ids: List[str]):
    """评估检索的准确率和召回率"""
    results = search_knowledge_base(query, top_k=10)
    retrieved_ids = [doc['file_path'] for doc in results]
    
    precision = len(set(retrieved_ids) & set(relevant_doc_ids)) / len(retrieved_ids)
    recall = len(set(retrieved_ids) & set(relevant_doc_ids)) / len(relevant_doc_ids)
    
    return precision, recall
```

## 常见问题

### Q1: 检索不到相关文档？
- 检查知识库是否正确导入
- 验证 embedding 模型配置
- 调整相似度阈值 `score_threshold`

### Q2: 检索速度慢？
- 启用 gRPC: `QDRANT_PREFER_GRPC=true`
- 增加索引参数
- 使用缓存机制

### Q3: 如何更新知识库？
```python
# 增量更新
manager.ingest_files("./new_docs")

# 重建索引
manager.reset_collection()
manager.ingest_files("./all_docs")
```

## 参考资料

- [Qdrant 官方文档](https://qdrant.tech/documentation/)
- [LangChain RAG 教程](https://python.langchain.com/docs/use_cases/question_answering/)
- [ACMG PS3/BS3 指南](knowledge_docs/)
