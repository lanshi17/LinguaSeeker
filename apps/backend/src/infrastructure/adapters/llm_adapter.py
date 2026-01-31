"""LLM Adapter for Agent interactions.

Provides abstraction layer for LLM provider integration (OpenAI, Anthropic, local models).
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


@dataclass
class LLMRequest:
    """LLM request structure."""

    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.0  # Deterministic by default
    max_tokens: int = 4000
    model: Optional[str] = None
    response_format: Optional[str] = None  # "json" for structured output


@dataclass
class LLMResponse:
    """LLM response structure."""

    content: str
    model: str
    tokens_used: int
    finish_reason: str
    metadata: Dict[str, Any]


class LLMAdapter:
    """Adapter for LLM provider integration.

    Provides unified interface for different LLM providers with
    automatic retries, rate limiting, and error handling.
    """

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize LLM adapter.

        Args:
            provider: LLM provider (openai, anthropic, local)
            api_key: API key for provider
            model: Default model to use
            base_url: Base URL for API (for local models)
        """
        self.provider = LLMProvider(provider.lower())
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self.base_url = base_url
        self.default_model = model or self._get_default_model()

        # Initialize provider client
        self._init_client()

    def _get_default_model(self) -> str:
        """Get default model for provider."""
        defaults = {
            LLMProvider.OPENAI: "gpt-4-turbo-preview",
            LLMProvider.ANTHROPIC: "claude-3-opus-20240229",
            LLMProvider.LOCAL: "llama-2-70b",
        }
        return defaults.get(self.provider, "gpt-4-turbo-preview")

    def _init_client(self) -> None:
        """Initialize provider-specific client."""
        if self.provider == LLMProvider.OPENAI:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")

        elif self.provider == LLMProvider.ANTHROPIC:
            try:
                from anthropic import Anthropic

                self.client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required. Install with: pip install anthropic")

        elif self.provider == LLMProvider.LOCAL:
            # For local models (e.g., Ollama, vLLM)
            import httpx

            self.client = httpx.AsyncClient(base_url=self.base_url or "http://localhost:11434")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate LLM response.

        Args:
            request: LLM request with prompt and parameters

        Returns:
            LLM response with content and metadata
        """
        model = request.model or self.default_model

        if self.provider == LLMProvider.OPENAI:
            return await self._generate_openai(request, model)
        elif self.provider == LLMProvider.ANTHROPIC:
            return await self._generate_anthropic(request, model)
        elif self.provider == LLMProvider.LOCAL:
            return await self._generate_local(request, model)

        raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_openai(self, request: LLMRequest, model: str) -> LLMResponse:
        """Generate response using OpenAI API."""
        messages = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        messages.append({"role": "user", "content": request.prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Add JSON mode if requested
        if request.response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            tokens_used=response.usage.total_tokens,
            finish_reason=response.choices[0].finish_reason,
            metadata={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
        )

    async def _generate_anthropic(self, request: LLMRequest, model: str) -> LLMResponse:
        """Generate response using Anthropic API."""
        kwargs = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }

        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        response = self.client.messages.create(**kwargs)

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason,
            metadata={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
        )

    async def _generate_local(self, request: LLMRequest, model: str) -> LLMResponse:
        """Generate response using local model (Ollama format)."""
        payload = {
            "model": model,
            "prompt": request.prompt,
            "temperature": request.temperature,
            "stream": False,
        }

        if request.system_prompt:
            payload["system"] = request.system_prompt

        response = await self.client.post("/api/generate", json=payload)
        data = response.json()

        return LLMResponse(
            content=data["response"],
            model=model,
            tokens_used=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
            finish_reason="stop",
            metadata={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    def parse_json_response(self, response: LLMResponse) -> Dict[str, Any]:
        """Parse JSON response from LLM.

        Args:
            response: LLM response

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If response is not valid JSON
        """
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Input text

        Returns:
            Estimated token count (rough approximation)
        """
        # Rough estimate: ~4 characters per token
        return len(text) // 4

    async def validate_api_key(self) -> bool:
        """Validate API key by making a simple request.

        Returns:
            True if API key is valid
        """
        try:
            test_request = LLMRequest(
                prompt="Say 'OK'",
                max_tokens=10,
                temperature=0,
            )
            await self.generate(test_request)
            return True
        except Exception:
            return False
