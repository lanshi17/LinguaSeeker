# ── Embedding Server ──────────────────────────────────────────────────
# Build context: services/model-server/ (self-contained, no project root).
# Model weights are mounted at /models/embedding (read-only).
#
# Build:
#   cd services/model-server
#   docker build -f docker/embedding.Dockerfile -t embedding-server .
# -------------------------------------------------------------------
FROM vllm/vllm-openai:latest

WORKDIR /app

 # 禁用 NVIDIA Container Toolkit 的严格版本检查，强制放行
ENV NVIDIA_DISABLE_REQUIRE=1

# Install extra Python deps not in vLLM base image
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    fastapi pydantic pydantic-settings loguru pyyaml pillow numpy uvicorn

# Copy model-server application code
COPY app /app/app
COPY main_embedding.py /app/main.py

ENV HOST=0.0.0.0
ENV PORT=8002

EXPOSE 8002

CMD ["python", "main.py", "--port", "8002"]
