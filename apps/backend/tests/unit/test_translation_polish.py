from __future__ import annotations

from src.domain.agent.workflow import EvidenceAgent


def test_polish_stage_improves_style_but_keeps_meaning(monkeypatch) -> None:
    agent = EvidenceAgent()

    monkeypatch.setattr(
        agent,
        "_run_translation_polish",
        lambda draft, terminology: "Polished English markdown",
    )

    state = {
        "translation_draft": "Draft English markdown",
        "translation_terminology": "term map",
        "translation_warnings": [],
    }
    result = agent._apply_translation_polish(state)

    assert result["translation_polished"] == "Polished English markdown"


def test_polish_stage_falls_back_to_draft_on_failure(monkeypatch) -> None:
    agent = EvidenceAgent()

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("llm failed")

    monkeypatch.setattr(agent, "_run_translation_polish", raise_error)

    state = {
        "translation_draft": "Draft English markdown",
        "translation_terminology": "term map",
        "translation_warnings": [],
    }
    result = agent._apply_translation_polish(state)

    assert result["translation_polished"] == "Draft English markdown"
    assert "translation_polish_failed" in result["translation_warnings"]
