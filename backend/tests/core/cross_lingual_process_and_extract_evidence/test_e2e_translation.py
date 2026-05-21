"""E2E tests for translation module systematic bugs.

Catches three classes of regression:
1. [REDACTED] mislabeling — false insertion around English words
2. Document boundary failure — content mixing between articles
3. Product name silent correction — identifiers changed by LLM

Uses real parsed data from: backend/downloads/zh/法布雷病1例.pdf
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
    TranslationSegment,
)
from src.core.cross_lingual_process_and_extract_evidence.config_context import (
    TranslationConfigContext,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.blocks import (
    _BLOCK_SEP,
    join_blocks_with_markers,
    split_by_markers,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import (
    MultiStageTranslator,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator import (
    fix_word_boundary_redacted,
    strip_source_contamination,
    validate_translation_output,
    normalize_placeholders,
    normalize_cjk_punctuation,
    fix_email_placeholder,
    fix_ocr_truncations,
    strip_prompt_artifacts,
    strip_inline_artifacts,
    strip_prompt_echo,
)

# Path to real parsed output from 法布雷病1例.pdf
_REAL_DATA_DIR = Path(__file__).resolve().parents[3] / "output" / "zh" / "法布雷病1例"


def _split_articles_by_page(
    blocks: list[ContentBlock],
    boundary_page: int = 3,
) -> tuple[list[ContentBlock], list[ContentBlock]]:
    """Split blocks into two articles by page boundary.

    In the 法布雷病1例.pdf, Article 1 is on pages 0-2 and
    Article 2 starts on page 3.
    """
    art1 = [b for b in blocks if b.page_idx < boundary_page and b.text.strip()]
    art2 = [b for b in blocks if b.page_idx >= boundary_page and b.text.strip()]
    return art1, art2


def _load_real_blocks() -> tuple[list[ContentBlock], list[ContentBlock]]:
    """Load real blocks from the Fabry disease PDF output.

    Returns:
        (article1_blocks, article2_blocks) — the two articles in this PDF.
        Article 1: Fabry disease (pages 0-2)
        Article 2: NR0B1/DAX-1 adrenal hypoplasia (page 3)
    """
    original_path = _REAL_DATA_DIR / "original.json"
    if not original_path.exists():
        pytest.skip(f"Real data not found: {original_path}")

    with open(original_path) as f:
        data = json.load(f)

    all_blocks = [ContentBlock.from_mineru_block(b) for b in data["blocks"]]
    return _split_articles_by_page(all_blocks)


def _load_translated_blocks() -> tuple[list[ContentBlock], list[ContentBlock]]:
    """Load translated blocks from the Fabry disease PDF output."""
    translated_path = _REAL_DATA_DIR / "translated.json"
    if not translated_path.exists():
        pytest.skip(f"Translated data not found: {translated_path}")

    with open(translated_path) as f:
        data = json.load(f)

    all_blocks = [ContentBlock.from_mineru_block(b) for b in data["blocks"]]
    return _split_articles_by_page(all_blocks)


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_ctx():
    return TranslationConfigContext(
        model="test-model",
        api_key="test-key",
        base_url="http://localhost:8001/v1",
    )


def _make_blocks(texts: list[str], page_idx: int = 0) -> list[ContentBlock]:
    """Create text ContentBlocks from a list of strings."""
    return [
        ContentBlock(type="text", text=t, page_idx=page_idx)
        for t in texts
    ]


def _make_doc(
    markdown: str,
    lang: str = "zh",
    blocks: list[ContentBlock] | None = None,
) -> FormattedDocument:
    return FormattedDocument(
        formatted_markdown=markdown,
        source_language=lang,
        original_blocks=blocks,
    )


# ══════════════════════════════════════════════════════════════════════════
# Bug 1: [REDACTED] mislabeling
# ══════════════════════════════════════════════════════════════════════════


class TestRedactedMislabeling:
    """[REDACTED] must NOT appear inside or adjacent to English words."""

    # ── Unit: fix_word_boundary_redacted ──────────────────────────────────

    def test_mid_word_redacted_removed(self):
        """Re[REDACTED]ferences → References"""
        assert fix_word_boundary_redacted("Re[REDACTED]ferences") == "References"

    def test_mid_word_multiple(self):
        text = "The Re[REDACTED]ferences and Ab[REDACTED]stract are clear."
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" not in result
        assert "References" in result
        assert "Abstract" in result

    def test_adjacent_after_english_word(self):
        """References [REDACTED] — [REDACTED] appended after a heading.

        This pattern occurs when the LLM inserts [REDACTED] after a
        section heading it misinterpreted as containing a missing value.
        """
        text = "References [REDACTED]"
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" not in result
        assert "References" in result

    def test_adjacent_before_english_word(self):
        """[REDACTED] Abstract — [REDACTED] prepended before a heading."""
        text = "[REDACTED] Abstract"
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" not in result
        assert "Abstract" in result

    def test_adjacent_all_heading_words(self):
        """All common section headings must be cleaned of adjacent [REDACTED]."""
        headings = [
            "References", "Abstract", "Introduction", "Background",
            "Methods", "Results", "Discussion", "Conclusion",
            "Acknowledgments", "Keywords",
        ]
        for h in headings:
            after = f"{h} [REDACTED]"
            result = fix_word_boundary_redacted(after)
            assert "[REDACTED]" not in result, f"Failed for: {after}"
            assert h in result, f"Heading lost: {after}"

            before = f"[REDACTED] {h}"
            result = fix_word_boundary_redacted(before)
            assert "[REDACTED]" not in result, f"Failed for: {before}"
            assert h in result, f"Heading lost: {before}"

    def test_legitimate_redacted_preserved(self):
        """Standalone [REDACTED] between CJK must be kept."""
        text = "患者男性，[REDACTED] 岁"
        result = fix_word_boundary_redacted(text)
        assert "[REDACTED]" in result

    def test_redacted_between_numbers_preserved(self):
        """Values like 'In [REDACTED], the onset' must survive."""
        text = "In [REDACTED], the onset was at age [REDACTED]."
        result = fix_word_boundary_redacted(text)
        assert result.count("[REDACTED]") == 2

    # ── Integration: full pipeline post-processing ───────────────────────

    def test_pipeline_strips_false_redacted_from_references(self):
        """run_pipeline output must not contain Re[REDACTED]ferences."""
        source = "## References\n\n1. Smith et al. 2020\n2. Jones et al. 2021"
        translated = (
            "## Re[REDACTED]ferences\n\n1. Smith et al. 2020\n"
            "2. Ab[REDACTED]stract of Jones et al. 2021"
        )
        # Simulate post-processing applied in run_pipeline
        result = fix_word_boundary_redacted(translated)
        assert "References" in result
        assert "Abstract" in result
        assert "[REDACTED]" not in result

    def test_pipeline_preserves_legitimate_redacted(self):
        """Legitimate [REDACTED] markers from source must survive the pipeline."""
        source = "患者男性，[REDACTED] 岁，因水肿入院。"
        translated = "A male patient, aged [REDACTED] years, was admitted for edema."
        # [REDACTED] should survive post-processing
        result = fix_word_boundary_redacted(translated)
        assert "[REDACTED]" in result

    def test_redacted_not_in_output_headings(self):
        """Section headings in translated output must not contain [REDACTED]."""
        headings_to_check = [
            "## Re[REDACTED]ferences",
            "# Ab[REDACTED]stract",
            "## Intro[REDACTED]duction",
            "## Back[REDACTED]ground",
        ]
        for heading in headings_to_check:
            result = fix_word_boundary_redacted(heading)
            assert "[REDACTED]" not in result, f"Failed for: {heading}"


# ══════════════════════════════════════════════════════════════════════════
# Bug 2: Document boundary failure
# ══════════════════════════════════════════════════════════════════════════


class TestDocumentBoundary:
    """Content from one article must NOT leak into another."""

    SEP = _BLOCK_SEP

    def test_split_by_markers_preserves_boundaries(self):
        """_split_by_markers must return per-block content without mixing."""
        marked = (
            "[BLOCK_1] First article title\n\n"
            "First article body text.\n\n"
            "[BLOCK_2] Second article title\n\n"
            "Second article body text."
        )
        parts = split_by_markers(marked, 2)
        assert len(parts) == 2
        assert "First article" in parts[0]
        assert "Second article" in parts[1]
        # Cross-contamination check
        assert "Second article" not in parts[0]
        assert "First article" not in parts[1]

    def test_split_markers_no_mixing_with_many_blocks(self):
        """Multiple blocks must be cleanly separated."""
        blocks = []
        for i in range(5):
            blocks.append(
                f"[BLOCK_{i+1}] Document {i+1} unique content "
                f"with identifier DOC{i+1}_MARKER"
            )
        marked = "\n\n".join(blocks)
        parts = split_by_markers(marked, 5)
        assert len(parts) == 5
        for i, part in enumerate(parts):
            assert f"DOC{i+1}_MARKER" in part
            # Each block must NOT contain other blocks' identifiers
            for j in range(5):
                if j != i:
                    assert f"DOC{j+1}_MARKER" not in part, (
                        f"Block {i+1} contains content from block {j+1}"
                    )

    def test_build_translated_blocks_delimiter_isolation(self):
        """Translated blocks joined by delimiter must split back cleanly."""
        original = [
            ContentBlock(type="title", text="法布雷病1例报告", page_idx=0),
            ContentBlock(type="text", text="患者男性，35岁", page_idx=0),
            ContentBlock(type="title", text="讨论", page_idx=1),
            ContentBlock(type="text", text="法布雷病是一种X连锁遗传病", page_idx=1),
        ]
        translated = (
            f"A Case of Fabry Disease{self.SEP}"
            f"The patient was a 35-year-old male{self.SEP}"
            f"Discussion{self.SEP}"
            f"Fabry disease is an X-linked inherited disorder"
        )
        result = MultiStageTranslator._build_translated_blocks(
            original, [], translated, text_block_indices=[0, 1, 2, 3],
        )
        assert len(result) == 4
        assert "Fabry Disease" in result[0].text
        assert "35-year-old" in result[1].text
        assert "Discussion" in result[2].text
        assert "X-linked" in result[3].text
        # Cross-contamination check
        assert "35-year-old" not in result[2].text
        assert "Discussion" not in result[0].text

    def test_two_documents_no_content_bleeding(self):
        """Two separate documents translated independently must not bleed."""
        # Document 1: Fabry disease case
        doc1_blocks = [
            ContentBlock(type="title", text="法布雷病1例", page_idx=0),
            ContentBlock(type="text", text="患者携带GLA基因变异", page_idx=0),
        ]
        doc1_translated = (
            f"A Case of Fabry Disease{self.SEP}"
            f"The patient carried a GLA gene variant"
        )

        # Document 2: PKU case
        doc2_blocks = [
            ContentBlock(type="title", text="苯丙酮尿症1例", page_idx=0),
            ContentBlock(type="text", text="患者携带PAH基因变异", page_idx=0),
        ]
        doc2_translated = (
            f"A Case of Phenylketonuria{self.SEP}"
            f"The patient carried a PAH gene variant"
        )

        result1 = MultiStageTranslator._build_translated_blocks(
            doc1_blocks, [], doc1_translated, text_block_indices=[0, 1],
        )
        result2 = MultiStageTranslator._build_translated_blocks(
            doc2_blocks, [], doc2_translated, text_block_indices=[0, 1],
        )

        # Doc 1 must not contain Doc 2 content
        assert all("PAH" not in b.text for b in result1)
        assert all("Phenylketonuria" not in b.text for b in result1)
        # Doc 2 must not contain Doc 1 content
        assert all("GLA" not in b.text for b in result2)
        assert all("Fabry" not in b.text for b in result2)

    def test_join_blocks_markers_preserve_order(self):
        """_join_blocks_with_markers must assign sequential [BLOCK_N] markers."""
        blocks = _make_blocks(["Title A", "Body A", "Title B", "Body B"])
        non_empty = list(enumerate(blocks))
        marked, indices, prefixes, overrides = (
            join_blocks_with_markers(non_empty)
        )
        assert "[BLOCK_1]" in marked
        assert "[BLOCK_2]" in marked
        assert "[BLOCK_3]" in marked
        assert "[BLOCK_4]" in marked
        # Order must be preserved
        pos1 = marked.index("[BLOCK_1]")
        pos2 = marked.index("[BLOCK_2]")
        pos3 = marked.index("[BLOCK_3]")
        pos4 = marked.index("[BLOCK_4]")
        assert pos1 < pos2 < pos3 < pos4

    def test_segment_context_does_not_bleed(self):
        """Segments with prev/next context must not mix document content."""
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.segmenter import (
            segment_text,
        )
        # Two paragraphs that are distinct documents
        doc1 = "法布雷病是一种罕见的X连锁遗传病。患者通常在儿童期或青春期出现症状。"
        doc2 = "苯丙酮尿症是一种常染色体隐性遗传病。患者需要终身饮食管理。"
        combined = doc1 + "\n\n" + doc2

        segments = segment_text(combined, max_tokens=200)
        # If split into separate segments, context should be bounded
        if len(segments) > 1:
            for seg in segments:
                # Each segment should be clearly from one document
                has_doc1 = "法布雷病" in seg
                has_doc2 = "苯丙酮尿症" in seg
                # A segment may contain both if they're short enough to merge,
                # but the _CONTEXT_CHARS limit (150 chars) should prevent
                # full document bleeding
                if has_doc1 and has_doc2:
                    # This is OK only if the segment is the full text
                    assert len(segments) == 1


# ══════════════════════════════════════════════════════════════════════════
# Bug 3: Product name silent correction
# ══════════════════════════════════════════════════════════════════════════


class TestProductNamePreservation:
    """Product names, vector names, and identifiers must survive unchanged."""

    # Names that LLMs commonly "correct"
    FRAGILE_NAMES = [
        "pET156",       # LLM "corrects" to pET15b
        "CondonPlus",   # LLM "corrects" to CodonPlus
        "pUC118",       # may get changed to pUC18
        "BL21(DE3)",    # strain designation
        "Rosetta-gami", # may get hyphenated differently
        "pcDNA3.1+",    # may get simplified
        "pGEM-T",       # may get changed
        "Top10",        # may get changed to TOP10
    ]

    def test_product_names_in_prompt_rules(self):
        """Verify product name preservation rules exist in translation prompts."""
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
            get_translate_prompt,
            get_full_document_translate_prompt,
            get_self_review_prompt,
        )
        prompt = get_translate_prompt("test", "")
        full_prompt = get_full_document_translate_prompt("test", "")
        review_prompt = get_self_review_prompt("source", "translated")

        # All prompts must mention product name preservation
        for p in [prompt, full_prompt, review_prompt]:
            assert "pET156" in p, "Product name preservation rule missing"
            assert "CondonPlus" in p, "Product name preservation rule missing"
            assert "silently" in p.lower() or "silent" in p.lower(), (
                "Silent correction warning missing"
            )

    def test_product_names_survive_post_processing(self):
        """Post-processing functions must not alter product names."""
        for name in self.FRAGILE_NAMES:
            text = f"The vector {name} was used for expression."
            # Apply all post-processing steps (same order as run_pipeline)
            result = text
            result = strip_prompt_artifacts(result)
            result = strip_inline_artifacts(result)
            result = normalize_cjk_punctuation(result)
            result = normalize_placeholders(result)
            result = fix_email_placeholder(result)
            result = fix_ocr_truncations(result)
            result = fix_word_boundary_redacted(result)
            assert name in result, (
                f"Post-processing changed product name '{name}' → '{result}'"
            )

    def test_product_names_in_terminology_map(self):
        """Product names must not be filtered by _parse_terminology."""
        # Product names are typically ASCII, so they should appear as
        # targets in the terminology map (source: target pairs)
        raw = "表达载体: pET156\n宿主菌: BL21(DE3)\n诱导剂: IPTG"
        result = MultiStageTranslator._parse_terminology(raw)
        # These have non-ASCII source, ASCII target — should parse
        assert "pET156" in result.values() or any("pET156" in v for v in result.values())

    def test_full_document_translate_prompt_product_rules(self):
        """The full-document prompt must explicitly preserve identifiers."""
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
            get_full_document_translate_prompt,
        )
        prompt = get_full_document_translate_prompt("test content", "terms")
        # Must contain explicit preservation rule
        assert "catalog numbers" in prompt.lower() or "accession" in prompt.lower()
        assert "EXACTLY" in prompt or "exactly" in prompt.lower()

    def test_self_review_prompt_reverts_corrections(self):
        """Self-review must check for and revert product name changes."""
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
            get_self_review_prompt,
        )
        prompt = get_self_review_prompt("source", "translated")
        # Must instruct to revert silent corrections
        assert "pET15b" in prompt, "Self-review must mention reverted name pET15b"
        assert "CodonPlus" in prompt, "Self-review must mention reverted name CodonPlus"
        assert "revert" in prompt.lower() or "match" in prompt.lower()


# ══════════════════════════════════════════════════════════════════════════
# Integration: full pipeline regression
# ══════════════════════════════════════════════════════════════════════════


class TestPipelineRegression:
    """End-to-end regression tests using mock LLM responses."""

    def _mock_invoke_factory(self, response_text: str):
        """Create a mock LLM that returns fixed text."""
        def mock_invoke(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.content = response_text
            return mock_response
        return mock_invoke

    def test_translated_blocks_no_redacted_in_english_headings(self):
        """Translated output must not have [REDACTED] in English section names."""
        # Simulate LLM output that incorrectly inserts [REDACTED]
        bad_output = (
            "## Re[REDACTED]ferences\n\n"
            "1. Smith J. 2020.\n"
            "2. Jones K. 2021.\n\n"
            "## Ab[REDACTED]stract\n\n"
            "This study examines Fabry disease."
        )
        # Apply all fixups
        result = fix_word_boundary_redacted(bad_output)
        assert "References" in result
        assert "Abstract" in result
        # No [REDACTED] should remain in headings
        headings = re.findall(r"^#{1,6}\s+.+", result, re.MULTILINE)
        for h in headings:
            assert "[REDACTED]" not in h, f"False [REDACTED] in heading: {h}"

    def test_two_article_blocks_isolated(self):
        """Two articles' blocks must be isolated after _build_translated_blocks."""
        sep = _BLOCK_SEP
        # Article 1 blocks
        art1 = [
            ContentBlock(type="title", text="法布雷病1例报告", page_idx=0),
            ContentBlock(type="text", text="患者携带GLA基因变异c.644A>G", page_idx=0),
        ]
        # Article 2 blocks
        art2 = [
            ContentBlock(type="title", text="苯丙酮尿症家系分析", page_idx=0),
            ContentBlock(type="text", text="先证者携带PAH基因c.1222C>T", page_idx=0),
        ]

        # Simulate correct LLM output (no cross-contamination)
        art1_translated = (
            f"A Case of Fabry Disease{sep}"
            f"The patient carried a GLA gene variant c.644A>G"
        )
        art2_translated = (
            f"Family Analysis of Phenylketonuria{sep}"
            f"The proband carried a PAH gene c.1222C>T"
        )

        result1 = MultiStageTranslator._build_translated_blocks(
            art1, [], art1_translated, text_block_indices=[0, 1],
        )
        result2 = MultiStageTranslator._build_translated_blocks(
            art2, [], art2_translated, text_block_indices=[0, 1],
        )

        # Verify isolation
        assert "GLA" in result1[1].text
        assert "PAH" not in result1[1].text
        assert "PAH" in result2[1].text
        assert "GLA" not in result2[1].text

    def test_product_name_end_to_end(self):
        """Product names from source must appear unchanged in final output."""
        source_blocks = [
            ContentBlock(
                type="text",
                text="使用pET156载体在CondonPlus宿主菌中表达目的蛋白。",
                page_idx=0,
            ),
        ]
        # Simulate LLM that does NOT change names (correct behavior)
        correct_output = "The target protein was expressed using pET156 vector in CondonPlus host strain."
        result = MultiStageTranslator._build_translated_blocks(
            source_blocks, [], correct_output, text_block_indices=[0],
        )
        assert "pET156" in result[0].text
        assert "CondonPlus" in result[0].text

    def test_product_name_silent_correction_detected(self):
        """If LLM silently corrects names, self-review prompt must catch it."""
        from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
            get_self_review_prompt,
        )
        source = "使用pET156载体在CondonPlus宿主菌中表达。"
        # Simulate LLM that silently "corrected" names
        bad_translation = "The protein was expressed using pET15b vector in CodonPlus host strain."
        prompt = get_self_review_prompt(source, bad_translation)

        # The prompt must explicitly mention the original names and their
        # incorrect corrections so the LLM can revert them
        assert "pET156" in prompt
        assert "pET15b" in prompt
        assert "CondonPlus" in prompt
        assert "CodonPlus" in prompt

    def test_no_repetition_loop_in_output(self):
        """Translated output must not contain repeated heading blocks."""
        # Simulate LLM repetition loop
        repetitive = (
            "## Introduction\n\nFabry disease is rare.\n\n"
            "## Introduction\n\nFabry disease is rare.\n\n"
            "## Introduction\n\nFabry disease is rare.\n\n"
            "## Methods\n\nWe analyzed GLA gene.\n\n"
            "## Methods\n\nWe analyzed GLA gene.\n\n"
        )
        result = MultiStageTranslator._trim_repetitive_content(repetitive)
        headings = re.findall(r"^## Introduction", result, re.MULTILINE)
        assert len(headings) == 1, f"Expected 1 'Introduction', got {len(headings)}"
        headings = re.findall(r"^## Methods", result, re.MULTILINE)
        assert len(headings) == 1, f"Expected 1 'Methods', got {len(headings)}"


