from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
    get_terminology_prompt,
    get_structure_prompt,
    get_draft_prompt,
    get_polish_prompt,
    get_review_prompt,
    get_format_prompt,
)


def test_terminology_prompt_contains_source():
    prompt = get_terminology_prompt("Some source text about genes.")
    assert "genes" in prompt
    assert "TERMINOLOGY" in prompt.upper() or "terminology" in prompt.lower()


def test_structure_prompt_contains_source():
    prompt = get_structure_prompt("Some source text.")
    assert "Some source text" in prompt


def test_draft_prompt_contains_all_inputs():
    prompt = get_draft_prompt("segment", "term_map", "structure_plan")
    assert "segment" in prompt
    assert "term_map" in prompt
    assert "structure_plan" in prompt


def test_polish_prompt_contains_draft():
    prompt = get_polish_prompt("draft text", "terminology")
    assert "draft text" in prompt


def test_review_prompt_contains_both_texts():
    prompt = get_review_prompt("source", "translated")
    assert "source" in prompt
    assert "translated" in prompt


def test_format_prompt_contains_markdown():
    prompt = get_format_prompt("# Title\n\nSome content.")
    assert "Title" in prompt
    assert "content" in prompt
