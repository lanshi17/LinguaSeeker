# upload_controller.py--上传控制器 
# fastapi upload controller implementation
# handles file upload requests
from src.presentation.base_controller import BaseController
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Type
from pydantic import BaseModel
from config.app_config import AppConfig
from utils.logger import Logger
from utils.exceptions import FileUploadError, ControllerException
cfg=AppConfig.from_env()

class UploadController(BaseController):
    """上传控制器类"""

    def __init__(self, config: Type[AppConfig] = cfg):
        super().__init__(config)
        self.register_routes()

    def register_routes(self):
        """注册上传路由"""
        @self.router.post("/upload/file/pdf", tags=["File Upload"], summary="上传PDF文件")
        async def upload_file(file: UploadFile = File(...)):
            try:
                # 文件处理逻辑
                if not file:
                    raise FileUploadError("No file provided")
                content = await file.read()
                if len(content) > self.config.max_upload_size:
                    raise FileUploadError("File size exceeds the maximum limit")
                elif not file.filename.endswith('.pdf'):
                    raise FileUploadError("Unsupported file type")
                # 处理文件上传逻辑
                self.logger.info("File uploaded successfully")
                
                return {"message": "File uploaded successfully"}
            except FileUploadError as e:
                self.logger.error(f"File upload error: {e.message}")
                raise HTTPException(status_code=400, detail=e.message)
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}")
                raise HTTPException(status_code=500, detail="Internal Server Error")
    
    def get_router(self) -> APIRouter:
        """获取上传路由器实例"""
        return self.router
        
