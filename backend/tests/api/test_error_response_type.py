"""Tests for error response type safety."""

from __future__ import annotations

import ast
import inspect


def test_error_response_uses_typed_dict():
    """_error_response should use TypedDict for body and error fields."""
    from app.main import _error_response

    source = inspect.getsource(_error_response)
    tree = ast.parse(source)

    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)

    found_error_detail_typed = False
    found_body_typed = False

    for node in ast.walk(func_def):
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                if node.target.id == "error_detail" and isinstance(node.annotation, ast.Name):
                    if node.annotation.id == "ErrorDetail":
                        found_error_detail_typed = True
                if node.target.id == "body" and isinstance(node.annotation, ast.Name):
                    if node.annotation.id == "ErrorResponseBody":
                        found_body_typed = True

    assert found_error_detail_typed, "error_detail should be typed as ErrorDetail"
    assert found_body_typed, "body should be typed as ErrorResponseBody"
