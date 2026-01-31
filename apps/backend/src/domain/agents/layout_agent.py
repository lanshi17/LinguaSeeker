"""Layout Agent for document structure parsing.

Analyzes PDF layout and generates clean markdown with preserved structure.
"""

from typing import Dict, Any
from dataclasses import dataclass

from src.domain.agents.agent_workflow import WorkflowContext
from src.infrastructure.adapters.llm_adapter import LLMAdapter, LLMRequest


@dataclass
class LayoutResult:
    """Layout analysis result."""

    markdown: str
    structure: Dict[str, Any]
    metadata: Dict[str, Any]


class LayoutAgent:
    """Agent for document layout analysis and markdown generation.

    Responsibilities:
    - Parse PDF structure (headings, paragraphs, tables, figures)
    - Generate clean markdown representation
    - Preserve document hierarchy
    """

    def __init__(self, llm_adapter: LLMAdapter):
        """Initialize layout agent.

        Args:
            llm_adapter: LLM adapter for analysis
        """
        self.llm = llm_adapter

    async def process(self, context: WorkflowContext) -> LayoutResult:
        """Process document layout.

        Args:
            context: Workflow context with PDF data

        Returns:
            Layout analysis result with markdown
        """
        # In production, this would use MinerU for parsing
        # For now, create a simplified structure

        # Parse document structure
        structure = await self._analyze_structure(context)

        # Generate markdown
        markdown = await self._generate_markdown(structure)

        # Extract metadata
        metadata = self._extract_metadata(structure)

        return LayoutResult(
            markdown=markdown,
            structure=structure,
            metadata=metadata,
        )

    async def _analyze_structure(self, context: WorkflowContext) -> Dict[str, Any]:
        """Analyze document structure.

        Args:
            context: Workflow context

        Returns:
            Document structure dictionary
        """
        # Placeholder: In production, use MinerU or similar
        return {
            "sections": [],
            "tables": [],
            "figures": [],
            "references": [],
        }

    async def _generate_markdown(self, structure: Dict[str, Any]) -> str:
        """Generate markdown from structure.

        Args:
            structure: Parsed document structure

        Returns:
            Markdown content
        """
        # Placeholder: Format structure as markdown
        markdown_parts = []

        for section in structure.get("sections", []):
            title = section.get("title", "")
            content = section.get("content", "")
            level = section.get("level", 2)

            markdown_parts.append(f"{'#' * level} {title}\n\n{content}\n\n")

        return "\n".join(markdown_parts)

    def _extract_metadata(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        """Extract document metadata.

        Args:
            structure: Document structure

        Returns:
            Metadata dictionary
        """
        return {
            "section_count": len(structure.get("sections", [])),
            "table_count": len(structure.get("tables", [])),
            "figure_count": len(structure.get("figures", [])),
            "has_references": bool(structure.get("references")),
        }

    def sanitize_markdown(self, markdown: str) -> str:
        """Sanitize markdown content.

        Args:
            markdown: Raw markdown

        Returns:
            Cleaned markdown
        """
        # Remove excessive whitespace
        lines = [line.rstrip() for line in markdown.split("\n")]

        # Remove multiple consecutive blank lines
        cleaned = []
        prev_blank = False

        for line in lines:
            is_blank = not line.strip()

            if is_blank and prev_blank:
                continue

            cleaned.append(line)
            prev_blank = is_blank

        return "\n".join(cleaned).strip()
