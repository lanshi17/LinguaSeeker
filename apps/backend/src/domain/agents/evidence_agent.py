"""Evidence Agent for ACMG evidence extraction.

Extracts ACMG criteria from document text using LLM analysis.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from decimal import Decimal

from src.infrastructure.adapters.llm_adapter import LLMAdapter, LLMRequest
from src.domain.value_objects.acmg_code import ACMGCode


@dataclass
class ExtractedEvidence:
    """Extracted evidence item."""

    acmg_code: str
    supporting_text: str
    page: int
    confidence: float
    reasoning: str


class EvidenceAgent:
    """Agent for ACMG evidence extraction.

    Responsibilities:
    - Identify ACMG evidence criteria in text
    - Extract supporting text passages
    - Map evidence to specific variants
    - Provide extraction reasoning
    """

    # ACMG criteria descriptions for prompting
    ACMG_CRITERIA = {
        "PS1": "Same amino acid change as established pathogenic variant",
        "PS2": "De novo in patient with disease and no family history",
        "PS3": "Well-established functional studies supportive of damaging effect",
        "PM1": "Located in mutational hot spot/critical functional domain",
        "PM2": "Absent from controls or extremely low frequency",
        "PP3": "Multiple computational evidence support deleterious effect",
        "BS3": "Well-established functional studies show no damaging effect",
        "BP4": "Multiple computational evidence suggest no impact",
        # Add more as needed
    }

    def __init__(self, llm_adapter: LLMAdapter):
        """Initialize evidence agent."""
        self.llm = llm_adapter

    async def process(
        self, text: str, page_number: int = 1
    ) -> List[ExtractedEvidence]:
        """Extract ACMG evidence from text.

        Args:
            text: Document text to analyze
            page_number: Source page number

        Returns:
            List of extracted evidence items
        """
        # Build extraction prompt
        prompt = self._build_extraction_prompt(text)

        # Request structured JSON response
        request = LLMRequest(
            prompt=prompt,
            system_prompt="You are an expert in ACMG variant interpretation guidelines.",
            temperature=0.0,  # Deterministic extraction
            max_tokens=4000,
            response_format="json",
        )

        response = await self.llm.generate(request)

        # Parse response
        evidence_list = self._parse_response(response.content, page_number)

        return evidence_list

    def _build_extraction_prompt(self, text: str) -> str:
        """Build evidence extraction prompt.

        Args:
            text: Source text

        Returns:
            Extraction prompt
        """
        criteria_list = "\n".join(
            f"- {code}: {desc}"
            for code, desc in list(self.ACMG_CRITERIA.items())[:10]
        )

        return f"""Extract ACMG evidence criteria from the following biomedical text.

ACMG Criteria (subset):
{criteria_list}

Text to analyze:
{text[:2000]}

For each identified criterion, provide:
1. ACMG code (e.g., PS1, PM2)
2. Supporting text passage (exact quote)
3. Confidence score (0.0-1.0)
4. Brief reasoning

Return as JSON array:
[
  {{
    "code": "PS3",
    "text": "functional studies demonstrated...",
    "confidence": 0.9,
    "reasoning": "Clear functional evidence"
  }}
]"""

    def _parse_response(
        self, response_text: str, page: int
    ) -> List[ExtractedEvidence]:
        """Parse LLM response into evidence items.

        Args:
            response_text: JSON response from LLM
            page: Page number

        Returns:
            List of extracted evidence
        """
        import json

        try:
            items = json.loads(response_text)

            evidence = []
            for item in items:
                evidence.append(
                    ExtractedEvidence(
                        acmg_code=item["code"],
                        supporting_text=item["text"],
                        page=page,
                        confidence=float(item.get("confidence", 0.5)),
                        reasoning=item.get("reasoning", ""),
                    )
                )

            return evidence

        except (json.JSONDecodeError, KeyError) as e:
            # Fallback: empty list if parsing fails
            return []

    def validate_evidence_code(self, code: str) -> bool:
        """Validate ACMG code.

        Args:
            code: ACMG code to validate

        Returns:
            True if valid code
        """
        try:
            ACMGCode.from_string(code)
            return True
        except ValueError:
            return False
