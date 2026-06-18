"""Tests for query_translator module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.query_translator import (
    TARGET_LANGUAGES,
    TranslatedQueries,
    _parse_response,
    translate_query,
)


# ── _parse_response ────────────────────────────────────────────────────────


class TestParseResponse:
    """Unit tests for _parse_response."""

    def test_valid_json(self) -> None:
        raw = json.dumps({
            "en": "Rett syndrome MECP2 mutation",
            "zh": "Rett综合征 MECP2 突变 病例报告",
            "ja": "レット症候群 MECP2 変異 症例報告",
            "de": "Rett-Syndrom MECP2 Mutation Fallbericht",
            "fr": "Syndrome de Rett mutation MECP2 cas clinique",
            "ru": "Синдром Ретта мутация MECP2 клинический случай",
        })
        result = _parse_response(raw, "Rett syndrome MECP2 mutation")
        assert isinstance(result, TranslatedQueries)
        assert result.en == "Rett syndrome MECP2 mutation"
        assert result.zh == "Rett综合征 MECP2 突变 病例报告"
        assert result.source_query == "Rett syndrome MECP2 mutation"

    def test_json_with_markdown_fences(self) -> None:
        raw = '```json\n{"en": "test", "zh": "test", "ja": "test", "de": "test", "fr": "test", "ru": "test"}\n```'
        result = _parse_response(raw, "test")
        assert result.en == "test"

    def test_missing_language_raises(self) -> None:
        raw = json.dumps({"en": "test", "zh": "test"})
        with pytest.raises(ValueError, match="missing languages"):
            _parse_response(raw, "test")

    def test_empty_language_falls_back_to_source(self) -> None:
        raw = json.dumps({
            "en": "test", "zh": "", "ja": "test",
            "de": "test", "fr": "test", "ru": "test",
        })
        result = _parse_response(raw, "original query")
        assert result.zh == "original query"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Failed to parse"):
            _parse_response("not json at all", "test")

    def test_null_value_falls_back_to_source(self) -> None:
        raw = json.dumps({
            "en": "test", "zh": None, "ja": "test",
            "de": "test", "fr": "test", "ru": "test",
        })
        result = _parse_response(raw, "original query")
        assert result.zh == "original query"

    def test_as_dict(self) -> None:
        raw = json.dumps({
            "en": "en_q", "zh": "zh_q", "ja": "ja_q",
            "de": "de_q", "fr": "fr_q", "ru": "ru_q",
        })
        result = _parse_response(raw, "src")
        d = result.as_dict()
        assert set(d.keys()) == set(TARGET_LANGUAGES)
        assert d["en"] == "en_q"


# ── translate_query ────────────────────────────────────────────────────────


class TestTranslateQuery:
    """Integration tests for translate_query (mocked LLM)."""

    @pytest.mark.asyncio
    async def test_translates_with_mock_llm(self) -> None:
        translation = {
            "en": "Rett syndrome MECP2 genetic variant",
            "zh": "Rett综合征 MECP2 基因变异",
            "ja": "レット症候群 MECP2 遺伝子変異",
            "de": "Rett-Syndrom MECP2 Genvariante",
            "fr": "Syndrome de Rett variant génétique MECP2",
            "ru": "Синдром Ретта генетический вариант MECP2",
        }
        mock_message = MagicMock()
        mock_message.content = json.dumps(translation)
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await translate_query(
            "Rett syndrome MECP2 mutation",
            client=mock_client,
            model="test-model",
            base_url="http://test",
            api_key="test-key",
        )

        assert result.en == "Rett syndrome MECP2 genetic variant"
        assert result.zh == "Rett综合征 MECP2 基因变异"
        assert result.source_query == "Rett syndrome MECP2 mutation"
        mock_client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_query_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            await translate_query("", model="m", base_url="http://x", api_key="k")

    @pytest.mark.asyncio
    async def test_missing_config_raises(self) -> None:
        mock_cfg = MagicMock()
        mock_cfg.llm.model = ""
        mock_cfg.llm.base_url = ""
        mock_cfg.llm.all_api_keys = []
        mock_cfg.llm.max_tokens = 4096
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition."
            "query_translator.get_config",
            return_value=mock_cfg,
        ):
            with pytest.raises(ValueError, match="LLM model"):
                await translate_query("test")
