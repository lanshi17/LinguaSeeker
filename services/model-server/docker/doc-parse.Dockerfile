# ── Doc Parse (MinerU PDF Parsing) Server ─────────────────────────────
# Build context: project root.
# Model weights mounted at /models/vlm (read-only, same model as VLM).
#
# Build:
#   docker build -f services/model-server/docker/doc-parse.Dockerfile -t lingua-doc-parse .
# -------------------------------------------------------------------
FROM nvidia/cuda:12.0.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
 && add-apt-repository -y ppa:deadsnakes/ppa \
 && apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev python3-pip git curl build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.12 /usr/bin/python

WORKDIR /app

COPY libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    "mineru[vlm]>=3.3.0" \
    fastapi pydantic pydantic-settings loguru pyyaml pillow uvicorn \
    && pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -e /app/libs/config-loader

COPY services/model-server/app /app/app
COPY services/model-server/main_doc_parse.py /app/main.py
COPY services/model-server/config /app/config

ENV HOST=0.0.0.0
ENV PORT=8005

EXPOSE 8005

CMD ["python", "main.py", "--port", "8005"]
