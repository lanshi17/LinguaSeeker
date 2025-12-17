"""数据库配置"""
from typing import Optional
from dataclasses import dataclass
import os
from enum import Enum


@dataclass
class PostgreSQLConfig:
    """PostgreSQL配置"""
    host: str = "localhost"
    port: int = 5432
    database: str = "acmg_ps3"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20


@dataclass
class Neo4jConfig:
    """Neo4j图数据库配置"""
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 50


@dataclass
class MilvusConfig:
    """Milvus向量数据库配置"""
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "paper_chunks"
    dimension: int = 1536  # nomic-embed-text或openai embedding维度
    index_type: str = "IVF_FLAT"
    metric_type: str = "L2"


@dataclass
class QdrantConfig:
    """Qdrant向量数据库配置"""
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "paper_chunks"
    dimension: int = 1536
    prefer_grpc: bool = False


class VectorBackend(str, Enum):
    """向量数据库后端选择"""
    QDRANT = "qdrant"
    MILVUS = "milvus"


@dataclass
class MinIOConfig:
    """MinIO对象存储配置"""
    endpoint: str = "localhost:9000"
    access_key: str = ""
    secret_key: str = ""
    bucket_name: str = "acmg-documents"
    secure: bool = False


class DatabaseConfig:
    """数据库配置管理"""
    
    def __init__(self):
        self.postgresql = PostgreSQLConfig()
        self.neo4j = Neo4jConfig()
        self.milvus = MilvusConfig()
        self.qdrant = QdrantConfig()
        self.vector_backend: VectorBackend = VectorBackend.QDRANT
        self.minio = MinIOConfig()
    
    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        cfg = cls()
        # PostgreSQL
        cfg.postgresql.host = os.getenv("POSTGRES_HOST", cfg.postgresql.host)
        cfg.postgresql.port = int(os.getenv("POSTGRES_PORT", cfg.postgresql.port))
        cfg.postgresql.database = os.getenv("POSTGRES_DB", cfg.postgresql.database)
        cfg.postgresql.user = os.getenv("POSTGRES_USER", cfg.postgresql.user)
        cfg.postgresql.password = os.getenv("POSTGRES_PASSWORD", cfg.postgresql.password)
        cfg.postgresql.pool_size = int(os.getenv("POSTGRES_POOL_SIZE", cfg.postgresql.pool_size))
        cfg.postgresql.max_overflow = int(os.getenv("POSTGRES_MAX_OVERFLOW", cfg.postgresql.max_overflow))

        # Neo4j
        cfg.neo4j.uri = os.getenv("NEO4J_URI", cfg.neo4j.uri)
        cfg.neo4j.user = os.getenv("NEO4J_USER", cfg.neo4j.user)
        cfg.neo4j.password = os.getenv("NEO4J_PASSWORD", cfg.neo4j.password)
        cfg.neo4j.database = os.getenv("NEO4J_DATABASE", cfg.neo4j.database)

        # Vector backend selection
        backend = os.getenv("VECTOR_DB", cfg.vector_backend.value).lower()
        cfg.vector_backend = VectorBackend(backend) if backend in (b.value for b in VectorBackend) else VectorBackend.QDRANT

        # Milvus
        cfg.milvus.host = os.getenv("MILVUS_HOST", cfg.milvus.host)
        cfg.milvus.port = int(os.getenv("MILVUS_PORT", cfg.milvus.port))
        cfg.milvus.collection_name = os.getenv("MILVUS_COLLECTION_NAME", cfg.milvus.collection_name)
        cfg.milvus.dimension = int(os.getenv("MILVUS_DIMENSION", cfg.milvus.dimension))
        cfg.milvus.index_type = os.getenv("MILVUS_INDEX_TYPE", cfg.milvus.index_type)
        cfg.milvus.metric_type = os.getenv("MILVUS_METRIC_TYPE", cfg.milvus.metric_type)

        # Qdrant
        cfg.qdrant.host = os.getenv("QDRANT_HOST", cfg.qdrant.host)
        cfg.qdrant.port = int(os.getenv("QDRANT_PORT", cfg.qdrant.port))
        cfg.qdrant.collection_name = os.getenv("QDRANT_COLLECTION_NAME", cfg.qdrant.collection_name)
        cfg.qdrant.dimension = int(os.getenv("QDRANT_DIMENSION", cfg.qdrant.dimension))

        return cfg
