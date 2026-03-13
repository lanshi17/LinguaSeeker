
## Fix: Duplicate Embedding Config Block - Completed

**Date**: 2026-03-12

### Problem
Pydantic BaseSettings was processing field declarations top-to-bottom. The `embedding_provider` field (and 5 other embedding fields) were declared TWICE:
1. First block (lines 78-84): NO defaults, would require all env vars
2. Second block (lines 137-143): HAS defaults like `embedding_provider: str = "nomic"`

When Pydantic processes, the SECOND declaration silently overrides the first. This meant:
- Anyone editing the first block would be confused (it's dead code)
- The first block should never have existed

### Solution Applied
✅ Removed lines 78-84 entirely (first embedding config block header + 6 field declarations)
✅ Kept lines 129-135 (second embedding config block with defaults) as single source of truth
✅ Changed `app_version` from `"2.0.0"` to `"2.1.0"` on line 11
✅ Verified Python syntax with py_compile

### Key Insight
In Pydantic BaseSettings (v2), field duplication doesn't raise an error—it silently uses the last declaration. This is a common gotcha when refactoring config files. Always verify there's only ONE field declaration per name.

### Verification
```bash
python -m py_compile src/config.py  # ✓ Passed
```

File now has 220 lines (was 228 lines) with duplicate block removed.

## CORS Origins Parser Fix - Session Complete

### Changes Made
1. **Fixed `_parse_cors_origins()` function** (lines 95-106)
   - Added JSON array parsing support using `json.loads()`
   - Maintains backward compatibility with CSV format fallback
   - Handles edge cases: empty strings, wildcards, malformed JSON

2. **Removed unused `import asyncio`** (line 7)
   - Cleaned up dead imports, no functional impact

### Implementation Details
- Try JSON parsing first with `json.loads(origins)`
- If successful and result is a list, use it (with str/strip on each element)
- If JSON parsing fails (JSONDecodeError/ValueError), fall back to CSV split
- Preserves existing empty-string check and wildcard behavior

### Testing Results
✓ JSON array format: `'["http://localhost:3000", "http://localhost:8080"]'` → correct parsing
✓ CSV format: `"http://localhost:3000, http://localhost:8080"` → correct parsing
✓ Wildcard: `"*"` → handled correctly
✓ Empty string: `""` → returns empty list
✓ Whitespace handling: JSON and CSV with extra spaces work correctly
✓ Malformed JSON: Falls back to CSV gracefully
✓ Syntax validation: Python compile check passed

### Files Modified
- `main.py`: Lines 6-7 (removed asyncio), Lines 95-106 (fixed _parse_cors_origins)

### Configuration Default Value
- Config default: `cors_origins: str = '["http://localhost:3000", "http://localhost:8080"]'`
- Old behavior: Split by comma → `['["http://localhost:3000"', '"http://localhost:8080"]']` (broken)
- New behavior: Parse as JSON array → `['http://localhost:3000', 'http://localhost:8080']` (correct)

## Temp File Cleanup Fix (Task: Fix src/api/routes/core.py)

### Problem
When Celery `apply_async()` fails (e.g., Redis/broker unavailable), the temp PDF file created at lines 348-350 was never cleaned up, causing disk space leaks over time.

### Solution Applied
Added cleanup in exception handler:
- Added `import os` at line 7 (after `import tempfile`)
- Added `try/except OSError` block around `os.unlink(tmp_file_path)` in the exception handler (lines 361-364)
- Wrapping the unlink prevents masking the original Celery failure if the unlink itself fails

### Key Pattern
- **Success path**: Temp file remains available for Celery worker (unchanged)
- **Error path**: Temp file is cleaned up before HTTPException is raised
- **Safety**: OSError is caught and ignored to preserve the original exception

### Changed Lines
- Line 7: Added `import os`
- Lines 361-365: Exception handler now includes cleanup before raising HTTPException

### Verification
- ✓ Python syntax valid
- ✓ No new linting errors
- ✓ Existing pre-conditions preserved (success path unchanged)

