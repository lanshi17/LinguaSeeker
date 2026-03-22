# 应用层 (Application Layer)

应用层负责业务流程编排，协调领域层和基础设施层，实现具体的业务用例。

## 目录结构

```
application/
├── __init__.py
├── services/           # 应用服务
│   ├── __init__.py
│   ├── base_service.py         # 服务基类
│   ├── document_service.py     # 文档处理服务
│   ├── embedding_service.py    # 向量化服务
│   ├── llm_service.py          # LLM 服务
│   └── rerank_service.py       # 重排序服务
├── processors/         # 处理器
│   └── async_document_processor.py  # 异步文档处理器
└── dtos/               # 数据传输对象
    └── document_dto.py
```

## 职责

应用层的主要职责：

1. **业务流程编排**: 协调多个领域对象完成业务用例
2. **服务封装**: 封装复杂的业务逻辑为可复用服务
3. **数据传输**: 定义 DTO 用于层间数据传递
4. **事务管理**: 管理数据库事务边界
5. **异步处理**: 处理异步任务和后台作业

## 架构位置

```
Presentation Layer (控制器)
    ↓
Application Layer (服务编排)  ← 本层
    ↓
Domain Layer (业务逻辑)
    ↓
Infrastructure Layer (外部依赖)
```

## 核心服务

### base_service.py

服务基类，定义通用接口：

```python
from abc import ABC, abstractmethod

class BaseService(ABC):
    """服务基类"""
    
    @abstractmethod
    async def execute(self, *args, **kwargs):
        """执行服务"""
        pass
```

### document_service.py

文档处理服务：

```python
class DocumentService:
    """文档处理服务"""
    
    async def upload_document(
        self, 
        file: UploadFile,
        user_id: str
    ) -> DocumentDTO:
        """上传文档"""
        pass
    
    async def process_document(
        self, 
        document_id: str
    ) -> ProcessingResult:
        """处理文档"""
        pass
    
    async def get_document(
        self, 
        document_id: str
    ) -> DocumentDTO:
        """获取文档"""
        pass
```

### embedding_service.py

向量化服务：

```python
class EmbeddingService:
    """向量化服务"""
    
    async def embed_text(self, text: str) -> list[float]:
        """文本向量化"""
        pass
    
    async def embed_batch(
        self, 
        texts: list[str]
    ) -> list[list[float]]:
        """批量向量化"""
        pass
```

### llm_service.py

LLM 服务（8 个专用 Agent + 主力/仲裁双 LLM）：

```python
class LLMService:
    """LLM 服务 - 支持 8 个专用 Agent + 主力/仲裁双 LLM
    
    8 个专用 Agent:
    - retrieval: 文献获取 (qwen3.5-flash)
    - parsing: 文档解析 (qwen3.5-flash)
    - mt: 多语种翻译 (qwen-mt-flash)
    - format: 多功能排版 (qwen3.5-flash)
    - vlm: 图片提取 (qwen3-vl-flash)
    - evidence: 证据提取 (qwen3.5-plus)
    - classification: ACMG 分类 (qwen3.5-plus)
    - arbitration: 专家裁决 (qwen3-max)
    
    主力/仲裁 LLM (可选):
    - DeepSeek: 通用任务、快速响应
    - Claude: 复杂推理、最终决策
    """
    
    def __init__(self, llm_config: dict):
        """
        初始化 LLM 服务
        
        Args:
            llm_config: LLM 配置字典，包含：
                # 8 个 Agent 配置
                retrieval_api_key, retrieval_base_url, retrieval_model
                parsing_api_key, parsing_base_url, parsing_model
                mt_api_key, mt_base_url, mt_model
                format_api_key, format_base_url, format_model
                vlm_api_key, vlm_base_url, vlm_model, vlm_enable
                evidence_api_key, evidence_base_url, evidence_model
                classification_api_key, classification_base_url, classification_model
                arbitration_api_key, arbitration_base_url, arbitration_model
                
                # 主力 LLM 配置（可选）
                deepseek_api_key, deepseek_base_url, deepseek_model
                
                # 仲裁 LLM 配置（可选）
                claude_api_key, anthropic_base_url, claude_model
                
                # Embedding 配置
                embedding_provider, embedding_base_url, embedding_api_key, embedding_model
                
                # Rerank 配置
                rerank_model, rerank_api_key
                
                # OCR 配置
                ocr_provider, ocr_base_url, ocr_api_key, ocr_model
                
                # MinerU 配置
                mineru_api_url, mineru_api_token
        """
        pass
    
    async def call_agent(
        self, 
        agent_role: str,
        messages: list[dict],
        **kwargs
    ) -> str:
        """
        调用指定 Agent
        
        Args:
            agent_role: Agent 角色 (retrieval/parsing/mt/format/vlm/evidence/classification/arbitration)
            messages: 消息列表
            **kwargs: 其他参数
        
        Returns:
            LLM 响应文本
        """
        pass
    
    async def extract_entities(
        self, 
        text: str, 
        entity_types: list[str]
    ) -> list[Entity]:
        """实体抽取 (使用 evidence Agent)"""
        pass
    
    async def generate_final_rating(
        self, 
        evidence: list[Evidence],
        gene: str,
        variant: str
    ) -> ACMGRating:
        """生成最终评级 (使用 arbitration Agent 或仲裁 LLM)"""
        pass
```

