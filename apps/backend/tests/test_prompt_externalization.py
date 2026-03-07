from __future__ import annotations

from pathlib import Path

from src.domain.agent import prompts


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src/knowledge/prompts"


def test_loader_caches_prompt_bundles() -> None:
    from src.knowledge.prompts.loader import _PROMPT_CACHE, load_prompt_bundle

    _PROMPT_CACHE.clear()
    first = load_prompt_bundle("extraction")
    second = load_prompt_bundle("extraction")

    assert first is second


def test_loader_raises_for_missing_prompt_key() -> None:
    from src.knowledge.prompts.loader import get_prompt_value

    try:
        get_prompt_value("extraction", "missing_key")
    except ValueError as exc:
        assert "missing_key" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing prompt key")


def test_translation_prompt_matches_snapshot() -> None:
    markdown = "# 标题\n\n正文"

    assert prompts.get_translation_prompt(markdown) == (
        "请将以下医学 Markdown 内容翻译为英文，保留所有医学术语的准确性和格式：\n\n"
        "# 标题\n\n正文\n\n"
        "仅返回翻译后的 Markdown 内容，不需要额外说明。"
    )


def test_image_description_prompt_matches_snapshot() -> None:
    assert prompts.get_image_description_prompt(2) == (
        "请详细描述这张医学/临床图片的内容。注意：\n"
        "1. 识别图片中的关键元素（图表、数据、解剖结构等）\n"
        "2. 用英文输出描述\n"
        "3. 描述应该简洁但全面\n\n"
        "输出格式：\n"
        "[Image 2 Description]\n"
        "<描述内容>"
    )


def test_layout_fusion_prompt_matches_snapshot() -> None:
    prompt = prompts.get_layout_fusion_prompt("# English", ["Figure summary"])

    assert prompt == (
        "请将以下内容融合为一份格式清晰、结构完整的医学文档：\n\n"
        "## Translated Medical Document\n"
        "# English\n\n"
        "## Image Descriptions\n"
        "### Image 1 Description\n"
        "Figure summary\n\n"
        "请求：\n"
        "1. 整合所有内容为单一、连贯的 Markdown 文档\n"
        "2. 在适当位置引用图片描述\n"
        "3. 保持医学术语的准确性\n"
        "4. 使用清晰的章节组织\n\n"
        "返回整合后的 Markdown（保留所有结构标记）"
    )


def test_extraction_prompt_uses_externalized_template() -> None:
    from src.knowledge.prompts.loader import render_prompt_template

    knowledge_section = render_prompt_template(
        "extraction",
        "knowledge_section",
        knowledge_context="Reference block",
    )
    rendered = render_prompt_template(
        "extraction",
        "ps3_evidence_extraction",
        knowledge_section=knowledge_section,
        evidence_field_rules=prompts.EVIDENCE_FIELD_RULES,
        translated_md="# translated",
        image_section_display="### Image 1 Description\nfigure",
    )

    prompt = prompts.get_ps3_evidence_extraction_prompt(
        "# translated",
        ["figure"],
        knowledge_context="Reference block",
    )

    assert prompt == rendered
    assert "## REFERENCE KNOWLEDGE BASE DOCUMENTS" in prompt
    assert "Reference block" in prompt
    assert "## MEDICAL DOCUMENT TO EVALUATE" in prompt
    assert "# translated" in prompt
    assert "### Image 1 Description\nfigure" in prompt
    assert prompt.endswith("**Return only valid JSON. No additional text.**")


def test_extraction_yaml_exists() -> None:
    assert (PROMPTS_DIR / "extraction.yaml").exists()
    assert (PROMPTS_DIR / "loader.py").exists()
