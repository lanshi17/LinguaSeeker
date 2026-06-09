import pytest
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
    EvidenceExtractionConfigContext,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
    LangChainEvidenceProvider,
)


class DemoSchema(BaseModel):
    answer: str


def test_provider_uses_strong_model_for_strong_tier():
    ctx = EvidenceExtractionConfigContext(
        api_key="key",
        base_url="http://localhost:8001/v1",
        max_tokens=8192,
        reasoning_api_key="reasoning-key",
        reasoning_base_url="http://localhost:8001/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    client = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = DemoSchema(answer="ok")
    client.with_structured_output.return_value = structured
    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.create_llm_client",
        return_value=client,
    ) as create_client:
        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=DemoSchema,
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )

    assert result.answer == "ok"
    create_client.assert_called_once_with(
        model="strong",
        base_url="http://localhost:8001/v1",
        api_keys=["reasoning-key"],
        max_tokens=8192,
        temperature=0.0,
        timeout=180,
        model_kwargs={"reasoning_effort": "high"},
    )


def test_provider_uses_json_mode_when_requested():
    ctx = EvidenceExtractionConfigContext(
        api_key="key",
        base_url="http://localhost:8001/v1",
        max_tokens=8192,
        reasoning_api_key="reasoning-key",
        reasoning_base_url="http://localhost:8001/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    client = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = DemoSchema(answer="ok")
    client.with_structured_output.return_value = structured
    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.create_llm_client",
        return_value=client,
    ):
        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt='Return JSON with {"answer": "ok"}.',
            output_schema=DemoSchema,
            tier=EvidenceModelTier.FAST,
            stage="evidence_map",
            response_method="json_mode",
        )

    assert result.answer == "ok"
    client.with_structured_output.assert_called_once_with(DemoSchema, method="json_mode")


def test_provider_falls_back_to_plain_json_when_response_format_is_unsupported():
    ctx = EvidenceExtractionConfigContext(
        api_key="key",
        base_url="http://localhost:8001/v1",
        max_tokens=8192,
        reasoning_api_key="reasoning-key",
        reasoning_base_url="http://localhost:8001/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    client = MagicMock()
    structured = MagicMock()
    structured.invoke.side_effect = ValueError("This response_format type is unavailable now")
    fallback_message = MagicMock()
    fallback_message.content = '{"answer": "ok"}'
    client.invoke.return_value = fallback_message
    client.with_structured_output.return_value = structured
    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.create_llm_client",
        return_value=client,
    ):
        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=DemoSchema,
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )

    assert result.answer == "ok"
    structured.invoke.assert_called_once()
    client.invoke.assert_called_once()


def test_provider_fallback_validates_list_schema():
    ctx = EvidenceExtractionConfigContext(
        api_key="key",
        base_url="http://localhost:8001/v1",
        max_tokens=8192,
        reasoning_api_key="reasoning-key",
        reasoning_base_url="http://localhost:8001/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    client = MagicMock()
    fallback_message = MagicMock()
    fallback_message.content = '[{"answer": "ok"}]'
    client.invoke.return_value = fallback_message
    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.create_llm_client",
        return_value=client,
    ):
        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=list[DemoSchema],
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )

    assert len(result) == 1
    assert result[0].answer == "ok"
    client.with_structured_output.assert_not_called()


def test_provider_fallback_repairs_invalid_json_backslash_escapes():
    ctx = EvidenceExtractionConfigContext(
        api_key="key",
        base_url="http://localhost:8001/v1",
        max_tokens=8192,
        reasoning_api_key="reasoning-key",
        reasoning_base_url="http://localhost:8001/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    client = MagicMock()
    structured = MagicMock()
    structured.invoke.side_effect = ValueError("This response_format type is unavailable now")
    fallback_message = MagicMock()
    fallback_message.content = '{"answer": "GLA\\p.R227X"}'
    client.invoke.return_value = fallback_message
    client.with_structured_output.return_value = structured
    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.create_llm_client",
        return_value=client,
    ):
        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=DemoSchema,
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )

    assert result.answer == "GLA\\p.R227X"


def test_provider_fallback_reasks_llm_to_repair_invalid_json():
    ctx = EvidenceExtractionConfigContext(
        api_key="key",
        base_url="http://localhost:8001/v1",
        max_tokens=8192,
        reasoning_api_key="reasoning-key",
        reasoning_base_url="http://localhost:8001/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    client = MagicMock()
    invalid_message = MagicMock()
    invalid_message.content = '{"answer": "broken"'
    repaired_message = MagicMock()
    repaired_message.content = '[{"answer": "ok"}]'
    client.invoke.side_effect = [invalid_message, repaired_message]
    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.create_llm_client",
        return_value=client,
    ):
        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=list[DemoSchema],
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )

    assert result[0].answer == "ok"
    assert client.invoke.call_count == 2


def test_provider_fails_fast_when_tier_has_no_api_keys():
    ctx = EvidenceExtractionConfigContext(
        api_key="",
        api_keys=[],
        base_url="https://api.example.test/v1",
        reasoning_api_key="",
        reasoning_api_keys=[],
        reasoning_base_url="https://api.example.test/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    provider = LangChainEvidenceProvider(ctx)

    with pytest.raises(RuntimeError, match="missing LLM API key"):
        provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=DemoSchema,
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )
