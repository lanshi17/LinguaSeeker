# 基础设施层 (Infrastructure Layer)

基础设施层实现外部依赖的具体实现，包括数据库、存储、第三方服务等。本层遵循适配器模式，将技术细节与业务逻辑解耦。

## 目录结构

```
infrastructure/
├── __init__.py
├── adapters/             # 适配器
│   └── mineru/
│       ├── mineru_adapter_interface.py
│       ├── mineru_adapter_impl.py
│       └── mineru_mapping.py
├── store/                # 存储适配器
│   ├── base_store.py
│   └── minio_store.py
├── minio.py              # MinIO 客户端
├── neo4j.py              # Neo4j 客户端
├── postgres.py           # PostgreSQL 客户端
├── qdrant.py             # Qdrant 客户端
├── redis.py              # Redis 客户端
├── models.py             # 数据库模型
└── enum.py               # 枚举定义
```

## 职责

基础设施层的主要职责：

1. **数据访问**: 实现数据库访问和持久化
2. **外部服务**: 封装第三方 API 和服务
3. **适配器**: 实现领域层定义的接口
4. **配置管理**: 管理外部服务配置
5. **连接管理**: 管理数据库连接池

## 架构位置

```
Domain Layer (领域层)
    ↓ (依赖接口)
Infrastructure Layer (基础设施层)  ← 本层 (实现接口)
    ↓
外部服务 (数据库、存储、API)
```

## 核心组件

### 数据库客户端

#### postgres.py

PostgreSQL 客户端：

```python
class PostgresClient:
    """PostgreSQL 客户端"""
    
    def __init__(self, config: PostgresConfig):
        """
        初始化
        
        Args:
            config: PostgreSQL 配置
                - host: 主机地址
                - port: 端口
                - user: 用户名
                - password: 密码
                - database: 数据库名
        """
        pass
    
    def find_document_by_hash(self, file_hash: str) -> Document | None:
        """按文件哈希查找文档"""
        pass
    
    def create_document(self, **kwargs) -> Document:
        """创建文档记录"""
        pass
    
    def update_document(self, document_id: UUID, **kwargs) -> None:
        """更新文档记录"""
        pass
```

#### neo4j.py

Neo4j 客户端：

```python
class Neo4jClient:
    """Neo4j 图数据库客户端"""
    
    def __init__(self, config: Neo4jConfig):
        """
        初始化
        
        Args:
            config: Neo4j 配置
                - uri: Bolt URI
                - user: 用户名
                - password: 密码
        """
        pass
    
    def execute_query(self, query: str, params: dict) -> list[dict]:
        """执行 Cypher 查询"""
        pass
    
    def create_gene_node(self, gene_symbol: str, **properties) -> None:
        """创建基因节点"""
        pass
    
    def create_variant_node(self, variant: str, **properties) -> None:
        """创建变异节点"""
        pass
    
    def create_evidence_relationship(
        self, 
        gene: str, 
        variant: str, 
        evidence: Evidence
    ) -> None:
        """创建证据关系"""
        pass
```

#### qdrant.py

Qdrant 向量数据库客户端：

```python
class QdrantClient:
    """Qdrant 向量数据库客户端"""
    
    def __init__(self, config: QdrantConfig):
        """
        初始化
        
        Args:
            config: Qdrant 配置
                - host: 主机地址
                - port: 端口
                - collection: 集合名称
        """
        pass
    
    async def search(
        self, 
        vector: list[float], 
        limit: int = 10
    ) -> list[ScoredPoint]:
        """向量搜索"""
        pass
    
    async def upsert(
        self, 
        points: list[PointStruct]
    ) -> None:
        """插入向量"""
        pass
    
    async def delete(self, ids: list[str]) -> None:
        """删除向量"""
        pass
```

#### redis.py

Redis 客户端：

```python
class RedisClient:
    """Redis 缓存客户端"""
    
    def __init__(self, config: RedisConfig):
        """
        初始化
        
        Args:
            config: Redis 配置
                - host: 主机地址
                - port: 端口
                - db: 数据库编号
        """
        pass
    
    def get_cached_pdf_result(self, pdf_hash: str) -> dict | None:
        """获取缓存的 PDF 处理结果"""
        pass
    
    def cache_pdf_result(
        self, 
        pdf_hash: str, 
        result: dict, 
        ttl: int = 3600
    ) -> None:
        """缓存 PDF 处理结果"""
        pass
    
    def check_pdf_hash(self, pdf_hash: str) -> bool:
        """检查 PDF 哈希是否存在"""
        pass
```

