# document dto
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

class DocumentUploadDTO(BaseModel):
    """文档上传数据传输对象"""
    id: Optional[int] = None
    filename: str
    content: bytes
    upload_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_type: Optional[str] = None
    size: Optional[int] = None
    url: Optional[str] = None
    temp_file_path: Optional[str] = None  # 临时文件路径,用于MinerU处理
    class Config:
        arbitrary_types_allowed = True

class DocumentProcessResultDTO(BaseModel):
    """文档处理结果数据传输对象"""
    document_id: str
    file_name: str
    minio_prefix: str
    minio_files: dict
    file_count: int
    processed_at: datetime
    mineru_file_id: Optional[str] = None
    state: Optional[str] = None
    full_zip_url: Optional[str] = None
    html_content: Optional[str] = None
    error_message: Optional[str] = None
    class Config:
        arbitrary_types_allowed = True
        
        
