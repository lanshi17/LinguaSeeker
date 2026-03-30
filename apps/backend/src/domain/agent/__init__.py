"""
agent 子包 —— Agent 工作流、提示词、RAG
"""
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from src.domain.agent.workflow import EvidenceAgent
	from src.domain.agent.rag import RAGComponent

__all__ = ["EvidenceAgent", "RAGComponent"]


def __getattr__(name: str) -> Any:
	if name == "EvidenceAgent":
		from src.domain.agent.workflow import EvidenceAgent

		return EvidenceAgent
	if name == "RAGComponent":
		from src.domain.agent.rag import RAGComponent

		return RAGComponent
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
