# ── Rerank Server ─────────────────────────────────────────────────────
# Build context: services/model-server/ (self-contained, no project root).
# Model weights are mounted at /models/rerank (read-only).
#
# Build:
#   cd services/model-server
#   docker build -f docker/rerank.Dockerfile -t rerank-server .
# -------------------------------------------------------------------
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8003

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    fastapi \
    uvicorn \
    pydantic \
    pydantic-settings \
    loguru \
    pyyaml \
    pillow \
    numpy \
    transformers==4.41.2 \
    accelerate

# 如果 rerank.py 仍然 import vllm
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    vllm==0.4.3

COPY app ./app
COPY main_rerank.py ./main.py

EXPOSE 8003

CMD ["python", "main.py", "--port", "8003"]
