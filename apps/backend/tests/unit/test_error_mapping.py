from __future__ import annotations

from src.presentation.error_contract import map_error_code, normalize_error_code


def test_map_error_code_file_type_unsupported() -> None:
    assert map_error_code(415, "Content-Type must be multipart/form-data") == "FILE_TYPE_UNSUPPORTED"


def test_map_error_code_graph_sync_failed() -> None:
    assert map_error_code(500, "Graph sync failed for document") == "GRAPH_SYNC_FAILED"


def test_map_error_code_parse_failed() -> None:
    assert map_error_code(500, "Parsing failed: invalid layout") == "PARSE_FAILED"


def test_map_error_code_translation_failed() -> None:
    assert map_error_code(500, "Translation failed: empty output") == "TRANSLATION_FAILED"


def test_map_error_code_fetch_timeout() -> None:
    assert map_error_code(500, "Fetch timeout while querying source") == "FETCH_TIMEOUT"


def test_map_error_code_status_default_404() -> None:
    assert map_error_code(404, "resource missing") == "INPUT_INVALID"


def test_map_error_code_status_default_500() -> None:
    assert map_error_code(500, "unexpected backend failure") == "INTERNAL_ERROR"


def test_normalize_error_code_rejects_non_frozen() -> None:
    assert normalize_error_code("TASK_NOT_FOUND", 404, "Task not found") == "INPUT_INVALID"


def test_normalize_error_code_accepts_frozen() -> None:
    assert normalize_error_code("GRAPH_SYNC_FAILED", 500, "x") == "GRAPH_SYNC_FAILED"
