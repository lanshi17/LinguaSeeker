from __future__ import annotations


def test_infrastructure_redis_reexports_legacy_singletons() -> None:
    from src.database.redis_client import RedisClient as LegacyRedisClient
    from src.database.redis_client import redis_client as legacy_redis_client
    from src.infrastructure.redis import RedisClient, redis_client

    assert RedisClient is LegacyRedisClient
    assert redis_client is legacy_redis_client


def test_health_module_uses_infrastructure_shims() -> None:
    import src.health as health
    from src.infrastructure.minio import MinIOClient
    from src.infrastructure.redis import redis_client

    assert health.MinIOClient is MinIOClient
    assert health.redis_client is redis_client
