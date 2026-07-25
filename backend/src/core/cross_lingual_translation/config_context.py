"""Typed configuration context — single injection point for all LLM settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _string_attr(obj: Any, name: str, default: str = "") -> str:
    """Return a string config attribute, ignoring mock/placeholder values."""
    value = getattr(obj, name, default)
    return value if isinstance(value, str) else default


def _list_attr(obj: Any, name: str) -> list[str]:
    """Return a list[str] config attribute, ignoring mock/placeholder values."""
    value = getattr(obj, name, [])
    return value if isinstance(value, list) else []


@dataclass(frozen=True)
class TranslationConfigContext:
    """Subset of app config needed by translation/formatting modules.

    Built once from ``cfg.translation`` at service init, then injected
    into sub-modules. Prevents raw config leakage into deep code.
    """

    model: str
    api_key: str
    api_keys: list[str] = field(default_factory=list)
    base_url: str = ""
    local_base_url: str = ""
    local_target_lang: str = "en"
    local_timeout: float = 60.0
    remote_base_url: str = ""
    remote_api_key: str = ""
    remote_api_keys: list[str] = field(default_factory=list)
    remote_model: str = ""
    temperature: float = 0.0
    max_tokens: int = 8192
    timeout: int = 60

    @classmethod
    def from_config(cls, cfg: Any) -> TranslationConfigContext:
        """Build from the global config object (``cfg.translation``)."""
        tr = getattr(cfg, "translation", None)
        if not isinstance(getattr(tr, "model", None), str):
            tr = cfg.llm
        remote_api_keys = getattr(tr, "remote_all_api_keys", None)
        if remote_api_keys is None:
            remote_api_keys = _list_attr(tr, "remote_api_keys")
        if not isinstance(remote_api_keys, list):
            remote_api_keys = []
        remote_base_url = _string_attr(tr, "remote_base_url")
        remote_model = _string_attr(tr, "remote_model")
        remote_api_key = _string_attr(tr, "remote_api_key")
        use_remote_override = bool(remote_base_url)
        api_keys = list(remote_api_keys) if use_remote_override and remote_api_keys else tr.all_api_keys
        return cls(
            model=remote_model or _string_attr(tr, "model"),
            api_key=remote_api_key or _string_attr(tr, "api_key"),
            api_keys=api_keys,
            base_url=remote_base_url or _string_attr(tr, "base_url"),
            local_base_url=_string_attr(tr, "local_base_url"),
            local_target_lang=_string_attr(tr, "local_target_lang", "en") or "en",
            local_timeout=getattr(tr, "local_timeout", 60.0)
            if isinstance(getattr(tr, "local_timeout", 60.0), (int, float))
            else 60.0,
            remote_base_url=remote_base_url,
            remote_api_key=remote_api_key,
            remote_api_keys=list(remote_api_keys),
            remote_model=remote_model,
            temperature=getattr(tr, "temperature", 0.0) or 0.0,
            max_tokens=getattr(tr, "max_tokens", 8192),
            timeout=tr.timeout,
        )
