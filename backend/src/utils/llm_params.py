"""LLM parameter resolution utilities."""
from __future__ import annotations


def resolve_max_tokens(
    configured_max_tokens: int,
    percentage: float = 1.0,
    *,
    minimum: int = 256,
) -> int:
    """Resolve effective max_tokens by applying a percentage to the configured value.

    Allows callers to dynamically scale down the model's output budget based on
    task complexity (e.g. short summaries use 25%, full extraction uses 100%).

    Args:
        configured_max_tokens: The base max_tokens from config (default 8192).
        percentage: Scale factor in [0.0, 1.0]. Clamped automatically.
        minimum: Floor value to prevent unreasonably small token budgets.

    Returns:
        Effective max_tokens to pass to the LLM client.
    """
    if configured_max_tokens <= 0:
        configured_max_tokens = 8192
    clamped = max(0.0, min(percentage, 1.0))
    effective = int(configured_max_tokens * clamped)
    return max(effective, minimum)
