# 向量数据库-qdrant 客户端
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from src.config import settings as cfg
from loguru import logger
from pydantic import SecretStr
from langchain_openai.embeddings import OpenAIEmbeddings
from src.component.models import (
    QdrantCollectionInfoResponse,
    QdrantSearchResponse,
    QdrantHealthResponse,
    QdrantPoint,
    QdrantSearchResultItem,
)
from src.utils.file_utils import get_all_files_in_directory
import os
from typing import Dict, List, Optional
from uuid import uuid4


class QdrantManager:
    """Qdrant 向量数据库管理类"""
    
    def __init__(self, collection_name: str = cfg.qdrant_collection_name):
        """初始化 Qdrant 管理器"""
        self.client = self._create_client()
        self.collection_name = collection_name
        self.embedding_size = cfg.qdrant_dimension  # 使用 config.py 中的 qdrant_dimension
        self.distance = rest.Distance.COSINE
        self.top_k = getattr(cfg, 'qdrant_top_k', 5)  # 默认值 5
        self.score_threshold = getattr(cfg, 'qdrant_score_threshold', 0.7)  # 默认值 0.7
        self.max_retries = getattr(cfg, 'qdrant_max_retries', 3)  # 默认值 3
        self.retry_delay = getattr(cfg, 'qdrant_retry_delay', 1.0)  # 默认值 1.0
        self._embedding_client: Optional[OpenAIEmbeddings] = None

    def _get_embedding_client(self) -> OpenAIEmbeddings:
        """获取 Embedding 客户端"""
        if self._embedding_client is None:
            provider = getattr(cfg, "embedding_provider", "openai").lower()
            check_embedding_ctx_length = provider == "openai"
            dimensions = getattr(cfg, "embedding_dimension", None)
            self._embedding_client = OpenAIEmbeddings(
                model=cfg.embedding_model,
                api_key=SecretStr(cfg.embedding_api_key),
                base_url=cfg.embedding_base_url,
                tiktoken_enabled=(provider == "openai"),
                check_embedding_ctx_length=check_embedding_ctx_length,
                dimensions=dimensions,
            )
        return self._embedding_client

    def _get_text_embedding(self, text: str) -> List[float]:
        """获取文本的嵌入向量"""
        client = self._get_embedding_client()
        return client.embed_query(text)

    def _chunk_text(self, text: str, max_chars: int, overlap: int) -> List[str]:
        """将文本按字符长度分块，避免超出嵌入模型限制"""
        if max_chars <= 0:
            return [text]
        text = text.strip()
        if not text:
            return []
        chunks = []
        start = 0
        step = max(max_chars - overlap, 1)
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += step
        return chunks
    
    def _create_client(self) -> AsyncQdrantClient:
        """创建 Qdrant 客户端"""
        api_key = cfg.qdrant_api_key
        if isinstance(api_key, SecretStr):
            api_key = api_key.get_secret_value()
        return AsyncQdrantClient(
            host=cfg.qdrant_host,
            port=cfg.qdrant_port,
            api_key=api_key or None,
            prefer_grpc=cfg.qdrant_prefer_grpc,
            https=cfg.qdrant_https,
            verify=cfg.qdrant_verify_ssl,
        )
    
    @property
    def get_client(self) -> AsyncQdrantClient:
        """获取 Qdrant 客户端"""
        return self.client
    
    # ==================== 集合管理 ====================
    
    async def create_collection_if_not_exists(self, collection_name: str = cfg.qdrant_collection_name) -> None:
        """如果集合不存在则创建 Qdrant 集合"""
        try:
            self.collection_name = collection_name
            if await self.client.collection_exists(collection_name):
                logger.info(f"Qdrant 集合 '{collection_name}' 已存在。")
                return
            logger.info(f"Qdrant 集合 '{collection_name}' 不存在，正在创建...")
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=rest.VectorParams(
                    size=self.embedding_size,
                    distance=self.distance,
                ),
            )
            logger.info(f"Qdrant 集合 '{collection_name}' 创建成功。")
        except Exception as e:
            logger.error(f"检查或创建 Qdrant 集合时出错: {e}")
            raise
    
    async def delete_collection(self) -> None:
        """删除 Qdrant 集合"""
        try:
            await self.client.delete_collection(self.collection_name)
            logger.info(f"Qdrant 集合 '{self.collection_name}' 删除成功。")
        except Exception as e:
            logger.error(f"删除 Qdrant 集合时出错: {e}")
            raise
    
    async def list_collections(self) -> List[str]:
        """列出所有 Qdrant 集合"""
        try:
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            logger.info(f"当前 Qdrant 集合列表: {collection_names}")
            return collection_names
        except Exception as e:
            logger.error(f"列出 Qdrant 集合时出错: {e}")
            raise
    
    async def get_collection_info(self) -> QdrantCollectionInfoResponse:
        """获取 Qdrant 集合信息"""
        try:
            collection_info = await self.client.get_collection(self.collection_name)
            logger.info(f"Qdrant 集合 '{self.collection_name}' 信息: {collection_info}")
            vectors_count = getattr(collection_info, "vectors_count", None)
            if vectors_count is None:
                vectors_count = getattr(collection_info, "points_count", 0)
            segments_count = int(getattr(collection_info, "segments_count", 0) or 0)
            index_status = str(getattr(collection_info, "status", "unknown"))
            storage_size = getattr(collection_info, "disk_data_size", None)
            if storage_size is None:
                storage_size = getattr(collection_info, "storage_size", None)
            config = getattr(collection_info, "config", None)
            if hasattr(config, "model_dump"):
                config = config.model_dump()
            return QdrantCollectionInfoResponse(
                name=self.collection_name,
                vectors_count=int(vectors_count or 0),
                segments_count=segments_count,
                index_status=index_status,
                storage_size=storage_size,
                config=config,
            )
        except Exception as e:
            logger.error(f"获取 Qdrant 集合信息时出错: {e}")
            raise
    
    async def reset_collection(self) -> None:
        """重置 Qdrant 集合（删除并重新创建）"""
        try:
            logger.info(f"正在重置 Qdrant 集合 '{self.collection_name}'...")
            await self.delete_collection()
            await self.create_collection_if_not_exists(self.collection_name)
            logger.info(f"Qdrant 集合 '{self.collection_name}' 重置成功。")
        except Exception as e:
            logger.error(f"重置 Qdrant 集合时出错: {e}")
            raise
    
    # ==================== 健康检查 ====================
    
    async def ping(self) -> QdrantHealthResponse:
        """检查 Qdrant 服务是否可用"""
        try:
            await self.client.get_collections()
            logger.info("Qdrant 服务连接成功。")
            return QdrantHealthResponse(status="ok")
        except Exception as e:
            logger.error(f"Qdrant 服务连接失败: {e}")
            return QdrantHealthResponse(status="error", details={"error": str(e)})
    
    
    # ==================== 数据操作 ====================
    
    async def ingest_files(self, file_dir: str) -> List[QdrantPoint]:
        """将指定文件夹中的所有文件向量化并存储到 Qdrant"""
        files = get_all_files_in_directory(file_dir)
        points = []
        qdrant_points: List[QdrantPoint] = []
        max_chars = getattr(cfg, "embedding_max_chars", 8000)
        overlap = getattr(cfg, "embedding_chunk_overlap", 200)
        
        for file_path, content in files.items():
            chunks = self._chunk_text(content, max_chars=max_chars, overlap=overlap)
            if not chunks:
                logger.warning(f"文件 '{file_path}' 内容为空，跳过。")
                continue
            for chunk_index, chunk in enumerate(chunks):
                vector = self._get_text_embedding(chunk)
                if len(vector) != self.embedding_size:
                    logger.warning(f"文件 '{file_path}' 的向量维度不匹配，跳过。")
                    continue
                
                point_id = uuid4().hex
                payload = {
                    "file_path": file_path,
                    "chunk_index": chunk_index,
                    "content": chunk,
                }
                qdrant_points.append(
                    QdrantPoint(id=point_id, vector=vector, payload=payload)
                )
                points.append(
                    rest.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                )

        if not points:
            logger.warning("未找到可写入的文件向量，跳过 Qdrant upsert。")
            return []
        
        try:
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            logger.info(f"成功将 {len(points)} 个文件向量化并存储到 Qdrant 集合 '{self.collection_name}'。")
            return qdrant_points
        except Exception as e:
            logger.error(f"向 Qdrant 集合插入向量时出错: {e}")
            raise

    async def search(self, query_vector: List[float], top_k: int, score_threshold: float) -> QdrantSearchResponse:
        """在 Qdrant 中检索 Top-K 文档"""
        query_response = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )
        results = getattr(query_response, "points", None)
        if results is None:
            results = getattr(query_response, "result", [])
        response_items = [
            QdrantSearchResultItem(
                point_id=str(item.id),
                score=float(item.score),
                payload=item.payload,
            )
            for item in results
        ]
        return QdrantSearchResponse(results=response_items)


# ==================== 单例入口 ====================

_qdrant_manager: Optional[QdrantManager] = None


def get_qdrant_manager() -> QdrantManager:
    """获取 QdrantManager 单例实例"""
    global _qdrant_manager
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager()
    return _qdrant_manager
    
    