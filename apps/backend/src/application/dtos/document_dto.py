# document dto
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

class DocumentDTO(BaseModel):
    """文档数据传输对象"""
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
    