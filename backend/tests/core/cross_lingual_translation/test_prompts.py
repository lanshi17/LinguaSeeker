from src.core.cross_lingual_translation.translate.prompts import (
    get_full_document_translate_prompt,
    get_terminology_prompt,
    get_translate_prompt,
    get_format_prompt,
    get_system_prompt_generation_prompt,
)


def test_terminology_prompt_contains_source():
    prompt = get_terminology_prompt("Some source text about genes.")
    assert "genes" in prompt
    assert "TERMINOLOGY" in prompt.upper() or "terminology" in prompt.lower()


def test_translate_prompt_contains_all_inputs():
    prompt = get_translate_prompt("segment", "term_map")
    assert "segment" in prompt
    assert "term_map" in prompt


def test_system_prompt_gen_includes_structure_and_images():
    meta = get_system_prompt_generation_prompt("# Title\n\n![](img.png)\n\ntext", "zh")
    assert "structure" in meta.lower() or "markdown" in meta.lower()
    assert "image" in meta.lower()


def test_translate_prompt_contains_context():
    prompt = get_translate_prompt("segment", "terms", prev_context="prev", next_context="next")
    assert "PRECEDING CONTEXT" in prompt
    assert "FOLLOWING CONTEXT" in prompt
    assert "segment" in prompt


def test_translation_prompts_are_medical_grade_literal_and_alignment_safe():
    segment_prompt = get_translate_prompt("基因检测提示ABCA3缺陷引起的间质性肺病。", "ABCA3缺陷: ABCA3 deficiency")
    full_prompt = get_full_document_translate_prompt(
        "[BLOCK_1] 基因检测提示ABCA3缺陷引起的间质性肺病。",
        "ABCA3缺陷: ABCA3 deficiency",
    )

    for prompt in (segment_prompt, full_prompt):
        prompt_lower = prompt.lower()
        assert "do not summarize" in prompt_lower
        assert "do not merge" in prompt_lower
        assert "do not omit" in prompt_lower
        assert "rare diseases" in prompt_lower
        assert "genetic mutations" in prompt_lower
        assert "compound modifiers" in prompt_lower
        assert "ABCA3 deficiency" in prompt


def test_format_prompt_contains_markdown():
    prompt = get_format_prompt("# Title\n\nSome content.")
    assert "Title" in prompt
    assert "content" in prompt
