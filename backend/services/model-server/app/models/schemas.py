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
