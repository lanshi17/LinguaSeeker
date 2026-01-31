# app.py--后端启动入口
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.presentation.controllers.pdf_parse_controller import PDFParseController
from src.presentation.controllers.task_controller import TaskController
# from src.presentation.websocket.progress_handler import router as websocket_router
from loguru import logger
from src.config import app_config, database_config
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
    contact={
        "name": "ACMG-PS3 Team",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT License"
    },
    openapi_tags=[
        {
            "name": "PDF Parsing",
            "description": "Upload and parse PDF documents for ACMG evidence extraction"
        },
        {
            "name": "Task Management",
            "description": "Monitor and manage parsing task status and lifecycle"
        }
    ],
    servers=[
        {"url": f"http://{cfg.host}:{cfg.port}", "description": "Development server"},
    ],
    json_encoder=custom_json_encoder
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize controllers
pdf_parse_controller = PDFParseController(config=cfg)
task_controller = TaskController(config=cfg)

# Include routers
app.include_router(pdf_parse_controller.router)
app.include_router(task_controller.router)
# app.include_router(websocket_router)

# 禁用网络代理
os.environ["NO_PROXY"] = ",".join(["localhost", "127.0.0.1"])

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting {cfg.app_name} version {cfg.app_version}")
    uvicorn.run(app, host=cfg.host, port=cfg.port)