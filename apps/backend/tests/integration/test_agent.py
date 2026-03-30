from typing import List
import json
from pathlib import Path
from loguru import logger
from src.domain.enums import ProcessingState
from src.domain.models import AgentRequest, EvidenceOutput

from src.domain.agent.workflow import (
    EvidenceAgent,
    search_knowledge_base,
)
from src.domain.evidence.tools import (
    load_intermediate_md,
    OddsPath_Calculator,
    determine_evidence_strength_from_oddspath,
    determine_max_evidence_from_controls,
)
import os
from src.utils.timer import Timer, timer
import src.utils.exceptions as exc
import src.utils.file_utils as file_utils
from src.config import settings
from src.domain.agent.rag import RAGComponent
import pytest

cfg = settings

rag = RAGComponent()
agent = EvidenceAgent(rag_component=rag)


class DummyResponse:
    def __init__(self, content: str):
        self.content = content


class DummyLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, messages):
        return DummyResponse(self._content)


class DummySearchResponse:
    def __init__(self):
        self.results = []


class DummyQdrantManager:
    score_threshold = 0.0

    async def search(self, query_vector, top_k, score_threshold):
        return DummySearchResponse()


class DummyEmbeddingClient:
    def embed_query(self, query):
        return [0.0]


class DummyRag:
    def get_qdrant_manager(self):
        return DummyQdrantManager()

    def get_embedding_client(self):
        return DummyEmbeddingClient()


class DummyTool:
    async def ainvoke(self, args):
        return []


@pytest.fixture(autouse=True)
def stub_llms(monkeypatch):
    evidence_json = json.dumps(
        {
            "overall_assessment": {"final_recommendation": "approved", "key_strengths": []},
            "ps3_step_1": {"score": 25},
            "ps3_step_2": {"score": 25},
            "ps3_step_3": {"score": 25},
            "ps3_step_4": {"score": 25, "final_evidence_strength": "PS3"},
        }
    )
    arbitration_json = json.dumps(
        {
            "arbitration_score": 90.0,
            "feedback": "ok",
            "final_decision": "approved",
            "score_adjustment": 0,
        }
    )

    monkeypatch.setattr(EvidenceAgent, "get_translation_llm", lambda self: DummyLLM("translated"))
    monkeypatch.setattr(EvidenceAgent, "get_format_llm", lambda self: DummyLLM("formatted"))
    monkeypatch.setattr(
        EvidenceAgent, "get_vlm", lambda self: DummyLLM("Image description: A test image.")
    )
    monkeypatch.setattr(EvidenceAgent, "get_evidence_llm", lambda self: DummyLLM(evidence_json))
    monkeypatch.setattr(
        EvidenceAgent, "get_arbitration_llm", lambda self: DummyLLM(arbitration_json)
    )
    monkeypatch.setattr(agent, "rag", DummyRag())
    monkeypatch.setattr("src.domain.agent.workflow.search_knowledge_base", DummyTool())


def _make_state(markdown_content: str, image_paths: List[str]) -> ProcessingState:
    return {
        "markdown_content": markdown_content,
        "image_paths": image_paths,
        "translated_md": "",
        "image_descriptions": [],
        "enable_vlm": True,
        "vlm_results": [],
        "ps3_evidence": {},
        "extracted_fields": {},
        "evidence_sources": [],
        "knowledge_context": "",
        "field_confidence_scores": {},
        "overall_confidence": 0.0,
        "evidence_classification": "",
        "acmg_evidence_levels": [],
        "arbitration_score": 0.0,
        "arbitration_confidence": 0.0,
        "arbitration_feedback": "",
        "iteration_count": 0,
        "max_iterations": 2,
        "needs_manual_review": False,
        "status": "pending",
        "output": None,
    }


# ==================== LLM 客户端配置test====================


