"""Model type registry."""

from enum import StrEnum


class ModelType(StrEnum):
    EMBEDDING = "embedding"
    RERANK = "rerank"
    LLM = "llm"
