from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple, Union
from uuid import uuid4

_ALLOWED_FILENAME_PATTERN = re.compile(r"[^\w\u4e00-\u9fa5.\- ]")
_SAFE_EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9]{1,16}$")
_SAFE_HASH_PATTERN = re.compile(r"[^a-f0-9]")
_SAFE_METADATA_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def sanitize_filename(filename: str) -> str:
    base_name = Path(filename or "").name
    cleaned_name = _ALLOWED_FILENAME_PATTERN.sub("_", base_name)
    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip(" ._")
    return cleaned_name or "file"


def is_ascii_safe(value: str) -> bool:
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def _is_visible_ascii(value: str) -> bool:
    return all(0x20 <= ord(char) <= 0x7E for char in value)


def filter_ascii_metadata(
    metadata: Optional[Mapping[str, object]],
) -> Dict[str, Union[str, List[str], Tuple[str]]]:
    if not metadata:
        return {}

    safe_metadata: Dict[str, Union[str, List[str], Tuple[str]]] = {}
    for raw_key, raw_value in metadata.items():
        if raw_value is None:
            continue

        key = str(raw_key).strip()
        value = str(raw_value)
        if not key:
            continue

        if (
            is_ascii_safe(key)
            and is_ascii_safe(value)
            and _SAFE_METADATA_KEY_PATTERN.match(key) is not None
            and _is_visible_ascii(value)
        ):
            safe_metadata[key] = value

    return safe_metadata


def build_storage_key(
    file_hash: str,
    filename: Optional[str],
    default_extension: str = ".bin",
) -> str:
    hash_prefix = _SAFE_HASH_PATTERN.sub("", (file_hash or "").lower())
    if not hash_prefix:
        hash_prefix = uuid4().hex

    normalized_default_extension = default_extension.lower()
    if not _SAFE_EXTENSION_PATTERN.match(normalized_default_extension):
        normalized_default_extension = ".bin"

    extension = Path(sanitize_filename(filename or "")).suffix.lower()
    if not _SAFE_EXTENSION_PATTERN.match(extension):
        extension = normalized_default_extension

    return f"{hash_prefix}/{uuid4().hex}{extension}"
