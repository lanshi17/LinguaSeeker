from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Mapping

from src.api.routes.task import create_task_request_by_web_crawl, submit_pubmed_selection
from src.services.api_request_submission import submit_api_acceptance_item
from src.services.dtos import PubMedSelectionSubmitRequest, WebLiteratureCrawlRequest
from src.services.release_reporting import AcceptancePaperRecord

AcceptanceDispatcher = Callable[[AcceptancePaperRecord], Any]


def _normalize_enqueue_result(result: Any) -> dict[str, str]:
    if isinstance(result, dict):
        request_id = result.get("request_id")
        paper_task_id = result.get("paper_task_id")
        papers = result.get("papers")
    else:
        request_id = getattr(result, "request_id", None)
        paper_task_id = getattr(result, "paper_task_id", None)
        papers = getattr(result, "papers", None)

    if not paper_task_id and papers:
        if len(papers) != 1:
            raise ValueError("Acceptance executor requires exactly one paper result")
        paper_task_id = getattr(papers[0], "paper_task_id", None)

    if not request_id:
        raise ValueError("Enqueue result must provide request_id")
    if not paper_task_id:
        raise ValueError("Enqueue result must provide paper_task_id")

    return {
        "request_id": str(request_id),
        "paper_task_id": str(paper_task_id),
    }


def _request_payload(paper: AcceptancePaperRecord) -> dict[str, Any]:
    payload = paper.request_payload
    if not isinstance(payload, dict):
        raise ValueError("Manifest paper request_payload must be a dictionary")
    return payload


def _task_form_components(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    task_form = str(
        payload.get("task_form")
        or payload.get("task_form_text")
        or ""
    ).strip()
    if not task_form:
        raise ValueError("Manifest paper request_payload must include task_form")

    try:
        parsed_task_form = json.loads(task_form)
    except json.JSONDecodeError:
        parsed_task_form = {}
    if not isinstance(parsed_task_form, dict):
        parsed_task_form = {}
    return task_form, parsed_task_form


def _clean_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Iterable):
        return []
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _pubmed_ids(payload: Mapping[str, Any]) -> list[str]:
    candidates = _clean_list(payload.get("selected_pmids"))
    if not candidates:
        raw_identifiers = payload.get("identifiers")
        if isinstance(raw_identifiers, dict):
            raw_identifiers = list(raw_identifiers.values())
        candidates = _clean_list(raw_identifiers)

    pmids: list[str] = []
    for candidate in candidates:
        normalized = candidate
        if ":" in candidate:
            prefix, value = candidate.split(":", 1)
            if prefix.strip().lower() != "pmid":
                continue
            normalized = value.strip()
        if normalized.isdigit():
            pmids.append(normalized)

    if not pmids:
        raise ValueError("PubMed acceptance rows require one PMID identifier")
    if len(pmids) != 1:
        raise ValueError("PubMed acceptance rows must map to exactly one PMID")
    return pmids


def _coerce_task_field(
    payload: Mapping[str, Any],
    parsed_task_form: Mapping[str, Any],
    *,
    key: str,
    fallback_keys: Iterable[str] = (),
    default: str | None = None,
) -> str:
    for candidate_key in (key, *fallback_keys):
        value = payload.get(candidate_key)
        if value is None:
            value = parsed_task_form.get(candidate_key)
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    if default is not None:
        return default
    raise ValueError(f"Manifest paper request_payload must include {key}")


def enqueue_web_manifest_paper(paper: AcceptancePaperRecord) -> dict[str, str]:
    payload = _request_payload(paper)
    task_form, _ = _task_form_components(payload)
    urls = _clean_list(payload.get("urls"))
    if not urls:
        raise ValueError("Web acceptance rows require urls")
    if len(urls) != 1:
        raise ValueError("Web acceptance rows must map to exactly one URL")

    response = create_task_request_by_web_crawl(
        WebLiteratureCrawlRequest(
            task_form=task_form,
            urls=urls,
            source="web",
            force_refresh=bool(payload.get("force_refresh", False)),
        )
    )
    return _normalize_enqueue_result(response)


def enqueue_api_manifest_paper(paper: AcceptancePaperRecord) -> dict[str, str]:
    if str(paper.source or "").lower() != "pubmed":
        return submit_api_acceptance_item(
            source=str(paper.source or ""),
            request_payload=_request_payload(paper),
        )

    payload = _request_payload(paper)
    task_form, parsed_task_form = _task_form_components(payload)
    response = submit_pubmed_selection(
        PubMedSelectionSubmitRequest(
            task_form=task_form,
            selected_pmids=_pubmed_ids(payload),
            target=_coerce_task_field(
                payload,
                parsed_task_form,
                key="target",
                fallback_keys=("goal", "query"),
            ),
            disease=_coerce_task_field(payload, parsed_task_form, key="disease"),
            country=_coerce_task_field(
                payload,
                parsed_task_form,
                key="country",
                default="不限",
            ),
            language=_coerce_task_field(
                payload,
                parsed_task_form,
                key="language",
                default="auto",
            ),
            source="pubmed",
        )
    )
    return _normalize_enqueue_result(response)


class AcceptanceExecutor:
    def __init__(
        self,
        *,
        dispatchers: Mapping[str, AcceptanceDispatcher] | None = None,
    ) -> None:
        default_dispatchers: dict[str, AcceptanceDispatcher] = {
            "web": enqueue_web_manifest_paper,
            "api": enqueue_api_manifest_paper,
        }
        if dispatchers:
            default_dispatchers.update(dispatchers)
        self._dispatchers = default_dispatchers

    def enqueue_manifest_paper(self, paper: AcceptancePaperRecord) -> dict[str, str]:
        missing_fields: list[str] = []
        if not paper.entry_kind:
            missing_fields.append("entry_kind")
        if not paper.source:
            missing_fields.append("source")
        if not paper.request_payload:
            missing_fields.append("request_payload")
        if missing_fields:
            raise ValueError(
                "Manifest paper is missing required fields: "
                + ", ".join(missing_fields)
            )

        dispatcher = self._dispatchers.get(paper.entry_kind)
        if dispatcher is None:
            raise ValueError(
                f"Unsupported acceptance entry_kind: {paper.entry_kind}"
            )

        return _normalize_enqueue_result(dispatcher(paper))


def enqueue_manifest_paper(
    paper: AcceptancePaperRecord,
    *,
    dispatchers: Mapping[str, AcceptanceDispatcher] | None = None,
) -> dict[str, str]:
    return AcceptanceExecutor(dispatchers=dispatchers).enqueue_manifest_paper(paper)
