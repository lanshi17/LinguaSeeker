"""Model server entry point.

Usage:
    uv run python main.py                 # default port 8001
    uv run python main.py --port 8002     # custom port
"""

from __future__ import annotations

import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# ── Ensure app is importable ─────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import embedding, health, rerank, vlm
from app.config import get_config
from app.domain.embedding import EmbeddingService
from app.domain.rerank import RerankService
from app.domain.vlm import VLMService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

# ── Build services ───────────────────────────────────────────────────────

cfg = get_config()

_embedding_svc = EmbeddingService(
    model_id=cfg.embedding_model_id,
    gpu_memory_utilization=cfg.embedding_gpu_memory_utilization,
    max_model_len=cfg.embedding_max_model_len,
)
_rerank_svc = RerankService(
    model_id=cfg.rerank_model_id,
    gpu_memory_utilization=cfg.rerank_gpu_memory_utilization,
)
_vlm_svc = VLMService(
    model_id=cfg.doc_parse_model_id,
    gpu_memory_utilization=cfg.vlm_gpu_memory_utilization,
    image_analysis=cfg.vlm_image_analysis,
) if cfg.doc_parse_model_id else None

# Wire services into API routes
embedding.bind(_embedding_svc)
rerank.bind(_rerank_svc)
if _vlm_svc:
    vlm.bind(_vlm_svc)

# Register services for health checks
health.register_services({
    "embedding": _embedding_svc,
    "rerank": _rerank_svc,
    **({"vlm": _vlm_svc} if _vlm_svc else {}),
})

# ── Assemble FastAPI app ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Free GPU memory on shutdown
    if _vlm_svc is not None:
        _vlm_svc.unload()


app = FastAPI(title="ACMG-Lingua Model Server", version="1.0.0", lifespan=lifespan)
app.add_middleware(request_monitor_middleware_factory())

app.include_router(embedding.router)
app.include_router(rerank.router)
if _vlm_svc:
    app.include_router(vlm.router)
app.include_router(health.router)

# ── Run ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=cfg.port)
    args = parser.parse_args()

    logger.info("Starting model server on {host}:{port}", host=args.host, port=args.port)
    logger.info("  Embedding : {id}", id=cfg.embedding_model_id)
    logger.info("  Rerank    : {id}", id=cfg.rerank_model_id)
    logger.info("  VLM       : {id}", id=cfg.doc_parse_model_id or "(not configured)")
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
