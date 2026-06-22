"""Embedding-only model server entry point.

Usage:
    uv run python main_embedding.py
    uv run python main_embedding.py --port 8002
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import embedding, health
from app.config import get_config
from app.domain.embedding import EmbeddingService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

_embedding_svc = EmbeddingService(
    model_id=cfg.embedding_model_id,
    gpu_memory_utilization=cfg.embedding_gpu_memory_utilization,
    max_model_len=cfg.embedding_max_model_len,
)
embedding.bind(_embedding_svc)
health.register_services({"embedding": _embedding_svc})

app = FastAPI(title="Lingua Seeker — Embedding Server", version="1.0.0")
app.add_middleware(request_monitor_middleware_factory())
app.include_router(embedding.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    logger.info("Starting embedding server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
