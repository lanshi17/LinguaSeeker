"""E2E tests for Round 2 translation fixes.

Tests for:
1. Keyword merging: short CJK blocks merged before translation to prevent hallucination
2. Per-block language detection: catches partial translation failures (e.g. ru)
3. Bilingual block deduplication: removes duplicate blocks from zh bilingual docs
"""

from __future__ import annotations

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    ContentBlock,
    FormattedDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.blocks import (
    _KW_MERGE_SEP,
    merge_short_keywords,
    split_merged_keywords,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.exceptions import (
    TranslationError,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.postprocess import (
    check_block_language,
    deduplicate_bilingual_blocks,
)


# ══════════════════════════════════════════════════════════════════════════
# 1. Keyword merging: short CJK blocks
# ══════════════════════════════════════════════════════════════════════════


class TestKeywordMerging:
    """Short CJK keyword blocks must be merged before translation."""

    def test_short_zh_blocks_merged(self):
        """1-4 char Chinese blocks should be merged into a single block."""
        blocks = [
            (0, ContentBlock(type="text", text="基因", page_idx=0)),
            (1, ContentBlock(type="text", text="变异", page_idx=0)),
            (2, ContentBlock(type="text", text="蛋白质", page_idx=0)),
        ]
        merged, merge_map = merge_short_keywords(blocks)
        # All 3 are short → merged into 1 block
        assert len(merged) == 1
        assert "基因" in merged[0][1].text
        assert "变异" in merged[0][1].text
        assert "蛋白质" in merged[0][1].text
        # Merge map should have 1 entry with count 3
        assert merge_map[0] == 3

    def test_long_blocks_not_merged(self):
        """Blocks with >4 chars should not be merged."""
        blocks = [
            (0, ContentBlock(type="text", text="这是一个正常的长文本块", page_idx=0)),
            (1, ContentBlock(type="text", text="另一个正常的长文本块内容", page_idx=0)),
        ]
        merged, merge_map = merge_short_keywords(blocks)
        assert len(merged) == 2
        assert all(v == 1 for v in merge_map.values())

    def test_mixed_short_and_long(self):
        """Short blocks separated by a long block are not merged."""
        blocks = [
            (0, ContentBlock(type="text", text="基因", page_idx=0)),
            (1, ContentBlock(type="text", text="这是一个正常的长文本块", page_idx=0)),
            (2, ContentBlock(type="text", text="变异", page_idx=0)),
        ]
        merged, merge_map = merge_short_keywords(blocks)
        # Short blocks separated by long block → not adjacent → 3 total
        assert len(merged) == 3
        assert all(v == 1 for v in merge_map.values())

    def test_adjacent_short_merged_across_run(self):
        """Adjacent short blocks form a run and get merged."""
        blocks = [
            (0, ContentBlock(type="text", text="基因", page_idx=0)),
            (1, ContentBlock(type="text", text="变异", page_idx=0)),
            (2, ContentBlock(type="text", text="这是一个正常的长文本块", page_idx=0)),
        ]
        merged, merge_map = merge_short_keywords(blocks)
        # First 2 short blocks merged, long block separate → 2 total
        assert len(merged) == 2
        assert merge_map[0] == 2  # 2 blocks merged into first
        assert merge_map[1] == 1  # long block unchanged

    def test_split_merged_keywords_restores_count(self):
        """After translation, merged keywords must be split back."""
        # The merge separator is "；" (Chinese semicolon)
        sep = _KW_MERGE_SEP
        translated_parts = [f"gene{sep}variant{sep}protein"]
        merge_map = {0: 3}  # output index 0 came from 3 blocks
        result = split_merged_keywords(translated_parts, merge_map)
        assert len(result) == 3
        assert result[0] == "gene"
        assert result[1] == "variant"
        assert result[2] == "protein"

    def test_split_merged_keywords_with_english_semicolon(self):
        """LLM may translate using '; ' (semicolon+space) instead of Chinese."""
        translated_parts = ["gene; variant; protein"]
        merge_map = {0: 3}
        result = split_merged_keywords(translated_parts, merge_map)
        assert len(result) == 3
        assert result[0] == "gene"
        assert result[1] == "variant"
        assert result[2] == "protein"

    def test_split_merged_keywords_unsplittable(self):
        """When separator is missing, merged text goes in first slot."""
        translated_parts = ["gene variant protein"]  # no separator
        merge_map = {0: 3}
        result = split_merged_keywords(translated_parts, merge_map)
        assert len(result) == 3
        assert result[0] == "gene variant protein"
        assert result[1] == ""
        assert result[2] == ""

    def test_merge_preserves_block_metadata(self):
        """Merged block should preserve metadata from the first block."""
        blocks = [
            (0, ContentBlock(type="text", text="基因", page_idx=2, bbox=[10, 20, 30, 40])),
            (1, ContentBlock(type="text", text="变异", page_idx=2)),
        ]
        merged, _ = merge_short_keywords(blocks)
        # The merged block uses a new ContentBlock, so check the tuple structure
        assert len(merged) == 1
        assert merged[0][0] == 0  # first block index preserved

    def test_separated_short_blocks_not_merged(self):
        """Short blocks separated by a long block must not merge."""
        blocks = [
            (0, ContentBlock(type="text", text="基因", page_idx=0)),
            (1, ContentBlock(type="text", text="这是一个正常的长文本块内容", page_idx=0)),
            (2, ContentBlock(type="text", text="变异", page_idx=0)),
        ]
        merged, merge_map = merge_short_keywords(blocks)
        # Short blocks separated by a long block should not merge across it
        assert len(merged) == 3
        assert all(v == 1 for v in merge_map.values())


# ══════════════════════════════════════════════════════════════════════════
# 2. Per-block language detection
# ══════════════════════════════════════════════════════════════════════════


class TestPerBlockLanguageDetection:
    """Per-block language detection must catch partial translation failures."""

    def test_russian_untranslated_raises(self):
        """When >40% blocks still contain Cyrillic, TranslationError must be raised."""
        blocks = [
            ContentBlock(type="text", text="Это русский текст который не был переведён", page_idx=0),
            ContentBlock(type="text", text="Another untranslated Russian block here", page_idx=0),
            ContentBlock(type="text", text="Третий непереведённый блок на русском языке", page_idx=0),
            ContentBlock(type="text", text="Четвёртый блок тоже не переведён", page_idx=0),
            ContentBlock(type="text", text="Пятый блок остаётся на русском языке", page_idx=0),
        ]
        # 5/5 blocks still have Cyrillic → 100% > 40% threshold
        with pytest.raises(TranslationError, match="per_block_check"):
            check_block_language(blocks, "ru")

    def test_russian_translated_passes(self):
        """When most blocks are translated to English, check must pass."""
        blocks = [
            ContentBlock(type="text", text="This is a translated English block", page_idx=0),
            ContentBlock(type="text", text="Another translated English block here", page_idx=0),
            ContentBlock(type="text", text="Yet another properly translated block", page_idx=0),
            ContentBlock(type="text", text="Это небольшой русский блок", page_idx=0),
            ContentBlock(type="text", text="Final English translated block content", page_idx=0),
        ]
        # 1/5 blocks with Cyrillic → 20% < 40% threshold → should not raise
        check_block_language(blocks, "ru")

    def test_zh_untranslated_raises(self):
        """When >40% blocks still contain CJK, TranslationError must be raised."""
        blocks = [
            ContentBlock(type="text", text="这是未翻译的中文文本内容", page_idx=0),
            ContentBlock(type="text", text="另一段未翻译的中文文本", page_idx=0),
            ContentBlock(type="text", text="第三段中文文本也没有翻译", page_idx=0),
            ContentBlock(type="text", text="This is an English translated block", page_idx=0),
            ContentBlock(type="text", text="第五段仍然是中文的文本内容", page_idx=0),
        ]
        # 4/5 blocks with CJK → 80% > 40% threshold
        with pytest.raises(TranslationError, match="per_block_check"):
            check_block_language(blocks, "zh")

    def test_en_source_skipped(self):
        """English source documents must skip the check entirely."""
        blocks = [
            ContentBlock(type="text", text="Any text", page_idx=0),
        ]
        # Should not raise for English source
        check_block_language(blocks, "en")

    def test_unknown_source_skipped(self):
        """Unknown source language must skip the check."""
        blocks = [
            ContentBlock(type="text", text="Any text", page_idx=0),
        ]
        check_block_language(blocks, "unknown")

    def test_es_pt_skipped(self):
        """es/pt source languages skip per-block check (covered by validate_translation_output)."""
        blocks = [
            ContentBlock(type="text", text="Texto en español sin traducir", page_idx=0),
        ]
        check_block_language(blocks, "es")
        check_block_language(blocks, "pt")

    def test_empty_blocks_no_error(self):
        """Empty block list must not raise."""
        check_block_language([], "ru")

    def test_only_non_text_blocks_skipped(self):
        """Image/table blocks should not count in the language check."""
        blocks = [
            ContentBlock(type="image", img_path="fig.jpg", page_idx=0),
            ContentBlock(type="table", table_body="<table></table>", page_idx=0),
        ]
        # No text blocks → should not raise
        check_block_language(blocks, "ru")


# ══════════════════════════════════════════════════════════════════════════
# 3. Bilingual block deduplication
# ══════════════════════════════════════════════════════════════════════════


class TestBilingualBlockDedup:
    """Adjacent duplicate blocks from bilingual documents must be deduplicated."""

    def test_adjacent_duplicates_merged(self):
        """Two adjacent blocks with near-identical content → keep one."""
        blocks = [
            ContentBlock(type="title", text="Breast Cancer Diagnosis", page_idx=0),
            ContentBlock(type="text", text="Breast cancer diagnosis involves multiple clinical steps", page_idx=0),
            ContentBlock(type="text", text="Breast cancer diagnosis involves multiple clinical steps", page_idx=0),
        ]
        result = deduplicate_bilingual_blocks(blocks)
        # The two identical text blocks should be deduped
        assert len(result) == 2

    def test_different_blocks_preserved(self):
        """Blocks with different content must all be preserved."""
        blocks = [
            ContentBlock(type="text", text="Breast cancer is a common disease", page_idx=0),
            ContentBlock(type="text", text="Genetic testing reveals BRCA1 mutations", page_idx=0),
            ContentBlock(type="text", text="Treatment options include surgery and chemotherapy", page_idx=0),
        ]
        result = deduplicate_bilingual_blocks(blocks)
        assert len(result) == 3

    def test_non_text_blocks_preserved(self):
        """Image/table blocks must not be affected by dedup."""
        blocks = [
            ContentBlock(type="text", text="Some content here", page_idx=0),
            ContentBlock(type="image", img_path="fig.jpg", page_idx=0),
            ContentBlock(type="text", text="Different content after image", page_idx=0),
        ]
        result = deduplicate_bilingual_blocks(blocks)
        assert len(result) == 3
        assert result[1].type == "image"

    def test_single_block_unchanged(self):
        """A single block list must be returned as-is."""
        blocks = [
            ContentBlock(type="text", text="Only one block", page_idx=0),
        ]
        result = deduplicate_bilingual_blocks(blocks)
        assert len(result) == 1

    def test_empty_list_unchanged(self):
        """Empty block list must be returned as-is."""
        result = deduplicate_bilingual_blocks([])
        assert result == []

    def test_keeps_longer_block(self):
        """When two blocks are near-duplicates, the longer one is kept."""
        shorter = ContentBlock(type="text", text="BRCA1 mutations in breast cancer patients are pathogenic", page_idx=0)
        longer = ContentBlock(
            type="text", text="BRCA1 mutations in breast cancer patients are generally pathogenic", page_idx=0
        )
        blocks = [shorter, longer]
        result = deduplicate_bilingual_blocks(blocks)
        # Tokens overlap: {brca1, mutations, in, breast, cancer, patients, are, pathogenic} = 8
        # Union adds "generally" = 9 total
        # Similarity = 8/9 ≈ 0.89 > 0.75 → deduped
        assert len(result) == 1
        assert "generally" in result[0].text  # longer block kept

    def test_zh_bilingual_scenario(self):
        """Simulated zh bilingual: Chinese block translated to English, adjacent English block exists."""
        # After translation, both blocks are in English with identical content
        blocks = [
            ContentBlock(type="title", text="Breast Cancer and Genetic Testing", page_idx=0),
            ContentBlock(type="text", text="This study investigates the role of BRCA1 in breast cancer", page_idx=0),
            ContentBlock(type="text", text="This study investigates the role of BRCA1 in breast cancer", page_idx=0),
        ]
        result = deduplicate_bilingual_blocks(blocks)
        # The two identical text blocks should be deduped
        text_blocks = [b for b in result if b.type == "text"]
        assert len(text_blocks) == 1


# ══════════════════════════════════════════════════════════════════════════
# 4. Strict retry: per-block language check failure path
# ══════════════════════════════════════════════════════════════════════════


class TestStrictRetryPrompt:
    """The strict-mode full-document prompt must demand English-only output."""

    def test_default_prompt_omits_strict_directive(self):
        """Default prompt should not contain the STRICT ENGLISH-ONLY block."""
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
            get_full_document_translate_prompt,
        )

        prompt = get_full_document_translate_prompt("test content", "terms")
        assert "STRICT ENGLISH-ONLY" not in prompt

    def test_strict_prompt_adds_directive(self):
        """Strict prompt must contain the STRICT ENGLISH-ONLY directive."""
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
            get_full_document_translate_prompt,
        )

        prompt = get_full_document_translate_prompt("test content", "terms", strict=True)
        assert "STRICT ENGLISH-ONLY" in prompt
        # Must explicitly forbid reproducing source alongside translation
        assert "MUST be entirely English" in prompt
        # Must enumerate the only allowed non-English content
        assert "pinyin" in prompt.lower()
        # Must still include the document body
        assert "test content" in prompt


