from __future__ import annotations

from typing import Any, Callable, Mapping

from src.services.release_reporting import AcceptancePaperRecord

AcceptanceDispatcher = Callable[[AcceptancePaperRecord], Any]


def _normalize_enqueue_result(result: Any) -> dict[str, str]:
    if isinstance(result, dict):
        request_id = result.get("request_id")
        paper_task_id = result.get("paper_task_id")
    else:
        request_id = getattr(result, "request_id", None)
        paper_task_id = getattr(result, "paper_task_id", None)

    if not request_id:
        raise ValueError("Enqueue result must provide request_id")
    if not paper_task_id:
        raise ValueError("Enqueue result must provide paper_task_id")

    return {
        "request_id": str(request_id),
        "paper_task_id": str(paper_task_id),
    }


def enqueue_web_manifest_paper(_: AcceptancePaperRecord) -> dict[str, str]:
    raise NotImplementedError("Task 3 will wire the web acceptance flow")


def enqueue_api_manifest_paper(_: AcceptancePaperRecord) -> dict[str, str]:
    raise NotImplementedError("Task 3 and Task 4 will wire the api acceptance flow")


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
