"""Standalone config loader for the Rett annotation tool.

Loads from config.yaml + .env, fully independent of backend/config/.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ANNOTATION_ROOT = Path(__file__).resolve().parent.parent


class LLMProviderConfig(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    max_tokens: int = 8192
    temperature: float = 0.0
    timeout: int = 120


class PdfParserConfig(BaseModel):
    backend: str = "mineru"
    mineru_base_url: str = "https://mineru.net/api/v4"
    mineru_model_version: str = "vlm"
    mineru_enable_formula: bool = True
    mineru_enable_table: bool = True
    mineru_language: str = "ch"
    poll_interval: float = 3.0
    max_poll_attempts: int = 200
    batch_size: int = 10


class AnnotationConfig(BaseModel):
    max_concurrency: int = 3
    chunk_size: int = 12000


class PathsConfig(BaseModel):
    pdf_source_dir: str = "../literature_acquisition/downloads/rett"
    draft_dir: str = "./draft"
    approved_dir: str = "./approved"
    rejected_dir: str = "./rejected"
    ground_truth_dir: str = "./ground_truth"

    def resolve(self, root: Path = _ANNOTATION_ROOT) -> dict[str, Path]:
        return {
            "pdf_source_dir": (root / self.pdf_source_dir).resolve(),
            "draft_dir": (root / self.draft_dir).resolve(),
            "approved_dir": (root / self.approved_dir).resolve(),
            "rejected_dir": (root / self.rejected_dir).resolve(),
            "ground_truth_dir": (root / self.ground_truth_dir).resolve(),
        }


class AnnotationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ANNOTATION_ROOT / ".env"),
        env_prefix="ANNOTATION_",
        extra="ignore",
    )

    llm_api_key: str = ""
    llm_fallback_api_key: str = ""
    mineru_token: str = ""


class Config:
    def __init__(self, config_path: Path | None = None):
        config_path = config_path or (_ANNOTATION_ROOT / "config.yaml")
        with open(config_path) as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        self._env = AnnotationSettings()

        llm_raw = raw.get("llm", {})
        llm_raw["api_key"] = self._env.llm_api_key
        self.llm = LLMProviderConfig(**llm_raw)

        fallback_raw = raw.get("llm_fallback")
        if fallback_raw:
            fallback_raw["api_key"] = self._env.llm_fallback_api_key
            self.llm_fallback = LLMProviderConfig(**fallback_raw)
        else:
            self.llm_fallback = None

        self.pdf_parser = PdfParserConfig(**raw.get("pdf_parser", {}))
        self.annotation = AnnotationConfig(**raw.get("annotation", {}))
        self.paths = PathsConfig(**raw.get("paths", {}))
        self.mineru_token = self._env.mineru_token
        self._resolved_paths = self.paths.resolve()

    @property
    def resolved_paths(self) -> dict[str, Path]:
        return self._resolved_paths

    def build_llm_client(self) -> Any:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.llm.model,
            base_url=self.llm.base_url,
            api_key=self.llm.api_key,
            max_tokens=self.llm.max_tokens,
            temperature=self.llm.temperature,
            timeout=self.llm.timeout,
        )

    def build_fallback_client(self) -> Any | None:
        if self.llm_fallback is None:
            return None
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.llm_fallback.model,
            base_url=self.llm_fallback.base_url,
            api_key=self.llm_fallback.api_key,
            max_tokens=self.llm_fallback.max_tokens,
            temperature=self.llm_fallback.temperature,
            timeout=self.llm_fallback.timeout,
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