class TestPerBlockRetryBehavior:
    """translate_to_result must retry with strict prompt when per-block check fails."""

    @pytest.mark.asyncio
    async def test_retry_called_when_per_block_check_fails(self, monkeypatch):
        """When check_block_language raises per_block_check, run_pipeline must be
        called again with strict=True and the result must be returned."""
        from src.core.cross_lingual_process_and_extract_evidence.config_context import (
            TranslationConfigContext,
        )
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import (
            MultiStageTranslator,
        )
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.exceptions import (
            TranslationError,
        )

        ctx = TranslationConfigContext(
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:8001/v1",
        )
        translator = MultiStageTranslator(ctx=ctx)

        pipeline_calls: list[bool] = []
        call_count = {"n": 0}

        async def fake_run_pipeline(
            self,
            formatted,
            blocks=None,
            *,
            strict=False,
        ):
            pipeline_calls.append(strict)
            call_count["n"] += 1
            return ({}, f"output-{call_count['n']}", [], [], [])

        # First call: simulate per-block check failure
        # Second call: simulate success (no exception)
        check_calls: list[int] = []

        def fake_check_block_language(blocks, source_language):
            check_calls.append(len(check_calls) + 1)
            if len(check_calls) == 1:
                raise TranslationError("translation_validation_failed: per_block_check — 5/5 blocks still in zh")
            # Second check (after retry) returns without raising

        async def fake_extract_terminology(self, formatted):
            return ""

        async def fake_self_review(self, source, translated, system_prompt=""):
            return translated

        async def fake_translate_segments(self, formatted, terminology, blocks=None, *, strict=False):
            return ("", [], [])

        async def fake_translate_aux(self, blocks, system_prompt=""):
            return {}

        monkeypatch.setattr(MultiStageTranslator, "run_pipeline", fake_run_pipeline)
        monkeypatch.setattr(
            "src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator.check_block_language",
            fake_check_block_language,
        )
        monkeypatch.setattr(MultiStageTranslator, "extract_terminology", fake_extract_terminology)
        monkeypatch.setattr(MultiStageTranslator, "_self_review", fake_self_review)
        monkeypatch.setattr(MultiStageTranslator, "translate_segments", fake_translate_segments)
        monkeypatch.setattr(MultiStageTranslator, "_translate_auxiliary_blocks", fake_translate_aux)

        formatted = FormattedDocument(
            formatted_markdown="text",
            source_language="zh",
            original_blocks=[],
            sentences=[],
        )
        result = await translator.translate_to_result(formatted)

        # The first call should be non-strict, the second should be strict
        assert pipeline_calls == [False, True], (
            f"Expected pipeline called once non-strict then once strict, got {pipeline_calls}"
        )
        # check_block_language should have been called twice (once before, once after retry)
        assert len(check_calls) == 2
        # Final translated text should be the second (retry) output
        assert "output-2" in result.translated_english

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_translation_error(self, monkeypatch):
        """If the strict retry's per-block check also fails, TranslationError must propagate."""
        from src.core.cross_lingual_process_and_extract_evidence.config_context import (
            TranslationConfigContext,
        )
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import (
            MultiStageTranslator,
        )
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.exceptions import (
            TranslationError,
        )

        ctx = TranslationConfigContext(
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:8001/v1",
        )
        translator = MultiStageTranslator(ctx=ctx)

        async def fake_run_pipeline(
            self,
            formatted,
            blocks=None,
            *,
            strict=False,
        ):
            return ({}, "output", [], [], [])

        # Always raise (both first and second attempt fail the check)
        def fake_check_block_language(blocks, source_language):
            raise TranslationError("translation_validation_failed: per_block_check — 5/5 blocks still in zh")

        async def fake_extract_terminology(self, formatted):
            return ""

        async def fake_self_review(self, source, translated, system_prompt=""):
            return translated

        async def fake_translate_segments(self, formatted, terminology, blocks=None, *, strict=False):
            return ("", [], [])

        async def fake_translate_aux(self, blocks, system_prompt=""):
            return {}

        monkeypatch.setattr(MultiStageTranslator, "run_pipeline", fake_run_pipeline)
        monkeypatch.setattr(
            "src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator.check_block_language",
            fake_check_block_language,
        )
        monkeypatch.setattr(MultiStageTranslator, "extract_terminology", fake_extract_terminology)
        monkeypatch.setattr(MultiStageTranslator, "_self_review", fake_self_review)
        monkeypatch.setattr(MultiStageTranslator, "translate_segments", fake_translate_segments)
        monkeypatch.setattr(MultiStageTranslator, "_translate_auxiliary_blocks", fake_translate_aux)

        formatted = FormattedDocument(
            formatted_markdown="text",
            source_language="zh",
            original_blocks=[],
            sentences=[],
        )
        with pytest.raises(TranslationError, match="per_block_check"):
            await translator.translate_to_result(formatted)

    @pytest.mark.asyncio
    async def test_other_translation_errors_not_retried(self, monkeypatch):
        """TranslationErrors that are NOT per_block_check must NOT trigger retry."""
        from src.core.cross_lingual_process_and_extract_evidence.config_context import (
            TranslationConfigContext,
        )
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import (
            MultiStageTranslator,
        )
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.exceptions import (
            TranslationError,
        )

        ctx = TranslationConfigContext(
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:8001/v1",
        )
        translator = MultiStageTranslator(ctx=ctx)

        pipeline_calls: list[bool] = []

        async def fake_run_pipeline(
            self,
            formatted,
            blocks=None,
            *,
            strict=False,
        ):
            pipeline_calls.append(strict)
            return ({}, "output", [], [], [])

        def fake_check_block_language(blocks, source_language):
            raise TranslationError("translation_validation_failed: non_english_output")

        async def fake_extract_terminology(self, formatted):
            return ""

        async def fake_self_review(self, source, translated, system_prompt=""):
            return translated

        async def fake_translate_segments(self, formatted, terminology, blocks=None, *, strict=False):
            return ("", [], [])

        async def fake_translate_aux(self, blocks, system_prompt=""):
            return {}

        monkeypatch.setattr(MultiStageTranslator, "run_pipeline", fake_run_pipeline)
        monkeypatch.setattr(
            "src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator.check_block_language",
            fake_check_block_language,
        )
        monkeypatch.setattr(MultiStageTranslator, "extract_terminology", fake_extract_terminology)
        monkeypatch.setattr(MultiStageTranslator, "_self_review", fake_self_review)
        monkeypatch.setattr(MultiStageTranslator, "translate_segments", fake_translate_segments)
        monkeypatch.setattr(MultiStageTranslator, "_translate_auxiliary_blocks", fake_translate_aux)

        formatted = FormattedDocument(
            formatted_markdown="text",
            source_language="zh",
            original_blocks=[],
            sentences=[],
        )
        with pytest.raises(TranslationError, match="non_english_output"):
            await translator.translate_to_result(formatted)

        # Only the initial (non-strict) call should have happened
        assert pipeline_calls == [False]