# ══════════════════════════════════════════════════════════════════════════
# Real-data tests: 法布雷病1例.pdf
# ══════════════════════════════════════════════════════════════════════════


class TestRealDataFabryPdf:
    """Tests using real parsed data from 法布雷病1例.pdf.

    This PDF contains TWO articles on different pages, making it ideal
    for testing document boundary isolation with real-world content.
    """

    def test_two_articles_detected(self):
        """The PDF must parse into two distinct articles."""
        art1, art2 = _load_real_blocks()
        # Article 1: Fabry disease
        assert any("法布雷病" in b.text for b in art1), (
            "Article 1 should mention Fabry disease"
        )
        # Article 2: NR0B1/DAX-1 adrenal hypoplasia
        assert any("NR0B1" in b.text or "DAX" in b.text for b in art2), (
            "Article 2 should mention NR0B1/DAX-1"
        )

    def test_article1_content_isolation(self):
        """Article 1 translated blocks must not contain Article 2 content."""
        art1_tr, art2_tr = _load_translated_blocks()

        # Fabry article must not contain DAX-1 content
        art1_text = " ".join(b.text for b in art1_tr)
        assert "DAX-1" not in art1_text, "Article 1 contaminated with DAX-1"
        assert "adrenal hypoplasia" not in art1_text.lower(), (
            "Article 1 contaminated with adrenal hypoplasia"
        )

    def test_article2_content_isolation(self):
        """Article 2 translated blocks must not contain Article 1 content."""
        art1_tr, art2_tr = _load_translated_blocks()

        # DAX-1 article must not contain Fabry content
        art2_text = " ".join(b.text for b in art2_tr)
        assert "Fabry" not in art2_text, "Article 2 contaminated with Fabry"
        assert "GLA" not in art2_text, "Article 2 contaminated with GLA gene"

    def test_article1_redacted_markers_valid(self):
        """[REDACTED] in translated Article 1 must be legitimate (not in headings).

        REAL BUG CAUGHT: The translated output contains 'References [REDACTED]'
        which is a false [REDACTED] insertion adjacent to a section heading.
        After fix_word_boundary_redacted is applied in the pipeline, this
        should be stripped. This test verifies the stored output has the issue
        so the pipeline fix can be validated.
        """
        art1_tr, _ = _load_translated_blocks()

        for block in art1_tr:
            text = block.text
            # No [REDACTED] inside English words
            assert "Re[REDACTED]" not in text, (
                f"Mid-word [REDACTED] in block: {text[:80]}"
            )

        # Check for the known bug: "References [REDACTED]" in stored output
        # This should be caught by fix_word_boundary_redacted when applied
        all_art1_text = " ".join(b.text for b in art1_tr)
        if "References [REDACTED]" in all_art1_text:
            # Verify the fix would clean it
            cleaned = fix_word_boundary_redacted(all_art1_text)
            assert "References [REDACTED]" not in cleaned, (
                "fix_word_boundary_redacted failed to clean 'References [REDACTED]'"
            )
            assert "References" in cleaned, "Heading 'References' lost after cleanup"

    def test_article1_preserves_medical_terms(self):
        """Medical terms and gene names must survive translation."""
        art1_tr, _ = _load_translated_blocks()
        art1_text = " ".join(b.text for b in art1_tr)

        # Key terms from the Fabry disease article
        expected_terms = [
            "GLA",           # gene name
            "Fabry",         # disease name
            "p.R227X",       # mutation notation
            "galactosidase", # enzyme name (may be α-galactosidase or alpha-galactosidase)
            "141",           # serum creatinine value
            "204.9",         # troponin I value
        ]
        for term in expected_terms:
            assert term in art1_text, (
                f"Medical term '{term}' missing from translated Article 1"
            )

    def test_article1_preserves_numeric_values(self):
        """Numeric lab values must not be altered or redacted."""
        art1_tr, _ = _load_translated_blocks()
        art1_text = " ".join(b.text for b in art1_tr)

        # These specific values from the abstract must survive
        assert "141" in art1_text, "Serum creatinine value 141 missing"
        assert "47" in art1_text, "eGFR value 47 missing"
        assert "204.9" in art1_text, "Troponin I value 204.9 missing"
        assert "33.82" in art1_text, "Lyso-GL-3 value 33.82 missing"
        assert "59" in art1_text, "LVEF value 59% missing"
        assert "25" in art1_text, "IVS thickness 25 mm missing"

    def test_article1_preserves_author_names(self):
        """Author names must be correctly transliterated."""
        art1_tr, _ = _load_translated_blocks()

        # Find the author block
        author_blocks = [
            b for b in art1_tr
            if "Zhang" in b.text and "Jiang" in b.text
        ]
        assert len(author_blocks) >= 1, "Author names (Zhang, Jiang) not found"
        author_text = author_blocks[0].text
        assert "Shao" in author_text, "Author 'Shao' missing"

    def test_article2_preserves_gene_notation(self):
        """NR0B1 gene notation must survive in Article 2."""
        _, art2_tr = _load_translated_blocks()
        art2_text = " ".join(b.text for b in art2_tr)

        assert "NR0B1" in art2_text, "Gene name NR0B1 missing from Article 2"
        assert "DAX-1" in art2_text, "Gene name DAX-1 missing from Article 2"

    def test_translated_block_count_matches(self):
        """Translated output must preserve the block structure."""
        art1_orig, art2_orig = _load_real_blocks()
        art1_tr, art2_tr = _load_translated_blocks()

        # Non-empty text blocks in original vs translated
        art1_orig_text = [b for b in art1_orig if b.type in ("text", "title")]
        art1_tr_text = [b for b in art1_tr if b.type in ("text", "title")]

        # Translated may have fewer blocks (empty filtered), but structure
        # should be roughly preserved
        assert len(art1_tr_text) >= len(art1_orig_text) * 0.5, (
            f"Too many blocks lost: {len(art1_orig_text)} → {len(art1_tr_text)}"
        )

    def test_no_prompt_artifacts_in_translated(self):
        """Translated output must not contain echoed prompt instructions."""
        art1_tr, art2_tr = _load_translated_blocks()

        prompt_markers = [
            "SYSTEM PROMPT", "CRITICAL RULES", "TERMINOLOGY STAGE",
            "TRANSLATE_STAGE", "Bilingual Terminology Map",
            "Preservation Rules",
        ]
        for block in art1_tr + art2_tr:
            for marker in prompt_markers:
                assert marker not in block.text, (
                    f"Prompt artifact '{marker}' found in: {block.text[:80]}"
                )
