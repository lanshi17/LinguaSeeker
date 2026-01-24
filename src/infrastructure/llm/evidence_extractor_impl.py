"""Evidence extractor service implementation."""

import json
import re
from typing import List, Optional

import orjson
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Using absolute imports from src root
from src.domain.entities import Evidence
from src.domain.services import EvidenceExtractorService
from src.infrastructure.utils.logger import Logger


class EvidenceExtractorServiceImpl(EvidenceExtractorService):
    """Evidence extraction service implementation using LLM."""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.logger = Logger.get_logger(__name__)

    def extract_evidence(
        self,
        english_text: str,
        ps3_context: List[str],
        feedback: Optional[str] = None,
    ) -> Evidence:
        system_prompt = self._build_system_prompt(feedback)
        
        human_prompt = self._build_human_prompt()
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", human_prompt),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        raw = chain.invoke(
            {
                "paper": english_text,
                "ctx": "\n---\n".join(ps3_context),
            }
        )

        data = self._parse_json_safe(raw)

        return Evidence(
            findings=data.get("findings", []),
            p1=self._safe_prob(data.get("p1"), 0.1),
            p2=self._safe_prob(data.get("p2"), 0.5),
            rationale=data.get("rationale", ""),
            experimental_details=data.get("experimental_details", ""),
            p1_source_location=data.get("p1_source_location", ""),
            p2_source_location=data.get("p2_source_location", ""),
            ps3_criteria_met=bool(data.get("ps3_criteria_met", False)),
            control_variants_count=int(data.get("control_variants_count", 0)),
            odds_path_computable=bool(data.get("odds_path_computable", True)),
            reason_if_not_applicable=data.get("reason_if_not_applicable", ""),
        )

    def _build_system_prompt(self, feedback: Optional[str] = None) -> str:
        """Build system prompt with optional feedback injection."""
        base_prompt = (
            "You are a clinical genomics assistant. Extract PS3 functional evidence following SVI 4-step framework. "
            "Return ONLY valid JSON with these exact fields: "
            "findings (list), p1 (float), p2 (float), rationale (string), experimental_details (string), "
            "p1_source_location (string), p2_source_location (string), ps3_criteria_met (boolean), "
            "control_variants_count (integer), odds_path_computable (boolean), reason_if_not_applicable (string)."
        )
        
        if feedback:
            base_prompt += f"\n\nIMPORTANT - Previous iteration feedback for improvement:\n{feedback}"
        
        return base_prompt

    @staticmethod
    def _build_human_prompt() -> str:
        """Build detailed human prompt with PS3 four-step framework."""
        return (
            "Paper:\n{paper}\n\nPS3 Knowledge Base:\n{ctx}\n\n"
            "MANDATORY PS3 SVI 4-STEP ASSESSMENT:\n\n"
            "STEP ①: DISEASE MECHANISM CLARITY\n"
            "- Is the pathogenic mechanism of the variant clearly described?\n"
            "- Must include: molecular/cellular impact, tissue relevance, biochemical consequence\n"
            "- If unclear → ps3_criteria_met=false, reason_if_not_applicable='mechanism unclear', STOP\n\n"
            "STEP ②: FUNCTIONAL ASSAY METHOD SUITABILITY\n"
            "- Is the selected assay type appropriate for the identified mechanism?\n"
            "- Examples: disease mechanism='loss of DNA binding' → suitable methods include EMSA, ChIP-seq\n"
            "- Examples: disease mechanism='trafficking defect' → suitable methods include immunofluorescence, cell fractionation\n"
            "- If unsuitable → ps3_criteria_met=false, reason_if_not_applicable='method inappropriate', STOP\n\n"
            "STEP ③: EXPERIMENTAL VALIDITY (ALL must be assessed)\n"
            "Check EACH of these components:\n"
            "  a) CONTROLS: Both normal/wild-type AND abnormal/pathogenic controls present? Y/N\n"
            "     → NO → max evidence level is PS3_supporting; set odds_path_computable=false\n"
            "  b) REPLICATES: Biological or technical replicates reported? Y/N\n"
            "     → NO → max evidence level is PS3_supporting; set odds_path_computable=false\n"
            "  c) METHOD RELIABILITY: Is this a historically validated/accepted method or certified kit? Y/N/Unknown\n"
            "     → Unknown/NO → ps3_criteria_met=false, reason_if_not_applicable='method not validated', STOP\n"
            "  d) POSITIVE CONTROLS: Known pathogenic (P/LP) or benign (B/LB) variants used as comparison? Y/N\n"
            "     → YES → record control_variants_count (how many?); max evidence is PS3_supporting\n"
            "     → NO → proceed to STEP ④\n\n"
            "STEP ④: VARIANT-SPECIFIC APPLICATION & ODDS PATH\n"
            "- Analyze reported statistics (p-values, OR, fold-change, functional assay quantification)\n"
            "- P1 = Proportion of pathogenic variants in model data (致病变异在模型数据中的比例)\n"
            "- P2 = Proportion of pathogenic variants in functionally abnormal group (功能异常组中致病变异的比例)\n"
            "- Can P1 and P2 be extracted from paper? Y/N\n"
            "  → YES: Compute OddsPath = [P2 × (1-P1)] / [(1-P2) × P1]\n"
            "          Validate OddsPath is in (0, +∞)\n"
            "          Map to strength per table:\n"
            "          | <0.017: BS3 | 0.017-0.05: BS3_moderate | 0.05-0.33: BS3_supporting |\n"
            "          | 0.33-3.0: none | 3.0-20: PS3_supporting | 20-60: PS3_moderate | ≥60: PS3 |\n"
            "  → NO: Record control_variants_count; evidence limited to PS3_supporting if③ passed\n\n"
            "CRITICAL OUTPUT REQUIREMENTS:\n"
            "1. p1_source_location & p2_source_location MUST cite exact paper location with maximum detail:\n"
            "   Format examples:\n"
            "   - 'Table 2, row 3: pathogenic variants = 45/100' (preferred)\n"
            "   - 'Figure 3B legend, pathogenic group n=23'\n"
            "   - 'Page 5, Results section, paragraph 2: \"functional abnormality rate was 0.85\"'\n"
            "   If NO explicit data found, state: 'P1/P2 data not explicitly reported'\n"
            "2. If P1/P2 implicit/missing: search for keywords 'control group', 'wild-type', 'benign variant', 'pathogenic variant'\n"
            "   and report their locations\n"
            "3. control_variants_count = total number of distinct variants used as controls (pathogenic+benign)\n"
            "4. odds_path_computable = true ONLY if P1 and P2 both explicitly quantified and OddsPath computed\n"
            "5. ps3_criteria_met = true ONLY if ALL steps ①–③ pass AND OddsPath/controls support PS3/PS3_supporting level\n"
            "6. For coordinate-level tracing: If bbox metadata is available in the paper, include page numbers and approximate\n"
            "   text positions to enable precise highlighting\n\n"
            "Return ONLY valid JSON. No preamble."
        )


    def _parse_json_safe(self, raw: str) -> dict:
        """Parse JSON output from LLM robustly, returning defaults on failure."""
        text = (raw or "").strip()
        if not text:
            self.logger.warning("Evidence extractor received empty response; using defaults")
            return {}

        # Try direct parse first
        data = self._try_loads(text)
        if data is not None:
            return data

        # Try to extract first JSON object if extra text present
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            data = self._try_loads(match.group(0))
            if data is not None:
                return data

        self.logger.warning("Evidence extractor failed to parse JSON; using defaults")
        return {}

    @staticmethod
    def _safe_prob(value, default: float) -> float:
        try:
            prob = float(value)
        except Exception:  # noqa: BLE001
            prob = default

        # Clamp to open interval (0, 1) to satisfy OddsPath constraints
        prob = max(1e-3, min(prob, 0.999))
        return prob

    @staticmethod
    def _try_loads(text: str) -> Optional[dict]:
        for loader in (orjson.loads, json.loads):
            try:
                return loader(text)
            except Exception:  # noqa: BLE001
                continue
        return None
