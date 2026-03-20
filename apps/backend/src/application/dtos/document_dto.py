# document dto
import sys
from datetime import datetime, timezone
from typing import ClassVar

from pydantic import BaseModel, Field

_module = sys.modules[__name__]
if __name__.startswith("src."):
    _ = sys.modules.setdefault(__name__[4:], _module)
else:
    _ = sys.modules.setdefault(f"src.{__name__}", _module)


class DocumentUploadDTO(BaseModel):
    """文档上传数据传输对象"""

    id: int | None = None
    filename: str
    content: bytes
    upload_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_type: str | None = None
    size: int | None = None
    url: str | None = None
    temp_file_path: str | None = None  # 临时文件路径,用于MinerU处理

    class Config:
        arbitrary_types_allowed: ClassVar[bool] = True


class DocumentProcessResultDTO(BaseModel):
    """文档处理结果数据传输对象"""

    document_id: str
    file_name: str
    minio_prefix: str
    minio_files: list[str]
    file_count: int
    processed_at: datetime
    mineru_file_id: str | None = None
    state: str | None = None
    full_zip_url: str | None = None
    html_content: str | None = None
    markdown_content: str | None = None
    json_content: dict[str, object] | None = None
    picture_content: bytes | None = None
    error_message: str | None = None

    class Config:
        arbitrary_types_allowed: ClassVar[bool] = True
