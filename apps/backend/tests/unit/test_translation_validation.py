from __future__ import annotations

import pytest

from src.services.translation_validation import (
    should_skip_translation,
    validate_translation_output,
)


def test_should_skip_translation_rejects_ascii_heavy_cjk_text() -> None:
    text = "NM_000059.4:c.7790G>A 研究显示该变异影响功能。Table 1 shows the assay result."
    assert should_skip_translation(text) is False


def test_validate_translation_output_rejects_untranslated_copy() -> None:
    source = "这是一段需要翻译的中文医学内容。"
    with pytest.raises(ValueError, match="translation_validation_failed"):
        validate_translation_output(source, source)
