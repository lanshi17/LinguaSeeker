# app.py--后端启动入口
from fastapi import FastAPI
from src.presentation.upload_controller import UploadController
from loguru import logger
from src.config import app_config,database_config
cfg = app_config.AppConfig.from_env()
db_cfg = database_config.DatabaseConfig.from_env()
from icecream.builtins import install
install()
app = FastAPI(title=cfg.app_name, version=cfg.app_version)
upload_controller = UploadController(config=cfg)
app.include_router(upload_controller.router)


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting {cfg.app_name} version {cfg.app_version}")
    uvicorn.run(app, host=cfg.host, port=cfg.port)