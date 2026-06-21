# ── VLM (MinerU Image Extraction) Server ─────────────────────────────
# Build context: project root.
# Model weights mounted at /models/vlm (read-only).
#
# Build:
#   docker build -f services/model-server/docker/vlm.Dockerfile -t lingua-vlm .
# -------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-devel-ubuntu24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip git curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.12 /usr/bin/python

WORKDIR /app

# Install vLLM + MinerU + app deps in one layer
COPY libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir \
    "vllm>=0.8.0" \
    "mineru[vlm]>=3.3.0" \
    "mineru_vl_utils>=1.0.4" \
    fastapi pydantic pydantic-settings loguru pyyaml pillow numpy uvicorn \
    && pip install --no-cache-dir -e /app/libs/config-loader

COPY services/model-server/app /app/app
COPY services/model-server/main_vlm.py /app/main.py
COPY services/model-server/config /app/config

ENV HOST=0.0.0.0
ENV PORT=8004

EXPOSE 8004

CMD ["python", "main.py", "--port", "8004"]
