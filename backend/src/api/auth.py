"""API key authentication dependency."""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from src.core.config import get_config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """Validate X-API-Key header against configured API_KEY.

    Returns the validated key string, or None if no key is configured
    (auth disabled). Routes that need a reviewer_id can use this value.
    """
    cfg = get_config()
    if not cfg.api_key:
        return None  # Auth disabled — no key configured

    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if not hmac.compare_digest(api_key, cfg.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key
