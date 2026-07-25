from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cross_lingual_translation.contracts import (
    ContentBlock,
    FormattedDocument,
    TranslationSegment,
)
from src.core.cross_lingual_translation.config_context import TranslationConfigContext
from src.core.cross_lingual_translation.translate.blocks import _BLOCK_SEP
from src.core.cross_lingual_translation.translate.providers import (
    LocalFirstTranslationAdapter,
    LocalTranslateGemmaClient,
    _to_text,
    invoke_json_with_retry,
    invoke_with_retry,
)
from src.core.cross_lingual_translation.translate.postprocess import (
    build_translated_blocks,
    check_block_coverage,
    check_block_language,
    deduplicate_bilingual_blocks,
    flag_quality_issues,
    trim_repetitive_content,
)
from src.core.cross_lingual_translation.translate.exceptions import TranslationError
from src.core.cross_lingual_translation.translate.translator import MultiStageTranslator


@pytest.fixture
def mock_ctx():
    return TranslationConfigContext(
        model="test-model",
        api_key="test-key",
        base_url="http://localhost:8001/v1",
    )


@pytest.fixture
def formatted_doc():
    return FormattedDocument(
        formatted_markdown="The patient carries a novel BRCA1 variant.",
        source_language="en",
    )


def test_translator_init(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    assert t._ctx == mock_ctx


def test_translator_llm(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    assert t._llm is not None


@pytest.mark.asyncio
async def test_run_pipeline_rejects_compressed_long_translation(mock_ctx, monkeypatch):
    translator = MultiStageTranslator(ctx=mock_ctx)
    source = (
        "患儿男，5月龄，因间断咳嗽半月余入院。患儿住院期间自主呼吸障碍显著，"
        "语言能力丧失，手部技能丧失并出现刻板动作，生长发育迟滞。二代基因检测发现"
        "MECP2基因存在c.194delC半合突变，此突变尚未见文献报道，父母该位点均无变异。"
    ) * 8
    summary_translation = (
        "This report describes a boy with Rett syndrome caused by a novel "
        "MECP2 mutation and emphasizes genetic testing."
    )

    async def fake_extract_terminology(formatted):
        return ""

    async def fake_translate_segments(formatted, terminology, blocks=None, *, strict=False):
        return summary_translation, [formatted.formatted_markdown], [summary_translation]

    async def fake_self_review(source_text, translated_text, system_prompt=""):
        return translated_text

    monkeypatch.setattr(translator, "extract_terminology", fake_extract_terminology)
    monkeypatch.setattr(translator, "translate_segments", fake_translate_segments)
    monkeypatch.setattr(translator, "_self_review", fake_self_review)

    formatted = FormattedDocument(
        formatted_markdown=source,
        source_language="zh",
    )

    with pytest.raises(TranslationError, match="incomplete_translation"):
        await translator.run_pipeline(formatted)


@pytest.mark.asyncio
async def test_translate_one_segment_uses_completeness_retry_prompt(mock_ctx, monkeypatch):
    translator = MultiStageTranslator(ctx=mock_ctx)
    source = (
        "患儿住院期间自主呼吸障碍显著，语言能力丧失，手部技能丧失并出现刻板动作，"
        "生长发育迟滞。二代基因检测发现MECP2基因存在c.194delC半合突变。"
    ) * 5
    full_translation = (
        "During hospitalization, the child had marked spontaneous breathing impairment, "
        "loss of language ability, loss of hand skills, stereotyped movements, and growth "
        "retardation. Next-generation sequencing identified a c.194delC hemizygous "
        "mutation in the MECP2 gene. "
    ) * 4
    retry_prompts: list[str] = []

    async def fake_json_invoke(llm, prompt, stage, system_prompt=""):
        return '{"translation": "Brief Rett syndrome summary."}'

    async def fake_invoke(llm, prompt, stage, system_prompt=""):
        retry_prompts.append(prompt)
        return full_translation

    monkeypatch.setattr(
        "src.core.cross_lingual_translation.translate.translator.invoke_json_with_retry",
        fake_json_invoke,
    )
    monkeypatch.setattr(
        "src.core.cross_lingual_translation.translate.translator.invoke_with_retry",
        fake_invoke,
    )

    result = await translator._translate_one_segment(source, "", 1, 1)

    assert result == full_translation.strip()
    assert any("previous translation was incomplete" in prompt.lower() for prompt in retry_prompts)


def test_providers_create_llm():
    from src.core.cross_lingual_translation.translate.providers import create_llm

    llm = create_llm(model="test-model", api_key="test-key", base_url="http://localhost:8001/v1", temperature=0.0)
    assert llm is not None


def test_providers_create_json_llm():
    from src.core.cross_lingual_translation.translate.providers import create_json_llm

    llm = create_json_llm(model="test-model", api_key="test-key", base_url="http://localhost:8001/v1", temperature=0.0)
    assert llm is not None


def test_local_translate_gemma_endpoint_normalization():
    client = LocalTranslateGemmaClient(base_url="http://localhost:59062/api")
    assert client.endpoint == "http://localhost:59062/api/translate"

    full_endpoint = LocalTranslateGemmaClient(base_url="http://localhost:8022/translate")
    assert full_endpoint.endpoint == "http://localhost:8022/translate"


@pytest.mark.asyncio
async def test_invoke_json_with_retry_uses_local_translation_first():
    class FakeLocalClient:
        async def translate(self, text):
            assert text == "你好,世界"
            return "Hello, world"

    remote_llm = AsyncMock()
    adapter = LocalFirstTranslationAdapter(remote_llm=remote_llm, local_client=FakeLocalClient())

    raw = await invoke_json_with_retry(
        adapter,
        '[TRANSLATE THIS SEGMENT]\n你好,世界\n\nReturn a JSON object with key "translation" containing the translated text.',
        "translate/1",
    )

    assert raw == '{"translation": "Hello, world"}'
    remote_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_invoke_with_retry_falls_back_to_remote_when_local_fails():
    class FakeLocalClient:
        async def translate(self, text):
            raise RuntimeError("local service unavailable")

    class FakeResponse:
        content = "remote translation"

    remote_llm = AsyncMock()
    remote_llm.ainvoke.return_value = FakeResponse()
    adapter = LocalFirstTranslationAdapter(remote_llm=remote_llm, local_client=FakeLocalClient())

    result = await invoke_with_retry(adapter, "[DOCUMENT]\n你好,世界", "translate/full")

    assert result == "remote translation"
    remote_llm.ainvoke.assert_awaited_once()


def test_to_text_none():
    assert _to_text(None) == ""


def test_to_text_string():
    assert _to_text(" hello ") == "hello"


def test_to_text_list():
    content = [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
    assert "hello" in _to_text(content)


def test_check_block_coverage_rejects_abstract_only_translation():
    original_blocks = [
        ContentBlock(type="title", text="Rett综合征的临床特点及MECP2基因突变分析"),
        ContentBlock(type="text", text="摘要 目的 分析典型 Rett 综合征患者的临床特点。"),
        ContentBlock(type="text", text="资料与方法 选取 9 例 RTT 患儿为研究对象。"),
        ContentBlock(type="text", text="结果 5 例存在 MECP2 基因突变。"),
        ContentBlock(type="text", text="讨论 MECP2 突变可能影响神经系统发育。"),
    ]
    translated_blocks = [
        ContentBlock(type="title", text="Clinical features and MECP2 mutations in children with Rett syndrome"),
        ContentBlock(type="text", text="This study analyzed clinical features and MECP2 mutations in children."),
    ]

    with pytest.raises(TranslationError, match="block_coverage"):
        check_block_coverage(original_blocks, translated_blocks)


def test_check_block_coverage_accepts_complete_translation():
    original_blocks = [
        ContentBlock(type="title", text="Rett 综合征 MECP2 突变分析"),
        ContentBlock(type="text", text="摘要 目的 分析典型 Rett 综合征患者的临床特点。"),
        ContentBlock(type="text", text="方法 对 9 例患儿进行 MECP2 基因检测。"),
        ContentBlock(type="text", text="结果 5 例患儿检出 MECP2 基因突变。"),
        ContentBlock(type="text", text="讨论 TRD 区域突变可能影响语言和发育。"),
    ]
    translated_blocks = [
        ContentBlock(type="title", text="MECP2 mutation analysis in Rett syndrome"),
        ContentBlock(type="text", text="Abstract This study analyzed clinical features in Rett syndrome."),
        ContentBlock(type="text", text="Methods MECP2 sequencing was performed in nine children."),
        ContentBlock(type="text", text="Results Five children carried MECP2 mutations."),
    ]

    check_block_coverage(original_blocks, translated_blocks)


def test_check_block_coverage_skips_short_documents():
    original_blocks = [
        ContentBlock(type="title", text="短文标题"),
        ContentBlock(type="text", text="只有一个正文块。"),
    ]

    check_block_coverage(original_blocks, [])


def test_check_block_coverage_rejects_low_character_coverage():
    original_blocks = [
        ContentBlock(type="title", text="标题" * 20),
        ContentBlock(type="text", text="摘要" * 60),
        ContentBlock(type="text", text="方法" * 60),
        ContentBlock(type="text", text="结果" * 60),
        ContentBlock(type="text", text="讨论" * 60),
    ]
    translated_blocks = [
        ContentBlock(type="title", text="Title"),
        ContentBlock(type="text", text="Aim"),
        ContentBlock(type="text", text="Method"),
        ContentBlock(type="text", text="Result"),
    ]

    with pytest.raises(TranslationError, match="block_coverage"):
        check_block_coverage(original_blocks, translated_blocks)


def test_check_block_coverage_rejects_low_block_coverage_even_with_enough_characters():
    original_blocks = [
        ContentBlock(type="title", text="标题"),
        ContentBlock(type="text", text="摘要"),
        ContentBlock(type="text", text="方法"),
        ContentBlock(type="text", text="结果"),
        ContentBlock(type="text", text="讨论"),
    ]
    translated_blocks = [
        ContentBlock(type="title", text="Title with enough translated characters"),
        ContentBlock(type="text", text="Abstract with enough translated characters"),
    ]

    with pytest.raises(TranslationError, match="block_coverage"):
        check_block_coverage(original_blocks, translated_blocks)


def test_check_block_language_skips_english_and_unknown_sources():
    blocks = [ContentBlock(type="text", text="仍然是中文内容")]

    check_block_language(blocks, "en")
    check_block_language(blocks, "unknown")


def test_check_block_language_accepts_translated_chinese_source():
    blocks = [
        ContentBlock(type="title", text="Clinical features and MECP2 mutations"),
        ContentBlock(type="text", text="Five children carried pathogenic variants."),
        ContentBlock(type="text", text="The parents did not carry the variants."),
    ]

    check_block_language(blocks, "zh")


def test_check_block_language_rejects_mostly_untranslated_chinese_blocks():
    blocks = [
        ContentBlock(type="title", text="Clinical features and MECP2 mutations"),
        ContentBlock(type="text", text="摘要 目的 分析临床特点。"),
        ContentBlock(type="text", text="结果 发现 MECP2 突变。"),
        ContentBlock(type="text", text="The parents did not carry the variants."),
    ]

    with pytest.raises(TranslationError, match="per_block_check"):
        check_block_language(blocks, "zh")


def test_trim_repetitive_content_removes_repeated_heading_blocks():
    text = "\n\n".join(
        [
            "# Abstract",
            "The study analyzed MECP2 mutations.",
            "# Results",
            "Five children carried variants.",
            "# Results",
            "Five children carried variants again.",
            "# Discussion",
            "The variants may affect development.",
        ]
    )

    result = trim_repetitive_content(text)

    assert result.count("# Results") == 1
    assert "Five children carried variants again" not in result
    assert "# Discussion" in result


def test_trim_repetitive_content_keeps_non_repetitive_text_unchanged():
    text = "# Abstract\n\nThe study analyzed MECP2 mutations.\n\n# Results\n\nFive children carried variants."

    assert trim_repetitive_content(text) == text


def test_deduplicate_bilingual_blocks_removes_adjacent_near_duplicates():
    blocks = [
        ContentBlock(type="text", text="MECP2 mutations were detected in five children."),
        ContentBlock(type="text", text="MECP2 mutations were detected in five children and patients."),
        ContentBlock(type="text", text="The parents did not carry these variants."),
    ]

    result = deduplicate_bilingual_blocks(blocks)

    assert len(result) == 2
    assert result[0].text == "MECP2 mutations were detected in five children and patients."
    assert result[1].text == "The parents did not carry these variants."


def test_deduplicate_bilingual_blocks_preserves_distinct_adjacent_blocks():
    blocks = [
        ContentBlock(type="text", text="MECP2 mutations were detected in five children."),
        ContentBlock(type="text", text="The parents did not carry these variants."),
    ]

    assert deduplicate_bilingual_blocks(blocks) == blocks


def test_flag_quality_issues_marks_suspicious_translation_artifacts():
    blocks = [
        ContentBlock(type="text", text="et al. [12] reported a similar patient."),
        ContentBlock(type="text", text="In 20, the assay was repeated, including that, in controls."),
        ContentBlock(type="text", text="This block is clear."),
    ]

    flagged = flag_quality_issues(blocks)

    assert flagged == 2
    assert blocks[0].needs_manual_review is True
    assert "truncated reference" in blocks[0].review_reason
    assert blocks[1].needs_manual_review is True
    assert "truncated year" in blocks[1].review_reason
    assert "ambiguous pronoun" in blocks[1].review_reason
    assert blocks[2].needs_manual_review is False


# ── _parse_terminology tests ─────────────────────────────────────────


def test_parse_terminology_valid():
    raw = "基因:gene\n变异:variant\n蛋白质:protein"
    result = MultiStageTranslator._parse_terminology(raw)
    assert result == {"基因": "gene", "变异": "variant", "蛋白质": "protein"}


def test_parse_terminology_skips_ascii_only_lines():
    raw = "Note: this is important\n基因:gene"
    # For CJK source languages, ASCII-only source terms are filtered
    result = MultiStageTranslator._parse_terminology(raw, source_language="zh")
    assert result == {"基因": "gene"}


def test_parse_terminology_accepts_ascii_for_latin_script():
    raw = "cancer:mama\nsíntoma:symptom"
    # For Latin-script source languages, ASCII source terms are accepted
    result = MultiStageTranslator._parse_terminology(raw, source_language="es")
    assert "cancer" in result
    assert result["cancer"] == "mama"


def test_parse_terminology_skips_long_lines():
    raw = "这是一个非常长的术语超过十个字的限制: this is a very long translation that exceeds the ten word limit here"
    result = MultiStageTranslator._parse_terminology(raw)
    assert result == {}


def test_parse_terminology_empty():
    assert MultiStageTranslator._parse_terminology("") == {}


def test_parse_terminology_skips_blank_lines():
    raw = "\n\n基因:gene\n\n"
    result = MultiStageTranslator._parse_terminology(raw)
    assert result == {"基因": "gene"}


# ── _invoke_with_retry tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_invoke_with_retry_success(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    mock_response = MagicMock()
    mock_response.content = "success"
    with patch("langchain_openai.ChatOpenAI.ainvoke", new_callable=AsyncMock, return_value=mock_response):
        result = await invoke_with_retry(t._llm, "test prompt", "test")
        assert result == "success"


@pytest.mark.asyncio
async def test_invoke_with_retry_transient_then_success(mock_ctx):
    import httpx

    t = MultiStageTranslator(ctx=mock_ctx)
    mock_response = MagicMock()
    mock_response.content = "success"
    with patch(
        "langchain_openai.ChatOpenAI.ainvoke",
        new_callable=AsyncMock,
        side_effect=[
            httpx.ConnectError("connection failed"),
            mock_response,
        ],
    ):
        result = await invoke_with_retry(t._llm, "test prompt", "test")
        assert result == "success"


@pytest.mark.asyncio
async def test_invoke_with_retry_non_transient_no_retry(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    with patch("langchain_openai.ChatOpenAI.ainvoke", new_callable=AsyncMock, side_effect=ValueError("bad input")):
        with pytest.raises(ValueError, match="bad input"):
            await invoke_with_retry(t._llm, "test prompt", "test")


@pytest.mark.asyncio
async def test_translate_one_segment_accepts_json_translation_list(mock_ctx):
    """JSON translation field may be a content-block list from some providers."""
    t = MultiStageTranslator(ctx=mock_ctx)
    raw_json = '{"translation": ["This is translated.", {"type": "text", "text": "It is English."}]}'

    with patch(
        "src.core.cross_lingual_translation.translate.translator.invoke_json_with_retry",
        new_callable=AsyncMock,
        return_value=raw_json,
    ):
        result = await t._translate_one_segment(
            "这是需要翻译的中文。",
            "",
            1,
            1,
        )

    assert result == "This is translated.\nIt is English."


@pytest.mark.asyncio
async def test_translate_one_segment_falls_back_when_json_mode_truncates(mock_ctx):
    """JSON mode truncation/parse failures fall back to plain translation."""
    t = MultiStageTranslator(ctx=mock_ctx)

    with (
        patch(
            "src.core.cross_lingual_translation.translate.translator.invoke_json_with_retry",
            new_callable=AsyncMock,
            side_effect=ValueError("Could not parse response content as the length limit was reached"),
        ) as mock_json,
        patch(
            "src.core.cross_lingual_translation.translate.translator.invoke_with_retry",
            new_callable=AsyncMock,
            return_value="This text was translated successfully.",
        ) as mock_plain,
    ):
        result = await t._translate_one_segment(
            "这是需要翻译的中文。",
            "",
            1,
            1,
        )

    assert result == "This text was translated successfully."
    mock_json.assert_awaited_once()
    mock_plain.assert_awaited_once()


@pytest.mark.asyncio
async def test_translate_one_segment_falls_back_when_json_provider_raises(mock_ctx):
    """Provider-side JSON parsing exceptions fall back to plain translation."""
    t = MultiStageTranslator(ctx=mock_ctx)

    with (
        patch(
            "src.core.cross_lingual_translation.translate.translator.invoke_json_with_retry",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Could not parse response content as the length limit was reached"),
        ) as mock_json,
        patch(
            "src.core.cross_lingual_translation.translate.translator.invoke_with_retry",
            new_callable=AsyncMock,
            return_value="This text was translated successfully.",
        ) as mock_plain,
    ):
        result = await t._translate_one_segment(
            "这是需要翻译的中文。",
            "",
            1,
            1,
        )

    assert result == "This text was translated successfully."
    mock_json.assert_awaited_once()
    mock_plain.assert_awaited_once()


# ── _build_translated_blocks tests ────────────────────────────────────

_SEP = _BLOCK_SEP


def test_build_translated_blocks_empty():
    segments = []
    result = build_translated_blocks([], segments, "")
    assert result == []


def test_build_translated_blocks_delimiter_split():
    original = [
        ContentBlock(type="title", text="Title", page_idx=0, bbox=[0, 0, 100, 20]),
        ContentBlock(type="text", text="Body text", page_idx=0),
    ]
    translated = f"Título{_SEP}Texto del cuerpo"
    result = build_translated_blocks(
        original,
        [],
        translated,
        text_block_indices=[0, 1],
    )

    assert len(result) == 2
    assert result[0].type == "title"
    assert result[0].text == "Título"
    assert result[0].page_idx == 0
    assert result[0].bbox == [0, 0, 100, 20]
    assert result[1].type == "text"
    assert result[1].text == "Texto del cuerpo"


def test_build_translated_blocks_title_preserves_level():
    original = [ContentBlock(type="title", text="Chapter 1", text_level=1, page_idx=0)]
    translated = "Capítulo 1"
    result = build_translated_blocks(original, [], translated)

    assert result[0].type == "title"
    assert result[0].text == "Capítulo 1"
    assert result[0].text_level == 1


def test_build_translated_blocks_image_copied_as_is():
    original = [
        ContentBlock(
            type="image",
            img_path="images/fig1.jpg",
            content="A diagram",
            image_caption=["Figure 1"],
            image_footnote=["Source: X"],
            sub_type="photo",
            page_idx=1,
        )
    ]
    result = build_translated_blocks(original, [], "some text")

    assert len(result) == 1
    assert result[0].type == "image"
    assert result[0].img_path == "images/fig1.jpg"
    assert result[0].content == "A diagram"
    assert result[0].image_caption == ["Figure 1"]
    assert result[0].image_footnote == ["Source: X"]
    assert result[0].sub_type == "photo"
    assert result[0].page_idx == 1


def test_build_translated_blocks_table_copied_as_is():
    original = [
        ContentBlock(
            type="table",
            table_body="<table><tr><td>1</td></tr></table>",
            table_caption=["Table 1"],
            table_footnote=["* p<0.05"],
            page_idx=2,
        )
    ]
    result = build_translated_blocks(original, [], "some text")

    assert result[0].type == "table"
    assert result[0].table_body == "<table><tr><td>1</td></tr></table>"
    assert result[0].table_caption == ["Table 1"]
    assert result[0].table_footnote == ["* p<0.05"]


def test_build_translated_blocks_mixed_types():
    original = [
        ContentBlock(type="title", text="Title", text_level=1, page_idx=0),
        ContentBlock(type="text", text="Body text", page_idx=0),
        ContentBlock(type="image", img_path="images/fig.jpg", page_idx=1),
    ]
    translated = f"Título{_SEP}Texto del cuerpo"
    result = build_translated_blocks(
        original,
        [],
        translated,
        text_block_indices=[0, 1],
    )

    assert len(result) == 3
    assert result[0].text == "Título"
    assert result[1].text == "Texto del cuerpo"
    assert result[2].type == "image"
    assert result[2].img_path == "images/fig.jpg"


def test_build_translated_blocks_fallback_no_delimiter():
    """When delimiter is missing, falls back to segment matching."""
    original = [
        ContentBlock(type="text", text="Hello world", page_idx=0),
    ]
    segments = [
        TranslationSegment(index=0, source_text="Hello world", translated_text="Hola mundo"),
    ]
    result = build_translated_blocks(original, segments, "Hola mundo")

    assert len(result) == 1
    assert result[0].text == "Hola mundo"


def test_build_translated_blocks_preserves_doi_footer():
    """Footer blocks with DOI info must be preserved (not filtered as non-body)."""
    original = [
        ContentBlock(type="title", text="Title", page_idx=0),
        ContentBlock(type="text", text="Body text", page_idx=0),
        ContentBlock(type="footer", text="DOI: 10.1234/example.2024", page_idx=0),
    ]
    translated = f"Translated Title{_BLOCK_SEP}Translated Body"
    result = build_translated_blocks(
        original,
        [],
        translated,
        text_block_indices=[0, 1],
    )
    # Title + Body translated, DOI footer preserved as-is
    assert len(result) == 3
    assert result[0].text == "Translated Title"
    assert result[1].text == "Translated Body"
    assert result[2].type == "footer"
    assert "DOI" in result[2].text
    assert result[2].text == "DOI: 10.1234/example.2024"


def test_translate_segments_includes_doi_footer_blocks():
    """translate_segments must include DOI footer blocks in the marked text.

    Replicates the filtering logic at translator.py:483 to verify that
    DOI footer blocks pass the filter while page-only footers are excluded.
    """
    from src.core.cross_lingual_translation.translate.postprocess import _DOI_RE

    blocks = [
        ContentBlock(type="title", text="Example Paper", page_idx=0),
        ContentBlock(type="text", text="Some body text here", page_idx=0),
        ContentBlock(type="footer", text="DOI: 10.1234/example.2024", page_idx=0),
        ContentBlock(type="footer", text="Page 1 of 10", page_idx=0),
        ContentBlock(type="header", text="Journal Header", page_idx=0),
    ]
    # Replicate the filter from translate_segments (translator.py:483-485)
    non_empty = [
        (i, b)
        for i, b in enumerate(blocks)
        if b.text.strip() and (b.type in ("text", "title") or (b.type == "footer" and _DOI_RE.search(b.text)))
    ]
    indices = [i for i, _ in non_empty]
    # title (0), text (1), DOI footer (2) should be included
    # page-only footer (3) and header (4) should be excluded
    assert 0 in indices  # title
    assert 1 in indices  # text
    assert 2 in indices  # DOI footer
    assert 3 not in indices  # page-only footer
    assert 4 not in indices  # header