### 对象存储

#### minio.py

MinIO 对象存储客户端：

```python
class MinIOClient:
    """MinIO 对象存储客户端"""
    
    def __init__(self, config: MinIOConfig):
        """
        初始化
        
        Args:
            config: MinIO 配置
                - endpoint: 端点地址
                - access_key: 访问密钥
                - secret_key: 密钥
                - secure: 是否使用 HTTPS
        """
        pass
    
    async def upload_literature_upload(
        self,
        storage_key: str,
        payload: bytes,
        content_type: str,
        metadata: dict
    ) -> MinioObjectRefModel:
        """上传文献文件"""
        pass
    
    async def download_processed_result(
        self, 
        object_key: str
    ) -> bytes:
        """下载处理结果"""
        pass
    
    async def file_exists(
        self, 
        bucket: str, 
        object_key: str
    ) -> bool:
        """检查文件是否存在"""
        pass
    
    @staticmethod
    def build_literature_object_key(
        file_hash: str,
        original_filename: str
    ) -> str:
        """构建文献对象键"""
        pass
```

#### store/minio_store.py

MinIO 存储适配器：

```python
class MinIOStore(BaseStore):
    """MinIO 存储适配器"""
    
    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict | None = None
    ) -> str:
        """保存数据"""
        pass
    
    async def load(self, key: str) -> bytes:
        """加载数据"""
        pass
    
    async def delete(self, key: str) -> None:
        """删除数据"""
        pass
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        pass
```

### 适配器

#### adapters/mineru/

MinerU 适配器，实现 PDF 解析接口：

| 文件 | 说明 |
|------|------|
| `mineru_adapter_interface.py` | MinerU 适配器接口 |
| `mineru_adapter_impl.py` | MinerU 适配器实现 |
| `mineru_mapping.py` | 数据映射 |

```python
class MinerUAdapterInterface(ABC):
    """MinerU 适配器接口"""
    
    @abstractmethod
    async def parse_pdf(self, file_path: str) -> ParsedDocument:
        """解析 PDF"""
        pass
    
    @abstractmethod
    async def translate(
        self, 
        markdown: str, 
        target_lang: str = "zh"
    ) -> str:
        """翻译 Markdown"""
        pass

class MinerUAdapterImpl(MinerUAdapterInterface):
    """MinerU 适配器实现"""
    
    def __init__(self, config: MinerUConfig):
        """
        初始化
        
        Args:
            config: MinerU 配置
                - api_url: API 地址
                - api_key: API 密钥
        """
        pass
    
    async def parse_pdf(self, file_path: str) -> ParsedDocument:
        """
        解析 PDF
        
        流程:
        1. 调用 MinerU API
        2. 解析返回结果
        3. 构建 ParsedDocument 对象
        """
        pass
    
    async def translate(self, markdown: str, target_lang: str = "zh") -> str:
        """
        翻译 Markdown
        
        流程:
        1. 调用翻译 API
        2. 处理返回结果
        3. 返回翻译后的 Markdown
        """
        pass
```

## 数据模型

### models.py

数据库模型定义：

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from enum import Enum

class MinioBucketNameEnum(str, Enum):
    """MinIO 桶名称枚举"""
    LITERATURE_UPLOADS = "literature-uploads"
    PROCESSED_RESULTS = "processed-results"

class MinioObjectRefModel(BaseModel):
    """MinIO 对象引用模型"""
    
    bucket: MinioBucketNameEnum
    object_key: str
    content_type: str
    metadata: dict | None = None

class DocumentModel(BaseModel):
    """文档数据库模型"""
    
    document_id: UUID
    title: str
    original_filename: str
    pmid: str | None
    local_path: str
    file_hash: str
    status: str
    summary: str | None
    created_at: datetime
    updated_at: datetime
```

### enum.py

基础设施枚举定义：

```python
from enum import Enum

class DatabaseSchema(str, Enum):
    """数据库 Schema"""
    PUBLIC = "public"
    EVIDENCE = "evidence"
    DOCUMENTS = "documents"

class CachePrefix(str, Enum):
    """缓存前缀"""
    PDF_HASH = "pdf_hash:"
    PDF_RESULT = "pdf_result:"
    TASK_STATUS = "task_status:"
    LOG_LINK = "log_link:"
