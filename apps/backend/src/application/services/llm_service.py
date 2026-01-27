from typing import Any
from utils.logger import Logger
from infrastructure.adapters.llm.llm_client import LLMClient
from src.application.services.base_service import BaseService



class LLMService(BaseService):
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate_response(self, prompt: str) -> str:
        response = self.llm_client.chat_completion(prompt)
        return response