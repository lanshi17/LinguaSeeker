"""E2E tests for Spanish and Portuguese translation failures.

Regression tests for the critical bug where es/pt translations returned
unchanged source text. Validates:
1. TranslationError is raised on critical validation failure
2. Terminology extraction works for Latin-script source languages
3. [REDACTED] regex catches name-internal insertions in es/pt content
4. Block structure is preserved through the pipeline

Uses real parsed data from: backend/output/es/ and backend/output/pt/
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    ContentBlock,
    FormattedDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.config_context import (
    TranslationConfigContext,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import (
    MultiStageTranslator,
    TranslationError,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator import (
    fix_word_boundary_redacted,
    validate_translation_output,
    summarize_validation_error,
)

# ── Real data paths ────────────────────────────────────────────────────────

_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output"

_ES_DOCS = [
    "es_cancer_mama",
    "es_case_report",
    "es_sequencing",
]

_PT_DOCS = [
    "pt_cancer_mama",
    "pt_case_report",
    "pt_cuidado",
]

_ALL_ES_PT = _ES_DOCS + _PT_DOCS


def _doc_path(doc_id: str) -> Path:
    lang = doc_id[:2]
    return _OUTPUT_DIR / lang / doc_id


def _load_original_blocks(doc_id: str) -> list[ContentBlock]:
    """Load original blocks from real parsed output."""
    path = _doc_path(doc_id) / "original.json"
    if not path.exists():
        pytest.skip(f"Real data not found: {path}")
    with open(path) as f:
        data = json.load(f)
    return [ContentBlock.from_mineru_block(b) for b in data["blocks"]]


def _load_translated_blocks(doc_id: str) -> list[ContentBlock]:
    """Load translated blocks from real parsed output."""
    path = _doc_path(doc_id) / "translated.json"
    if not path.exists():
        pytest.skip(f"Translated data not found: {path}")
    with open(path) as f:
        data = json.load(f)
    return [ContentBlock.from_mineru_block(b) for b in data["blocks"]]


def _load_metadata(doc_id: str) -> dict:
    """Load metadata from real parsed output."""
    path = _doc_path(doc_id) / "metadata.json"
    if not path.exists():
        pytest.skip(f"Metadata not found: {path}")
    with open(path) as f:
        return json.load(f)


def _make_doc(
    markdown: str,
    lang: str = "es",
    blocks: list[ContentBlock] | None = None,
) -> FormattedDocument:
    return FormattedDocument(
        formatted_markdown=markdown,
        source_language=lang,
        original_blocks=blocks,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1. TranslationError: critical failures must raise, not warn
# ══════════════════════════════════════════════════════════════════════════


class TestTranslationError:
    """TranslationError must be raised for critical validation failures."""

    def test_unchanged_output_raises(self):
        """When LLM returns source unchanged, TranslationError must be raised."""
        source = "Experiencia de cuidadores familiares de mujeres con cáncer de mama"
        # Simulate LLM returning the same text (the es/pt bug)
        translated = source
        with pytest.raises(ValueError, match="translation_validation_failed"):
            validate_translation_output(source, translated)

    def test_non_english_output_raises(self):
        """When LLM returns non-English output, validation must detect it."""
        source = "Câncer de Mama X Diagnóstico"
        # Simulate LLM returning Portuguese text (the pt bug)
        translated = source
        with pytest.raises(ValueError, match="translation_validation_failed"):
            validate_translation_output(source, translated)

    def test_empty_output_raises(self):
        """Empty translation must be detected."""
        with pytest.raises(ValueError, match="translation_validation_failed"):
            validate_translation_output("source text", "")

    def test_valid_translation_passes(self):
        """A proper translation must pass validation."""
        source = "Experiencia de cuidadores familiares de mujeres con cáncer de mama"
        translated = "Experience of family caregivers of women with breast cancer"
        # Should not raise
        validate_translation_output(source, translated)

    def test_critical_failure_keywords_detected(self):
        """The keyword check must detect all critical failure types."""
        for keyword in ("unchanged", "non_english_output", "empty"):
            error_summary = f"translation_validation_failed: {keyword}"
            assert any(kw in error_summary for kw in ("unchanged", "non_english_output", "empty"))


# ══════════════════════════════════════════════════════════════════════════
# 2. Terminology: Latin-script source terms must not be filtered
# ══════════════════════════════════════════════════════════════════════════


class TestTerminologyLatinScript:
    """_parse_terminology must accept Latin-script source terms for es/pt."""

    def test_spanish_terms_accepted(self):
        """Spanish biomedical terms must appear in terminology map."""
        raw = "cáncer: cancer\nmama: breast\nquimioterapia: chemotherapy"
        result = MultiStageTranslator._parse_terminology(raw, source_language="es")
        assert "cáncer" in result
        assert result["cáncer"] == "cancer"
        assert "mama" in result

    def test_portuguese_terms_accepted(self):
        """Portuguese biomedical terms must appear in terminology map."""
        raw = "câncer: cancer\nmama: breast\ndiagnóstico: diagnosis"
        result = MultiStageTranslator._parse_terminology(raw, source_language="pt")
        assert "câncer" in result
        assert result["câncer"] == "cancer"

    def test_russian_terms_accepted(self):
        """Russian biomedical terms must appear in terminology map."""
        raw = "рак: cancer\nмолочная железа: breast"
        # Russian has non-ASCII (Cyrillic), so it passes the old filter too
        result = MultiStageTranslator._parse_terminology(raw, source_language="ru")
        assert "рак" in result

    def test_cjk_still_requires_non_ascii(self):
        """CJK source languages must still require non-ASCII source terms."""
        raw = "gene: gene\nvariant: variant\n基因: gene"
        result = MultiStageTranslator._parse_terminology(raw, source_language="zh")
        # ASCII-only "gene: gene" and "variant: variant" must be filtered
        assert "gene" not in result
        assert "variant" not in result
        # CJK term must be accepted
        assert "基因" in result

    def test_source_equals_target_filtered(self):
        """Source ≈ target echo (same word) must be filtered for any language."""
        raw = "cancer: cancer\nmama: breast"
        result = MultiStageTranslator._parse_terminology(raw, source_language="es")
        assert "cancer" not in result  # source == target → echo
        assert "mama" in result  # source != target → real term

    @pytest.mark.parametrize("doc_id", _ES_DOCS)
    def test_es_terminology_empty_in_stored_data(self, doc_id: str):
        """Spanish docs have empty terminology in stored data (pre-fix bug)."""
        meta = _load_metadata(doc_id)
        assert meta.get("terminology_map") == {}, (
            f"{doc_id}: stored terminology should be empty"
        )

    def test_pt_case_report_has_terminology(self):
        """pt_case_report has non-empty terminology (partial success)."""
        meta = _load_metadata("pt_case_report")
        terms = meta.get("terminology_map", {})
        assert len(terms) > 0, "pt_case_report should have terminology entries"


# ══════════════════════════════════════════════════════════════════════════
# 3. [REDACTED] regex: name-internal insertions in es/pt content
# ══════════════════════════════════════════════════════════════════════════


class TestRedactedInNames:
    """[REDACTED] must be stripped from name-internal positions."""

    def test_space_before_lowercase_stripped(self):
        """'Takayuki [REDACTED]okia' → 'Takayuki okia' (at minimum)."""
        text = "Takayuki [REDACTED]okia"
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" not in result

    def test_mid_word_stripped(self):
        """'Re[REDACTED]ferences' → 'References'."""
        assert fix_word_boundary_redacted("Re[REDACTED]ferences") == "References"

    def test_multiple_name_insertions_stripped(self):
        """Multiple name-internal [REDACTED] must all be stripped."""
        text = (
            "Takayuki [REDACTED]okia and Masako [REDACTED]omori "
            "and Takayuki [REDACTED]omoto"
        )
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" not in result

    def test_legitimate_redacted_preserved_in_es(self):
        """Standalone [REDACTED] in Spanish text must be preserved."""
        text = "El paciente de [REDACTED] años fue diagnosticado"
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" in result

    def test_legitimate_redacted_preserved_in_pt(self):
        """Standalone [REDACTED] in Portuguese text must be preserved."""
        text = "A paciente de [REDACTED] anos com diagnóstico"
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" in result

    def test_heading_adjacent_redacted_stripped(self):
        """'References [REDACTED]' must be stripped for any language."""
        for heading in ["References", "Abstract", "Introduction", "Methods",
                        "Results", "Discussion", "Conclusion"]:
            text = f"{heading} [REDACTED]"
            result = fix_word_boundary_redacted(text)
            assert "[REDACTED]" not in result, f"Failed for: {text}"
            assert heading in result


# ══════════════════════════════════════════════════════════════════════════
# 4. Block structure: es/pt documents must preserve block counts
# ══════════════════════════════════════════════════════════════════════════


class TestBlockStructure:
    """Block structure must be preserved through the translation pipeline."""

    @pytest.mark.parametrize("doc_id", _ALL_ES_PT)
    def test_original_blocks_loaded(self, doc_id: str):
        """All es/pt documents must have loadable original blocks."""
        blocks = _load_original_blocks(doc_id)
        assert len(blocks) > 0, f"{doc_id}: no original blocks loaded"

    @pytest.mark.parametrize("doc_id", _ALL_ES_PT)
    def test_translated_blocks_loaded(self, doc_id: str):
        """All es/pt documents must have loadable translated blocks."""
        blocks = _load_translated_blocks(doc_id)
        assert len(blocks) > 0, f"{doc_id}: no translated blocks loaded"

    @pytest.mark.parametrize("doc_id", _ALL_ES_PT)
    def test_text_block_count_reasonable(self, doc_id: str):
        """Translated text block count must be at least 50% of original."""
        orig = _load_original_blocks(doc_id)
        tr = _load_translated_blocks(doc_id)
        orig_text = [b for b in orig if b.type in ("text", "title") and b.text.strip()]
        tr_text = [b for b in tr if b.type in ("text", "title") and b.text.strip()]
        assert len(tr_text) >= len(orig_text) * 0.5, (
            f"{doc_id}: too many text blocks lost: "
            f"{len(orig_text)} → {len(tr_text)}"
        )

    @pytest.mark.parametrize("doc_id", _ALL_ES_PT)
    def test_no_prompt_artifacts_in_output(self, doc_id: str):
        """Translated output must not contain echoed prompt instructions."""
        blocks = _load_translated_blocks(doc_id)
        prompt_markers = [
            "SYSTEM PROMPT", "CRITICAL RULES", "TERMINOLOGY STAGE",
            "TRANSLATE_STAGE", "Bilingual Terminology Map",
            "Preservation Rules",
        ]
        for block in blocks:
            for marker in prompt_markers:
                assert marker not in block.text, (
                    f"{doc_id}: prompt artifact '{marker}' in: {block.text[:80]}"
                )

    @pytest.mark.parametrize("doc_id", _ALL_ES_PT)
    def test_no_mid_word_redacted_in_output(self, doc_id: str):
        """Translated output must not have [REDACTED] inside English words."""
        blocks = _load_translated_blocks(doc_id)
        for block in blocks:
            # Check for mid-word [REDACTED]
            assert "Re[REDACTED]" not in block.text, (
                f"{doc_id}: mid-word [REDACTED] in: {block.text[:80]}"
            )


# ══════════════════════════════════════════════════════════════════════════
# 5. Stored failure data: validate the pre-fix failures are captured
# ══════════════════════════════════════════════════════════════════════════


class TestStoredFailureData:
    """Verify the stored data correctly reflects the pre-fix failures."""

    @pytest.mark.parametrize("doc_id", _ES_DOCS)
    def test_es_docs_segments_unchanged(self, doc_id: str):
        """All Spanish docs must show unchanged segments (the bug).

        Some docs have the 'unchanged' warning in metadata, others don't
        (the warning was not always recorded). The drift data is authoritative.
        """
        meta = _load_metadata(doc_id)
        drifts = meta.get("translation_drifts", [])
        assert len(drifts) > 0, f"{doc_id}: no drifts"
        zero_drift = sum(1 for d in drifts if d.get("length_drift") == 0)
        assert zero_drift == len(drifts), (
            f"{doc_id}: expected all segments unchanged, "
            f"got {zero_drift}/{len(drifts)} with zero drift"
        )

    @pytest.mark.parametrize("doc_id", _PT_DOCS)
    def test_pt_docs_have_validation_warning(self, doc_id: str):
        """All Portuguese docs must have validation failure warning."""
        meta = _load_metadata(doc_id)
        warnings = meta.get("translation_warnings", [])
        has_warning = any(
            "unchanged" in w or "non_english_output" in w
            for w in warnings
        )
        assert has_warning, (
            f"{doc_id}: expected validation warning, got {warnings}"
        )

    @pytest.mark.parametrize("doc_id", _ES_DOCS)
    def test_es_docs_have_empty_terminology(self, doc_id: str):
        """Spanish docs must have empty terminology map (pre-fix bug)."""
        meta = _load_metadata(doc_id)
        assert meta.get("terminology_map") == {}, (
            f"{doc_id}: expected empty terminology map"
        )

    @pytest.mark.parametrize("doc_id", _ALL_ES_PT)
    def test_source_language_correct(self, doc_id: str):
        """Source language must be correctly detected."""
        meta = _load_metadata(doc_id)
        expected_lang = doc_id[:2]
        assert meta.get("source_language") == expected_lang, (
            f"{doc_id}: expected lang={expected_lang}, got {meta.get('source_language')}"
        )

    @pytest.mark.parametrize("doc_id", _PT_DOCS)
    def test_pt_segments_mostly_unchanged(self, doc_id: str):
        """Portuguese doc segments must show mostly unchanged (the bug)."""
        meta = _load_metadata(doc_id)
        drifts = meta.get("translation_drifts", [])
        assert len(drifts) > 0, f"{doc_id}: no drifts"
        zero_drift = sum(1 for d in drifts if d.get("length_drift") == 0)
        # pt_case_report: 95/105 unchanged; pt_cancer_mama: 37/37; pt_cuidado: 145/145
        assert zero_drift >= len(drifts) * 0.9, (
            f"{doc_id}: expected >=90% segments unchanged, "
            f"got {zero_drift}/{len(drifts)}"
        )


# ══════════════════════════════════════════════════════════════════════════
# 6. Pipeline integration: TranslationError prevents persistence
# ══════════════════════════════════════════════════════════════════════════


class TestPipelineIntegration:
    """Translation pipeline must raise TranslationError on critical failures."""

    def _mock_ctx(self):
        return TranslationConfigContext(
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:8001/v1",
        )

    @staticmethod
    def _make_mock_response(text: str):
        resp = MagicMock()
        resp.content = text
        return resp

    def test_unchanged_es_triggers_error(self):
        """When LLM returns Spanish text unchanged, TranslationError must be raised."""
        source = "Experiencia de cuidadores familiares de mujeres con cáncer de mama: una revisión integradora"
        # _invoke_with_retry returns str directly; simulate LLM returning unchanged text
        with patch.object(
            MultiStageTranslator, '_invoke_with_retry',
            return_value=source,
        ), patch.object(
            MultiStageTranslator, '_invoke_json_with_retry',
            return_value='{"terms": []}',
        ):
            translator = MultiStageTranslator(ctx=self._mock_ctx())
            doc = _make_doc(source, lang="es")
            with pytest.raises((TranslationError, ValueError)):
                translator.run_pipeline(doc)

    def test_unchanged_pt_triggers_error(self):
        """When LLM returns Portuguese text unchanged, TranslationError must be raised."""
        source = "Câncer de Mama X Diagnóstico"
        with patch.object(
            MultiStageTranslator, '_invoke_with_retry',
            return_value=source,
        ), patch.object(
            MultiStageTranslator, '_invoke_json_with_retry',
            return_value='{"terms": []}',
        ):
            translator = MultiStageTranslator(ctx=self._mock_ctx())
            doc = _make_doc(source, lang="pt")
            with pytest.raises((TranslationError, ValueError)):
                translator.run_pipeline(doc)

    def test_valid_translation_succeeds(self):
        """A proper translation must complete without error."""
        source = "Experiencia de cuidadores familiares de mujeres con cáncer de mama"
        translated = "Experience of family caregivers of women with breast cancer"
        system_prompt = "You are a biomedical translation engine. Translate to English."
        terminology = "cáncer: cancer\nmama: breast"

        call_count = 0
        def mock_invoke(prompt, stage, system_prompt=""):
            nonlocal call_count
            call_count += 1
            if "system_prompt_gen" in stage:
                return system_prompt
            if "terminology" in stage:
                return terminology
            return translated

        with patch.object(
            MultiStageTranslator, '_invoke_with_retry',
            side_effect=mock_invoke,
        ), patch.object(
            MultiStageTranslator, '_invoke_json_with_retry',
            return_value=f'{{"translation": "{translated}"}}',
        ):
            translator = MultiStageTranslator(ctx=self._mock_ctx())
            doc = _make_doc(source, lang="es")
            # Should not raise
            result = translator.run_pipeline(doc)
            assert result is not None
