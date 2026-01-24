"""Translator service implementation."""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Using absolute imports from src root
from src.domain.services import TranslatorService
from src.domain.value_objects import Language
from src.infrastructure.utils.exceptions import TranslationError


class TranslatorServiceImpl(TranslatorService):
    """Translator service implementation using LLM."""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        # Increase timeout for translation tasks
        if hasattr(self.llm, 'request_timeout'):
            self.llm.request_timeout = 180  # 3 minutes

    def translate_to_english(self, text: str, source_lang: Language) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a precise scientific translator. Preserve structure, "
                        "headings, tables if present."
                    ),
                ),
                (
                    "human",
                    (
                        "Source language: {lang}\n"
                        "Translate the following to English with clean markdown:\n\n{text}"
                    ),
                ),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        try:
            return chain.invoke({"text": text, "lang": source_lang.value})
        except Exception as exc:  # noqa: BLE001
            raise TranslationError(str(exc))
