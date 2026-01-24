"""Arbiter service implementation with structured PS3 evaluation."""

import json
import re
from typing import Optional, List

import orjson
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.domain.entities import Evidence
from src.domain.services import ArbiterService
from src.domain.value_objects import ArbiterFeedback, DimensionScore
from src.infrastructure.utils.exceptions import ReasoningException
from src.infrastructure.utils.logger import Logger


class ArbiterServiceImpl(ArbiterService):
    """Arbiter service implementation using LLM with structured PS3 evaluation."""

    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        self.logger = Logger.get_logger(__name__)

    def score_evidence(
        self, evidence: Evidence, kb_context: Optional[List[str]] = None
    ) -> ArbiterFeedback:
        """Score evidence following PS3 four-step framework with structured feedback."""
        
        system_prompt = self._build_system_prompt(kb_context)
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "Evaluate this evidence:\nEvidence JSON:\n{ev}\n\nProvide detailed JSON assessment."),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        score_str = chain.invoke({"ev": orjson.dumps(evidence.to_dict()).decode()})
        
        return self._parse_feedback(score_str, evidence)

    def _build_system_prompt(self, kb_context: Optional[List[str]] = None) -> str:
        """Build comprehensive system prompt for PS3 four-step evaluation."""
        base_prompt = """You are a clinical genomics arbiter specialized in ACMG PS3 (Functional Evidence) classification.
Evaluate evidence extraction quality following the PS3 SVI four-step framework:

① DISEASE MECHANISM CLARITY
   - Is the pathogenic mechanism of the variant clearly explained?
   - Status: pass (clear) | fail (unclear) | partial (partially clear)

② FUNCTIONAL ASSAY METHOD SUITABILITY
   - Is the selected functional assay type appropriate for the disease mechanism?
   - Status: pass (appropriate) | fail (inappropriate) | na (not applicable)

③ EXPERIMENTAL VALIDITY
   Check ALL of these:
   a) CONTROLS: Are both normal/wild-type AND abnormal/pathogenic controls present?
      Status: pass | fail → max PS3_supporting/BS3_supporting
   b) REPLICABILITY: Are biological or technical replicates used?
      Status: pass | fail → max PS3_supporting/BS3_supporting
   c) METHOD RELIABILITY: Is this a historically accepted/validated method or certified kit?
      Status: pass | fail → not applicable to PS3/BS3
   d) POSITIVE CONTROLS: Are known pathogenic (P/LP) or benign (B/LB) variants used as controls?
      Status: pass (controls used) → max PS3_supporting/BS3_supporting
      Status: fail (no controls) → proceed to step ④

④ VARIANT-SPECIFIC APPLICATION & ODDS PATH
   - Can OddsPath be calculated from reported statistics?
     - If YES: Validate P1/P2 values are in (0,1); verify OddsPath mapping matches evidence strength
     - If NO: Record control_variants_count; allow only PS3_supporting/BS3_supporting
   - OddsPath Mapping:
     | OddsPath Range | Evidence Strength |
     | < 0.017        | BS3              |
     | 0.017–0.05     | BS3_moderate     |
     | 0.05–0.33      | BS3_supporting   |
     | 0.33–3.0       | —                |
     | 3.0–20         | PS3_supporting   |
     | 20–60          | PS3_moderate     |
     | ≥ 60           | PS3              |

OUTPUT FORMAT (must be valid JSON):
{{
  "overall_score": <0-100>,
  "normalized_score": <0-100 after normalization>,
  "ps3_step_1": {{
    "status": "pass|fail|partial",
    "score": <0-25>,
    "reason": "explanation",
    "suggestions": ["improvement 1", "improvement 2"]
  }},
  "ps3_step_2": {{
    "status": "pass|fail|na",
    "score": <0-20>,
    "reason": "explanation",
    "suggestions": []
  }},
  "ps3_step_3": {{
    "controls": {{"status": "pass|fail", "score": <0-15>}},
    "replicates": {{"status": "pass|fail", "score": <0-10>}},
    "method_reliability": {{"status": "pass|fail|na", "score": <0-15>}},
    "positive_controls": {{"status": "pass|fail", "score": <0-10>}},
    "step3_total_score": <0-50>,
    "step3_status": "pass|fail|partial",
    "reason": "overall assessment"
  }},
  "ps3_step_4": {{
    "odds_path_computable": true|false,
    "odds_path_valid": true|false,
    "mapping_correct": true|false,
    "score": <0-20>,
    "reason": "explanation",
    "suggestions": []
  }},
  "key_issues": ["issue 1", "issue 2"],
  "recommendations": ["rec 1", "rec 2"],
  "should_iterate": true|false,
  "confidence": <0.0-1.0>
}}"""
        
        if kb_context:
            kb_text = "\n".join(kb_context[:3]) if isinstance(kb_context, list) else str(kb_context)
            base_prompt += f"\n\nPREE-LOADED PS3 GUIDANCE FROM ACMG KNOWLEDGE BASE:\n{kb_text}"
        
        return base_prompt

    def _parse_feedback(self, raw: str, evidence: Evidence) -> ArbiterFeedback:
        """Parse LLM response into structured ArbiterFeedback."""
        try:
            # Extract JSON from response
            data = self._try_parse_json(raw)
            if not data:
                self.logger.warning(f"Failed to parse arbiter response; using default feedback")
                return self._create_default_feedback(evidence)
            
            # Extract dimension scores
            dimensions = []
            
            # Step 1: Disease Mechanism
            if "ps3_step_1" in data:
                step1 = data["ps3_step_1"]
                dimensions.append(DimensionScore(
                    name="disease_mechanism",
                    score=float(step1.get("score", 0)),
                    max_score=25,
                    status=step1.get("status", "fail"),
                    reason=step1.get("reason", ""),
                    suggestions=step1.get("suggestions", []),
                ))
            
            # Step 2: Method Suitability
            if "ps3_step_2" in data:
                step2 = data["ps3_step_2"]
                dimensions.append(DimensionScore(
                    name="method_suitability",
                    score=float(step2.get("score", 0)),
                    max_score=20,
                    status=step2.get("status", "fail"),
                    reason=step2.get("reason", ""),
                    suggestions=step2.get("suggestions", []),
                ))
            
            # Step 3: Experimental Validity (aggregate)
            if "ps3_step_3" in data:
                step3 = data["ps3_step_3"]
                dimensions.append(DimensionScore(
                    name="experimental_validity",
                    score=float(step3.get("step3_total_score", 0)),
                    max_score=50,
                    status=step3.get("step3_status", "fail"),
                    reason=step3.get("reason", ""),
                    suggestions=[],
                ))
            
            # Step 4: Odds Path Validity
            if "ps3_step_4" in data:
                step4 = data["ps3_step_4"]
                dimensions.append(DimensionScore(
                    name="odds_path_validity",
                    score=float(step4.get("score", 0)),
                    max_score=20,
                    status="pass" if step4.get("odds_path_valid") else "fail",
                    reason=step4.get("reason", ""),
                    suggestions=step4.get("suggestions", []),
                ))
            
            # Determine if iteration is needed
            overall_score = float(data.get("overall_score", 0))
            should_iterate = data.get("should_iterate", overall_score < 75)
            
            feedback = ArbiterFeedback(
                overall_score=overall_score,
                max_score=100.0,
                dimensions=dimensions,
                key_issues=data.get("key_issues", []),
                recommendations=data.get("recommendations", []),
                should_iterate=should_iterate,
            )
            
            # Store feedback in evidence for reference
            evidence.arbiter_score = overall_score
            
            return feedback
            
        except Exception as exc:
            self.logger.error(f"Error parsing arbiter feedback: {exc}")
            return self._create_default_feedback(evidence)

    def _create_default_feedback(self, evidence: Evidence) -> ArbiterFeedback:
        """Create default feedback when parsing fails."""
        return ArbiterFeedback(
            overall_score=0.0,
            dimensions=[
                DimensionScore("disease_mechanism", 0, 25, "fail", "Not evaluated"),
                DimensionScore("method_suitability", 0, 20, "fail", "Not evaluated"),
                DimensionScore("experimental_validity", 0, 50, "fail", "Not evaluated"),
                DimensionScore("odds_path_validity", 0, 20, "fail", "Not evaluated"),
            ],
            key_issues=["Failed to parse arbiter evaluation"],
            should_iterate=True,
        )

    @staticmethod
    def _try_parse_json(text: str) -> Optional[dict]:
        """Try multiple JSON parsers to extract structured feedback."""
        text = (text or "").strip()
        if not text:
            return None
        
        # Try direct parse
        for loader in (orjson.loads, json.loads):
            try:
                return loader(text)
            except Exception:
                continue
        
        # Try to extract JSON object from text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            for loader in (orjson.loads, json.loads):
                try:
                    return loader(match.group(0))
                except Exception:
                    continue
        
        return None