```

## 使用示例

### 数据库操作

```python
from src.infrastructure.postgres import get_postgres_client

# 获取客户端
client = get_postgres_client()

# 查询文档
doc = client.find_document_by_hash("abc123")

# 创建文档
new_doc = client.create_document(
    title="Test",
    document_id=uuid4(),
    original_filename="test.pdf",
    file_hash="abc123",
    status="uploaded"
)
```

### 对象存储

```python
from src.infrastructure.minio import MinIOClient, MinioBucketNameEnum

# 创建客户端
minio = MinIOClient()

# 上传文件
ref = await minio.upload_literature_upload(
    storage_key="doc_id/file.pdf",
    payload=file_bytes,
    content_type="application/pdf",
    metadata={"hash": "abc123"}
)

# 下载文件
data = await minio.download_processed_result("doc_id/result.json")
```

### 缓存操作

```python
from src.infrastructure.redis import (
    get_cached_pdf_result,
    cache_pdf_result,
    redis_client
)

# 获取缓存
result = get_cached_pdf_result("abc123")

# 设置缓存
cache_pdf_result("abc123", result, ttl=3600)

# 直接使用 Redis 客户端
redis = redis_client.get_connection()
redis.set("key", "value")
```

## 配置管理

### 环境变量

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=admin
POSTGRES_PASSWORD=password
POSTGRES_DB=acmg_ps3

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=acmg_paper_chunks

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

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

# 主力 LLM 配置（可选）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 仲裁 LLM 配置（可选）
CLAUDE_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=https://api.anthropic.com
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

## 连接池管理

### PostgreSQL 连接池

```python
from psycopg2 import pool

class PostgresPool:
    _pool = None
    
    @classmethod
    def init_pool(cls, config: PostgresConfig):
        cls._pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database
        )
    
    @classmethod
    def get_connection(cls):
        return cls._pool.getconn()
    
    @classmethod
    def release_connection(cls, conn):
        cls._pool.putconn(conn)
```

## 最佳实践

### 1. 依赖注入

```python
# ✅ 推荐
def get_postgres_client() -> PostgresClient:
    return PostgresClient(config)

@router.get("/documents")
async def get_documents(
    client: PostgresClient = Depends(get_postgres_client)
):
    pass

# ❌ 不推荐
@router.get("/documents")
async def get_documents():
    client = PostgresClient(config)  # 硬编码
    pass
```

### 2. 错误处理

```python
from src.utils.exceptions import InfrastructureException

async def upload_file(self, key: str, data: bytes):
    try:
        await self.client.put_object(...)
    except Exception as e:
        logger.exception("Upload failed: {}", e)
        raise InfrastructureException("STORAGE_UPLOAD_FAILED", str(e))
```

### 3. 连接管理

```python
# ✅ 推荐 - 使用上下文管理器
async with get_db_session() as session:
    result = await session.execute(query)

# ❌ 不推荐 - 手动管理连接
session = get_db_session()
result = await session.execute(query)
await session.close()
```

### 4. 配置验证

```python
from pydantic import BaseModel, Field, validator

class PostgresConfig(BaseModel):
    host: str = Field(..., min_length=1)
    port: int = Field(5432, ge=1, le=65535)
    user: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    database: str = Field(..., min_length=1)
    
    @validator('host')
    def validate_host(cls, v):
        if not re.match(r'^[a-zA-Z0-9.-]+$', v):
            raise ValueError('Invalid host format')
        return v
```

## 测试

### 单元测试

```python
import pytest
from src.infrastructure.minio import MinIOClient

@pytest.mark.asyncio
async def test_upload_file():
    minio = MinIOClient(test_config)
    ref = await minio.upload_literature_upload(
        storage_key="test/file.pdf",
        payload=b"test",
        content_type="application/pdf"
    )
    assert ref.object_key == "test/file.pdf"
```

### 集成测试

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_integration():
    client = get_postgres_client()
    
    # 创建
    doc = client.create_document(...)
    
    # 查询
    found = client.find_document_by_hash(doc.file_hash)
    assert found is not None
    
    # 更新
    client.update_document(doc.document_id, status="processed")
    
    # 清理
    # ...
```

## 相关文档

- [后端 README](../../README.md)
- [领域层 README](../domain/README.md)
- [应用层 README](../application/README.md)

---

**最后更新**: 2026-03-22 (v3.0)
