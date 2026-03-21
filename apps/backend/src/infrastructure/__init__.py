"""Infrastructure package exports.

Keep optional store exports resilient so importing submodules like
``src.infrastructure.minio`` does not fail when legacy store deps are absent.
"""

BaseStore = None
MinIOStore = None
__all__ = []

try:
    from .store import BaseStore, MinIOStore

    __all__ = ["BaseStore", "MinIOStore"]
except Exception:
    # Legacy store module has optional dependencies in some environments.
    pass
