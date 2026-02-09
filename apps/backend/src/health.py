from loguru import logger
import psycopg2
from qdrant_client import QdrantClient
from functools import lru_cache

from src.config import settings as cfg
from src.database.redis_client import redis_client
from src.database.minio_client import MinIOClient


@lru_cache(maxsize=1)
def _get_minio_client() -> MinIOClient:
    return MinIOClient(
        endpoint=cfg.minio_endpoint,
        access_key=cfg.minio_access_key,
        secret_key=cfg.minio_secret_key,
        secure=cfg.minio_secure,
        bucket_name=cfg.minio_results_bucket,
    )


@lru_cache(maxsize=1)
def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        host=cfg.qdrant_host,
        port=cfg.qdrant_port,
        api_key=cfg.qdrant_api_key or None,
        https=cfg.qdrant_https,
        prefer_grpc=cfg.qdrant_prefer_grpc,
        verify=cfg.qdrant_verify_ssl,
    )


def check_redis_connection() -> bool:
    try:
        conn = redis_client.get_connection()
        return bool(conn.ping())
    except Exception as exc:
        logger.warning("Redis connection failed: {}", exc)
        return False


def check_postgres_connection() -> bool:
    try:
        conninfo = (
            f"host={cfg.postgres_host} "
            f"port={cfg.postgres_port} "
            f"dbname={cfg.postgres_db} "
            f"user={cfg.postgres_user} "
            f"password={cfg.postgres_password} "
            "connect_timeout=3"
        )
        with psycopg2.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception as exc:
        logger.warning("PostgreSQL connection failed: {}", exc)
        return False


def check_minio_connection() -> bool:
    try:
        client = _get_minio_client()
        client.client.list_buckets()
        return True
    except Exception as exc:
        logger.warning("MinIO connection failed: {}", exc)
        return False


def check_qdrant_connection() -> bool:
    try:
        client = _get_qdrant_client()
        client.get_collections()
        return True
    except Exception as exc:
        logger.warning("Qdrant connection failed: {}", exc)
        return False


def check_all_connections() -> dict[str, bool]:
    return {
        "redis": check_redis_connection(),
        "postgres": check_postgres_connection(),
        "minio": check_minio_connection(),
        "qdrant": check_qdrant_connection(),
    }