from src.domain.agent.prompts import get_translation_prompt
from src.domain.agent.workflow import EvidenceAgent
from src.domain.enums import ProcessingState


def translate_markdown(state: ProcessingState) -> ProcessingState:
    return EvidenceAgent().translate_markdown(state)


__all__ = ["get_translation_prompt", "translate_markdown"]
