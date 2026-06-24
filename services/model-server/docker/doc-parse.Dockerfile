# ── Doc Parse (MinerU PDF Parsing) Server ─────────────────────────────
# Build context: services/model-server/ (self-contained, no project root).
# Uses vllm/vllm-openai base (torch 2.11+cu129, Python 3.12) — compatible
# with R525 driver (CUDA 12.1) via CUDA 12.x minor version compatibility.
# Model weights mounted at /models/vlm (read-only).
#
# Build:
#   cd services/model-server
#   docker build -f docker/doc-parse.Dockerfile -t doc-parse-server .
# -------------------------------------------------------------------
FROM vllm/vllm-openai:latest

WORKDIR /app

# 关键新增：禁用 NVIDIA Container Toolkit 的严格版本检查，强制放行
ENV NVIDIA_DISABLE_REQUIRE=1

# Install extra deps NOT in vllm base. torch is already pinned at 2.11+cu129
# in the base image — pip won't upgrade it since these deps don't require newer.
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    "mineru[vlm]>=3.3.0" \
    fastapi pydantic pydantic-settings loguru pyyaml pillow uvicorn

COPY main_doc_parse.py /app/main.py

ENV HOST=0.0.0.0
ENV PORT=8004

EXPOSE 8004

CMD ["python3", "main.py", "--port", "8004"]