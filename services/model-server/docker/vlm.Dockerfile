# ── VLM (MinerU Image Extraction) Server ─────────────────────────────
# Uses vllm/vllm-openai base (torch 2.11+cu129, Python 3.12) — compatible
# with R525 driver (CUDA 12.1) via CUDA 12.x minor version compatibility.
#
# Build:
#   docker build -f services/model-server/docker/vlm.Dockerfile -t lingua-vlm .
# -------------------------------------------------------------------
FROM vllm/vllm-openai:latest

WORKDIR /app

# Install local config-loader first (needed by app code).
COPY libs/config-loader /app/libs/config-loader
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -e /app/libs/config-loader

# Install extra deps NOT in vllm base. torch is already pinned at 2.11+cu129
# in the base image — pip won't upgrade it since these deps don't require newer.
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    "mineru[vlm]>=3.3.0" \
    "mineru_vl_utils>=1.0.4" \
    fastapi pydantic pydantic-settings loguru pyyaml pillow numpy uvicorn

COPY services/model-server/app /app/app
COPY services/model-server/main_vlm.py /app/main.py
COPY services/model-server/config /app/config

ENV HOST=0.0.0.0
ENV PORT=8004

EXPOSE 8004

CMD ["python3", "main.py", "--port", "8004"]
