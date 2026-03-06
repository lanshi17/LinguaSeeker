from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, TypedDict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from langgraph.graph import END, START, StateGraph


LiteratureSource = Literal["upload", "pubmed", "web"]


@dataclass(frozen=True)
class AcquisitionPlanItem:
    source: LiteratureSource
    raw_value: str
    normalized_value: str
    fingerprint: str
    display_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class AcquisitionPlanningState(TypedDict, total=False):
    source: LiteratureSource
    raw_items: List[str]
    plan_items: List[AcquisitionPlanItem]


_TRACKING_QUERY_PREFIXES = (
    "utm_",
    "mc_",
)


_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "dclid",
    "gbraid",
    "wbraid",
    "igshid",
    "mkt_tok",
    "ref_src",
    "ref_url",
    "yclid",
}


def _normalize_netloc(scheme: str, parsed: Any) -> str:
    hostname = str(parsed.hostname or "").lower()
    if not hostname:
        return ""

    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"

    port = parsed.port
    is_default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    port_suffix = ""
    if port and not is_default_port:
        port_suffix = f":{port}"

    return f"{userinfo}{hostname}{port_suffix}"


def _normalize_query(query: str) -> str:
    if not query:
        return ""

    normalized_items = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        normalized_key = key.strip()
        lowered_key = normalized_key.lower()
        if lowered_key in _TRACKING_QUERY_KEYS:
            continue
        if any(lowered_key.startswith(prefix) for prefix in _TRACKING_QUERY_PREFIXES):
            continue
        normalized_items.append((normalized_key, value))

    normalized_items.sort(key=lambda item: (item[0], item[1]))
    return urlencode(normalized_items, doseq=True)


def normalize_web_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        raise ValueError("INPUT_INVALID: url is required")

    parsed = urlsplit(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = _normalize_netloc(scheme, parsed)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    if not netloc:
        raise ValueError(f"INPUT_INVALID: invalid url '{raw}'")
    normalized_query = _normalize_query(parsed.query)
    normalized = urlunsplit((scheme, netloc, path, normalized_query, ""))
    return normalized


def fingerprint_web_url(url: str) -> str:
    return hashlib.sha256(f"url:{normalize_web_url(url)}".encode("utf-8")).hexdigest()


def fingerprint_pmid(pmid: str) -> str:
    return hashlib.sha256(f"pmid:{str(pmid).strip()}".encode("utf-8")).hexdigest()


class LiteratureAcquisitionAgent:
    def __init__(self) -> None:
        graph = StateGraph(AcquisitionPlanningState)
        graph.add_node("dispatch", self._dispatch)
        graph.add_node("plan_web", self._plan_web)
        graph.add_node("plan_pubmed", self._plan_pubmed)
        graph.add_node("plan_upload", self._plan_upload)
        graph.add_edge(START, "dispatch")
        graph.add_conditional_edges(
            "dispatch",
            self._route_source,
            {
                "web": "plan_web",
                "pubmed": "plan_pubmed",
                "upload": "plan_upload",
            },
        )
        graph.add_edge("plan_web", END)
        graph.add_edge("plan_pubmed", END)
        graph.add_edge("plan_upload", END)
        self._graph = graph.compile()

    def plan(self, source: LiteratureSource, raw_items: List[str]) -> List[AcquisitionPlanItem]:
        state = self._graph.invoke({"source": source, "raw_items": raw_items})
        return list(state.get("plan_items") or [])

    def plan_web_request(self, urls: List[str]) -> List[AcquisitionPlanItem]:
        return self.plan("web", urls)

    def plan_pubmed_request(self, pmids: List[str]) -> List[AcquisitionPlanItem]:
        return self.plan("pubmed", pmids)

    def _dispatch(self, state: AcquisitionPlanningState) -> AcquisitionPlanningState:
        return state

    def _route_source(self, state: AcquisitionPlanningState) -> LiteratureSource:
        source = state.get("source", "web")
        if source not in {"upload", "pubmed", "web"}:
            raise ValueError(f"INPUT_INVALID: unsupported acquisition source '{source}'")
        return source

    def _plan_web(self, state: AcquisitionPlanningState) -> AcquisitionPlanningState:
        items: List[AcquisitionPlanItem] = []
        for raw in state.get("raw_items", []):
            normalized = normalize_web_url(raw)
            items.append(
                AcquisitionPlanItem(
                    source="web",
                    raw_value=str(raw),
                    normalized_value=normalized,
                    fingerprint=fingerprint_web_url(normalized),
                    display_name=normalized,
                    metadata={"source_url": normalized},
                )
            )
        return {"plan_items": items}

    def _plan_pubmed(self, state: AcquisitionPlanningState) -> AcquisitionPlanningState:
        items: List[AcquisitionPlanItem] = []
        for raw in state.get("raw_items", []):
            pmid = str(raw or "").strip()
            if not pmid:
                raise ValueError("INPUT_INVALID: pmid is required")
            items.append(
                AcquisitionPlanItem(
                    source="pubmed",
                    raw_value=pmid,
                    normalized_value=pmid,
                    fingerprint=fingerprint_pmid(pmid),
                    display_name=f"PMID:{pmid}",
                    metadata={"pmid": pmid},
                )
            )
        return {"plan_items": items}

    def _plan_upload(self, state: AcquisitionPlanningState) -> AcquisitionPlanningState:
        items = [
            AcquisitionPlanItem(
                source="upload",
                raw_value=str(raw),
                normalized_value=str(raw),
                fingerprint="",
                display_name=str(raw),
                metadata={},
            )
            for raw in state.get("raw_items", [])
        ]
        return {"plan_items": items}


_literature_acquisition_agent: LiteratureAcquisitionAgent | None = None


def get_literature_acquisition_agent() -> LiteratureAcquisitionAgent:
    global _literature_acquisition_agent
    if _literature_acquisition_agent is None:
        _literature_acquisition_agent = LiteratureAcquisitionAgent()
    return _literature_acquisition_agent
