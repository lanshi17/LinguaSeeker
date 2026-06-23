"""MinerU document parsing server entry point.

Usage:
    uv run python main_doc_parse.py
    uv run python main_doc_parse.py --port 8004
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI

from app.api import file_parse, health
from app.config import get_config
from app.domain.doc_parse import DocParseService
from app.utils.logger import get_logger, request_monitor_middleware_factory, setup_logging

setup_logging()
logger = get_logger()

cfg = get_config()

_doc_parse_svc = DocParseService(
    backend=cfg.doc_parse_backend,
    gpu_memory_utilization=cfg.doc_parse_gpu_memory_utilization,
    model_path=cfg.doc_parse_model_path,
)
file_parse.bind(_doc_parse_svc)
health.register_services({"doc_parse": _doc_parse_svc})

app = FastAPI(title="Lingua Seeker — Doc Parse Server", version="1.0.0")
app.add_middleware(request_monitor_middleware_factory())
app.include_router(file_parse.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.host)
    parser.add_argument("--port", type=int, default=8004)
    args = parser.parse_args()
    logger.info("Starting doc-parse server on {host}:{port}", host=args.host, port=args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level)
