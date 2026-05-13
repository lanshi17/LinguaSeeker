"""Independent routing logic — decoupled from orchestrator."""
from __future__ import annotations

from typing import Literal

from .contracts import PipelineState
from .cross_lingual.translate.language_detector import should_skip_translation


class LanguageRouter:
    """Decides whether a document needs translation.

    Single-responsibility: routing logic lives here, not in workflow.py.
    """

    @staticmethod
    def route(state: PipelineState) -> Literal["translate", "skip_translate"]:
        text = state.formatted.formatted_markdown if state.formatted else ""
        if should_skip_translation(text):
            return "skip_translate"
        return "translate"
