from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


_PROMPT_CACHE: dict[str, dict[str, Any]] = {}
_PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt_bundle(name: str) -> dict[str, Any]:
    if name in _PROMPT_CACHE:
        return _PROMPT_CACHE[name]

    path = _PROMPTS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise ValueError(f"Prompt bundle not found: {name}")

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or not data:
        raise ValueError(f"Prompt bundle '{name}' is empty or malformed")

    _PROMPT_CACHE[name] = data
    return data


def get_prompt_value(bundle: str, key: str) -> Any:
    data = load_prompt_bundle(bundle)
    if key not in data:
        raise ValueError(f"Prompt key '{key}' not found in bundle '{bundle}'")
    return data[key]


def render_prompt_template(bundle: str, key: str, **kwargs: Any) -> str:
    template = get_prompt_value(bundle, key)
    if not isinstance(template, str) or not template:
        raise ValueError(f"Prompt '{bundle}.{key}' is empty or not a string")
    return template.format(**kwargs)


__all__ = [
    "_PROMPT_CACHE",
    "get_prompt_value",
    "load_prompt_bundle",
    "render_prompt_template",
]
