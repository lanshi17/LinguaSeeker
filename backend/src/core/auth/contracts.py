"""Typed authentication contracts used by API dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


AuthAccountType = Literal["public", "user"]
AuthMethod = Literal["anonymous", "api_key", "session"]


@dataclass(frozen=True)
class AuthContext:
    """Current request account context.

    ``user_id=None`` is the public account scope. Personal accounts always
    carry their persisted ``users.user_id``.
    """

    authenticated: bool
    account_type: AuthAccountType
    user_id: UUID | None
    email: str | None
    display_name: str | None
    method: AuthMethod

    @property
    def owner_user_id(self) -> UUID | None:
        """Return the DB owner scope for task and evidence isolation."""
        return self.user_id if self.account_type == "user" else None


@dataclass(frozen=True)
class SessionClaims:
    """Decoded signed session-cookie claims."""

    expires_at: int
    user_id: UUID | None = None
    email: str | None = None


PUBLIC_AUTH_CONTEXT = AuthContext(
    authenticated=False,
    account_type="public",
    user_id=None,
    email=None,
    display_name="Public account",
    method="anonymous",
)

