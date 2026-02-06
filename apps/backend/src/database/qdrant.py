# 向量数据库-qdrant 客户端
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from src.config import settings as cfg
from loguru import logger
from pydantic import SecretStr
from src.utils.file_utils import get_all_files_in_directory
import os
from typing import Dict, List, Optional


class QdrantManager:
    """Qdrant 向量数据库管理类"""
    
    def __init__(self):
        """初始化 Qdrant 管理器"""
        self.client = self._create_client()
        self.collection_name = cfg.qdrant_collection_name
        self.embedding_size = cfg.qdrant_dimension  # 使用 config.py 中的 qdrant_dimension
        self.distance = rest.Distance.COSINE
        self.top_k = getattr(cfg, 'qdrant_top_k', 5)  # 默认值 5
        self.score_threshold = getattr(cfg, 'qdrant_score_threshold', 0.7)  # 默认值 0.7
        self.max_retries = getattr(cfg, 'qdrant_max_retries', 3)  # 默认值 3
        self.retry_delay = getattr(cfg, 'qdrant_retry_delay', 1.0)  # 默认值 1.0
    
    def _create_client(self) -> QdrantClient:
        """创建 Qdrant 客户端"""
        # 构建 URL
        qdrant_url = f"http://{cfg.qdrant_host}:{cfg.qdrant_port}"
        
        return QdrantClient(
            url=qdrant_url,
            api_key=SecretStr(cfg.qdrant_api_key) if cfg.qdrant_api_key else None,
            prefer_grpc=cfg.qdrant_prefer_grpc,
        )
    
    def _get_text_embedding(self, text: str) -> List[float]:
        """获取文本的嵌入向量"""
        embedding_model = get_embedding_model(cfg.embedding_model)
        return embedding_model.get_embedding(text)
    
    @property
    def get_client(self) -> QdrantClient:
        """获取 Qdrant 客户端"""
        return self.client
    
    # ==================== 集合管理 ====================
    
    def create_collection_if_not_exists(self):
        """如果集合不存在则创建 Qdrant 集合"""
        try:
            if not self.client.get_collection(self.collection_name):
                logger.info(f"Qdrant 集合 '{self.collection_name}' 不存在，正在创建...")
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest.VectorParams(
                        size=self.embedding_size,
                        distance=self.distance,
                    ),
                )
                logger.info(f"Qdrant 集合 '{self.collection_name}' 创建成功。")
            else:
                logger.info(f"Qdrant 集合 '{self.collection_name}' 已存在。")
        except Exception as e:
            logger.error(f"检查或创建 Qdrant 集合时出错: {e}")
            raise
    
    def delete_collection(self):
        """删除 Qdrant 集合"""
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Qdrant 集合 '{self.collection_name}' 删除成功。")
        except Exception as e:
            logger.error(f"删除 Qdrant 集合时出错: {e}")
            raise
    
    def list_collections(self) -> List[str]:
        """列出所有 Qdrant 集合"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            logger.info(f"当前 Qdrant 集合列表: {collection_names}")
            return collection_names
        except Exception as e:
            logger.error(f"列出 Qdrant 集合时出错: {e}")
            raise
    
    def get_collection_info(self):
        """获取 Qdrant 集合信息"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            logger.info(f"Qdrant 集合 '{self.collection_name}' 信息: {collection_info}")
            return collection_info
        except Exception as e:
            logger.error(f"获取 Qdrant 集合信息时出错: {e}")
            raise
    
    def reset_collection(self):
        """重置 Qdrant 集合（删除并重新创建）"""
        try:
            logger.info(f"正在重置 Qdrant 集合 '{self.collection_name}'...")
            self.delete_collection()
            self.create_collection_if_not_exists()
            logger.info(f"Qdrant 集合 '{self.collection_name}' 重置成功。")
        except Exception as e:
            logger.error(f"重置 Qdrant 集合时出错: {e}")
            raise
    
    # ==================== 健康检查 ====================
    
    def ping(self) -> bool:
        """检查 Qdrant 服务是否可用"""
        try:
            self.client.get_collections()
            logger.info("Qdrant 服务连接成功。")
            return True
        except Exception as e:
            logger.error(f"Qdrant 服务连接失败: {e}")
            return False
    
    def health_check(self) -> bool:
        """检查 Qdrant 服务健康状态"""
        try:
            health = self.client.health_check()
            if health.status == "ok":
                logger.info("Qdrant 服务健康状态良好。")
                return True
            else:
                logger.warning(f"Qdrant 服务健康状态异常: {health.status}")
                return False
        except Exception as e:
            logger.error(f"检查 Qdrant 服务健康状态时出错: {e}")
            return False
    
    # ==================== 数据操作 ====================
    
    def ingest_files(self, file_dir: str):
        """将指定文件夹中的所有文件向量化并存储到 Qdrant"""
        files = get_all_files_in_directory(file_dir)
        points = []
        
        for file_path, content in files.items():
            vector = get_text_embedding(content)
            if len(vector) != self.embedding_size:
                logger.warning(f"文件 '{file_path}' 的向量维度不匹配，跳过。")
                continue
            
            point_id = os.path.basename(file_path)
            point = rest.PointStruct(
                id=point_id,
                vector=vector,
                payload={"file_path": file_path, "content": content},
            )
            points.append(point)
        
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            logger.info(f"成功将 {len(points)} 个文件向量化并存储到 Qdrant 集合 '{self.collection_name}'。")
        except Exception as e:
            logger.error(f"向 Qdrant 集合插入向量时出错: {e}")
            raise


