from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
    get_terminology_prompt,
    get_translate_prompt,
    get_format_prompt,
)


def test_terminology_prompt_contains_source():
    prompt = get_terminology_prompt("Some source text about genes.")
    assert "genes" in prompt
    assert "TERMINOLOGY" in prompt.upper() or "terminology" in prompt.lower()


def test_translate_prompt_contains_all_inputs():
    prompt = get_translate_prompt("segment", "term_map")
    assert "segment" in prompt
    assert "term_map" in prompt


def test_translate_prompt_preserves_structure():
    prompt = get_translate_prompt("segment", "terms")
    assert "structure" in prompt.lower() or "heading" in prompt.lower() or "preserve" in prompt.lower()


def test_translate_prompt_preserves_images():
    prompt = get_translate_prompt("segment", "terms")
    assert "image" in prompt.lower() or "![]" in prompt


def test_format_prompt_contains_markdown():
    prompt = get_format_prompt("# Title\n\nSome content.")
    assert "Title" in prompt
    assert "content" in prompt
