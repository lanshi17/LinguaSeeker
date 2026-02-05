from pydantic import BaseModel, Field
# ==================== 数据结构模型 ====================

class FileUploadItem(BaseModel):
    """单个文件上传项"""
    name: str = Field(..., description="文件名")
    data_id: str = Field(default="", description="数据ID，可选")

class BatchUploadRequest(BaseModel):
    """批量上传请求体"""
    files: List[FileUploadItem] = Field(..., description="文件列表")
    callback: Optional[str] = Field(None, description="回调URL")
    model_version: Optional[str] = Field(None, description="模型版本")

class BatchUploadResponseData(BaseModel):
    """批量上传响应数据"""
    batch_id: str = Field(..., description="批次ID")
    file_urls: List[str] = Field(..., description="上传URL列表")

class ApiResponse(BaseModel):
    """API 通用响应结构"""
    code: int = Field(..., description="状态码，0表示成功")
    msg: str = Field(..., description="消息")
    trace_id: Optional[str] = Field(None, description="追踪ID")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")

class FileExtractResult(BaseModel):
    """文件解析结果"""
    file_name: str = Field(..., description="文件名")
    state: str = Field(..., description="任务状态")
    err_msg: str = Field(default="", description="错误信息")
    err_code: Optional[str] = Field(None, description="错误码")
    full_zip_url: Optional[str] = Field(None, description="解析结果 ZIP 下载链接")

class BatchStatusData(BaseModel):
    """批量任务状态数据"""
    batch_id: str = Field(..., description="批次ID")
    extract_result: List[FileExtractResult] = Field(..., description="解析结果列表")
    download_url: Optional[str] = Field(None, description="批量下载链接（如有）")