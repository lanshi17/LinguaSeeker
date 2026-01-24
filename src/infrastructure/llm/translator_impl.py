"""Translator service implementation."""

import re
import time
from typing import Iterable

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
        
        # Batch translation settings
        self.max_batch_chars = 8000  # Max characters per batch
        self.min_batch_chars = 2000  # Min characters to batch

    def translate_to_english(self, text: str, source_lang: Language) -> str:
        """Translate text to English, with batching for long content.
        
        Args:
            text: Text to translate (HTML format)
            source_lang: Source language
            
        Returns:
            Translated English text (HTML format)
        """
        # For small content, direct translation
        if len(text) <= self.max_batch_chars:
            return self._single_translation(text, source_lang)
        
        # For large content, use batching
        return self._batch_translation(text, source_lang)
    
    def _single_translation(self, text: str, source_lang: Language) -> str:
        """Perform single translation attempt with retry logic.
        
        Args:
            text: Text to translate
            source_lang: Source language
            
        Returns:
            Translated text
            
        Raises:
            TranslationError: If translation fails after retries
        """
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
                        "Translate the following HTML to English HTML. Requirements:\n"
                        "1. Keep all HTML tags intact (do not modify <p>, <h1>, <table>, etc.)\n"
                        "2. Only translate the text content inside HTML tags\n"
                        "3. Preserve HTML structure and formatting\n"
                        "4. Keep LaTeX math formulas unchanged\n"
                        "5. Maintain line breaks and spacing\n"
                        "6. Output clean, valid HTML\n\n{text}"
                    ),
                ),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()

        # Retry on timeout to improve robustness under slow proxies
        exceptions_to_retry: Iterable[str] = (
            "timed out",
            "ReadTimeout",
            "APITimeoutError",
        )

        for attempt in range(1, 3):
            try:
                return chain.invoke({"text": text, "lang": source_lang.value})
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                is_timeout = any(token in message for token in exceptions_to_retry)
                if attempt < 2 and is_timeout:
                    backoff = 5 * attempt
                    time.sleep(backoff)
                    continue
                raise TranslationError(message)
    
    def _batch_translation(self, html: str, source_lang: Language) -> str:
        """Translate large HTML by splitting into batches.
        
        Args:
            html: HTML content to translate
            source_lang: Source language
            
        Returns:
            Translated HTML with batches joined
        """
        # Split HTML into semantic chunks (at paragraph boundaries)
        batches = self._split_html_into_batches(html)
        translated_batches = []
        
        for idx, batch in enumerate(batches):
            try:
                translated = self._single_translation(batch, source_lang)
                translated_batches.append(translated)
            except TranslationError as e:
                raise TranslationError(
                    f"Batch {idx + 1}/{len(batches)} failed: {str(e)}"
                )
        
        # Reconstruct HTML from translated batches
        return "".join(translated_batches)
    
    def _split_html_into_batches(self, html: str) -> list[str]:
        """Split HTML into batches at paragraph boundaries.
        
        Args:
            html: HTML content to split
            
        Returns:
            List of HTML batches
        """
        batches = []
        current_batch = ""
        
        # Split by paragraph tags
        paragraphs = re.split(r'(<p>.*?</p>|<h[1-6]>.*?</h[1-6]>|<table>.*?</table>)', 
                             html, flags=re.DOTALL)
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            # Add to current batch
            test_batch = current_batch + para
            
            if len(test_batch) <= self.max_batch_chars:
                current_batch = test_batch
            else:
                # Current batch would exceed limit
                if current_batch:
                    batches.append(current_batch)
                    current_batch = para
                elif len(para) > self.max_batch_chars:
                    # Single paragraph exceeds limit, split further
                    sub_batches = self._split_large_element(para)
                    batches.extend(sub_batches[:-1])
                    current_batch = sub_batches[-1]
        
        # Add final batch
        if current_batch:
            batches.append(current_batch)
        
        return batches or [html]  # Fallback to original if no split occurred
    
    def _split_large_element(self, element: str) -> list[str]:
        """Split a single large HTML element by sentences.
        
        Args:
            element: HTML element to split
            
        Returns:
            List of split elements
        """
        batches = []
        current = ""
        
        # Split by sentence-like patterns
        sentences = re.split(r'(?<=[。.!?])\s*', element)
        
        for sent in sentences:
            if not sent.strip():
                continue
            
            test = current + sent
            if len(test) <= self.max_batch_chars:
                current = test
            else:
                if current:
                    batches.append(current)
                current = sent
        
        if current:
            batches.append(current)
        
        return batches or [element]
