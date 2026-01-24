"""Language detector service implementation."""

import json

import orjson
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Using absolute imports from src root
from src.domain.repositories import PDFRepository
from src.domain.services import LanguageDetectorService
from src.domain.value_objects import Language


class LanguageDetectorServiceImpl(LanguageDetectorService):
    """Language detection service implementation using PDF repo."""

    def __init__(self, pdf_repo: PDFRepository):
        self.pdf_repo = pdf_repo

    def detect(self, pdf_path: str) -> Language:
        """Detect language from PDF."""
        return self.pdf_repo.detect_language(pdf_path)
