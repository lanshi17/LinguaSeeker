# acmg-config-loader

Shared layered YAML configuration loader. Loads `defaults/main.yaml` →
`environments/<env>.yaml` → `vault/<env>.yaml` in order, then flattens nested
keys into UPPERCASE env vars. Existing environment variables always win.

Used by:
- `backend/` (FastAPI app)
- `services/model-server/` (inference microservice)

Pure stdlib + PyYAML — no FastAPI / Pydantic / vllm dependency.
