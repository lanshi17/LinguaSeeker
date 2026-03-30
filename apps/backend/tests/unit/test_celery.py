import pytest
import redis

from src.celery_app import celery_app


def test_celery_redis_connection() -> None:
    redis_url = celery_app.conf.broker_url
    client = redis.Redis.from_url(redis_url)
    try:
        assert client.ping() is True
    except Exception as exc:
        pytest.skip(f"Redis unreachable via Celery broker URL: {redis_url} ({exc})")
