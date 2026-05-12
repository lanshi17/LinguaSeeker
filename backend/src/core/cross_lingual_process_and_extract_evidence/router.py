"""Independent routing logic — decoupled from orchestrator."""
from __future__ import annotations

from typing import Literal

from .contracts import PipelineState
from .translate.language_detector import should_skip_translation


class LanguageRouter:
    """Decides whether a document needs translation.

    Single-responsibility: routing logic lives here, not in workflow.py.
    """

    @staticmethod
    def route(state: PipelineState) -> Literal["translate", "skip_translate"]:
        if state.needs_translation and not should_skip_translation(
            state.formatted.formatted_markdown if state.formatted else ""
        ):
            return "translate"
        return "skip_translate"
