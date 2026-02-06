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
    middleware_md: str = Field(..., description="处理后的中间 Markdown 文档")
    image_descriptions: List[str] = Field(default_factory=list, description="图片描述列表")
    final_evidence_strength: Optional[str] = Field(None, description="最终证据强度等级")
    status: Optional[str] = Field("pending", description="处理状态")
    
# ==================== RAG ====================
class RAGQueryRequest(BaseModel):
    """RAG 查询请求体"""
    query: str = Field(..., description="查询内容")
    top_k: Optional[int] = Field(5, description="返回的最相似文档数量")
    score_threshold: Optional[float] = Field(0.7, description="相似度阈值")
class RAGQueryResponseItem(BaseModel):
    """RAG 查询响应单项"""
    document_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容")
    score: float = Field(..., description="相似度分数")
class RAGQueryResponse(BaseModel):
    """RAG 查询响应体"""
    results: List[RAGQueryResponseItem] = Field(..., description="查询结果列表")
# ==================== Qdrant ====================
class QdrantHealthResponse(BaseModel):
    """Qdrant 健康检查响应体"""
    status: str = Field(..., description="服务状态，通常为 'ok' 或 'error'")
    details: Optional[Dict[str, Any]] = Field(None, description="附加的健康信息")
class QdrantCollectionInfoResponse(BaseModel):
    """Qdrant 集合信息响应体"""
    name: str = Field(..., description="集合名称")
    vectors_count: int = Field(..., description="向量数量")
    segments_count: int = Field(..., description="段数量")
    index_status: str = Field(..., description="索引状态")
    storage_size: Optional[int] = Field(None, description="存储大小（字节）")
    config: Optional[Dict[str, Any]] = Field(None, description="集合配置详情")
class QdrantPoint(BaseModel):
    """Qdrant 向量点"""
    id: str = Field(..., description="向量点ID")
    vector: List[float] = Field(..., description="向量数据")
    payload: Optional[Dict[str, Any]] = Field(None, description="附加负载数据")
class QdrantSearchResultItem(BaseModel):
    """Qdrant 搜索结果单项"""
    point_id: str = Field(..., description="向量点ID")
    score: float = Field(..., description="相似度分数")
    payload: Optional[Dict[str, Any]] = Field(None, description="附加负载数据")
class QdrantSearchResponse(BaseModel):
    """Qdrant 搜索响应体"""
    results: List[QdrantSearchResultItem] = Field(..., description="搜索结果列表")
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
    