# ── Rerank Server ─────────────────────────────────────────────────────
# Build context: services/model-server/ (self-contained, no project root).
# Model weights are mounted at /models/rerank (read-only).
#
# Build:
#   cd services/model-server
#   docker build -f docker/rerank.Dockerfile -t rerank-server .
# -------------------------------------------------------------------
FROM vllm/vllm-openai:v0.8.5

WORKDIR /app

RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    fastapi pydantic pydantic-settings loguru pyyaml pillow numpy uvicorn

COPY app /app/app
COPY main_rerank.py /app/main.py

ENV HOST=0.0.0.0
ENV PORT=8003

EXPOSE 8003

CMD ["python", "main.py", "--port", "8003"]
