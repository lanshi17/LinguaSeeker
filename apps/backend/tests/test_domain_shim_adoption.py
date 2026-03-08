from __future__ import annotations


def test_domain_support_modules_use_infrastructure_shims() -> None:
    import src.domain.agent.interaction as interaction
    from src.infrastructure.redis import RedisClient

    assert interaction.RedisClient is RedisClient