@pytest.mark.unit
def test_llm_client_configuration():
    """测试 LLM 客户端配置"""
    evidence_llm = agent.get_evidence_llm()
    arbitration_llm = agent.get_arbitration_llm()
    translation_llm = agent.get_translation_llm()
    format_llm = agent.get_format_llm()
    vlm = agent.get_vlm()

    evidence_base = (
        getattr(evidence_llm, "bound", None) or getattr(evidence_llm, "llm", None) or evidence_llm
    )
    evidence_model = getattr(evidence_base, "model_name", None) or getattr(
        evidence_base, "model", None
    )
    arbitration_model = getattr(arbitration_llm, "model_name", None) or getattr(
        arbitration_llm, "model", None
    )
    translation_model = getattr(translation_llm, "model_name", None) or getattr(
        translation_llm, "model", None
    )
    format_model = getattr(format_llm, "model_name", None) or getattr(format_llm, "model", None)
    vlm_model = getattr(vlm, "model_name", None) or getattr(vlm, "model", None)

    if evidence_model is None:
        pytest.skip("Evidence LLM does not expose model name")
    if arbitration_model is None:
        pytest.skip("Arbitration LLM does not expose model name")

    assert evidence_model == cfg.evidence_model, "证据 LLM 模型名称不匹配"
    assert arbitration_model == cfg.arbitration_model, "仲裁 LLM 模型名称不匹配"
    assert translation_model == "qwen-mt-flash", "翻译 LLM 模型名称不匹配"
    assert format_model == "qwen-flash", "格式化 LLM 模型名称不匹配"
    assert vlm_model == "qwen3-vl-flash", "视觉 LLM 模型名称不匹配"
    logger.debug("LLM 客户端配置测试通过。")


# ========================= tools--test ====================
@pytest.mark.unit
def test_tool():
    """测试工具函数"""
    # test save_intermediate_md load_intermediate_md
    test_content = "# 测试内容\n这是一些测试内容。"
    test_filepath = "test_intermediate.md"
    Path(test_filepath).write_text(test_content, encoding="utf-8")
    loaded_content = load_intermediate_md.invoke({"file_path": test_filepath})
    assert loaded_content == test_content, "保存和加载的中间文件内容不匹配"
    os.remove(test_filepath)
    logger.debug("工具函数测试通过。")


@pytest.mark.unit
def test_OddsPath_Calculator():
    """测试 OddsPath 计算器"""
    P1 = 0.1
    P2 = 0.2
    result = OddsPath_Calculator.invoke({"P1": P1, "P2": P2})
    expected = (P2 * (1 - P1)) / ((1 - P2) * P1)
    assert abs(result - expected) < 1e-6, "OddsPath 计算结果不正确"
    logger.debug("OddsPath 计算器测试通过。")


@pytest.mark.unit
def test_determine_evidence_strength_from_oddspath():
    """测试根据 OddsPath 确定证据强度"""
    test_cases = [
        (0.002, "BS3_very_strong"),
        (0.02, "BS3"),
        (0.1, "BS3_moderate"),
        (0.6, "BS3_supporting"),
        (3.0, "PS3_supporting"),
        (10.0, "PS3_moderate"),
        (100.0, "PS3"),
        (400.0, "PS3_very_strong"),
    ]
    for odds, expected_strength in test_cases:
        strength = determine_evidence_strength_from_oddspath.invoke({"oddspath": odds})
        assert strength == expected_strength, (
            f"Odds: {odds}, 预期强度: {expected_strength}, 实际强度: {strength}"
        )
    logger.debug("根据 OddsPath 确定证据强度测试通过。")


@pytest.mark.unit
def test_determine_max_evidence_from_controls():
    """测试根据对照组确定最大证据强度"""
    test_cases = [
        (0, "no_evidence"),
        (5, "max_supporting"),
        (10, "max_supporting"),
        (11, "max_moderate"),
    ]
    for controls, expected_classification in test_cases:
        classification = determine_max_evidence_from_controls.invoke(
            {"control_variants_count": controls}
        )
        assert classification == expected_classification, (
            f"Controls: {controls}, 预期分类: {expected_classification}, 实际分类: {classification}"
        )
    logger.debug("根据对照组确定最大证据强度测试通过。")


@pytest.mark.asyncio
async def test_search_knowledge_base():
    query = "Explain the concept of reinforcement learning."
    response = await search_knowledge_base.ainvoke(
        {
            "query": query,
            "top_k": 5,
        }
    )
    assert isinstance(response, list)
    logger.info("知识库搜索测试通过。")


