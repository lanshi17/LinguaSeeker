# ── Doc Parse (MinerU PDF Parsing) Server ─────────────────────────────
# Build context: project root.
# Model weights mounted at /models/vlm (read-only, same model as VLM).
#
# Build:
#   docker build -f services/model-server/docker/doc-parse.Dockerfile -t lingua-doc-parse .
# -------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-devel-ubuntu24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip git curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.12 /usr/bin/python

WORKDIR /app

COPY libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir \
    "mineru[vlm]>=3.3.0" \
    fastapi pydantic pydantic-settings loguru pyyaml pillow uvicorn \
    && pip install --no-cache-dir -e /app/libs/config-loader

COPY services/model-server/app /app/app
COPY services/model-server/main_doc_parse.py /app/main.py
COPY services/model-server/config /app/config

ENV HOST=0.0.0.0
ENV PORT=8005

EXPOSE 8005

CMD ["python", "main.py", "--port", "8005"]
