# ── Model Server Code Patch — thin overlay on existing image ─────────
# Use when only model-server Python code changed (no dependency changes).
# Build ON the target server. Pass BASE_IMAGE build-arg to select which
# model-server to patch.
#
#   # Patch VLM:
#   docker build -t lingua-vlm:local \
#     --build-arg BASE_IMAGE=lingua-vlm:local \
#     -f deploy/compose/single-server/patch-model-server.Dockerfile .
#
#   # Patch doc-parse:
#   docker build -t lingua-doc-parse:local \
#     --build-arg BASE_IMAGE=lingua-doc-parse:local \
#     -f deploy/compose/single-server/patch-model-server.Dockerfile .
#
#   # Patch embedding:
#   docker build -t lingua-embedding:local \
#     --build-arg BASE_IMAGE=lingua-embedding:local \
#     -f deploy/compose/single-server/patch-model-server.Dockerfile .
#
#   # Patch rerank:
#   docker build -t lingua-rerank:local \
#     --build-arg BASE_IMAGE=lingua-rerank:local \
#     -f deploy/compose/single-server/patch-model-server.Dockerfile .
# -------------------------------------------------------------------
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

WORKDIR /app

# Only copies changed source files — one thin layer (~KB)
COPY services/model-server/app/ /app/app/
COPY services/model-server/main_vlm.py /app/main_vlm.py
COPY services/model-server/main_embedding.py /app/main_embedding.py
COPY services/model-server/main_rerank.py /app/main_rerank.py
COPY services/model-server/main_doc_parse.py /app/main_doc_parse.py