### rerank_service.py

重排序服务：

```python
class RerankService:
    """重排序服务"""
    
    async def rerank(
        self, 
        query: str,
        documents: list[Document],
        top_k: int = 10
    ) -> list[Document]:
        """重排序文档"""
        pass
```

## 处理器

### async_document_processor.py

异步文档处理器：

```python
class AsyncDocumentProcessor:
    """异步文档处理器"""
    
    def __init__(
        self,
        document_service: DocumentService,
        embedding_service: EmbeddingService,
        llm_service: LLMService
    ):
        pass
    
    async def process(
        self, 
        document_id: str
    ) -> ProcessingResult:
        """
        处理文档
        
        流程:
        1. 获取文档
        2. PDF 解析
        3. 文本翻译
        4. 实体抽取
        5. 证据推理
        6. 向量化存储
        """
        pass
```

## 数据传输对象 (DTO)

### document_dto.py

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class DocumentDTO(BaseModel):
    """文档数据传输对象"""
    
    document_id: UUID
    title: str
    original_filename: str
    file_hash: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

class ProcessingResult(BaseModel):
    """处理结果"""
    
    document_id: UUID
    extracted_entities: list[Entity]
    evidence_records: list[Evidence]
    vector_ids: list[str]
    processing_time: float
```

## 使用示例

### 服务调用

```python
from src.application.services.document_service import DocumentService
from src.application.dtos.document_dto import DocumentDTO

# 获取服务实例
service = DocumentService()

# 上传文档
dto = await service.upload_document(file, user_id)

# 处理文档
result = await service.process_document(dto.document_id)
```

### 依赖注入

```python
from fastapi import Depends

def get_document_service() -> DocumentService:
    """获取文档服务"""
    return DocumentService()

def get_embedding_service() -> EmbeddingService:
    """获取向量化服务"""
    return EmbeddingService()

@router.post("/documents")
async def upload_document(
    file: UploadFile,
    document_service: DocumentService = Depends(get_document_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """上传并处理文档"""
    dto = await document_service.upload_document(file, user_id)
    result = await document_service.process_document(dto.document_id)
    return result
```

### 异步任务

```python
from celery import Celery
from src.application.processors.async_document_processor import AsyncDocumentProcessor

celery_app = Celery('tasks')

@celery_app.task
def process_document_task(document_id: str):
    """异步处理文档"""
    processor = AsyncDocumentProcessor()
    result = asyncio.run(processor.process(document_id))
    return result
```

## 最佳实践

### 1. 服务职责单一

每个服务只负责一个业务领域：

```python
# ✅ 推荐
class DocumentService:  # 只处理文档
    pass

class EmbeddingService:  # 只处理向量化
    pass

# ❌ 不推荐
class MegaService:  # 什么都做
    def upload_document(self): pass
    def embed_text(self): pass
    def call_llm(self): pass
```

### 2. 使用 DTO 传递数据

```python
# ✅ 推荐
def get_document(self, id: str) -> DocumentDTO:
    return DocumentDTO(...)

# ❌ 不推荐
def get_document(self, id: str) -> dict:
    return {...}
```

### 3. 异步优先

```python
# ✅ 推荐
async def process_document(self, id: str):
    await self.service.execute()

# ❌ 不推荐 (除非必须)
def process_document(self, id: str):
    self.service.execute()
```

### 4. 错误处理

```python
from src.utils.exceptions import BusinessException

async def process_document(self, id: str):
    try:
        result = await self.service.execute()
        return result
    except ResourceNotFoundError:
        raise BusinessException("RESOURCE_NOT_FOUND", f"Document {id} not found")
    except Exception as e:
        logger.exception("Processing failed: {}", e)
        raise BusinessException("PROCESSING_FAILED", str(e))
```

## 测试

### 单元测试

```python
import pytest
from src.application.services.document_service import DocumentService

@pytest.mark.asyncio
async def test_upload_document():
    service = DocumentService()
    dto = await service.upload_document(test_file, "user_123")
    assert dto.document_id is not None
    assert dto.status == "uploaded"
```

### 集成测试

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_document_end_to_end():
    service = DocumentService()
    processor = AsyncDocumentProcessor()
    
    # 上传
    dto = await service.upload_document(test_file, "user_123")
    
    # 处理
    result = await processor.process(dto.document_id)
    
    # 验证
    assert result.extracted_entities is not None
    assert len(result.evidence_records) > 0
```

## 相关文档

- [后端 README](../../README.md)
- [领域层 README](../domain/README.md)
- [基础设施层 README](../infrastructure/README.md)

---

**最后更新**: 2026-03-22 (v3.0)
