"""Tests for SourceLocation context_type validation."""

import pytest
from pydantic import ValidationError


def test_source_location_accepts_academic_section_types():
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import SourceLocation

    for section in ("results", "discussion", "methods", "background", "introduction", "conclusion", "abstract"):
        loc = SourceLocation(context_type=section, context_ref="test", text_snippet="test")
        assert loc.context_type == section


def test_source_location_rejects_unknown_type():
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import SourceLocation

    with pytest.raises(ValidationError):
        SourceLocation(context_type="nonexistent_type", context_ref="test", text_snippet="test")
