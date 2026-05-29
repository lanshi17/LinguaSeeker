"""Centralized lazy imports for rust_io native extensions.

Usage::

    from src.utils.rust_io import files_io, net_io

    if files_io is not None:
        files_io.File(path).write(data)
    else:
        # stdlib fallback …

    if net_io is not None:
        result = await net_io.fetch_one(...)
    else:
        # handle missing extension …

``files_io`` is either the real ``rust_io.files`` module or ``None``.
``net_io`` is either the real ``rust_io.net`` module or ``None``.

Callers that hard-depend on rust_io may use them unconditionally —
but when the extension is missing, ``files_io`` / ``net_io`` will be
``None``, and attribute access (e.g. ``files_io.File(...)``) will
raise ``AttributeError``, **not** ``ImportError``.
"""

from __future__ import annotations

from loguru import logger

FILES_AVAILABLE: bool = False
NET_AVAILABLE: bool = False
files_io = None
net_io = None

try:
    import rust_io.files as files_io  # noqa: F811
    FILES_AVAILABLE = True
except ImportError:
    logger.warning("rust_io.files not available — file I/O features disabled")

try:
    import rust_io.net as net_io  # noqa: F811
    NET_AVAILABLE = True
except ImportError:
    logger.warning("rust_io.net not available — HTTP / MinerU features disabled")
