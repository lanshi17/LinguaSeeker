import pytest
from types import SimpleNamespace
from typing import Any, cast

from src.domain.agent import prompts
from src.domain.agent.rag import RAGComponent
from src.domain.agent.workflow import EvidenceAgent
from src.domain.enums import ProcessingState
from src.domain.models import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGQueryResponseItem,
    RerankResponse,
    RerankResponseItem,
)


def _make_processing_state(**overrides: Any) -> ProcessingState:
    state = {
        "markdown_content": "",
        "image_paths": [],
        "translated_md": "",
        "image_descriptions": [],
        "ps3_evidence": {},
        "extracted_fields": {},
        "evidence_sources": [],
        "knowledge_context": "",
        "field_confidence_scores": {},
        "overall_confidence": 0.0,
        "evidence_classification": "",
        "acmg_evidence_levels": [],
        "arbitration_confidence": 0.0,
        "arbitration_feedback": "",
        "arbitration_score": 0.0,
        "iteration_count": 0,
        "max_iterations": 1,
        "needs_manual_review": False,
        "enable_vlm": False,
        "vlm_results": [],
        "status": "pending",
        "output": None,
    }
    return cast(ProcessingState, cast(object, {**state, **overrides}))


def test_translation_prompt_includes_markdown() -> None:
    content = "# Title"
    prompt = prompts.get_translation_prompt(content)
    assert content in prompt


def test_image_description_prompt_includes_index() -> None:
    prompt = prompts.get_image_description_prompt(2)
    assert "Image 2" in prompt


def test_layout_fusion_prompt_includes_images() -> None:
    prompt = prompts.get_layout_fusion_prompt("doc", ["img1", "img2"])
    assert "Image 1 Description" in prompt
    assert "Image 2 Description" in prompt


def test_ps3_evidence_prompt_includes_knowledge_context() -> None:
    prompt = prompts.get_ps3_evidence_extraction_prompt(
        "doc",
        ["img"],
        knowledge_context="kb",
    )
    assert "REFERENCE KNOWLEDGE BASE" in prompt
    assert "kb" in prompt


def test_estimate_tokens_ascii_and_unicode() -> None:
    agent = EvidenceAgent()
    assert agent._estimate_tokens("abcd") == 1
    assert agent._estimate_tokens("\u4f60\u597d") == 2


def test_split_paragraph_respects_max_chars() -> None:
    agent = EvidenceAgent()
    paragraph = "Hello world. Another sentence here."
    chunks = agent._split_paragraph(paragraph, max_tokens=50, max_chars=10)
    assert len(chunks) >= 2
    assert all(0 < len(chunk) <= 10 for chunk in chunks)


def test_segment_text_for_translation_splits() -> None:
    agent = EvidenceAgent()
    text = "Alpha beta\n\nGamma delta"
    segments = agent._segment_text_for_translation(text, max_tokens=50, max_chars=10)
    assert len(segments) >= 2
    assert all(0 < len(seg) <= 10 for seg in segments)


def test_extract_json_payload_from_wrapped_content() -> None:
    agent = EvidenceAgent()
    payload = agent._extract_json_payload('prefix {"a": 1} suffix')
    assert payload["a"] == 1


def test_extract_json_payload_from_plain_json() -> None:
    agent = EvidenceAgent()
    payload = agent._extract_json_payload('{"ok": true}')
    assert payload["ok"] is True


def test_extract_json_payload_from_fenced_json() -> None:
    agent = EvidenceAgent()
    payload = agent._extract_json_payload('```json\n{"a": 1}\n```')
    assert payload["a"] == 1


def test_extract_json_payload_with_trailing_commas() -> None:
    agent = EvidenceAgent()
    payload = agent._extract_json_payload('{"a": 1, "b": [1, 2,],}')
    assert payload == {"a": 1, "b": [1, 2]}


def test_parse_json_payload_with_repair_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = EvidenceAgent()

    class FakeRepairLLM:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, _: object) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(content='{"ok": true, "source": "repair"}')

    fake_llm = FakeRepairLLM()
    monkeypatch.setattr(agent, "get_json_repair_llm", lambda: fake_llm)

    payload = agent._parse_json_payload_with_repair("malformed payload", "单元测试")

    assert payload == {"ok": True, "source": "repair"}
    assert fake_llm.calls == 1


