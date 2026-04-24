from __future__ import annotations

import pytest

from src.services.translation_validation import (
    reset_translation_artifacts,
    should_skip_translation,
    validate_translation_output,
)


def test_should_skip_translation_rejects_ascii_heavy_cjk_text() -> None:
    text = "NM_000059.4:c.7790G>A 研究显示该变异影响功能。Table 1 shows the assay result."
    assert should_skip_translation(text) is False


def test_should_skip_translation_returns_false_for_non_english_markdown() -> None:
    assert should_skip_translation("## 病例摘要\n\n患者表现为肌无力") is False


def test_reset_translation_artifacts_clears_stage_outputs() -> None:
    state = {
        "translation_required": True,
        "translation_terminology": "term map",
        "translation_structure": "plan",
        "translation_draft": "draft",
        "translation_polished": "polished",
        "translation_review": "review",
        "translation_warnings": ["warning"],
    }

    reset_translation_artifacts(state)

    assert state["translation_required"] is False
    assert state["translation_terminology"] == ""
    assert state["translation_structure"] == ""
    assert state["translation_draft"] == ""
    assert state["translation_polished"] == ""
    assert state["translation_review"] == ""
    assert state["translation_warnings"] == []


def test_validate_translation_output_rejects_untranslated_copy() -> None:
    source = "这是一段需要翻译的中文医学内容。"
    with pytest.raises(ValueError, match="translation_validation_failed"):
        validate_translation_output(source, source)


def test_validate_translation_output_allows_small_cjk_ratio() -> None:
    source = "DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例"
    translated = (
        "A case of Charcot-Marie-Tooth disease type 2 associated with compound "
        "heterozygous mutations in DNAJB2 (张三 et al., 中华医学杂志)"
    )
    validate_translation_output(source, translated)


def test_validate_translation_output_rejects_high_cjk_ratio() -> None:
    source = "DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例"
    translated = "DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例的翻译结果仍然是中文"
    with pytest.raises(ValueError, match="translation_validation_failed"):
        validate_translation_output(source, translated)
