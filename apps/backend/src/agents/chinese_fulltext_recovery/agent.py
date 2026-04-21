from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.chinese_fulltext_recovery import tools


class ChineseFulltextRecoveryState(TypedDict, total=False):
    source_url: str
    html: str
    extracted_body: str
    normalized_markdown: str
    body_selector: str | None
    warnings: list[str]
    provider: str
    status: str
    success: bool


class ChineseFulltextRecoveryAgent:
    def __init__(self) -> None:
        graph = StateGraph(ChineseFulltextRecoveryState)
        graph.add_node("fetch_html", self._fetch_html)
        graph.add_node("extract_body", self._extract_body)
        graph.add_node("maybe_normalize", self._maybe_normalize)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "fetch_html")
        graph.add_edge("fetch_html", "extract_body")
        graph.add_conditional_edges(
            "extract_body",
            self._route_after_extract,
            {"maybe_normalize": "maybe_normalize", "finalize": "finalize"},
        )
        graph.add_edge("maybe_normalize", "finalize")
        graph.add_edge("finalize", END)
        self._graph = graph.compile()

    def run(self, source_url: str) -> dict[str, Any]:
        state = self._graph.invoke({"source_url": source_url, "warnings": []})
        return {
            "success": bool(state.get("success")),
            "status": str(state.get("status") or "failed"),
            "provider": str(state.get("provider") or "chinese_fulltext_recovery"),
            "normalized_markdown": str(state.get("normalized_markdown") or ""),
            "body_selector": state.get("body_selector"),
            "warnings": list(state.get("warnings") or []),
        }

    def _canonical_hans_detail_url(
        self, source_url: str, final_url: str | None
    ) -> str | None:
        source = str(source_url or "").strip()
        resolved = str(final_url or "").strip().rstrip("/")
        if "hanspub.org" not in source or resolved != "https://www.hanspub.org":
            return None
        match = re.search(r"_(\d+)\.htm(?:$|\?)", source, re.IGNORECASE)
        if not match:
            return None
        return f"https://www.hanspub.org/journal/paperinformation?paperid={match.group(1)}"

    def _fetch_html(
        self, state: ChineseFulltextRecoveryState
    ) -> ChineseFulltextRecoveryState:
        source_url = state.get("source_url", "")
        fetched = tools.fetch_detail_html(source_url)
        warnings = list(state.get("warnings") or [])
        warnings.extend(fetched.get("warnings") or [])
        html = str(fetched.get("html") or "")
        final_url = str(fetched.get("final_url") or "")

        canonical_hans_url = self._canonical_hans_detail_url(source_url, final_url)
        if canonical_hans_url:
            canonical = tools.fetch_detail_html(canonical_hans_url)
            canonical_html = str(canonical.get("html") or "")
            if canonical_html:
                html = canonical_html
                warnings.extend(canonical.get("warnings") or [])
                warnings.append("fallback:hans_canonical")

        return {
            "html": html,
            "warnings": warnings,
        }

    def _extract_body(
        self, state: ChineseFulltextRecoveryState
    ) -> ChineseFulltextRecoveryState:
        extracted = tools.extract_readable_body(state.get("html", ""))
        warnings = list(state.get("warnings") or [])
        warnings.extend(extracted.get("warnings") or [])
        body = str(extracted.get("body") or "").strip()
        if body:
            warnings.append("fallback:html_body")
        return {
            "extracted_body": body,
            "body_selector": extracted.get("body_selector"),
            "warnings": warnings,
        }

    def _route_after_extract(
        self, state: ChineseFulltextRecoveryState
    ) -> Literal["maybe_normalize", "finalize"]:
        body = str(state.get("extracted_body") or "").strip()
        if body and tools.validate_normalized_body(body):
            return "finalize"
        return "maybe_normalize"

    def _maybe_normalize(
        self, state: ChineseFulltextRecoveryState
    ) -> ChineseFulltextRecoveryState:
        body = str(state.get("extracted_body") or "").strip()
        warnings = list(state.get("warnings") or [])
        if not body:
            return {"warnings": warnings}
        normalized_markdown = str(tools.normalize_body_with_format_llm(body) or "").strip()
        if normalized_markdown:
            warnings.append("fallback:format_llm")
        return {
            "normalized_markdown": normalized_markdown,
            "warnings": warnings,
        }

    def _finalize(
        self, state: ChineseFulltextRecoveryState
    ) -> ChineseFulltextRecoveryState:
        normalized_markdown = str(
            state.get("normalized_markdown") or state.get("extracted_body") or ""
        ).strip()
        success = bool(normalized_markdown)
        return {
            "success": success,
            "status": "success" if success else "failed",
            "provider": "chinese_fulltext_recovery",
            "normalized_markdown": normalized_markdown,
        }


_agent: ChineseFulltextRecoveryAgent | None = None



def get_chinese_fulltext_recovery_agent() -> ChineseFulltextRecoveryAgent:
    global _agent
    if _agent is None:
        _agent = ChineseFulltextRecoveryAgent()
    return _agent



def run_chinese_fulltext_recovery(source_url: str) -> dict[str, Any]:
    return get_chinese_fulltext_recovery_agent().run(source_url)
