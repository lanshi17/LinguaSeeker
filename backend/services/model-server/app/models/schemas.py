"""Request / Response schemas — shared contracts across all layers."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Health ───────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    models: dict[str, bool] = Field(default_factory=dict)


# ── Embedding ────────────────────────────────────────────────────────────


class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str = ""
    encoding_format: str = "float"


class EmbeddingObject(BaseModel):
    object: str = "embedding"
    embedding: list[float]
    index: int


class EmbeddingUsage(BaseModel):
    prompt_tokens: int = 0
    total_tokens: int = 0


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingObject]
    model: str
    usage: EmbeddingUsage = Field(default_factory=EmbeddingUsage)


# ── Rerank ───────────────────────────────────────────────────────────────


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    model: str = ""
    top_k: int | None = None


class RerankResult(BaseModel):
    index: int
    document: str
    relevance_score: float


class RerankUsage(BaseModel):
    prompt_tokens: int = 0
    total_tokens: int = 0


class RerankResponse(BaseModel):
    model: str
    results: list[RerankResult]
    usage: RerankUsage = Field(default_factory=RerankUsage)


# ── Chat / LLM (placeholder for future local LLM) ──────────────────────


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = ""
    messages: list[ChatMessage]
    max_tokens: int = 512
    temperature: float = 0.0
    stream: bool = False


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    id: str = ""
    object: str = "chat.completion"
    model: str
    choices: list[ChatChoice]
    usage: ChatUsage = Field(default_factory=ChatUsage)


# ── VLM / MinerU Extraction ─────────────────────────────────────────────


class VLMDocumentMetadata(BaseModel):
    """Document-level metadata from VLM extraction."""

    total_pages: int = 1
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract_text: str | None = None


class VLMFigurePosition(BaseModel):
    """Position of a figure within the document."""

    page: int = Field(ge=1)
    index: int = Field(ge=1)
    caption: str | None = None


class VLMTableStructure(BaseModel):
    """Structured table data extracted by VLM."""

    page: int = Field(ge=1)
    index: int = Field(ge=1)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class VLMPageContent(BaseModel):
    """Content of a single page extracted by VLM."""

    page_number: int = Field(ge=1)
    markdown: str
    figures: list[VLMFigurePosition] = Field(default_factory=list)
    tables: list[VLMTableStructure] = Field(default_factory=list)


class VLMImageUrl(BaseModel):
    """Image URL in OpenAI multimodal content part."""

    url: str


class VLMContentPart(BaseModel):
    """A single content part in an OpenAI multimodal message."""

    type: str  # "text" | "image_url"
    text: str | None = None
    image_url: VLMImageUrl | None = None


class VLMMessage(BaseModel):
    """OpenAI multimodal chat message."""

    role: str
    content: str | list[VLMContentPart]


class VLMExtractRequest(BaseModel):
    """OpenAI-compatible multimodal chat request for VLM extraction."""

    model: str = ""
    messages: list[VLMMessage]
    max_tokens: int = 4096
    temperature: float = 0.0


class VLMUsage(BaseModel):
    """Token usage for VLM extraction."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class VLMExtractResponse(BaseModel):
    """Structured extraction response from VLM."""

    id: str = ""
    object: str = "vlm.extraction"
    model: str
    metadata: VLMDocumentMetadata = Field(default_factory=VLMDocumentMetadata)
    pages: list[VLMPageContent] = Field(default_factory=list)
    full_markdown: str = ""
    choices: list[dict] = Field(default_factory=list)
    usage: VLMUsage = Field(default_factory=VLMUsage)
