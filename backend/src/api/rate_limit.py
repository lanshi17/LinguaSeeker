"""API rate limiting singleton."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Global rate limiter (initialized here, registered in main.py)
limiter = Limiter(key_func=get_remote_address)
