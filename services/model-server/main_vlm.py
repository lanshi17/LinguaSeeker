"""VLM / MinerU image extraction server entry point.

Usage:
    uv run python main_vlm.py
    uv run python main_vlm.py --port 8004
"""
from __future__ import annotations

import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import health, vlm
from app.config import get_config
from app.domain.vlm import VLMService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

if not cfg.doc_parse_model_id:
    logger.error("DOC_PARSE_MODEL_ID is required for VLM server. Set it in config or env var.")
    sys.exit(1)

_vlm_svc = VLMService(
    model_id=cfg.doc_parse_model_id,
    gpu_memory_utilization=cfg.doc_parse_gpu_memory_utilization,
    image_analysis=cfg.doc_parse_image_analysis,
)
vlm.bind(_vlm_svc)
health.register_services({"vlm": _vlm_svc})


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _vlm_svc.unload()


app = FastAPI(title="Lingua Seeker — VLM Server", version="1.0.0", lifespan=lifespan)
app.add_middleware(request_monitor_middleware_factory())
app.include_router(vlm.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=8004)
    args = parser.parse_args()
    logger.info("Starting VLM server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
