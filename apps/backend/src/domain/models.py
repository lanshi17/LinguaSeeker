from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
# ==================== MinerU ====================

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

class MinerURequest(BaseModel):
    """MinerU 请求体"""
    file_paths: List[str] = Field(..., description="文件路径列表")
    callback: Optional[str] = Field(None, description="回调URL")

    #language: Optional[str] = Field("en", description="处理语言，默认为英文")
class MinerUResponse(BaseModel):
    """MinerU 响应体"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    message: Optional[str] = Field(None, description="附加消息")
    folder_path: Optional[str] = Field(None, description="解析解压后的文件夹路径")
    # minio_urls: Optional[List[str]] = Field(None, description="MinIO 文件链接列表")
    
# ==================== Agent ====================
class AgentRequest(BaseModel):
    """Agent 请求体"""
    question: str = Field(..., description="用户问题")
    context: Optional[str] = Field(None, description="上下文信息")
    max_response_tokens: Optional[int] = Field(2048, description="最大响应令牌数")
    temperature: Optional[float] = Field(0.7, description="生成文本的温度参数")
    top_p: Optional[float] = Field(0.9, description="nucleus 采样的 top_p 参数")
    stream: Optional[bool] = Field(False, description="是否启用流式响应")
class AgentResponse(BaseModel):
    """Agent 响应体"""
    answer: str = Field(..., description="生成的答案")
    source_documents: Optional[List[str]] = Field(None, description="引用的源文档列表")

class EvidenceOutput(BaseModel):
    """证据提取输出"""
    ps3_evidence: Dict[str, Any] = Field(..., description="PS3 证据评估结果")
    arbitration_score: float = Field(..., description="仲裁评分 (0-100)")
    image_descriptions: List[str] = Field(default_factory=list, description="图片描述列表")
    final_evidence_strength: Optional[str] = Field(None, description="最终证据强度等级")
    status: Optional[str] = Field("pending", description="处理状态")
    origin_format_md: Optional[str] = Field(None, description="原始格式的 排版后的Markdown 内容")
    en_format_md: Optional[str] = Field(None, description="翻译成英文的排版后的Markdown 内容")


class PipelineFiles(BaseModel):
    """Pipeline 输出文件路径集合"""
    origin_md_path: str = Field(..., description="原始 Markdown MinIO 对象键")
    en_md_path: str = Field(..., description="英文 Markdown MinIO 对象键")
    image_desc_path: str = Field(..., description="图片描述文本 MinIO 对象键")
    ps3_evidence_path: str = Field(..., description="PS3 证据 JSON MinIO 对象键")
    image_dir: str = Field(..., description="图片 MinIO 前缀")
    origin_md_url: Optional[str] = Field(None, description="原始 Markdown API 路由")
    en_md_url: Optional[str] = Field(None, description="英文 Markdown API 路由")
    image_desc_url: Optional[str] = Field(None, description="图片描述文本 API 路由")
    ps3_evidence_url: Optional[str] = Field(None, description="PS3 证据 JSON API 路由")
    image_urls: Optional[List[str]] = Field(None, description="图片 API 路由列表")


class PipelineResult(BaseModel):
    """Pipeline 结果输出"""
    document_id: str = Field(..., description="文档唯一 ID")
    output_dir: str = Field(..., description="MinIO 输出前缀")
    mineru_folder: str = Field(..., description="MinerU 输出目录")
    files: PipelineFiles = Field(..., description="输出文件集合")
    evidence: EvidenceOutput = Field(..., description="证据提取结果")
    
# ==================== RAG ====================
class RAGQueryRequest(BaseModel):
    """RAG 查询请求体"""
    query: str = Field(..., description="查询内容")
    top_k: Optional[int] = Field(5, description="返回的最相似文档数量")
    score_threshold: Optional[float] = Field(0.7, description="相似度阈值")
    max_context_chars: Optional[int] = Field(4000, description="上下文最大字符数")
    chunk_overlap: Optional[int] = Field(200, description="文本块重叠字符数")
    enable_rerank: Optional[bool] = Field(True, description="是否启用重排序")
class RAGQueryResponseItem(BaseModel):
    """RAG 查询响应单项"""
    document_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容")
    score: float = Field(..., description="相似度分数")
class RAGQueryResponse(BaseModel):
    """RAG 查询响应体"""
    results: List[RAGQueryResponseItem] = Field(..., description="查询结果列表")
# ==================== Embedding ====================
class EmbeddingRequest(BaseModel):
    """嵌入请求体"""
    texts: List[str] = Field(..., description="文本列表")
class EmbeddingResponse(BaseModel):
    """嵌入响应体"""
    embeddings: List[List[float]] = Field(..., description="嵌入向量列表")

# ==================== Rerank ====================
class RerankRequest(BaseModel):
    """重排序请求体"""
    query: str = Field(..., description="查询内容")
    documents: List[str] = Field(..., description="待排序文档列表")
class RerankResponseItem(BaseModel):
    """重排序响应单项"""
    document: str = Field(..., description="文档内容")
    score: float = Field(..., description="相关性分数")
class RerankResponse(BaseModel):
    """重排序响应体"""
    results: List[RerankResponseItem] = Field(..., description="排序结果列表")
    
