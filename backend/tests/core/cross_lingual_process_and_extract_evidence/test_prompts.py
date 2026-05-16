from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
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


def test_format_prompt_contains_markdown():
    prompt = get_format_prompt("# Title\n\nSome content.")
    assert "Title" in prompt
    assert "content" in prompt
