# Code Quality Issues

## Secrets Scrubbing

### Qdrant API Key in docker-compose.yml
- **Issue**: File `apps/backend/tests/docker-compose.yml` contained hardcoded Qdrant API key `EDhs@gJcftnT3sBU`
- **Fix**: Replaced literal secret with environment variable reference `${QDRANT_API_KEY}` on line 13
- **Status**: Fixed - credential must be rotated out-of-band (this key has been exposed in tracked git history)
- **Date**: 2026-03-13
- **Action Required**: The exposed secret `EDhs@gJcftnT3sBU` should be rotated immediately in all environments where it was deployed
