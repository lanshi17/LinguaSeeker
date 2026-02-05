# app.py--后端启动入口
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.presentation.controllers.pdf_parse_controller import PDFParseController
from src.presentation.websocket.progress_handler import router as websocket_router
from loguru import logger
from src.config import app_config, database_config
from src.infrastructure.database.bootstrap import ensure_database_ready
import os
import json
from typing import Any, Callable

# 加载配置
cfg = app_config.AppConfig.from_env()
db_cfg = database_config.DatabaseConfig.from_env()

from icecream.builtins import install

install()


# Custom JSON encoder to handle bytes and other types
def custom_json_encoder(obj: Any) -> Any:
    if isinstance(obj, bytes):
        return obj.hex()  # Convert bytes to hex string
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# Create FastAPI app with OpenAPI documentation
app = FastAPI(
    title=cfg.app_name,
    version=cfg.app_version,
    description="Intelligent Parsing Pipeline System for ACMG Evidence Extraction",
    contact={"name": "ACMG-PS3 Team", "email": "support@example.com"},
    license_info={"name": "MIT License"},
    openapi_tags=[
        {
            "name": "PDF Parsing",
            "description": "Upload and parse PDF documents for ACMG evidence extraction",
        },
        {
            "name": "Task Management",
            "description": "Monitor and manage parsing task status and lifecycle",
        },
    ],
    servers=[
        {"url": f"http://{cfg.host}:{cfg.port}", "description": "Development server"},
    ],
    json_encoder=custom_json_encoder,
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handler for RequestValidationError to handle bytes in error messages
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with proper bytes encoding."""

    def encode_errors(errors):
        for error in errors:
            if isinstance(error.get("input"), bytes):
                error["input"] = f"<binary data: {len(error['input'])} bytes>"
            if isinstance(error.get("ctx"), dict) and isinstance(
                error["ctx"].get("error"), Exception
            ):
                err_msg = str(error["ctx"]["error"])
                if any(
                    isinstance(arg, bytes)
                    for arg in error["ctx"]["error"].args
                    if error["ctx"]["error"].args
                ):
                    err_msg = "<error contains binary data>"
                error["ctx"]["error"] = err_msg
            if "loc" in error:
                yield {
                    "loc": error["loc"],
                    "msg": error.get("msg", ""),
                    "type": error.get("type", ""),
                }
            else:
                yield error

    return JSONResponse(
        status_code=422,
        content={"detail": list(encode_errors(exc.errors()))},
    )


app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Initialize controllers
pdf_parse_controller = PDFParseController(config=cfg)

# Include routers
app.include_router(pdf_parse_controller.router)
app.include_router(websocket_router)

# Basic health endpoints
@app.get("/")
async def root() -> dict:
    """Simple root endpoint to confirm service availability."""
    return {"status": "ok", "app": cfg.app_name, "version": cfg.app_version}


@app.get(cfg.api_prefix)
async def api_root() -> dict:
    """List available API versions."""
    return {"status": "ok", "versions": [cfg.api_version]}


@app.get(f"{cfg.api_prefix}/{cfg.api_version}")
async def api_version_root() -> dict:
    """Version-specific root endpoint."""
    return {
        "status": "ok",
        "version": cfg.api_version,
        "available_resources": ["pdf", "tasks", "ws/task/{task_id}/progress"],
    }


@app.get(f"{cfg.api_prefix}/{cfg.api_version}/health")
async def api_health() -> dict:
    """API health probe for load balancers and uptime checks."""
    return {"status": "ok"}

# 禁用网络代理
os.environ["NO_PROXY"] = ",".join(["localhost", "127.0.0.1"])


@app.on_event("startup")
async def bootstrap_database() -> None:
    """Ensure the PostgreSQL schema matches the required structure."""

    db_ready = await ensure_database_ready(raise_on_failure=False)
    if not db_ready:
        logger.error(
            "Database bootstrap failed during startup. API will continue running,"
            " but database-backed endpoints may return errors until credentials"
            " or connectivity are fixed."
        )

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting {cfg.app_name} version {cfg.app_version}")
    uvicorn.run(app, host=cfg.host, port=cfg.port)
