from src.config import settings as cfg
from loguru import logger
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from typing import Optional
from datetime import datetime
from pydantic import SecretStr
import sys
import os
import pytest
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)
os.environ.pop("ANTHROPIC_BASE_URL", None)
os.environ.pop("OPENAI_BASE_URL", None)
os.environ.pop("GOOGLE_GEMINI_BASE_URL", None)
#========================= 测试代码 ====================
"""  generic_api_key: str
generic_base_url: str

evidence_api_key: str
evidence_base_url: str
evidence_model: str

arbitration_api_key: str
arbitration_model: str
arbitration_base_url: str

llm_temperature: float = 0.0
llm_max_tokens: int = 2000
llm_timeout: int = 60
llm_max_retries: int = 3
llm_mode: str = "api"
"""

#测试api是否可用
@pytest.mark.unit
def test_generic_llm_api():
    if cfg.llm_mode != "api":
        pytest.skip("跳过测试: 当前 LLM 模式不是 API 模式")
    try:
        llm = ChatOpenAI(
            api_key=SecretStr(cfg.format_api_key),
            base_url=cfg.format_base_url,
            temperature=cfg.llm_temperature,
            timeout=cfg.llm_timeout,
            max_retries=cfg.llm_max_retries,
            model=cfg.format_model,
        )
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello, how are you?")
        ]
        response = llm.invoke(messages)
        assert response.content is not None
        logger.info("Generic LLM API 测试通过，响应内容: {}", response.content)
    except Exception as e:
        logger.error("Generic LLM API 测试失败: {}", e)
        pytest.fail(f"Generic LLM API 测试失败: {e}")
        
@pytest.mark.unit
def test_evidence_llm_api():
    logger.debug("environment evidence_base_url: {}", cfg.evidence_base_url)
    logger.debug("environment evidence_model: {}", cfg.evidence_model)
    if cfg.llm_mode != "api":
        pytest.skip("跳过测试: 当前 LLM 模式不是 API 模式")
    try:
        llm = ChatAnthropic(
            api_key=SecretStr(cfg.evidence_api_key),
            base_url=cfg.evidence_base_url,
            temperature=cfg.llm_temperature,
            verbose=True,
            timeout=cfg.llm_timeout,
            max_retries=cfg.llm_max_retries,
            model_name=cfg.evidence_model,
            stop=["\n\n"]
        )
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello, how are you?")
        ]
        response = llm.invoke(messages)
        assert response.content is not None
        logger.info("Evidence LLM API 测试通过，响应内容: {}", response.content)
    except Exception as e:
        logger.error("Evidence LLM API 测试失败: {}", e)
        pytest.fail(f"Evidence LLM API 测试失败: {e}")
        
@pytest.mark.unit
def test_arbitration_llm_api():
    if cfg.llm_mode != "api":
        pytest.skip("跳过测试: 当前 LLM 模式不是 API 模式")
    try:
        llm = ChatAnthropic(
            api_key=SecretStr(cfg.arbitration_api_key),
            base_url="https://yunwu.ai/",
            temperature=cfg.llm_temperature,
            timeout=cfg.llm_timeout,
            max_retries=cfg.llm_max_retries,
            model_name=cfg.arbitration_model,
            stop=["\n\n"]
        )
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello, how are you?")
        ]
        response = llm.invoke(messages)
        assert response.content is not None
        logger.info("Arbitration LLM API 测试通过，响应内容: {}", response.content)
    except Exception as e:
        logger.error("Arbitration LLM API 测试失败: {}", e)
        pytest.fail(f"Arbitration LLM API 测试失败: {e}")