# ==================== 处理步骤函数 --test====================
# 步骤一：翻译 Markdown 内容
@pytest.mark.unit
def test_translate_markdown():
    """测试翻译 Markdown 内容"""
    test_content = "# 标题\n这是一些中文内容。"
    state = _make_state(test_content, [])
    result = agent.translate_markdown(state)
    translated_content = result.get("translated_md")
    assert isinstance(translated_content, str) and translated_content, "翻译内容不正确"
    logger.debug("翻译 Markdown 内容测试通过。")


# 步骤二：图片描述生成
@pytest.mark.unit
def test_describe_images():
    """测试图片描述生成"""
    # 准备测试图片
    test_image_path = "test_image.jpg"
    with open(test_image_path, "wb") as f:
        f.write(b"test")
    state = _make_state("# 标题\n这是一些内容。", [test_image_path])
    result = agent.describe_images(state)
    descriptions = result.get("image_descriptions")
    assert descriptions is not None, "图片描述为空"
    assert len(descriptions) == 1, "图片描述数量不正确"
    assert isinstance(descriptions[0], str) and descriptions[0], "图片描述内容不正确"
    logger.debug("图片描述生成测试通过。{}", descriptions[0])
    os.remove(test_image_path)


@pytest.mark.unit
def test_describe_images_disabled():
    """默认禁用 VLM 时跳过图片描述"""
    state = _make_state("# 标题\n这是一些内容。", ["missing.jpg"])
    state["enable_vlm"] = False
    result = agent.describe_images(state)
    assert result.get("image_descriptions") == []
    logger.debug("VLM 禁用情况下成功跳过图片描述")


# 步骤4: 证据提取+RAG
@pytest.mark.asyncio
async def test_extract_ps3_evidence():
    """测试提取 PS3 证据"""
    test_content = "# 标题\n这是一些内容，包含功能性研究结果。"
    state = _make_state(test_content, [])
    state["translated_md"] = "# Title\nSome content."
    state["image_descriptions"] = ["Image description: A test image."]
    result = await agent.extract_ps3_evidence(state)
    evidence = result.get("ps3_evidence")
    assert evidence is not None, "提取的证据为空"
    assert isinstance(evidence, dict), "提取的证据格式不正确"
    logger.debug("提取 PS3 证据测试通过。")


# 步骤5: 仲裁评分
@pytest.mark.unit
def test_arbitrate_score():
    """测试仲裁评分"""
    state = _make_state("# 标题\n这是一些内容。", [])
    state["translated_md"] = "# Title\nSome content."
    state["image_descriptions"] = ["Image description: A test image."]
    state["ps3_evidence"] = {
        "overall_assessment": {"final_recommendation": "needs_refinement"},
        "ps3_step_1": {"score": 10},
        "ps3_step_2": {"score": 10},
        "ps3_step_3": {"score": 10},
        "ps3_step_4": {"score": 10},
        "calculated_total_score": 40,
    }
    result = agent.arbitrate_score(state)
    score = result.get("arbitration_score")
    feedback = result.get("arbitration_feedback")
    assert isinstance(score, float), "仲裁得分类型不正确"
    assert 0.0 <= score <= 100.0, "仲裁得分范围不正确"
    assert isinstance(feedback, str), "反馈类型不正确"
    logger.debug("仲裁评分测试通过。")


# =================================agent集成测试=================================
@pytest.mark.integration
def test_process_medical_evidence():
    """集成测试医学证据处理流程"""
    # 准备测试输入
    timer = Timer("医学证据处理流程集成测试")
    timer.start()
    test_markdown_content = "# 标题\n这是一些中文内容，包含功能性研究结果。"
    test_image_path = "test_image.jpg"
    with open(test_image_path, "wb") as f:
        f.write(b"test")
    test_request = AgentRequest(
        question="Analyze the medical evidence",
        context=test_markdown_content,
        max_response_tokens=2000,
        temperature=0.7,
        top_p=0.9,
        stream=False,
    )

    # 调用处理函数
    response: EvidenceOutput = agent.process_medical_evidence(
        test_markdown_content, [test_image_path]
    )

    # 断言结果
    assert response is not None, "输出结果为空"
    assert hasattr(response, "ps3_evidence"), "输出结果格式不正确"
    assert "entity_extractions" in response.ps3_evidence
    assert "relation_extractions" in response.ps3_evidence
    assert "experiment_info_extractions" in response.ps3_evidence

    logger.debug("医学证据处理流程集成测试通过。{}", response)
    os.remove(test_image_path)
    timer.stop()
