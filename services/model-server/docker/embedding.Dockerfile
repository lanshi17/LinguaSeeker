# ── Embedding Server ──────────────────────────────────────────────────
# Build context: services/model-server/ (self-contained, no project root).
# Model weights are mounted at /models/embedding (read-only).
#
# Build:
#   cd services/model-server
#   docker build -f docker/embedding.Dockerfile -t embedding-server .
# -------------------------------------------------------------------
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8002

# vLLM 0.4.x 编译时需要
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 固定兼容版本
RUN pip install \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    fastapi==0.115.0 \
    uvicorn==0.30.6 \
    pydantic==2.9.2 \
    pydantic-settings==2.5.2 \
    loguru==0.7.2 \
    pyyaml==6.0.2 \
    pillow \
    numpy \
    transformers==4.41.2 \
    accelerate==0.33.0 \
    sentence-transformers==3.0.1

# Driver 525 推荐锁定旧版
RUN pip install \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    vllm==0.4.3

COPY app ./app
COPY main_embedding.py ./main.py

EXPOSE 8002

CMD ["python", "main.py", "--port", "8002"]
