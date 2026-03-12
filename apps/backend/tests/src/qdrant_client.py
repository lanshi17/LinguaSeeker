"""
Qdrant向量数据库客户端
处理Qdrant连接和操作，特别针对SSL/TLS问题进行了优化
"""
import logging
import urllib3
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.database_config import DatabaseConfig

logger = logging.getLogger(__name__)

# 禁用SSL警告（对于开发环境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class QdrantManager:
    """Qdrant向量数据库管理器，专门处理SSL/TLS连接问题"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig.from_env()
        self.client = None
        
    def connect(self) -> bool:
        """建立Qdrant连接，具有多重回退机制以解决SSL/TLS问题"""
        try:
            # 根据TLS配置定义连接方式的优先级顺序
            if self.config.qdrant.use_tls:
                # 如果启用了TLS，优先尝试HTTPS连接
                connection_methods = [
                    self._create_https_client,         # 1. HTTPS连接
                    self._create_url_based_client,     # 2. 基于URL的HTTPS连接
                    self._create_http_client_no_verify, # 3. HTTP连接（忽略SSL验证）
                    self._create_http_client_basic,     # 4. 基础HTTP连接
                    self._create_grpc_client_no_ssl,    # 5. gRPC连接（无SSL）
                ]
            else:
                # 如果未启用TLS，按传统顺序尝试
                connection_methods = [
                    self._create_http_client_basic,     # 1. 基础HTTP连接（无SSL）
                    self._create_http_client_no_verify, # 2. HTTP连接（忽略SSL验证）
                    self._create_grpc_client_no_ssl,    # 3. gRPC连接（无SSL）
                    self._create_url_based_client,      # 4. 基于URL的连接
                ]
            
            for i, method in enumerate(connection_methods, 1):
                try:
                    logger.info(f"尝试连接方式 {i}: {method.__name__}")
                    self.client = method()
                    
                    if self.client:
                        # 测试连接
                        collections = self.client.get_collections()
                        logger.info(f"✓ Qdrant 连接成功 - 可用集合数量: {len(collections.collections)}, 使用方式: {method.__name__}")
                        return True
                except Exception as e:
                    logger.warning(f"连接方式 {i} ({method.__name__}) 失败: {str(e)}")
                    continue
            
            logger.error("所有Qdrant连接方式均失败")
            return False
            
        except Exception as e:
            logger.error(f"Qdrant 服务连接失败: {str(e)}")
            return False
    
    def _create_http_client_basic(self):
        """创建基础HTTP客户端 - 无SSL配置"""
        try:
            return QdrantClient(
                host=self.config.qdrant.host,
                port=self.config.qdrant.port,
                api_key=self.config.qdrant.api_key,
                prefer_grpc=False,
                timeout=30.0
            )
        except Exception as e:
            logger.debug(f"基础HTTP连接失败: {str(e)}")
            raise
    
    def _create_http_client_no_verify(self):
        """创建HTTP客户端，忽略SSL验证"""
        try:
            return QdrantClient(
                host=self.config.qdrant.host,
                port=self.config.qdrant.port,
                api_key=self.config.qdrant.api_key,
                prefer_grpc=False,
                timeout=30.0,
                https=self.config.qdrant.use_tls,  # 根据配置决定是否使用HTTPS
                verify=self.config.qdrant.verify_ssl  # 根据配置决定是否验证SSL
            )
        except Exception as e:
            logger.debug(f"HTTP SSL配置连接失败: {str(e)}")
            raise
    
    def _create_https_client(self):
        """创建HTTPS客户端"""
        try:
            return QdrantClient(
                host=self.config.qdrant.host,
                port=self.config.qdrant.port,
                api_key=self.config.qdrant.api_key,
                prefer_grpc=False,
                timeout=30.0,
                https=True,  # 强制使用HTTPS
                verify=self.config.qdrant.verify_ssl  # 根据配置决定是否验证SSL
            )
        except Exception as e:
            logger.debug(f"HTTPS连接失败: {str(e)}")
            raise
    
    def _create_grpc_client_no_ssl(self):
        """创建gRPC客户端，避免SSL配置冲突"""
        try:
            # 为避免SSL版本问题，使用最简单的配置
            return QdrantClient(
                host=self.config.qdrant.host,
                port=self.config.qdrant.port,
                grpc_port=self.config.qdrant.grpc_port,
                api_key=self.config.qdrant.api_key,
                prefer_grpc=True,  # 仍使用gRPC但不指定SSL参数
                timeout=30.0
                # 不设置任何SSL相关参数以避免OPENSSL_INTERNAL:WRONG_VERSION_NUMBER错误
            )
        except Exception as e:
            logger.debug(f"gRPC无SSL连接失败: {str(e)}")
            raise
    
    def _create_url_based_client(self):
        """创建基于URL的客户端，用于HTTPS连接"""
        try:
            # 构建URL
            protocol = "https" if self.config.qdrant.use_tls else "http"
            url = f"{protocol}://{self.config.qdrant.host}:{self.config.qdrant.port}"
            
            return QdrantClient(
                url=url,
                api_key=self.config.qdrant.api_key,
                timeout=30.0,
                verify=self.config.qdrant.verify_ssl
            )
        except Exception as e:
            logger.debug(f"URL-based连接失败: {str(e)}")
            raise
    
    def ping(self) -> bool:
        """测试Qdrant服务连通性"""
        try:
            if self.client is None:
                if not self.connect():
                    return False
            
            # 获取集合列表作为连接测试
            collections = self.client.get_collections()
            logger.info(f"✓ Qdrant 服务连通性测试成功 - 集合数量: {len(collections.collections)}")
            return True
            
        except Exception as e:
            logger.error(f"Qdrant 服务连接失败: {str(e)}")
            return False
    
    def ensure_collection(self, collection_name: str = None) -> bool:
        """确保指定的集合存在"""
        try:
            if self.client is None:
                if not self.connect():
                    return False
                    
            target_collection = collection_name or self.config.qdrant.collection_name
            
            collections = self.client.get_collections()
            existing_collections = [col.name for col in collections.collections]
            
            if target_collection not in existing_collections:
                # 创建集合
                self.client.create_collection(
                    collection_name=target_collection,
                    vectors_config=models.VectorParams(
                        size=self.config.qdrant.dimension,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"✓ Qdrant 集合 '{target_collection}' 创建成功")
            else:
                logger.info(f"✓ Qdrant 集合 '{target_collection}' 已存在")
                
            return True
            
        except Exception as e:
            logger.error(f"Qdrant 集合操作失败: {str(e)}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.client:
            # QdrantClient没有显式的关闭方法，但我们可以清理引用
            self.client = None


def ping() -> bool:
    """独立的Qdrant连接测试函数，用于兼容现有代码"""
    try:
        config = DatabaseConfig.from_env()
        manager = QdrantManager(config)
        
        # 尝试连接
        if manager.connect():
            # 成功连接后测试ping
            return manager.ping()
        else:
            return False
        
    except Exception as e:
        logger.error(f"Qdrant 服务连接失败: {str(e)}")
        return False