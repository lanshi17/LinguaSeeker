import pytest

from src.domain.agent import prompts
from src.domain.agent.rag import RAGComponent
from src.domain.agent.workflow import EvidenceAgent
from src.domain.models import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGQueryResponseItem,
    RerankResponse,
    RerankResponseItem,
)


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


def test_normalize_anthropic_base_url() -> None:
    agent = EvidenceAgent()
    assert agent._normalize_anthropic_base_url("https://a.com/v1/") == "https://a.com"
    assert agent._normalize_anthropic_base_url("https://a.com/") == "https://a.com"
    assert agent._normalize_anthropic_base_url("") == ""


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
    payload = agent._extract_json_payload("prefix {\"a\": 1} suffix")
    assert payload["a"] == 1


def test_extract_json_payload_from_plain_json() -> None:
    agent = EvidenceAgent()
    payload = agent._extract_json_payload("{\"ok\": true}")
    assert payload["ok"] is True


def test_route_decision_thresholds() -> None:
    approved = EvidenceAgent.route_decision({"arbitration_score": 85})
    manual = EvidenceAgent.route_decision({"arbitration_score": 84})
    assert approved == "approved"
    assert manual == "manual_review"


def test_finish_states() -> None:
    approved = EvidenceAgent.finish_approved({"status": "pending"})
    manual = EvidenceAgent.finish_manual({"status": "pending"})
    assert approved["status"] == "approved"
    assert manual["status"] == "manual_review"


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
    request = RAGQueryRequest(query="   ")
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

    request = RAGQueryRequest(query="q", top_k=2, enable_rerank=True)
    output = await rag.rag_pipeline(request)
    assert output["results"][0]["content"] == "beta"
    assert "beta" in output["context"]
