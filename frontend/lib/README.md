# Lib (Legacy)

> Reserved directory structure. All subdirectories contain only `.gitkeep` placeholders.

Active library implementations live in:

| Directory | Purpose |
|-----------|---------|
| `src/lib/api/` | Axios client, error handling |
| `src/lib/config/` | App and API configuration |
| `src/lib/hooks/` | Shared React hooks (polling, debounce, health check) |
| `src/lib/types/` | Common TypeScript types |
| `src/lib/utils/` | Utility functions (cn, formatters) |

This directory is kept for potential future shared library extraction.
