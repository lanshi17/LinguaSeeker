# upload_controller.py--上传控制器
from pydantic import BaseModel
from src.presentation.base_controller import BaseController
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Any, Dict
from src.utils.logger import Logger
from src.application.dtos.document_dto import DocumentUploadDTO, DocumentProcessResultDTO
from src.configs.app_config import AppConfig
from src.utils.exceptions import FileUploadError
from src.application.services.document_service import DocumentService
import tempfile
import os
from pathlib import Path

cfg = AppConfig.from_env()

class UploadController(BaseController):
    """上传控制器类"""

    def __init__(self, config: AppConfig = cfg):
        super().__init__(config)
        self.document_service = DocumentService()
        self.temp_dir = Path(tempfile.gettempdir()) / "pdf_uploads"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.logger = Logger()
        self._register_routes()

    def handle_request(self, request: BaseModel) -> BaseModel:
        """处理上传请求的占位方法"""
        self.logger.info("Handling upload request")
        self._register_routes()
        return request
    def _register_routes(self):
        """注册上传路由"""
        self.router.post(
            "/upload/file/pdf",
            tags=["File Upload"],
            summary="上传PDF文件"
        )(self._upload_pdf)

    async def _upload_pdf(self, file: UploadFile = File(...)):
        """上传PDF文件处理逻辑"""
        temp_file_path = None
        try:
            if not file:
                raise FileUploadError("No file provided")

            content = await file.read()
            if len(content) > self.config.max_upload_size:
                raise FileUploadError("File size exceeds the maximum limit")
            if not file.filename or not file.filename.endswith(".pdf"):
                raise FileUploadError("Unsupported file type")

            # 创建DocumentUploadDTO实体
            document = DocumentUploadDTO(
                filename=file.filename,
                content=content,
                size=len(content),
                content_type=file.content_type or "application/pdf"
            )

            # 保存临时文件供MinerU处理(需要文件路径)
            temp_file_path = self.temp_dir / file.filename
            with open(temp_file_path, "wb") as f:
                f.write(content)

            # 将临时文件路径添加到DTO
            document.temp_file_path = str(temp_file_path)

            # 调用应用层服务处理PDF，传递DTO对象
            self.logger.info(f"Processing PDF file: {file.filename}")
            result = self.document_service.process_pdf_document(document)
            if isinstance(result, DocumentProcessResultDTO):
                result_data: Dict[str, Any] = result.model_dump()
            elif hasattr(result, "model_dump"):
                result_data = result.model_dump()
            elif hasattr(result, "dict"):
                result_data = result.dict()
            elif isinstance(result, dict):
                result_data = result
            else:
                result_data = dict(result)

            self.logger.info(f"File {file.filename} uploaded and processed successfully")
            return {
                "message": "File uploaded and processed successfully",
                "filename": file.filename,
                "size": len(content),
                "document_id": result_data.get("document_id"),
                "minio_prefix": result_data.get("minio_prefix"),
                "minio_files": result_data.get("minio_files", []),
                "file_count": len(result_data.get("minio_files", [])),
                "processed_at": result_data.get("processed_at")
            }

        except FileUploadError as e:
            self.logger.error(f"File upload error: {e.message}")
            raise HTTPException(status_code=400, detail=e.message)
        except Exception as e:
            self.logger.error(f"Unexpected error during PDF processing: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
        finally:
            # 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    self.logger.info(f"Temporary file removed: {temp_file_path}")
                except Exception as cleanup_error:
                    self.logger.warning(f"Failed to remove temporary file: {cleanup_error}")
    
    def get_router(self) -> APIRouter:
        """获取上传路由器实例"""
        return self.router
