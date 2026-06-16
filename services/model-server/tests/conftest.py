"""Test configuration - ensure app is importable from tests directory."""

import os
import sys
from types import ModuleType

# Add model-server directory to Python path so `from app import ...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _install_optional_dependency_stubs() -> None:
    """Provide import-time stubs for optional GPU dependencies.

    Unit tests patch these objects before use, so the real vllm stack is not
    required for CPU-only test runs.
    """
    if "vllm" not in sys.modules:
        vllm_stub = ModuleType("vllm")
        vllm_stub.LLM = _MissingOptionalDependency  # type: ignore[attr-defined]
        sys.modules["vllm"] = vllm_stub


class _MissingOptionalDependency:
    """Fail clearly if a test uses an optional dependency without patching it."""

    def __init__(self, *args, **kwargs) -> None:
        raise RuntimeError("Optional model-server dependency was not patched in this unit test.")


_install_optional_dependency_stubs()
