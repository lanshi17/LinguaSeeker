from typing import Any
from loguru import logger
from infrastructure.adapters.llm.llm_client import LLMClient
from src.application.services.base_service import BaseService



class LLMService(BaseService):
    def __init__(self, llm_client):
        self.llm_client = llm_client
        logger.info("LLMService initialized")

    def generate_response(self, prompt: str) -> str:
        try:
            response = self.llm_client.chat_completion(prompt)
            logger.info("LLM response generated successfully")
            return response
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            raise