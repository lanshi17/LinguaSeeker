"""Domain repositories (abstract interfaces)."""

from abc import ABC, abstractmethod
from typing import List

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from .pdf_repository import PDFRepository
from .rag_repository import RAGRepository

__all__ = [
    "PDFRepository",
    "RAGRepository",
]
