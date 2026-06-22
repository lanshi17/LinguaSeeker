# ── Embedding Server ──────────────────────────────────────────────────
# Build context: project root (so we can COPY libs/config-loader).
# Model weights are mounted at /models/embedding (read-only).
#
# Build:
#   docker build -f services/model-server/docker/embedding.Dockerfile -t lingua-embedding .
# -------------------------------------------------------------------
FROM vllm/vllm-openai:latest

WORKDIR /app

# Install extra Python deps not in vLLM base image
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    fastapi pydantic pydantic-settings loguru pyyaml pillow numpy uvicorn

# Install local config-loader (--no-build-isolation: vllm base has setuptools)
COPY libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -e /app/libs/config-loader

# Copy model-server application code
COPY services/model-server/app /app/app
COPY services/model-server/main_embedding.py /app/main.py
COPY services/model-server/config /app/config

ENV HOST=0.0.0.0
ENV PORT=8002

EXPOSE 8002

CMD ["python", "main.py", "--port", "8002"]
