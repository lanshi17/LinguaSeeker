"""Rerank-only model server entry point.

Usage:
    uv run python main_rerank.py
    uv run python main_rerank.py --port 8003
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import health, rerank
from app.config import get_config
from app.domain.rerank import RerankService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

_rerank_svc = RerankService(
    model_id=cfg.rerank_model_id,
    gpu_memory_utilization=cfg.rerank_gpu_memory_utilization,
)
rerank.bind(_rerank_svc)
health.register_services({"rerank": _rerank_svc})

app = FastAPI(title="Lingua Seeker — Rerank Server", version="1.0.0")
app.add_middleware(request_monitor_middleware_factory())
app.include_router(rerank.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args()
    logger.info("Starting rerank server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
