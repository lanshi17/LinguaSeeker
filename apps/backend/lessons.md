
2026-03-21 - Literature module test collection failures due to missing test env file
- Symptom: pytest collection failed while importing `src.config.settings` with many missing required env vars.
- Root cause: `tests/conftest.py` expects `.env.test`, but repository did not include one in this workspace.
- Additional issue: direct copy from `.env.example` still failed because placeholders (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`) and empty `VLM_ENABLE` violate strict Settings validators.
- Fix applied locally for test execution: created `.env.test` from `.env.example`, then set `VLM_ENABLE=false` and non-placeholder MinIO credentials.
- Lesson: add a committed `.env.test.example` (or CI-safe `.env.test`) aligned with strict validator rules to avoid repetitive collection-time failures.