def test_route_decision_thresholds() -> None:
    approved = EvidenceAgent.route_decision(_make_processing_state(arbitration_score=85))
    manual = EvidenceAgent.route_decision(_make_processing_state(arbitration_score=84))
    assert approved == "approved"
    assert manual == "manual_review"


def test_finish_states() -> None:
    approved = EvidenceAgent.finish_approved(_make_processing_state(status="pending"))
    manual = EvidenceAgent.finish_manual(_make_processing_state(status="pending"))
    assert approved["status"] == "approved"
    assert manual["status"] == "manual_review"


def test_extract_output_contract_fields_backfills_nested_payload() -> None:
    agent = EvidenceAgent()
    state = _make_processing_state(
        ps3_evidence={
            "extracted_fields": {
                "gene": {"symbol": "GENE", "confidence": 95.0},
                "variant": {"hgvs_c": "c.1A>T", "confidence": 90.0},
            },
            "evidence_quality": {
                "overall_confidence": 91.5,
                "evidence_classification": "Pathogenic",
                "acmg_evidence_levels": ["PS3"],
            },
        },
        extracted_fields={},
        field_confidence_scores={},
        overall_confidence=0.0,
        evidence_classification="",
        acmg_evidence_levels=[],
    )

    fields = agent._extract_output_contract_fields(state, "PS3")

    assert fields["extracted_fields"]["gene"]["symbol"] == "GENE"
    assert fields["overall_confidence"] == 91.5
    assert fields["evidence_classification"] == "Pathogenic"
    assert fields["acmg_evidence_levels"] == ["PS3"]


def test_extract_output_contract_fields_uses_state_extracted_fields_fallback() -> None:
    agent = EvidenceAgent()
    state = _make_processing_state(
        ps3_evidence={},
        extracted_fields={
            "gene": {"symbol": "STATE_GENE", "confidence": 88.0},
        },
        field_confidence_scores={},
        overall_confidence=0.0,
        evidence_classification="",
        acmg_evidence_levels=[],
    )

    fields = agent._extract_output_contract_fields(state, "PS3_supporting")

    assert fields["extracted_fields"]["gene"]["symbol"] == "STATE_GENE"
    assert fields["overall_confidence"] > 0.0
    assert fields["acmg_evidence_levels"]


def test_build_context_limits_chars() -> None:
    rag = RAGComponent()
    results = [
        {"content": "a" * 20, "score": 0.9},
        {"content": "b" * 20, "score": 0.8},
    ]
    context = rag.build_context(results, max_chars=50)
    assert "Doc 1" in context
    assert "Doc 2" not in context


@pytest.mark.asyncio
async def test_rag_pipeline_empty_query_raises() -> None:
    rag = RAGComponent()
    request = RAGQueryRequest(
        query="   ",
        top_k=5,
        score_threshold=0.7,
        max_context_chars=4000,
        chunk_overlap=200,
        enable_rerank=True,
    )
    with pytest.raises(ValueError):
        await rag.rag_pipeline(request)


@pytest.mark.asyncio
async def test_rag_pipeline_with_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    rag = RAGComponent()

    async def fake_search_qdrant(*_: object, **__: object) -> RAGQueryResponse:
        return RAGQueryResponse(
            results=[
                RAGQueryResponseItem(document_id="1", content="alpha", score=0.9),
                RAGQueryResponseItem(document_id="2", content="beta", score=0.8),
            ]
        )

    def fake_rerank(*_: object, **__: object) -> RerankResponse:
        return RerankResponse(
            results=[
                RerankResponseItem(document="beta", score=0.95),
                RerankResponseItem(document="alpha", score=0.7),
            ]
        )

    monkeypatch.setattr(rag, "search_qdrant", fake_search_qdrant)
    monkeypatch.setattr(rag, "rerank", fake_rerank)

    request = RAGQueryRequest(
        query="q",
        top_k=2,
        score_threshold=0.7,
        max_context_chars=4000,
        chunk_overlap=200,
        enable_rerank=True,
    )
    output = await rag.rag_pipeline(request)
    assert output["results"][0]["content"] == "beta"
    assert "beta" in output["context"]
