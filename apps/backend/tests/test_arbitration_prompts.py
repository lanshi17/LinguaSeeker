from __future__ import annotations

import json
from pathlib import Path

from src.domain.agent import prompts


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src/knowledge/prompts"


def test_acmg_rules_yaml_matches_code_constants() -> None:
    from src.knowledge.prompts.loader import load_prompt_bundle

    rules = load_prompt_bundle("acmg_rules")

    assert rules["oddspath_thresholds"] == prompts.ODDSPATH_THRESHOLDS
    assert rules["control_variants_thresholds"] == prompts.CONTROL_VARIANTS_THRESHOLDS
    assert rules["arbitration_confidence_threshold"] == prompts.ARBITRATION_CONFIDENCE_THRESHOLD
    assert rules["arbitration_score_threshold"] == prompts.ARBITRATION_SCORE_THRESHOLD
    assert rules["evidence_field_rules"] == prompts.EVIDENCE_FIELD_RULES


def test_arbitration_prompt_uses_externalized_template() -> None:
    from src.knowledge.prompts.loader import render_prompt_template

    knowledge_section = render_prompt_template(
        "arbitration",
        "knowledge_section",
        knowledge_context="KB",
    )
    rendered = render_prompt_template(
        "arbitration",
        "arbitration",
        knowledge_section=knowledge_section,
        translated_md="# translated",
        image_section_display="### Image 1 Description\nfigure",
        ps3_evidence_json=json.dumps({"ok": True}, ensure_ascii=False, indent=2),
        calculated_score=87.5,
        final_recommendation="approved",
    )

    prompt = prompts.get_arbitration_prompt(
        "# translated",
        ["figure"],
        {"ok": True},
        87.5,
        "approved",
        knowledge_context="KB",
    )

    assert prompt == rendered
    assert '"confidence": <0-1之间的置信度' in prompt
    assert 'final_decision 设为 "approved"' in prompt


def test_feedback_prompt_uses_externalized_template() -> None:
    from src.knowledge.prompts.loader import render_prompt_template

    knowledge_section = render_prompt_template(
        "arbitration",
        "knowledge_section_short",
        knowledge_context="KB",
    )
    rendered = render_prompt_template(
        "arbitration",
        "ps3_evidence_feedback",
        knowledge_section=knowledge_section,
        translated_md="# translated",
        image_section_display="### Image 1 Description\nfigure",
        ps3_evidence_json=json.dumps({"ok": True}, ensure_ascii=False, indent=2),
        arbitration_feedback="Tighten control evidence",
    )

    prompt = prompts.get_ps3_evidence_feedback_prompt(
        "# translated",
        ["figure"],
        {"ok": True},
        "Tighten control evidence",
        knowledge_context="KB",
    )

    assert prompt == rendered
    assert "## ARBITRATION FEEDBACK" in prompt


def test_refinement_prompt_uses_externalized_template() -> None:
    from src.knowledge.prompts.loader import render_prompt_template

    rendered = render_prompt_template(
        "arbitration",
        "feedback_refinement",
        translated_md="# translated",
        image_section_display="### Image 1 Description\nfigure",
        arbitration_feedback="Need stronger controls",
        arbitration_confidence="0.40",
        weaknesses_str="missing controls",
        improvements_str="- add controls",
    )

    prompt = prompts.get_feedback_refinement_prompt(
        "# translated",
        ["figure"],
        "Need stronger controls",
        0.4,
        ["missing controls"],
        ["add controls"],
    )

    assert prompt == rendered
    assert "## 主要问题" in prompt
    assert "- 仲裁置信度: 0.40" in prompt


def test_arbitration_yaml_exists() -> None:
    assert (PROMPTS_DIR / "arbitration.yaml").exists()
    assert (PROMPTS_DIR / "acmg_rules.yaml").exists()
