"""
Redis client utility for the application.

Handles Redis connection with proper authentication and configuration.
"""
import redis.asyncio as redis
from typing import Optional
from src.config.database_config import DatabaseConfig


class RedisClient:
    """Redis client wrapper with proper authentication handling."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """Initialize Redis client with configuration."""
        self.config = config or DatabaseConfig.from_env()
        
    def get_connection(self) -> redis.Redis:
        """Get Redis connection with proper authentication."""
        redis_cfg = self.config.redis
        
        # Create connection with authentication
        connection = redis.Redis(
            host=redis_cfg.host,
            port=redis_cfg.port,
            db=redis_cfg.db,
            password=redis_cfg.password,  # This handles authentication
            max_connections=redis_cfg.max_connections,
            decode_responses=False,  # Keep responses as bytes to handle all types
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        return connection
    
    async def get_async_connection(self) -> redis.Redis:
        """Get async Redis connection with proper authentication."""
        redis_cfg = self.config.redis
        
        # Create async connection with authentication
        connection = redis.Redis(
            host=redis_cfg.host,
            port=redis_cfg.port,
            db=redis_cfg.db,
            password=redis_cfg.password,  # This handles authentication
            max_connections=redis_cfg.max_connections,
            decode_responses=False,  # Keep responses as bytes to handle all types
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        return connection


# Global Redis client instance
redis_client = RedisClient()


def get_redis_client(config: Optional[DatabaseConfig] = None) -> RedisClient:
    """Get Redis client instance."""
    return RedisClient(config)