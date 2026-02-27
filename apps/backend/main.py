from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from contextlib import asynccontextmanager
import asyncio
import json
import sys
import os
from pathlib import Path
from uuid import uuid4
from loguru import logger
from datetime import datetime
from typing import Callable, Optional, Dict, Any
import src.presentation.api as api_routers
import src.presentation.task_api as task_api_routers
import src.presentation.graph_api as evidence_api_routers
from src.utils.exceptions import ACMGException, TaskNotFoundException, ValidationException
from src.health import check_all_connections
from src.database.minio_client import MinIOClient
from src.config import settings as cfg # 导入配置实例
# 添加一个 sink 到文件，实现滚动和保留策略
# 这里使用 "a" 模式追加，每天凌晨滚动，保留最近7天的日志
logger.add(
    sink=f"logs/app_{datetime.now().strftime('%Y%m%d')}.log", # 文件名包含日期
    level="DEBUG", # 记录 DEBUG 及以上级别的日志到文件
    rotation="00:00", # 每天午夜滚动
    retention="7 days", # 保留最近7天的日志文件
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}",
    compression="zip", # 可选：对旧日志进行压缩
    enqueue=False, # 禁用多进程队列，避免 SemLock 权限错误
    serialize=False # 默认为 False，如果为 True，整个日志记录会被序列化成 JSON
)

# 添加一个 sink 到标准错误输出 (stderr)，通常是你的终端
# 你可以根据需要设置不同的 level，例如 DEBUG
logger.add(
    sink=sys.stderr,
    level="DEBUG", # 记录 DEBUG 及以上级别的日志到控制台
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True, # 启用颜色，使终端日志更易读
    backtrace=True, # 记录完整的回溯信息
    diagnose=True, # 提供更详细的错误上下文 (在生产环境中可能需要关闭以保护敏感信息)
    enqueue=False, # 禁用多进程队列
)

def _parse_cors_origins(origins: str) -> list[str]:
    if not origins:
        return []
    if origins.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    checks = check_all_connections()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.warning("Startup connectivity check failed: {}", ", ".join(failed))
    else:
        logger.info("Startup connectivity check passed")
    try:
        await MinIOClient().ensure_buckets()
    except Exception as exc:
        logger.warning("MinIO bucket init failed: {}", exc)
    yield


app = FastAPI(
    title=cfg.app_name,
    debug=cfg.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(cfg.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

app.include_router(api_routers.router, prefix=cfg.api_prefix)
app.include_router(task_api_routers.router, prefix=cfg.api_prefix)
app.include_router(evidence_api_routers.router, prefix=cfg.api_prefix)


@app.exception_handler(ACMGException)
async def handle_acmg_exception(_, exc: ACMGException):
    status_code = 400
    if isinstance(exc, TaskNotFoundException):
        status_code = 404
    elif isinstance(exc, ValidationException):
        status_code = 422

    return JSONResponse(
        status_code=status_code,
        content={"code": exc.code, "message": exc.message},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request payload",
                "errors": exc.errors(),
            }
        ),
    )

@app.get("/") 
def read_root():
    return {
        "Hello": "World", "App Name": cfg.app_name, "Debug Mode": cfg.debug,
        "Environment": cfg.environment, "API Prefix": cfg.api_prefix,
        "Health Check Endpoint": f"http://{cfg.api_host}:{cfg.api_port}{cfg.api_prefix}/health"
            }

os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)   
# 使用配置初始化数据库连接等...
if __name__ == "__main__":
    import uvicorn
    # 配置可以从 .env 或环境变量自动加载
    uvicorn.run(app, host=cfg.api_host, port=cfg.api_port, env_file=".env.local")
