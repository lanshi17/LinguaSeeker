from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from src.config import settings as cfg

FROZEN_ERROR_CODES = {
    "INPUT_INVALID",
    "FILE_TOO_LARGE",
    "FILE_TYPE_UNSUPPORTED",
    "FILE_DUPLICATE",
    "FETCH_TIMEOUT",
    "FETCH_NO_RESULT",
    "FULLTEXT_UNAVAILABLE",
    "PARSE_FAILED",
    "OCR_FAILED",
    "OCR_TIMEOUT",
    "TRANSLATION_FAILED",
    "TRANSLATION_EMPTY",
    "ALIGNMENT_FAILED",
    "ENTITY_EXTRACTION_FAILED",
    "EVIDENCE_EXTRACTION_FAILED",
    "ACMG_RULE_UNSUPPORTED",
    "ACMG_PARSE_FAILED",
    "GRAPH_SYNC_FAILED",
    "TASK_TIMEOUT",
    "INTERNAL_ERROR",
    "RESOURCE_NOT_FOUND",
}


def build_log_link(request_id: str) -> str:
    return f"{cfg.api_prefix}/logs/reissue?request_id={request_id}"


def _map_error_code_by_detail(detail: str) -> Optional[str]:
    text = (detail or "").lower()
    if "graph sync" in text:
        return "GRAPH_SYNC_FAILED"
    if "ocr failed" in text:
        return "OCR_FAILED"
    if "ocr timeout" in text:
        return "OCR_TIMEOUT"
    if "parse failed" in text or "parsing failed" in text:
        return "PARSE_FAILED"
    if "translation failed" in text:
        return "TRANSLATION_FAILED"
    if "translation empty" in text:
        return "TRANSLATION_EMPTY"
    if "alignment failed" in text:
        return "ALIGNMENT_FAILED"
    if "entity extraction failed" in text:
        return "ENTITY_EXTRACTION_FAILED"
    if "evidence extraction failed" in text:
        return "EVIDENCE_EXTRACTION_FAILED"
    if "acmg" in text and "unsupported" in text:
        return "ACMG_RULE_UNSUPPORTED"
    if "acmg" in text and "parse" in text:
        return "ACMG_PARSE_FAILED"
    if "fetch timeout" in text:
        return "FETCH_TIMEOUT"
    if "too large" in text:
        return "FILE_TOO_LARGE"
    if "unsupported" in text or "invalid pdf" in text or "content-type must" in text:
        return "FILE_TYPE_UNSUPPORTED"
    if "duplicate" in text:
        return "FILE_DUPLICATE"
    if "not found" in text and "result file" in text:
        return "FETCH_NO_RESULT"
    if "timeout" in text:
        return "TASK_TIMEOUT"
    if "fetch" in text and "no result" in text:
        return "FETCH_NO_RESULT"
    if "full text" in text and "unavailable" in text:
        return "FULLTEXT_UNAVAILABLE"
    return None


def _map_error_code_by_status(status_code: int) -> str:
    if status_code == 415:
        return "FILE_TYPE_UNSUPPORTED"
    if status_code == 400:
        return "INPUT_INVALID"
    if status_code == 429:
        return "INPUT_INVALID"
    if status_code == 404:
        return "INPUT_INVALID"
    if status_code in (422,):
        return "INPUT_INVALID"
    if status_code in (500, 502, 503, 504):
        return "INTERNAL_ERROR"
    return "INTERNAL_ERROR"


def map_error_code(status_code: int, detail: str) -> str:
    if status_code == 415:
        return "FILE_TYPE_UNSUPPORTED"
    by_detail = _map_error_code_by_detail(detail)
    if by_detail is not None:
        return by_detail
    return _map_error_code_by_status(status_code)


def normalize_error_code(error_code: Optional[str], fallback_status: int, detail: str) -> str:
    candidate = (error_code or "").strip().upper()
    if candidate in FROZEN_ERROR_CODES:
        return candidate
    return map_error_code(fallback_status, detail)


def contract_http_exception(status_code: int, error_code: str, detail: str) -> HTTPException:
    normalized_error_code = normalize_error_code(error_code, status_code, detail)
    return HTTPException(
        status_code=status_code,
        detail={"error_code": normalized_error_code, "detail": detail},
    )


def extract_error_contract(status_code: int, detail: Any) -> Tuple[str, str, Optional[Any]]:
    if isinstance(detail, dict):
        message = str(detail.get("detail") or detail.get("message") or "")
        explicit_code = normalize_error_code(detail.get("error_code"), status_code, message)
        return explicit_code, message, detail.get("errors")

    detail_text = detail if isinstance(detail, str) else str(detail)
    return map_error_code(status_code, detail_text), detail_text, None


def failed_payload(
    error_code: str, detail: str, request_id: str, errors: Optional[Any] = None
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "status": "failed",
        "error_code": error_code,
        "log_link": build_log_link(request_id),
        "detail": detail,
    }
    if errors is not None:
        payload["errors"] = errors
    return payload
