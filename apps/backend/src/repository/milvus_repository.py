"""Milvus向量数据库仓储"""
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
        """向量相似度搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回top K个结果
            filters: 过滤条件，例如: {"pmid": "12345678"}
        """
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


class MilvusVectorRepository(IVectorRepository):
    """Milvus向量数据库仓储实现"""
    
    def __init__(self, milvus_client, collection_name: str = "paper_chunks"):
        self.client = milvus_client
        self.collection_name = collection_name
    
    async def insert(self, document: VectorDocument) -> bool:
        """插入向量文档"""
        # TODO: 实现Milvus插入逻辑
        pass
    
    async def batch_insert(self, documents: List[VectorDocument]) -> bool:
        """批量插入向量文档"""
        # TODO: 实现Milvus批量插入
        pass
    
    async def search_by_vector(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorDocument]:
        """向量相似度搜索"""
        # TODO: 实现Milvus向量搜索
        # collection.search(data=[query_embedding], ...)
        pass
    
    async def search_by_text(
        self, 
        query_text: str, 
        top_k: int = 10
    ) -> List[VectorDocument]:
        """文本语义搜索"""
        # TODO: 先用embedding模型转换text为向量，再调用search_by_vector
        pass
    
    async def delete_by_pmid(self, pmid: str) -> bool:
        """根据PMID删除相关文档"""
        # TODO: 实现Milvus删除逻辑
        pass
