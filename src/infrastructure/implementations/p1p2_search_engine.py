"""P1/P2 data search engine - technical implementation."""

import re
from typing import Dict, List, Optional, Tuple


class P1P2SearchEngine:
    """Search engine for extracting P1/P2 data locations when not explicitly found.
    
    This is a technical utility for text search patterns.
    Core business logic is in domain services.
    """
    
    # Keywords for secondary search
    CONTROL_GROUP_KEYWORDS = [
        r"control\s+group",
        r"control\s+(?:population|cohort)",
        r"normal\s+(?:individuals|subjects|controls)",
        r"wild[\s-]?type",
        r"healthy\s+controls",
        r"disease[\s-]?free",
    ]
    
    BENIGN_VARIANT_KEYWORDS = [
        r"benign\s+(?:variant|mutation)",
        r"likely[\s-]?benign",
        r"b/lb",
        r"benign\s+class",
        r"normal\s+variation",
        r"polymorphism",
    ]
    
    PATHOGENIC_VARIANT_KEYWORDS = [
        r"pathogenic\s+(?:variant|mutation)",
        r"likely[\s-]?pathogenic",
        r"p/lp",
        r"disease[\s-]?causing",
        r"deleterious",
        r"loss[\s-]?of[\s-]?function",
    ]
    
    STATISTICAL_KEYWORDS = [
        r"p\s*(?:=|<|>)\s*\d+\.?\d*",  # p-value
        r"odds\s+ratio|or\s*=",
        r"fold[\s-]?change",
        r"confidence\s+interval|ci",
        r"effect\s+size",
    ]

    @staticmethod
    def search_for_p1p2_locations(
        text: str, bbox_fragments: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """Search for P1 (prior prob) and P2 (posterior prob) locations."""
        
        p1_candidates = []
        p2_candidates = []
        
        # Search for control group mentions (potential P1)
        for keyword_pattern in P1P2SearchEngine.CONTROL_GROUP_KEYWORDS:
            matches = list(re.finditer(keyword_pattern, text, re.IGNORECASE))
            for match in matches:
                location = P1P2SearchEngine._get_location_context(
                    text, match.start(), match.end(), bbox_fragments
                )
                if location:
                    p1_candidates.append(location)
        
        # Search for pathogenic/benign controls (potential P2)
        for keyword_pattern in P1P2SearchEngine.PATHOGENIC_VARIANT_KEYWORDS:
            matches = list(re.finditer(keyword_pattern, text, re.IGNORECASE))
            for match in matches:
                location = P1P2SearchEngine._get_location_context(
                    text, match.start(), match.end(), bbox_fragments
                )
                if location:
                    p2_candidates.append(location)
        
        return p1_candidates, p2_candidates

    @staticmethod
    def _get_location_context(
        text: str, start: int, end: int, bbox_fragments: List[Dict]
    ) -> Optional[Dict]:
        """Extract context and bbox for a match location."""
        # Get surrounding context (±100 chars)
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 100)
        context = text[context_start:context_end]
        
        # Find closest bbox fragment
        for i, frag in enumerate(bbox_fragments):
            frag_text = frag.get("text", "")
            # Simple heuristic: match first few words
            if len(frag_text) > 3 and frag_text[:3].lower() in context.lower():
                return {
                    "matched_text": text[start:end],
                    "context": context,
                    "bbox": frag.get("bbox"),
                    "page": frag.get("page"),
                    "fragment_id": frag.get("fragment_id"),
                }
        
        return None
