"""Tests for LanguageRouter."""

from src.core.cross_lingual_translation.contracts import (
    FormattedDocument,
    PipelineState,
)
from src.core.cross_lingual_translation.router import LanguageRouter


def test_route_english_document():
    """English documents should skip translation."""
    state = PipelineState(
        pages=[],
        formatted=FormattedDocument(
            formatted_markdown="The patient carries a BRCA1 variant.",
            source_language="en",
        ),
    )
    assert LanguageRouter.route(state) == "skip_translate"


def test_route_chinese_document():
    """Non-English documents should be translated."""
    state = PipelineState(
        pages=[],
        formatted=FormattedDocument(
            formatted_markdown="该患者携带BRCA1基因的新变异。",
            source_language="zh",
        ),
    )
    assert LanguageRouter.route(state) == "translate"


def test_route_empty_document():
    """Empty documents should skip translation."""
    state = PipelineState(
        pages=[],
        formatted=FormattedDocument(
            formatted_markdown="",
            source_language="",
        ),
    )
    assert LanguageRouter.route(state) == "skip_translate"


def test_route_no_formatted():
    """Documents without formatted content should skip translation."""
    state = PipelineState(pages=[])
    assert LanguageRouter.route(state) == "skip_translate"
