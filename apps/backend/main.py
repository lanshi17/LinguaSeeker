import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.dependencies import (
    extract_error_contract,
    failed_payload,
    normalize_error_code,
)
from src.api.routes.core import router as api_routers
from src.api.routes.evidence import router as evidence_api_routers
from src.api.routes.stream import router as stream_api_routers
from src.api.routes.task import router as task_api_routers
from src.config import app_config as cfg  # 导入配置实例
from src.health import check_all_connections
from src.infrastructure.minio import MinIOClient
from src.utils.exceptions import (
    ACMGException,
    TaskNotFoundException,
    ValidationException,
)


def _is_production_environment(environment: str) -> bool:
    return str(environment or "").strip().lower() in {"prod", "production"}


def _build_loguru_runtime_options(environment: str, debug: bool) -> Dict[str, bool]:
    production = _is_production_environment(environment)
    return {
        "backtrace": bool(debug) and not production,
        "diagnose": bool(debug) and not production,
        "enqueue": production,
    }


def _build_cors_options(origins: list[str]) -> Dict[str, Any]:
    has_wildcard = "*" in origins
    return {
        "allow_origins": origins,
        "allow_credentials": not has_wildcard,
    }


def _build_root_payload() -> Dict[str, Any]:
    return {
        "name": cfg.app_name,
        "version": cfg.app_version,
        "status": "ok",
    }


def _maybe_clear_proxy_env() -> None:
    if not getattr(cfg, "clear_proxy_env_on_startup", False):
        return
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)


_loguru_runtime = _build_loguru_runtime_options(cfg.environment.value, cfg.debug)
# 添加一个 sink 到文件，实现滚动和保留策略
# 这里使用 "a" 模式追加，每天凌晨滚动，保留最近7天的日志
logger.add(
    sink=f"logs/app_{datetime.now().strftime('%Y%m%d')}.log",  # 文件名包含日期
    level="DEBUG",  # 记录 DEBUG 及以上级别的日志到文件
    rotation="00:00",  # 每天午夜滚动
    retention="7 days",  # 保留最近7天的日志文件
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}",
    compression="zip",  # 可选：对旧日志进行压缩
    enqueue=_loguru_runtime["enqueue"],
    serialize=False,  # 默认为 False，如果为 True，整个日志记录会被序列化成 JSON
)

# 添加一个 sink 到标准错误输出 (stderr)，通常是你的终端
# 你可以根据需要设置不同的 level，例如 DEBUG
logger.add(
    sink=sys.stderr,
    level="DEBUG",  # 记录 DEBUG 及以上级别的日志到控制台
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,  # 启用颜色，使终端日志更易读
    backtrace=_loguru_runtime["backtrace"],
    diagnose=_loguru_runtime["diagnose"],
    enqueue=_loguru_runtime["enqueue"],
)


def _parse_cors_origins(origins: str) -> list[str]:
    if not origins:
        return []
    if origins.strip() == "*":
        return ["*"]
    try:
        parsed = json.loads(origins)
        if isinstance(parsed, list):
            return [str(o).strip() for o in parsed if str(o).strip()]
    except (json.JSONDecodeError, ValueError):
        pass
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


_cors_options = _build_cors_options(
    _parse_cors_origins('["http://localhost:3000", "http://localhost:8080"]')
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        checks = check_all_connections()
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            logger.warning("Startup connectivity check failed: {}", ", ".join(failed))
        else:
            logger.info("Startup connectivity check passed")
    except Exception as exc:
        logger.error("Startup connectivity check error: {}", exc)
        raise

    try:
        minio_client = MinIOClient()
        logger.info("MinIO client initialized with endpoint: {}", cfg.minio.endpoint)
        await minio_client.ensure_buckets()
        logger.info("MinIO buckets verified successfully")
    except Exception as exc:
        logger.error("MinIO initialization failed: {}", exc)
        raise RuntimeError(f"Failed to initialize MinIO storage: {exc}") from exc

    yield


app = FastAPI(
    title=cfg.app_name,
    debug=cfg.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_options["allow_origins"],
    allow_credentials=_cors_options["allow_credentials"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_routers, prefix=cfg.api_prefix)
app.include_router(task_api_routers, prefix=cfg.api_prefix)
app.include_router(evidence_api_routers, prefix=cfg.api_prefix)
app.include_router(stream_api_routers, prefix=cfg.api_prefix)


@app.exception_handler(ACMGException)
async def handle_acmg_exception(request: Request, exc: ACMGException):
    status_code = 400
    if isinstance(exc, TaskNotFoundException):
        status_code = 404
    elif isinstance(exc, ValidationException):
        status_code = 422

    request_id = request.headers.get("x-request-id") or str(uuid4())
    error_code = normalize_error_code(exc.code, status_code, exc.message)

    return JSONResponse(
        status_code=status_code,
        content=failed_payload(error_code, exc.message, request_id),
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    error_code, detail, errors = extract_error_contract(exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=failed_payload(error_code, detail, request_id, errors=errors),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            failed_payload(
                "INPUT_INVALID",
                "Invalid request payload",
                request_id,
                errors=exc.errors(),
            )
        ),
    )


@app.get("/")
def read_root():
    return _build_root_payload()


_maybe_clear_proxy_env()
# 使用配置初始化数据库连接等...
if __name__ == "__main__":
    import uvicorn

    # 配置可以从 .env 或环境变量自动加载
    uvicorn.run(app, host=cfg.host, port=cfg.port, env_file=".env.local")