# ==================== 向后兼容的函数接口 ====================

# 创建全局单例实例
_qdrant_manager: Optional[QdrantManager] = None


def get_qdrant_manager() -> QdrantManager:
    """获取 QdrantManager 单例实例"""
    global _qdrant_manager
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager()
    return _qdrant_manager


def get_qdrant_client() -> QdrantClient:
    """获取 Qdrant 客户端（向后兼容）"""
    return get_qdrant_manager().get_client


def get_qdrant_collection_name() -> str:
    """获取 Qdrant 集合名称（向后兼容）"""
    return cfg.qdrant_collection_name


def get_qdrant_embedding_size() -> int:
    """获取 Qdrant 向量维度（向后兼容）"""
    return cfg.qdrant_dimension


def get_qdrant_distance() -> rest.Distance:
    """获取 Qdrant 距离度量方式（向后兼容）"""
    return rest.Distance.COSINE


def get_qdrant_top_k() -> int:
    """获取 Qdrant 检索返回的 Top K 数量（向后兼容）"""
    return getattr(cfg, 'qdrant_top_k', 5)


def get_qdrant_score_threshold() -> float:
    """获取 Qdrant 检索结果的相似度阈值（向后兼容）"""
    return getattr(cfg, 'qdrant_score_threshold', 0.7)


def get_qdrant_max_retries() -> int:
    """获取 Qdrant 操作的最大重试次数（向后兼容）"""
    return getattr(cfg, 'qdrant_max_retries', 3)


def get_qdrant_retry_delay() -> float:
    """获取 Qdrant 操作的重试延迟时间（秒）（向后兼容）"""
    return getattr(cfg, 'qdrant_retry_delay', 1.0)


# CRUD 操作（向后兼容）
def create_qdrant_collection_if_not_exists(client: Optional[QdrantClient] = None):
    """如果集合不存在则创建 Qdrant 集合（向后兼容）"""
    get_qdrant_manager().create_collection_if_not_exists()


def delete_qdrant_collection(client: Optional[QdrantClient] = None):
    """删除 Qdrant 集合（向后兼容）"""
    get_qdrant_manager().delete_collection()


def list_qdrant_collections(client: Optional[QdrantClient] = None) -> List[str]:
    """列出所有 Qdrant 集合（向后兼容）"""
    return get_qdrant_manager().list_collections()


def get_qdrant_collection_info(client: Optional[QdrantClient] = None):
    """获取 Qdrant 集合信息（向后兼容）"""
    return get_qdrant_manager().get_collection_info()


def ping_qdrant(client: Optional[QdrantClient] = None) -> bool:
    """检查 Qdrant 服务是否可用（向后兼容）"""
    return get_qdrant_manager().ping()


def health_check_qdrant(client: Optional[QdrantClient] = None) -> bool:
    """检查 Qdrant 服务健康状态（向后兼容）"""
    return get_qdrant_manager().health_check()


def reset_qdrant_collection(client: Optional[QdrantClient] = None):
    """重置 Qdrant 集合（删除并重新创建）（向后兼容）"""
    get_qdrant_manager().reset_collection()


def ingest_files_to_qdrant(client: Optional[QdrantClient] = None, file_dir: str = ""):
    """将指定文件夹中的所有文件向量化并存储到 Qdrant（向后兼容）"""
    get_qdrant_manager().ingest_files(file_dir)
    
    