import redis
from typing import Optional
# TODO 存入Redis缓存,记录文件的哈希值, 防止重复处理,如果存在相同哈希值的结果,则直接返回结果,否则继续处理
from src.config import settings as cfg

class RedisClient:
    """Redis client wrapper with proper authentication handling."""

    def __init__(self):
        self._connection = None
        
        
    def get_connection(self) -> redis.Redis:
        """Get Redis connection with proper authentication."""        
        # Create connection with authentication
        connection = redis.Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
            password=cfg.redis_password,  # This handles authentication
            max_connections=cfg.redis_max_connections,
            decode_responses=False,  # Keep responses as bytes to handle all types
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        return connection
    
    async def get_async_connection(self) -> redis.Redis:
        """Get async Redis connection with proper authentication."""
        
        # Create async connection with authentication
        connection = redis.Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
            password=cfg.redis_password,  # This handles authentication
            max_connections=cfg.redis_max_connections,
            decode_responses=False,  # Keep responses as bytes to handle all types
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        return connection


# Global Redis client instance
redis_client = RedisClient()
async def store_pdf_hash_in_redis(pdf_hash: str, expiration: Optional[int] = 86400) -> None:
    """Store the PDF hash in Redis with an optional expiration time (default 1 day)."""
    redis_conn = await redis_client.get_async_connection()
    await redis_conn.set(pdf_hash, "processed", ex=expiration)
async def check_pdf_hash_in_redis(pdf_hash: str) -> bool:
    """Check if the PDF hash exists in Redis."""
    redis_conn = await redis_client.get_async_connection()
    exists = await redis_conn.exists(pdf_hash)
    return exists == 1
