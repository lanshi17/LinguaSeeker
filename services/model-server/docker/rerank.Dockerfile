# ── Rerank Server ─────────────────────────────────────────────────────
# Build context: project root (so we can COPY libs/config-loader).
# Model weights are mounted at /models/rerank (read-only).
#
# Build:
#   docker build -f services/model-server/docker/rerank.Dockerfile -t lingua-rerank .
# -------------------------------------------------------------------
FROM vllm/vllm-openai:latest

WORKDIR /app

RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    fastapi pydantic pydantic-settings loguru pyyaml pillow numpy uvicorn

COPY libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -e /app/libs/config-loader

COPY services/model-server/app /app/app
COPY services/model-server/main_rerank.py /app/main.py

ENV HOST=0.0.0.0
ENV PORT=8003

EXPOSE 8003

CMD ["python", "main.py", "--port", "8003"]
