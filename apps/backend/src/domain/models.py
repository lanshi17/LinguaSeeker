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
    arbitration_confidence: Optional[float] = Field(None, description="仲裁置信度 (0-1)")
    image_descriptions: List[str] = Field(default_factory=list, description="图片描述列表")
    final_evidence_strength: Optional[str] = Field(None, description="最终证据强度等级")
    status: Optional[str] = Field("pending", description="处理状态")
    origin_format_md: Optional[str] = Field(None, description="原始格式的 排版后的Markdown 内容")
    en_format_md: Optional[str] = Field(None, description="翻译成英文的排版后的Markdown 内容")
    extracted_fields: Optional[Dict[str, Any]] = Field(None, description="提取的结构化证据字段")
    field_confidence_scores: Optional[Dict[str, float]] = Field(None, description="各字段置信度评分")
    overall_confidence: Optional[float] = Field(None, description="总体置信度 (0-100)")
    evidence_classification: Optional[str] = Field(None, description="证据分类: Pathogenic/Strong/Moderate等")
    acmg_evidence_levels: Optional[List[str]] = Field(None, description="ACMG 证据等级列表")


# ==================== 结构化证据字段模型 ====================

class GeneInfo(BaseModel):
    """基因信息"""
    symbol: str = Field(..., description="基因符号，如 BRCA1, TP53")
    full_name: Optional[str] = Field(None, description="基因全名")
    ncbi_gene_id: Optional[str] = Field(None, description="NCBI Gene ID")
    ensembl_id: Optional[str] = Field(None, description="Ensembl Gene ID")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class TranscriptInfo(BaseModel):
    """转录本信息"""
    transcript_id: str = Field(..., description="转录本ID，如 NM_007294.4")
    source: Optional[str] = Field(None, description="来源: RefSeq/Ensembl")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class ReferenceGenomeInfo(BaseModel):
    """参考基因组信息"""
    version: str = Field(..., description="参考基因组版本，如 GRCh37, GRCh38, hg19, hg38")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class ExperimentData(BaseModel):
    """实验数据"""
    assay_type: str = Field(..., description="实验类型，如 functional assay, splicing assay")
    method_description: Optional[str] = Field(None, description="实验方法描述")
    key_findings: Optional[List[str]] = Field(None, description="关键发现列表")
    statistical_data: Optional[Dict[str, Any]] = Field(None, description="统计数据: p值, CI等")
    sample_size: Optional[str] = Field(None, description="样本量")
    cell_line: Optional[str] = Field(None, description="细胞系")
    model_organism: Optional[str] = Field(None, description="模型生物")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class DiseaseInfo(BaseModel):
    """疾病信息"""
    disease_name: str = Field(..., description="疾病名称")
    chpo_id: Optional[str] = Field(None, description="CHPO (中文人类表型本体) ID")
    icd10_code: Optional[str] = Field(None, description="ICD-10 编码")
    omim_id: Optional[str] = Field(None, description="OMIM ID")
    inheritance_pattern: Optional[str] = Field(None, description="遗传模式: AD/AR/XL/XD等")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class SpeciesInfo(BaseModel):
    """物种信息"""
    species_name: str = Field(..., description="物种名称")
    is_human: bool = Field(True, description="是否为人类样本")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class PhenotypeInfo(BaseModel):
    """表型信息"""
    phenotype_description: str = Field(..., description="表型描述")
    hpo_ids: Optional[List[str]] = Field(None, description="HPO ID列表")
    severity: Optional[str] = Field(None, description="严重程度: mild/moderate/severe")
    onset_age: Optional[str] = Field(None, description="发病年龄")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class VariantInfo(BaseModel):
    """变异信息"""
    hgvs_c: Optional[str] = Field(None, description="cDNA变异描述，如 c.5382insC")
    hgvs_p: Optional[str] = Field(None, description="蛋白变异描述，如 p.Arg1443Gln")
    hgvs_g: Optional[str] = Field(None, description="基因组变异描述")
    chromosome: Optional[str] = Field(None, description="染色体位置")
    position: Optional[int] = Field(None, description="基因组位置")
    ref_allele: Optional[str] = Field(None, description="参考等位基因")
    alt_allele: Optional[str] = Field(None, description="替代等位基因")
    variant_type: Optional[str] = Field(None, description="变异类型: missense/nonsense/frameshift等")
    rs_id: Optional[str] = Field(None, description="dbSNP rs ID")
    clinvar_id: Optional[str] = Field(None, description="ClinVar ID")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class ControlInfo(BaseModel):
    """阴性/阳性对照信息"""
    has_negative_control: bool = Field(False, description="是否有阴性对照")
    has_positive_control: bool = Field(False, description="是否有阳性对照")
    negative_control_description: Optional[str] = Field(None, description="阴性对照描述")
    positive_control_description: Optional[str] = Field(None, description="阳性对照描述")
    control_variants: Optional[List[Dict[str, Any]]] = Field(None, description="对照变异列表")
    total_control_count: int = Field(0, description="对照变异总数")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class PedigreeInfo(BaseModel):
    """家系信息"""
    has_pedigree: bool = Field(False, description="是否有家系数据")
    family_size: Optional[int] = Field(None, description="家系规模")
    affected_count: Optional[int] = Field(None, description="受累人数")
    segregation_data: Optional[str] = Field(None, description="共分离数据描述")
    inheritance_pattern: Optional[str] = Field(None, description="遗传模式")
    confidence: float = Field(0.0, ge=0, le=100, description="提取置信度")
    evidence_quote: Optional[str] = Field(None, description="原文引用")


