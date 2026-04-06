"""Domain package initializer.

Avoid importing all subpackages eagerly because some legacy modules depend on
optional infrastructure settings that may be unavailable in lightweight flows.
"""

__all__: list[str] = []
