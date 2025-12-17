"""Qdrant向量数据库仓储"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from ..domain.entities.vector_entity import VectorDocument


class IVectorRepository(ABC):
    """向量数据库仓储接口"""
    
    @abstractmethod
    async def insert(self, document: VectorDocument) -> bool:
        """插入向量文档"""
        pass
    
    @abstractmethod
    async def batch_insert(self, documents: List[VectorDocument]) -> bool:
        """批量插入向量文档"""
        pass
    
    @abstractmethod
    async def search_by_vector(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorDocument]:
        """向量相似度搜索"""
        pass
    
    @abstractmethod
    async def search_by_text(
        self, 
        query_text: str, 
        top_k: int = 10
    ) -> List[VectorDocument]:
        """文本语义搜索（需要先转换为向量）"""
        pass
    
    @abstractmethod
    async def delete_by_pmid(self, pmid: str) -> bool:
        """根据PMID删除相关文档"""
        pass


class QdrantVectorRepository(IVectorRepository):
    """Qdrant向量数据库仓储实现"""
    
    def __init__(self, qdrant_client, collection_name: str = "paper_chunks"):
        self.client = qdrant_client
        self.collection_name = collection_name
    
    async def insert(self, document: VectorDocument) -> bool:
        """插入向量文档"""
        # TODO: 使用qdrant_client.upsert插入
        pass
    
    async def batch_insert(self, documents: List[VectorDocument]) -> bool:
        """批量插入向量文档"""
        # TODO: 批量upsert
        pass
    
    async def search_by_vector(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorDocument]:
        """向量相似度搜索"""
        # TODO: client.search(collection_name, query_vector, limit=top_k, filter=...)
        pass
    
    async def search_by_text(
        self, 
        query_text: str, 
        top_k: int = 10
    ) -> List[VectorDocument]:
        """文本语义搜索"""
        # TODO: 将文本转为向量后调用search_by_vector
        pass
    
    async def delete_by_pmid(self, pmid: str) -> bool:
        """根据PMID删除相关文档"""
        # TODO: 根据payload过滤删除
        pass