# pyright: reportUnsupportedDunderAll=false

__all__ = [
    "settings",
]


def __getattr__(name: str):
    if name == "settings":
        from .config import get_settings

        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# 版本信息
__version__ = "1.0.0"
