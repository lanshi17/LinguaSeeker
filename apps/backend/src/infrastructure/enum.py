from enum import Enum

from src.config import settings as cfg


class DatabaseTypeEnum(str, Enum):
    QDRANT = "qdrant"
    REDIS = "redis"
    MINIO = "minio"
    NEO4J = "neo4j"


class HealthStatusEnum(str, Enum):
    OK = "ok"
    ERROR = "error"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class QdrantEntityTypeEnum(str, Enum):
    COLLECTION = "collection"
    POINT = "point"
    PAYLOAD = "payload"


class QdrantIndexStatusEnum(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


class RedisEntityTypeEnum(str, Enum):
    KEY = "key"
    HASH = "hash"
    LIST = "list"
    SET = "set"
    ZSET = "zset"
    STREAM = "stream"


class RedisCacheStatusEnum(str, Enum):
    HIT = "hit"
    MISS = "miss"
    STALE = "stale"


class MinioEntityTypeEnum(str, Enum):
    BUCKET = "bucket"
    OBJECT = "object"


class MinioObjectStatusEnum(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    DELETED = "deleted"


class MinioBucketNameEnum(str, Enum):
    LITERATURE_UPLOADS = cfg.minio_uploads_bucket
    PROCESSED_RESULTS = cfg.minio_results_bucket


class Neo4jEntityTypeEnum(str, Enum):
    NODE = "node"
    RELATIONSHIP = "relationship"
    PATH = "path"


class Neo4jQueryStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