class ExtractedEvidenceFields(BaseModel):
    """标准化提取的11个证据字段"""
    gene: Optional[GeneInfo] = Field(None, description="基因信息")
    transcript_id: Optional[TranscriptInfo] = Field(None, description="转录本信息")
    reference_genome_version: Optional[ReferenceGenomeInfo] = Field(None, description="参考基因组版本")
    experiment_data: Optional[ExperimentData] = Field(None, description="实验数据")
    disease_chpo: Optional[DiseaseInfo] = Field(None, description="疾病信息(CHPO)")
    disease_icd10: Optional[DiseaseInfo] = Field(None, description="疾病信息(ICD10)")
    species: Optional[SpeciesInfo] = Field(None, description="物种信息")
    phenotype: Optional[PhenotypeInfo] = Field(None, description="表型信息")
    variant: Optional[VariantInfo] = Field(None, description="变异信息")
    negative_positive_control: Optional[ControlInfo] = Field(None, description="阴性/阳性对照")
    pedigree_information: Optional[PedigreeInfo] = Field(None, description="家系信息")

    def compute_field_confidence_scores(self) -> Dict[str, float]:
        """计算各字段置信度评分"""
        scores = {}
        for field_name in [
            "gene", "transcript_id", "reference_genome_version",
            "experiment_data", "disease_chpo", "disease_icd10",
            "species", "phenotype", "variant",
            "negative_positive_control", "pedigree_information",
        ]:
            field_value = getattr(self, field_name, None)
            if field_value is not None and hasattr(field_value, "confidence"):
                scores[field_name] = field_value.confidence
            else:
                scores[field_name] = 0.0
        return scores

    def compute_overall_confidence(self) -> float:
        """计算总体置信度"""
        scores = self.compute_field_confidence_scores()
        non_zero = [v for v in scores.values() if v > 0]
        if not non_zero:
            return 0.0
        return sum(non_zero) / len(non_zero)


class EvidenceStrengthClassification(BaseModel):
    """证据强度分类结果"""
    overall_score: float = Field(..., ge=0, le=100, description="总体评分")
    classification: str = Field(..., description="分类结果")
    acmg_levels: List[str] = Field(default_factory=list, description="ACMG 证据等级列表")
    is_valid: bool = Field(False, description="证据是否有效 (置信度>=85)")
    validity_reason: Optional[str] = Field(None, description="有效性判定原因")
    supporting_evidence: List[str] = Field(default_factory=list, description="支持证据列表")
    reasoning: Optional[str] = Field(None, description="分类推理")

    @staticmethod
    def classify_from_score(score: float) -> str:
        """根据分数映射证据分类（委托给 EvidenceClassifier）"""
        from src.domain.evidence.classifier import EvidenceClassifier
        return EvidenceClassifier.score_to_classification(score)

    @staticmethod
    def determine_acmg_levels(
        ps3_step_4: Dict[str, Any],
        overall_score: float,
    ) -> List[str]:
        """根据 PS3 步骤4判定 ACMG 证据等级（委托给 EvidenceClassifier）"""
        from src.domain.evidence.classifier import EvidenceClassifier
        raw_strength = ps3_step_4.get("final_evidence_strength")
        if isinstance(raw_strength, str):
            cleaned = raw_strength.strip()
            if cleaned.lower() in {"n/a", "na", "not_applicable"}:
                final_strength = "inconclusive"
            else:
                final_strength = cleaned or "inconclusive"
        else:
            final_strength = "inconclusive"
        return EvidenceClassifier.strength_to_acmg_levels(final_strength)


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
    
