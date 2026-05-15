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
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.ChatOpenAI"
    ) as chat_cls:
        chat = MagicMock()
        structured = MagicMock()
        structured.invoke.return_value = DemoSchema(answer="ok")
        chat.with_structured_output.return_value = structured
        chat_cls.return_value = chat

        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=DemoSchema,
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )

    assert result.answer == "ok"
    chat_cls.assert_called_with(
        model="strong",
        api_key=provider._secret,
        base_url="http://localhost:8001/v1",
        temperature=0.0,
        timeout=60,
    )
