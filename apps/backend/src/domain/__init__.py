"""Domain package initializer.

Avoid importing all subpackages eagerly because some legacy modules depend on
optional infrastructure settings that may be unavailable in lightweight flows.
"""

try:
    from .impl import *  # type: ignore[F403]
except Exception:
    pass

try:
    from .abc import *  # type: ignore[F403]
except Exception:
    pass

try:
    from .models import *  # type: ignore[F403]
except Exception:
    pass
